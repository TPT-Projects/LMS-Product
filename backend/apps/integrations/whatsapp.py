"""WhatsApp Business: connect with a Facebook login popup (no API keys to copy).

The popup uses the same Facebook app and return URL as Meta lead ads; the signed state says
it is a WhatsApp login. After login, the WhatsApp Business Accounts the person allowed and
their phone numbers are listed; one number is the default for sending.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Membership
from apps.audit.service import INTEGRATION_CONNECTED, audit
from apps.meta_integration.graph import GraphError, get_graph
from apps.meta_integration.services import oauth_state

from .models import Integration, IntegrationStatus

APP = "whatsapp"
SCOPES = ["whatsapp_business_management", "whatsapp_business_messaging", "business_management"]


def start(membership: Membership) -> str:
    return get_graph().oauth_url(oauth_state(membership, APP), scopes=SCOPES)


def _label(number: dict | None) -> str:
    if not number:
        return ""
    parts = [number.get("display_phone_number", ""), number.get("verified_name", "")]
    return " · ".join(p for p in parts if p)


def _pick(accounts: list[dict], phone_number_id: str | None) -> tuple[dict | None, dict | None]:
    for account in accounts:
        for number in account["numbers"]:
            if not phone_number_id or number["id"] == phone_number_id:
                return account, number
    return None, None


@transaction.atomic
def complete(membership: Membership, *, code: str) -> Integration:
    graph = get_graph()
    try:
        token, expires_unix = graph.exchange_code(code)
        accounts = graph.list_whatsapp_accounts(token)
    except GraphError as exc:
        raise ValidationError({"detail": _("Meta said: %s") % exc}) from None
    if not accounts:
        raise ValidationError(
            {
                "detail": _(
                    "No WhatsApp Business Account was shared. Log in again and allow your "
                    "WhatsApp Business Account in the popup."
                )
            }
        )

    integration = Integration.objects.filter(tenant_id=membership.tenant_id, app=APP).first()
    if integration is None:
        integration = Integration(
            tenant_id=membership.tenant_id, app=APP, connected_by=membership.user
        )
    previous = integration.config.get("phone_number_id") if integration.pk else None
    account, number = _pick(accounts, previous)
    if number is None:
        account, number = _pick(accounts, None)
    integration.secrets = {"access_token": token}
    integration.config = {
        "phone_number_id": number["id"] if number else "",
        "business_account_id": account["id"] if account else "",
    }
    integration.settings = {
        **integration.settings,
        "accounts": accounts,
        "token_expires_at": (
            datetime.fromtimestamp(expires_unix, tz=UTC).isoformat() if expires_unix else None
        ),
    }
    integration.status = IntegrationStatus.CONNECTED
    integration.account_label = _label(number) or (account or {}).get("name", "")
    integration.last_checked_at = integration.synced_at = timezone.now()
    integration.last_error = ""
    integration.save()
    audit(
        tenant_id=membership.tenant_id,
        actor=membership.user,
        action=INTEGRATION_CONNECTED,
        details={"app": APP, "account": integration.account_label},
    )
    return integration


# --- Embedded Signup (Make.com-style: new number or WhatsApp Business app number) -----------------
NEW_NUMBER = "new"  # a new number, or one already on the Cloud API
COEXISTENCE = "coexistence"  # keep using the number in the WhatsApp Business app too


def signup_config() -> dict:
    return {
        "available": bool(settings.META_APP_ID and settings.META_WHATSAPP_CONFIG_ID),
        "app_id": settings.META_APP_ID,
        "config_id": settings.META_WHATSAPP_CONFIG_ID,
        "graph_version": settings.META_GRAPH_VERSION,
    }


def _register(graph, integration: Integration, token: str, number: dict) -> str | None:
    """Register a number that is not on the Cloud API yet. Returns an error or None."""
    pin = integration.secrets.get("pin") or f"{secrets.randbelow(10**6):06d}"
    try:
        graph.register_phone(number["id"], token, pin)
    except GraphError as exc:
        return str(exc)
    integration.secrets = {**integration.secrets, "pin": pin}
    number["platform_type"] = "CLOUD_API"
    return None


@transaction.atomic
def complete_embedded(
    membership: Membership,
    *,
    code: str,
    waba_id: str = "",
    phone_number_id: str = "",
    flow: str = NEW_NUMBER,
) -> Integration:
    """After the Embedded Signup popup: exchange the code, find the account and number,
    subscribe the app to the account and (new numbers only) register the number."""
    graph = get_graph()
    try:
        token = graph.exchange_signup_code(code)
        accounts = graph.list_whatsapp_accounts(token)
    except GraphError as exc:
        raise ValidationError({"detail": _("Meta said: %s") % exc}) from None
    if not accounts:
        raise ValidationError(
            {"detail": _("Meta did not share a WhatsApp Business Account. Please try again.")}
        )

    integration = Integration.objects.filter(tenant_id=membership.tenant_id, app=APP).first()
    if integration is None:
        integration = Integration(
            tenant_id=membership.tenant_id, app=APP, connected_by=membership.user
        )
    integration.secrets = {**(integration.secrets if integration.pk else {}), "access_token": token}

    issues: list[str] = []
    for account in accounts:
        if waba_id and account["id"] != waba_id:
            continue
        try:
            graph.subscribe_waba(account["id"], token)
        except GraphError as exc:
            issues.append(
                _("Could not subscribe to %(name)s: %(error)s")
                % {"name": account["name"], "error": exc}
            )
        for number in account["numbers"]:
            wanted = not phone_number_id or number["id"] == phone_number_id
            if wanted and flow != COEXISTENCE and number.get("platform_type") == "NOT_APPLICABLE":
                if error := _register(graph, integration, token, number):
                    issues.append(
                        _("Could not register %(n)s: %(e)s")
                        % {"n": number["display_phone_number"], "e": error}
                    )

    account, number = _pick(accounts, phone_number_id or None)
    if number is None:
        account, number = _pick(accounts, None)
    integration.config = {
        "phone_number_id": number["id"] if number else "",
        "business_account_id": (account or {}).get("id", ""),
    }
    integration.settings = {
        **integration.settings,
        "accounts": accounts,
        "flow": flow,
        "setup_issues": issues,
        "token_expires_at": None,  # business tokens from Embedded Signup do not expire
    }
    integration.status = IntegrationStatus.CONNECTED
    integration.account_label = _label(number) or (account or {}).get("name", "")
    integration.last_checked_at = integration.synced_at = timezone.now()
    integration.last_error = "; ".join(issues)
    integration.save()
    audit(
        tenant_id=membership.tenant_id,
        actor=membership.user,
        action=INTEGRATION_CONNECTED,
        details={"app": APP, "account": integration.account_label, "flow": flow},
    )
    return integration


def register_number(integration: Integration, phone_number_id: str) -> Integration:
    """'Register' button on the Manage page, for a number Meta still lists as not registered."""
    account, number = _pick(integration.settings.get("accounts", []), str(phone_number_id))
    if number is None or number["id"] != str(phone_number_id):
        raise ValidationError({"phone_number_id": [_("This number is not in your accounts.")]})
    error = _register(get_graph(), integration, integration.secrets.get("access_token", ""), number)
    if error:
        raise ValidationError({"detail": _("Meta said: %s") % error})
    integration.settings = dict(integration.settings)  # the number dict was updated in place
    integration.save(update_fields=["settings", "_secrets"])
    return integration


def refresh(integration: Integration) -> Integration:
    try:
        accounts = get_graph().list_whatsapp_accounts(integration.secrets.get("access_token", ""))
    except GraphError as exc:
        raise ValidationError({"detail": _("Meta said: %s") % exc}) from None
    integration.settings = {**integration.settings, "accounts": accounts}
    integration.synced_at = timezone.now()
    account, number = _pick(accounts, integration.config.get("phone_number_id"))
    if number:
        integration.account_label = _label(number)
    integration.save(update_fields=["settings", "synced_at", "account_label"])
    return integration


def choose_number(integration: Integration, phone_number_id: str) -> Integration:
    account, number = _pick(integration.settings.get("accounts", []), str(phone_number_id))
    if number is None or number["id"] != str(phone_number_id):
        raise ValidationError({"phone_number_id": [_("This number is not in your accounts.")]})
    integration.config = {"phone_number_id": number["id"], "business_account_id": account["id"]}
    integration.account_label = _label(number)
    integration.save(update_fields=["config", "account_label"])
    return integration
