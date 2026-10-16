"""Connect, check and disconnect apps. Meta lead ads is reported here but managed by its own app."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit.service import INTEGRATION_CONNECTED, INTEGRATION_DISCONNECTED, audit
from apps.meta_integration.models import ConnectionStatus, MetaConnection

from .models import Integration, IntegrationStatus
from .providers import PROVIDERS, CheckFailed, Provider

META = "meta"
OAUTH_APPS = ("google_sheets",)  # connected with a login popup, not a form


def known_app(app: str) -> None:
    if app not in PROVIDERS and app not in OAUTH_APPS:
        raise NotFound(_("This app cannot be connected here."))


def provider_for(app: str) -> Provider:
    provider = PROVIDERS.get(app)
    if provider is None:
        raise NotFound(_("This app cannot be connected here."))
    return provider


def _clean(provider: Provider, values: dict, existing: Integration | None) -> dict[str, str]:
    """Validate the form. A blank secret on an existing connection keeps the stored one."""
    if not isinstance(values, dict):
        raise ValidationError({"values": [_("Send the app's details.")]})
    stored = existing.secrets if existing else {}
    clean: dict[str, str] = {}
    errors: dict[str, list[str]] = {}
    for key, spec in provider.fields.items():
        value = str(values.get(key) or "").strip()
        if not value and spec.secret and stored.get(key):
            value = stored[key]
        if problem := spec.problem(value):
            errors[key] = [problem]
        elif value:
            clean[key] = value
    if errors:
        raise ValidationError({"values": errors})
    return clean


def _check(provider: Provider, values: dict[str, str]) -> str:
    try:
        return provider.check(values)
    except CheckFailed as exc:
        error: dict = {"non_field_errors": [exc.message]}
        if exc.field:
            error["values"] = {exc.field: [exc.message]}
        raise ValidationError(error) from None


@transaction.atomic
def connect(tenant_id: int, app: str, values: dict, *, user, request=None) -> Integration:
    """Check the details with the provider first; save only when they work."""
    provider = provider_for(app)
    existing = Integration.objects.filter(tenant_id=tenant_id, app=app).first()
    clean = _clean(provider, values, existing)
    label = _check(provider, clean)

    integration = existing or Integration(tenant_id=tenant_id, app=app, connected_by=user)
    integration.config = {k: v for k, v in clean.items() if not provider.fields[k].secret}
    integration.secrets = {k: v for k, v in clean.items() if provider.fields[k].secret}
    integration.status = IntegrationStatus.CONNECTED
    integration.account_label = label[:255]
    integration.last_checked_at = timezone.now()
    integration.last_error = ""
    integration.save()
    if app == "exotel":
        _load_exotel_numbers(integration)
    audit(
        tenant_id=tenant_id,
        actor=user,
        action=INTEGRATION_CONNECTED,
        details={"app": app, "account": integration.account_label, "updated": bool(existing)},
        request=request,
    )
    return integration


def _load_exotel_numbers(integration: Integration) -> None:
    from .exotel import ExotelError, refresh_numbers

    try:
        with transaction.atomic():
            refresh_numbers(integration)
    except ExotelError as exc:  # connected anyway; numbers can be refreshed later
        integration.last_error = str(exc)
        integration.save(update_fields=["last_error"])


def _check_oauth_app(integration: Integration) -> str:
    """Google Sheets / WhatsApp (Facebook login): the stored login still works."""
    if integration.app == "google_sheets":
        from . import google

        google.access_token(integration)
        return integration.account_label
    from . import whatsapp

    whatsapp.refresh(integration)
    if not integration.config.get("phone_number_id"):
        raise CheckFailed(_("No WhatsApp number was found in your accounts."))
    return integration.account_label


def check(integration: Integration) -> Integration:
    """'Test connection': re-run the provider check with the stored details."""
    try:
        if integration.app in OAUTH_APPS or (
            integration.app == "whatsapp" and "accounts" in integration.settings
        ):
            integration.account_label = _check_oauth_app(integration)[:255]
        else:
            integration.account_label = provider_for(integration.app).check(integration.values())[
                :255
            ]
        integration.status = IntegrationStatus.CONNECTED
        integration.last_error = ""
    except CheckFailed as exc:
        integration.status = IntegrationStatus.ERROR
        integration.last_error = exc.message
    except ValidationError as exc:
        detail = exc.detail.get("detail") if isinstance(exc.detail, dict) else exc.detail
        integration.status = IntegrationStatus.ERROR
        integration.last_error = str(detail[0] if isinstance(detail, list) else detail)
    integration.last_checked_at = timezone.now()
    integration.save(update_fields=["account_label", "status", "last_error", "last_checked_at"])
    return integration


def disconnect(integration: Integration, *, user, request=None) -> None:
    """Deletes the stored details (secrets included)."""
    audit(
        tenant_id=integration.tenant_id,
        actor=user,
        action=INTEGRATION_DISCONNECTED,
        details={"app": integration.app, "account": integration.account_label},
        request=request,
    )
    from .models import AutoCall, AutoCallStatus, ExotelNumber, SheetLink

    if integration.app == "exotel":
        ExotelNumber.objects.filter(tenant_id=integration.tenant_id).delete()
        AutoCall.objects.filter(
            tenant_id=integration.tenant_id, status=AutoCallStatus.PENDING
        ).update(status=AutoCallStatus.CANCELLED, error=_("Exotel was disconnected."))
    if integration.app == "google_sheets":
        SheetLink.objects.filter(tenant_id=integration.tenant_id).delete()
    integration.delete()


# --- overview --------------------------------------------------------------------------------
def _name(user) -> str:
    return (getattr(user, "full_name", "") or getattr(user, "email", "")) if user else ""


def _meta_payload(tenant_id: int) -> dict:
    connection = MetaConnection.objects.filter(tenant_id=tenant_id).first()
    status = "not_connected"
    if connection and connection.status == ConnectionStatus.CONNECTED:
        status = "error" if connection.token_state == "expired" else "connected"
    elif connection and connection.status == ConnectionStatus.PENDING_PAGE:
        status = "needs_setup"
    live = status != "not_connected"
    return {
        "app": META,
        "status": status,
        "account_label": connection.page_name if live else "",
        "connected_at": connection.connected_at if live else None,
        "connected_by": _name(connection.connected_by) if live else "",
        "last_checked_at": connection.leads_access_checked_at if live else None,
        "last_error": "",
        "config": {},
        "secrets_set": [],
    }


def payload(integration: Integration) -> dict:
    return {
        "app": integration.app,
        "status": integration.status,
        "account_label": integration.account_label,
        "connected_at": integration.connected_at,
        "connected_by": _name(integration.connected_by),
        "last_checked_at": integration.last_checked_at,
        "last_error": integration.last_error,
        "config": integration.config,
        "secrets_set": sorted(integration.secrets),
        "settings": integration.settings,  # never holds secrets
        "synced_at": integration.synced_at,
    }


def overview(tenant_id: int) -> list[dict]:
    """Every connectable app with this workspace's status (not connected apps included)."""
    stored = {
        i.app: i
        for i in Integration.objects.filter(tenant_id=tenant_id).select_related("connected_by")
    }
    apps = [_meta_payload(tenant_id)]
    for key in (*PROVIDERS, *OAUTH_APPS):
        if key in stored:
            apps.append(payload(stored[key]))
        else:
            apps.append({"app": key, "status": "not_connected", "config": {}, "secrets_set": []})
    return apps
