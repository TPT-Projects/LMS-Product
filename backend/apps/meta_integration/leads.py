"""From a Meta lead to an Enquiry (spec flow F2).

    webhook -> raw event saved -> fetch full lead from Graph API
      -> form connected?  no  -> keep in MongoDB as form_not_connected, stop
                          yes -> save lead in MongoDB
      -> one PostgreSQL transaction: Contact (dedupe) + Enquiry (leadgen_id unique)
      -> MongoDB updated with enquiry_id, sync log, live alert
      -> any failure -> failed_sync_logs (Retry button, backfill also retries)

Idempotent on leadgen_id: a webhook delivered twice, a retry and the backfill
can all see the same lead without creating a second enquiry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.activity.service import ActivityType, record
from apps.customfields.models import CustomField, FieldType
from apps.customfields.values import CustomValueError, coerce
from apps.enquiries.ingestion import EnquiryData, ingest_enquiry
from apps.enquiries.models import Enquiry, Source
from apps.integrations import autocall
from apps.tenants.models import Tenant
from common.dates import parse_meta_time
from common.realtime import send_to_tenant
from common.tenancy.context import tenant_context

from . import capi, formdata
from .graph import GraphError, get_graph
from .models import (
    ConnectionStatus,
    FailedSyncLog,
    FormFieldMapping,
    MetaConnection,
    MetaForm,
    SyncLog,
    SyncSource,
    SyncStatus,
    TargetType,
)

logger = logging.getLogger(__name__)

# Questions Meta uses for its standard contact fields.
DEFAULT_TARGETS = {
    "full_name": TargetType.NAME,
    "phone_number": TargetType.PHONE,
    "email": TargetType.EMAIL,
}


@dataclass
class SyncResult:
    status: str
    enquiry_id: int | None = None
    message: str = ""


# --- mapping ----------------------------------------------------------------------------
def build_enquiry_data(
    form: MetaForm, lead: dict, detect_ad_details: bool
) -> tuple[EnquiryData, list[str], list[str]]:
    """Apply the form's field mapping. Returns (data, unmapped questions, notes)."""
    mappings = {
        m.question_name: m
        for m in FormFieldMapping.objects.filter(form=form).select_related("custom_field")
    }
    data = EnquiryData(source=Source.META, leadgen_id=lead["id"], form_id=lead.get("form_id", ""))
    if detect_ad_details:
        data.campaign_name = lead.get("campaign_name", "") or ""
        data.adset_name = lead.get("adset_name", "") or ""
        data.ad_name = lead.get("ad_name", "") or ""
    if lead.get("created_time"):
        data.created_at = parse_meta_time(lead["created_time"])
    data.extra_details = {"form_id": form.form_id, "form_name": form.name}

    unmapped: list[str] = []
    notes: list[str] = []
    first_last: dict[str, str] = {}
    for item in lead.get("field_data", []):
        question = str(item.get("name", ""))
        values = [str(v) for v in item.get("values", []) if v not in (None, "")]
        if not question or not values:
            continue
        mapping = mappings.get(question)
        target = mapping.target_type if mapping else DEFAULT_TARGETS.get(question)
        if question in ("first_name", "last_name") and not mapping:
            first_last[question] = values[0]
            continue
        if target is None:
            unmapped.append(question)
            continue
        if target == TargetType.IGNORE:
            continue
        if target == TargetType.NAME:
            data.name = ", ".join(values)
        elif target == TargetType.PHONE:
            data.phone = values[0]
        elif target == TargetType.EMAIL:
            data.email = values[0]
        elif target == TargetType.CUSTOM and mapping and mapping.custom_field:
            _set_custom(data, mapping.custom_field, values, notes)
    if not data.name and first_last:
        data.name = " ".join(
            v for v in (first_last.get("first_name"), first_last.get("last_name")) if v
        )
    return data, unmapped, notes


def _set_custom(data: EnquiryData, field: CustomField, values: list[str], notes: list[str]) -> None:
    if field in data.custom_values and data.custom_values[field] not in (None, "", []):
        return  # many-to-one: the first answered question wins
    raw = values if field.type == FieldType.MULTI_SELECT else values[0]
    if field.type in (FieldType.DROPDOWN, FieldType.MULTI_SELECT):
        # Answers are stored exactly as received; a new answer becomes a new option.
        new = [v for v in (raw if isinstance(raw, list) else [raw]) if v not in field.options]
        if new:
            field.options = [*field.options, *new]
            field.save(update_fields=["options"])
    try:
        data.custom_values[field] = coerce(field, raw)
    except CustomValueError as exc:
        notes.append(f"{field.label}: {exc} ({raw})")


# --- sync steps -------------------------------------------------------------------------
def _log(
    tenant_id: int,
    leadgen_id: str,
    form_id: str,
    status: str,
    source: str,
    *,
    enquiry_id=None,
    message="",
):
    SyncLog.objects.create(
        tenant_id=tenant_id,
        leadgen_id=leadgen_id,
        form_id=form_id,
        status=status,
        source=source,
        enquiry_id=enquiry_id,
        message=message[:500],
    )


def record_failure(tenant_id: int, *, value: dict, error: str, source: str) -> None:
    leadgen_id = str(value.get("leadgen_id") or value.get("id") or "")
    with tenant_context(tenant_id):
        failed, created = FailedSyncLog.objects.get_or_create(
            tenant_id=tenant_id,
            leadgen_id=leadgen_id,
            defaults={
                "form_id": str(value.get("form_id", "")),
                "page_id": str(value.get("page_id", "")),
                "error": error[:500],
                "payload": value,
            },
        )
        if not created:
            failed.attempts += 1
            failed.error = error[:500]
            failed.last_attempt_at = timezone.now()
            failed.resolved_at = None
            failed.save(update_fields=["attempts", "error", "last_attempt_at", "resolved_at"])
        _log(tenant_id, leadgen_id, failed.form_id, SyncStatus.FAILED, source, message=error)
    formdata.set_status(tenant_id, leadgen_id, formdata.FAILED, error=error)


def _restore(enquiry: Enquiry) -> None:
    Enquiry.objects.filter(pk=enquiry.pk).update(deleted_at=None)
    contact = enquiry.contact
    if contact.deleted_at:
        contact.deleted_at = None
        contact.save(update_fields=["deleted_at", "updated_at"])
    record(
        tenant_id=enquiry.tenant_id,
        enquiry_id=enquiry.pk,
        contact_id=enquiry.contact_id,
        type=ActivityType.ENQUIRY_RESTORED,
        actor=None,
        details={"source": "meta"},
    )


def ingest_lead(tenant_id: int, lead: dict, *, page_id: str, source: str) -> SyncResult:
    """Lead (full Graph object) -> Enquiry. Safe to call many times for the same lead."""
    leadgen_id = str(lead["id"])
    form_id = str(lead.get("form_id", ""))
    formdata.save_lead(tenant_id, lead=lead, page_id=page_id)

    with tenant_context(tenant_id):
        tenant = Tenant.objects.get(pk=tenant_id)
        existing = Enquiry.objects.filter(tenant_id=tenant_id, leadgen_id=leadgen_id).first()
        if existing and existing.deleted_at and source == SyncSource.MANUAL:
            # "Sync leads" is an explicit request for these leads: undo the LMS delete.
            # Automatic syncs leave deleted enquiries alone (they were deleted on purpose).
            _restore(existing)
            _log(
                tenant_id, leadgen_id, form_id, SyncStatus.RESTORED, source, enquiry_id=existing.pk
            )
            formdata.set_status(tenant_id, leadgen_id, formdata.SYNCED, enquiry_id=existing.pk)
            return SyncResult(SyncStatus.RESTORED, existing.pk)
        if existing:
            _log(
                tenant_id, leadgen_id, form_id, SyncStatus.DUPLICATE, source, enquiry_id=existing.pk
            )
            formdata.set_status(tenant_id, leadgen_id, formdata.SYNCED, enquiry_id=existing.pk)
            FailedSyncLog.objects.filter(leadgen_id=leadgen_id, resolved_at__isnull=True).update(
                resolved_at=timezone.now()
            )
            return SyncResult(SyncStatus.DUPLICATE, existing.pk)

        form, _ = MetaForm.objects.get_or_create(
            tenant_id=tenant_id, form_id=form_id, defaults={"page_id": page_id}
        )
        connection = MetaConnection.objects.filter(tenant_id=tenant_id).first()
        if not form.is_connected and connection and connection.auto_connect_forms:
            from .services import set_form_connected  # services imports this module

            set_form_connected(form, connected=True, user=None)
        if not form.is_connected:
            _log(tenant_id, leadgen_id, form_id, SyncStatus.FORM_NOT_CONNECTED, source)
            formdata.set_status(tenant_id, leadgen_id, formdata.FORM_NOT_CONNECTED)
            return SyncResult(SyncStatus.FORM_NOT_CONNECTED)

        detect = connection.detect_ad_details if connection else True
        data, unmapped, notes = build_enquiry_data(form, lead, detect)
        try:
            with transaction.atomic():
                result = ingest_enquiry(tenant=tenant, data=data, actor=None)
        except IntegrityError:
            # Another worker created it a moment ago (leadgen_id is unique per workspace).
            existing = Enquiry.objects.get(tenant_id=tenant_id, leadgen_id=leadgen_id)
            _log(
                tenant_id, leadgen_id, form_id, SyncStatus.DUPLICATE, source, enquiry_id=existing.pk
            )
            return SyncResult(SyncStatus.DUPLICATE, existing.pk)

        enquiry = result.enquiry
        MetaForm.objects.filter(pk=form.pk).update(
            leads_received=F("leads_received") + 1, last_lead_at=timezone.now()
        )
        FailedSyncLog.objects.filter(leadgen_id=leadgen_id, resolved_at__isnull=True).update(
            resolved_at=timezone.now()
        )
        _log(
            tenant_id,
            leadgen_id,
            form_id,
            SyncStatus.SYNCED,
            source,
            enquiry_id=enquiry.pk,
            message="; ".join(notes),
        )
        formdata.set_status(
            tenant_id, leadgen_id, formdata.SYNCED, enquiry_id=enquiry.pk, unmapped=unmapped
        )
        payload = {
            "id": enquiry.pk,
            "name": enquiry.name,
            "campaign_name": enquiry.campaign_name,
            "form_name": form.name,
        }
        transaction.on_commit(lambda: send_to_tenant(tenant_id, "enquiry.created", payload))
        autocall.on_new_meta_lead(enquiry, form)  # Exotel: call at once if the form says so
        capi.send_after_commit(enquiry.pk, tenant_id, enquiry.status.name)  # first stage
        return SyncResult(SyncStatus.SYNCED, enquiry.pk, "; ".join(notes))


def handle_webhook_change(
    tenant_id: int, value: dict, *, source: str = SyncSource.WEBHOOK
) -> SyncResult:
    """One `leadgen` change from the webhook: fetch the full lead, then ingest it."""
    leadgen_id = str(value.get("leadgen_id", ""))
    with tenant_context(tenant_id):
        connection = MetaConnection.objects.filter(
            tenant_id=tenant_id, status=ConnectionStatus.CONNECTED
        ).first()
        if connection is None or str(value.get("page_id")) != connection.page_id:
            return SyncResult("ignored", message="Not the connected Page.")
        page_id, token = connection.page_id, connection.page_token
        existing = Enquiry.objects.filter(tenant_id=tenant_id, leadgen_id=leadgen_id).first()
        if existing:  # delivered again: nothing to fetch or create
            form_id = str(value.get("form_id", ""))
            _log(
                tenant_id, leadgen_id, form_id, SyncStatus.DUPLICATE, source, enquiry_id=existing.pk
            )
            return SyncResult(SyncStatus.DUPLICATE, existing.pk)

    try:
        lead = get_graph().get_lead(leadgen_id, token)
    except GraphError as exc:
        record_failure(tenant_id, value=value, error=str(exc), source=source)
        return SyncResult(SyncStatus.FAILED, message=str(exc))
    try:
        return ingest_lead(tenant_id, lead, page_id=page_id, source=source)
    except Exception as exc:  # never lose a lead silently
        logger.exception("Meta lead %s could not be ingested", leadgen_id)
        record_failure(tenant_id, value=value, error=f"Could not save: {exc}", source=source)
        return SyncResult(SyncStatus.FAILED, message=str(exc))
