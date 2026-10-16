"""Background work for Meta: process webhook leads and the scheduled backfill."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.enquiries.models import Enquiry
from common.tenancy.context import rls_bypass, tenant_context

from .graph import GraphError, get_graph
from .leads import handle_webhook_change, ingest_lead
from .models import (
    ConnectionStatus,
    FailedSyncLog,
    MetaConnection,
    MetaForm,
    SyncSource,
    SyncStatus,
)

logger = logging.getLogger(__name__)
MAX_AUTO_RETRIES = 5


@shared_task(acks_late=True, ignore_result=True)
def process_lead(tenant_id: int, value: dict, source: str = SyncSource.WEBHOOK) -> None:
    handle_webhook_change(tenant_id, value, source=source)


@shared_task(ignore_result=True)
def backfill_all() -> None:
    """Celery Beat, every 15 minutes: one backfill job per connected workspace."""
    with transaction.atomic(), rls_bypass():
        tenant_ids = list(
            MetaConnection.objects.filter(status=ConnectionStatus.CONNECTED).values_list(
                "tenant_id", flat=True
            )
        )
    for tenant_id in tenant_ids:
        backfill_connection.delay(tenant_id)


@shared_task(ignore_result=True)
def backfill_connection(
    tenant_id: int,
    days: int | None = None,
    restore_deleted: bool = False,
    form_ids: list[str] | None = None,
    active_only: bool = False,
) -> dict:
    """Recover missed webhooks: re-read recent leads of connected forms, retry failures.

    days: read that many days back instead of "since the last backfill".
    restore_deleted: the "Sync leads" button also brings back Meta enquiries deleted in the LMS.
    form_ids: only these forms (a form was just switched on).
    active_only: skip archived / deleted forms (the frequent poll; they get no new leads).
    """
    with tenant_context(tenant_id):
        connection = MetaConnection.objects.filter(status=ConnectionStatus.CONNECTED).first()
        if connection is None:
            return {"checked": 0, "added": 0, "restored": 0, "errors": []}
        page_id, token = connection.page_id, connection.page_token
        if days:
            since = timezone.now() - timedelta(days=days)
        else:
            since = (connection.last_backfill_at or timezone.now() - timedelta(days=1)) - timedelta(
                hours=1
            )
        forms = MetaForm.objects.filter(is_connected=True)
        if form_ids:
            forms = forms.filter(form_id__in=form_ids)
        if active_only:
            forms = forms.filter(status_on_meta__in=["ACTIVE", ""])
        names = dict(forms.values_list("form_id", "name"))
        form_ids = list(names)
        retries = list(
            FailedSyncLog.objects.filter(
                resolved_at__isnull=True, attempts__lt=MAX_AUTO_RETRIES
            ).values_list("payload", flat=True)
        )
        started = timezone.now()

    source = SyncSource.MANUAL if restore_deleted else SyncSource.BACKFILL
    checked = added = restored = 0
    errors: list[str] = []
    for form_id in form_ids:
        try:
            leads = get_graph().list_form_leads(form_id, token, int(since.timestamp()))
        except GraphError as exc:
            logger.warning("Backfill could not read form %s", form_id, exc_info=True)
            errors.append(f"{names.get(form_id) or form_id}: {exc}")
            continue
        for lead in leads:
            checked += 1
            with tenant_context(tenant_id):
                known = Enquiry.objects.filter(leadgen_id=str(lead["id"]))
                if restore_deleted:
                    known = known.alive()
                if known.exists():
                    continue
            result = ingest_lead(tenant_id, lead, page_id=page_id, source=source)
            added += result.status == SyncStatus.SYNCED
            restored += result.status == SyncStatus.RESTORED
    for payload in retries:
        handle_webhook_change(tenant_id, payload, source=SyncSource.RETRY)

    if not form_ids:  # a single-form sync must not move the window for the other forms
        with tenant_context(tenant_id):
            MetaConnection.objects.filter(tenant_id=tenant_id).update(last_backfill_at=started)
    return {"checked": checked, "added": added, "restored": restored, "errors": errors}
