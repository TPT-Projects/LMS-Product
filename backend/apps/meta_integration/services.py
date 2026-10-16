"""Connecting Meta (spec flow F5, "Make.com style"): login -> one Page -> leads access -> forms."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Membership
from apps.audit.service import (
    META_CONNECTED,
    META_DISCONNECTED,
    META_FORM_CONNECTED,
    META_FORM_DISCONNECTED,
    audit,
)
from apps.customfields.models import CustomField
from apps.permissions.matrix import has_capability
from apps.permissions.roles import Capability
from common.dates import parse_meta_time
from common.tenancy.context import rls_bypass

from . import formdata
from .graph import GraphError, get_graph
from .leads import DEFAULT_TARGETS
from .models import (
    ConnectionStatus,
    FormFieldMapping,
    MetaConnection,
    MetaForm,
    TargetType,
)
from .tasks import backfill_connection

logger = logging.getLogger(__name__)

STATE_SALT = "meta-oauth"
STATE_MAX_AGE = 15 * 60
ONE_PAGE_ONLY = _("Only one Meta Page can be connected. Disconnect the current Page first.")


def connection_for(tenant_id: int) -> MetaConnection | None:
    return MetaConnection.objects.filter(tenant_id=tenant_id).first()


def _graph_error(exc: GraphError) -> ValidationError:
    return ValidationError({"detail": _("Meta said: %(m)s") % {"m": str(exc)}})


# --- OAuth ---------------------------------------------------------------------------
def start_oauth(membership: Membership) -> str:
    connection = connection_for(membership.tenant_id)
    if connection and connection.status == ConnectionStatus.CONNECTED:
        raise ValidationError({"detail": ONE_PAGE_ONLY})
    return get_graph().oauth_url(oauth_state(membership))


def oauth_state(membership: Membership, purpose: str = "meta") -> str:
    data = {"t": membership.tenant_id, "u": membership.user_id, "n": secrets.token_urlsafe(8)}
    if purpose != "meta":
        data["p"] = purpose
    return signing.dumps(data, salt=STATE_SALT)


def state_purpose(state: str) -> str:
    """ "meta" (lead ads) or another app using the same Facebook login, e.g. "whatsapp"."""
    try:
        return signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE).get("p") or "meta"
    except signing.BadSignature:
        return "meta"


def membership_from_state(state: str) -> Membership:
    """The popup returns without our login token: the signed state says who started it."""
    try:
        data = signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE)
    except signing.BadSignature:
        raise ValidationError(
            {"detail": _("This login link expired. Please connect again.")}
        ) from None
    with rls_bypass():
        membership = (
            Membership.objects.select_related("user", "tenant")
            .filter(tenant_id=data.get("t"), user_id=data.get("u"), is_active=True)
            .first()
        )
    if membership is None or not membership.user.is_active:
        raise ValidationError({"detail": _("You no longer have access to this workspace.")})
    if not has_capability(membership.role, Capability.MANAGE_META):
        raise ValidationError({"detail": _("Only an Owner or Admin can connect Meta.")})
    return membership


def complete_oauth(membership: Membership, *, code: str, state: str) -> MetaConnection:
    """Facebook sent the user back. The signed state must belong to this user and workspace."""
    try:
        data = signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE)
    except signing.BadSignature:
        raise ValidationError(
            {"detail": _("This login link expired. Please connect again.")}
        ) from None
    if data.get("t") != membership.tenant_id or data.get("u") != membership.user_id:
        raise ValidationError({"detail": _("This login was started by someone else.")})
    try:
        token, expires_unix = get_graph().exchange_code(code)
    except GraphError as exc:
        raise _graph_error(exc) from None

    connection = connection_for(membership.tenant_id) or MetaConnection(
        tenant_id=membership.tenant_id
    )
    if connection.status == ConnectionStatus.CONNECTED:
        raise ValidationError({"detail": ONE_PAGE_ONLY})
    connection.user_token = token
    connection.token_expires_at = (
        datetime.fromtimestamp(expires_unix, tz=UTC) if expires_unix else None
    )
    connection.status = ConnectionStatus.PENDING_PAGE
    connection.connected_by = membership.user
    connection.save()
    return connection


def list_pages(connection: MetaConnection) -> list[dict]:
    try:
        pages = get_graph().list_pages(connection.user_token)
    except GraphError as exc:
        raise _graph_error(exc) from None
    taken = _pages_used_elsewhere(connection.tenant_id, [p["id"] for p in pages])
    return [
        {"id": p["id"], "name": p.get("name", ""), "available": p["id"] not in taken} for p in pages
    ]


def _pages_used_elsewhere(tenant_id: int, page_ids: list[str]) -> set[str]:
    # A Page can belong to one workspace only: look across workspaces (ids only).
    with rls_bypass():
        return set(
            MetaConnection.objects.filter(page_id__in=page_ids)
            .exclude(tenant_id=tenant_id)
            .values_list("page_id", flat=True)
        )


@transaction.atomic
def select_page(connection: MetaConnection, *, page_id: str, user) -> MetaConnection:
    """Choose the ONE Page. Enforced here, in the UI and by a unique constraint."""
    if connection.status == ConnectionStatus.CONNECTED:
        raise ValidationError({"detail": ONE_PAGE_ONLY})
    try:
        pages = {p["id"]: p for p in get_graph().list_pages(connection.user_token)}
    except GraphError as exc:
        raise _graph_error(exc) from None
    page = pages.get(page_id)
    if page is None:
        raise ValidationError({"page_id": [_("You do not manage this Page.")]})
    if page_id in _pages_used_elsewhere(connection.tenant_id, [page_id]):
        raise ValidationError(
            {"page_id": [_("This Page is already connected to another workspace.")]}
        )

    connection.page_id = page_id
    connection.page_name = page.get("name", "")
    connection.page_token = page["access_token"]
    connection.status = ConnectionStatus.CONNECTED
    connection.connected_at = timezone.now()
    connection.auto_connect_forms = True  # a new Page starts with Auto Sync for every form
    try:
        with transaction.atomic():
            connection.save()
    except IntegrityError:
        raise ValidationError(
            {"page_id": [_("This Page is already connected to another workspace.")]}
        ) from None
    try:
        get_graph().subscribe_page(page_id, connection.page_token)
    except GraphError as exc:
        raise _graph_error(exc) from None
    audit(
        tenant_id=connection.tenant_id,
        actor=user,
        action=META_CONNECTED,
        details={"page_id": page_id, "page_name": connection.page_name},
    )
    ensure_app_webhook()
    check_access(connection)
    try:
        refresh_forms(connection)
    except ValidationError:
        pass  # forms can be refreshed later (e.g. once Leads Access is granted)
    return connection


def check_access(connection: MetaConnection) -> MetaConnection:
    """Can this app read the Page's leads? (Business Suite > Integrations > Leads Access)."""
    try:
        get_graph().check_leads_access(connection.page_id, connection.page_token)
        connection.leads_access_ok, connection.leads_access_error = True, ""
    except GraphError as exc:
        connection.leads_access_ok, connection.leads_access_error = False, str(exc)[:500]
    connection.leads_access_checked_at = timezone.now()
    connection.save(
        update_fields=["leads_access_ok", "leads_access_error", "leads_access_checked_at"]
    )
    return connection


@transaction.atomic
def disconnect(connection: MetaConnection, *, user) -> None:
    """Removes the webhook subscription. Existing enquiries stay."""
    page_id = connection.page_id
    if page_id and connection.page_token:
        try:
            get_graph().unsubscribe_page(page_id, connection.page_token)
        except GraphError:
            pass  # token may already be revoked; we still disconnect locally
    MetaForm.objects.filter(tenant_id=connection.tenant_id).update(is_connected=False)
    connection.page_id = None
    connection.page_name = ""
    connection._user_token = ""
    connection._page_token = ""
    connection.token_expires_at = None
    connection.leads_access_ok = False
    connection.status = ConnectionStatus.DISCONNECTED
    connection.save()
    audit(
        tenant_id=connection.tenant_id,
        actor=user,
        action=META_DISCONNECTED,
        details={"page_id": page_id},
    )


# --- forms -----------------------------------------------------------------------------
def refresh_forms(connection: MetaConnection) -> list[MetaForm]:
    if connection.status != ConnectionStatus.CONNECTED:
        raise ValidationError({"detail": _("Connect a Page first.")})
    try:
        remote = get_graph().list_forms(connection.page_id, connection.page_token)
    except GraphError as exc:
        raise _graph_error(exc) from None
    forms = []
    for item in remote:
        form, _created = MetaForm.objects.update_or_create(
            tenant_id=connection.tenant_id,
            form_id=str(item["id"]),
            defaults={
                "page_id": connection.page_id,
                "name": item.get("name", ""),
                "status_on_meta": item.get("status", ""),
                "created_time": (
                    parse_meta_time(item["created_time"]) if item.get("created_time") else None
                ),
                "questions": [
                    {
                        "key": q.get("key", ""),
                        "label": q.get("label", ""),
                        "type": q.get("type", ""),
                    }
                    for q in item.get("questions", [])
                ],
            },
        )
        forms.append(form)
    if connection.auto_connect_forms:
        for form in forms:
            if not form.is_connected:
                set_form_connected(form, connected=True, user=None)
    MetaConnection.objects.filter(pk=connection.pk).update(forms_refreshed_at=timezone.now())
    return forms


def set_auto_connect(connection: MetaConnection, enabled: bool, *, user) -> MetaConnection:
    """Auto mode connects every form now and any new form as soon as it is seen."""
    connection.auto_connect_forms = enabled
    connection.save(update_fields=["auto_connect_forms"])
    if enabled:
        for form in MetaForm.objects.filter(tenant_id=connection.tenant_id, is_connected=False):
            set_form_connected(form, connected=True, user=user)
    return connection


SYNC_DAYS = (1, 7, 30)  # last 24 hours, 7 days, 30 days


def sync_leads(
    connection: MetaConnection,
    *,
    days: int,
    restore_deleted: bool = True,
    form: MetaForm | None = None,
) -> dict:
    """Read the last `days` of leads from connected forms (no duplicates).

    The "Sync leads" button also restores Meta enquiries deleted in the LMS. The automatic
    sync after connecting a Page or switching a form on does not (restore_deleted=False).
    """
    if connection.status != ConnectionStatus.CONNECTED:
        raise ValidationError({"detail": _("Connect a Page first.")})
    if days not in SYNC_DAYS:
        raise ValidationError({"days": [_("Choose 1, 7 or 30 days.")]})
    if connection.auto_connect_forms and form is None:
        try:
            refresh_forms(connection)  # pick up forms created since the last look
        except ValidationError:
            pass
    return backfill_connection(
        connection.tenant_id,
        days=days,
        restore_deleted=restore_deleted,
        form_ids=[form.form_id] if form else None,
    )


POLL_EVERY = timedelta(seconds=50)
FORMS_REFRESH_EVERY = timedelta(minutes=15)


def poll_new_leads(tenant_id: int) -> dict:
    """The browser asks about every minute: new leads appear without a public webhook.

    At most one check per workspace per POLL_EVERY (claimed atomically), active forms only.
    With Auto Sync, new forms on the Page are picked up every FORMS_REFRESH_EVERY.
    """
    now = timezone.now()
    due = Q(last_polled_at__isnull=True) | Q(last_polled_at__lt=now - POLL_EVERY)
    claimed = (
        MetaConnection.objects.filter(tenant_id=tenant_id, status=ConnectionStatus.CONNECTED)
        .filter(due)
        .update(last_polled_at=now)
    )
    if not claimed:
        return {"polled": False}
    connection = MetaConnection.objects.get(tenant_id=tenant_id)
    stale = not connection.forms_refreshed_at or (
        connection.forms_refreshed_at < now - FORMS_REFRESH_EVERY
    )
    if connection.auto_connect_forms and stale:
        try:
            refresh_forms(connection)
        except ValidationError:
            pass
    result = backfill_connection(tenant_id, active_only=True)
    return {"polled": True, "checked": result["checked"], "added": result["added"]}


def ensure_app_webhook() -> str | None:
    """On a public HTTPS server, point Meta's leadgen webhook here automatically.

    New leads then arrive within seconds without any setup in the Meta dashboard.
    Skipped for localhost (Meta cannot reach it; polling covers development).
    """
    base = settings.BACKEND_URL.rstrip("/")
    host = urlparse(base).hostname or ""
    local = host in ("localhost", "127.0.0.1") or host.endswith((".localhost", ".test"))
    if not base.startswith("https://") or local or not settings.META_WEBHOOK_VERIFY_TOKEN:
        return None
    url = f"{base}/webhooks/meta"
    try:
        get_graph().subscribe_app_webhook(url, settings.META_WEBHOOK_VERIFY_TOKEN)
    except GraphError:
        logger.warning("Could not register the Meta webhook at %s", url, exc_info=True)
        return None
    return url


def set_form_connected(form: MetaForm, *, connected: bool, user) -> MetaForm:
    form.is_connected = connected
    form.connected_at = timezone.now() if connected else None
    form.save(update_fields=["is_connected", "connected_at"])
    if connected and not form.mappings.exists():
        # Sensible start: Meta's standard questions map to Name / Phone / Email.
        FormFieldMapping.objects.bulk_create(
            FormFieldMapping(
                tenant_id=form.tenant_id, form=form, question_name=question, target_type=target
            )
            for question, target in DEFAULT_TARGETS.items()
        )
    audit(
        tenant_id=form.tenant_id,
        actor=user,
        action=META_FORM_CONNECTED if connected else META_FORM_DISCONNECTED,
        details={"form_id": form.form_id, "name": form.name},
    )
    return form


# --- mapping ---------------------------------------------------------------------------
def mapping_for(form: MetaForm) -> dict:
    """Questions (from Meta and from stored leads) with sample answers and the current mapping."""
    samples = formdata.question_samples(form.tenant_id, form.form_id)
    labels = {q["key"]: q.get("label", "") for q in form.questions}
    names = list(dict.fromkeys([*labels.keys(), *samples.keys()]))
    current = {m.question_name: m for m in form.mappings.select_related("custom_field")}
    rows = []
    for name in names:
        m = current.get(name)
        rows.append(
            {
                "question": name,
                "label": labels.get(name) or name.replace("_", " "),
                "samples": samples.get(name, []),
                "target_type": m.target_type if m else (DEFAULT_TARGETS.get(name) or ""),
                "custom_field": m.custom_field.key if m and m.custom_field else None,
                "is_mapped": bool(m) or name in DEFAULT_TARGETS,
            }
        )
    return {"form_id": form.form_id, "name": form.name, "questions": rows}


@transaction.atomic
def save_mapping(form: MetaForm, rows: list[dict]) -> dict:
    """Replace the mapping. Name/Phone/Email once each; custom fields may take many questions."""
    fields = {
        f.key: f for f in CustomField.objects.filter(tenant_id=form.tenant_id, is_active=True)
    }
    errors: dict[str, list[str]] = {}
    seen_standard: dict[str, str] = {}
    new = []
    for row in rows:
        question = str(row.get("question", "")).strip()
        target = row.get("target_type") or ""
        if not question or not target:
            continue
        if target not in TargetType.values:
            errors[question] = [_("Unknown field.")]
            continue
        custom = None
        if target == TargetType.CUSTOM:
            custom = fields.get(row.get("custom_field") or "")
            if custom is None:
                errors[question] = [_("Choose a custom field.")]
                continue
        elif target in (TargetType.NAME, TargetType.PHONE, TargetType.EMAIL):
            if target in seen_standard:
                errors[question] = [_("Only one question can be %(t)s.") % {"t": target}]
                continue
            seen_standard[target] = question
        new.append(
            FormFieldMapping(
                tenant_id=form.tenant_id,
                form=form,
                question_name=question[:255],
                target_type=target,
                custom_field=custom,
            )
        )
    if errors:
        raise ValidationError({"mapping": errors})
    # New mappings apply to new enquiries only (spec 14, decision 4).
    form.mappings.all().delete()
    FormFieldMapping.objects.bulk_create(new)
    return mapping_for(form)


# --- status ------------------------------------------------------------------------------
def status_payload(connection: MetaConnection | None) -> dict:
    if connection is None:
        return {"status": "not_connected", "token_state": "none"}
    return {
        "status": connection.status,
        "page_id": connection.page_id,
        "page_name": connection.page_name,
        "token_state": connection.token_state,
        "token_expires_at": connection.token_expires_at,
        "leads_access_ok": connection.leads_access_ok,
        "leads_access_error": connection.leads_access_error,
        "leads_access_checked_at": connection.leads_access_checked_at,
        "detect_ad_details": connection.detect_ad_details,
        "auto_connect_forms": connection.auto_connect_forms,
        "connected_at": connection.connected_at,
        "last_backfill_at": connection.last_backfill_at,
    }
