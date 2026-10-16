"""Apps connected with credentials: the details each one needs and how they are checked.

Meta lead ads is not here: it connects with a Facebook login popup (apps.meta_integration).
The full catalog shown in the UI (including "coming soon" apps) lives in the frontend.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import requests
from django.conf import settings
from django.utils.translation import gettext as _

TIMEOUT = 15


class CheckFailed(Exception):
    """The provider refused the details. `field` names the likely culprit, if known."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


@dataclass(frozen=True)
class FieldSpec:
    secret: bool = False  # stored encrypted, never sent back to the browser
    required: bool = True
    pattern: str | None = None
    choices: tuple[str, ...] = ()

    def problem(self, value: str) -> str | None:
        if not value:
            return _("This field is required.") if self.required else None
        if self.choices and value not in self.choices:
            return _("Choose one of the options.")
        if self.pattern and not re.fullmatch(self.pattern, value):
            return _("This does not look right. Check the value and try again.")
        return None


@dataclass(frozen=True)
class Provider:
    key: str
    fields: dict[str, FieldSpec]
    check: Callable[[dict[str, str]], str]  # returns a label for the connected account


def _json(response: requests.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


# --- WhatsApp Business (Cloud API) -----------------------------------------------------
def check_whatsapp(values: dict[str, str]) -> str:
    """Read the phone number with the access token (Graph API)."""
    url = f"https://graph.facebook.com/{settings.META_GRAPH_VERSION}/{values['phone_number_id']}"
    try:
        response = requests.get(
            url,
            params={
                "fields": "display_phone_number,verified_name",
                "access_token": values["access_token"],
            },
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise CheckFailed(_("Could not reach WhatsApp. Try again in a moment.")) from exc
    body = _json(response)
    if response.status_code >= 400 or "error" in body:
        error = body.get("error", {})
        message = error.get("message") or f"HTTP {response.status_code}"
        field = "access_token" if error.get("code") in (102, 190) else "phone_number_id"
        raise CheckFailed(_("WhatsApp said: %s") % message, field)
    parts = [body.get("display_phone_number", ""), body.get("verified_name", "")]
    return " · ".join(p for p in parts if p) or values["phone_number_id"]


# --- Exotel (calling) --------------------------------------------------------------------
EXOTEL_HOSTS = {"in": "api.in.exotel.com", "sg": "api.exotel.com"}  # Mumbai, Singapore


def check_exotel(values: dict[str, str]) -> str:
    """List one call with HTTP Basic auth (API key + token): proves key, token and SID."""
    host = EXOTEL_HOSTS[values["region"]]
    url = f"https://{host}/v1/Accounts/{values['account_sid']}/Calls.json"
    try:
        response = requests.get(
            url,
            params={"PageSize": 1},
            auth=(values["api_key"], values["api_token"]),
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise CheckFailed(_("Could not reach Exotel. Try again in a moment.")) from exc
    if response.status_code in (401, 403):
        raise CheckFailed(_("Exotel refused this API key and token."), "api_token")
    if response.status_code == 404:
        raise CheckFailed(
            _("Exotel has no account with this SID in the chosen region."), "account_sid"
        )
    if response.status_code == 429:
        raise CheckFailed(_("Exotel is limiting requests right now. Try again in a minute."))
    if response.status_code >= 400:
        raise CheckFailed(_("Exotel answered with error %s.") % response.status_code)
    return values["account_sid"]


PROVIDERS: dict[str, Provider] = {
    "whatsapp": Provider(
        key="whatsapp",
        fields={
            "phone_number_id": FieldSpec(pattern=r"[0-9]{5,25}"),
            "business_account_id": FieldSpec(required=False, pattern=r"[0-9]{5,25}"),
            "access_token": FieldSpec(secret=True, pattern=r"\S{20,}"),
        },
        check=check_whatsapp,
    ),
    "exotel": Provider(
        key="exotel",
        fields={
            "region": FieldSpec(choices=tuple(EXOTEL_HOSTS)),
            "account_sid": FieldSpec(pattern=r"[A-Za-z0-9_\-]{2,64}"),
            "api_key": FieldSpec(pattern=r"\S{4,}"),
            "api_token": FieldSpec(secret=True, pattern=r"\S{4,}"),
        },
        check=check_exotel,
    ),
}
