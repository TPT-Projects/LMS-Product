"""Exotel: the account's ExoPhones (virtual numbers) and the "connect two numbers" call.

API (HTTP Basic auth with the API key and token, regional host):
- GET  /v2_beta/Accounts/{sid}/IncomingPhoneNumbers  -> {"incoming_phone_numbers": [...]}
- POST /v1/Accounts/{sid}/Calls/connect.json         -> {"Call": {"Sid": ...}}
  Exotel rings `From` (the agent) first, then `To` (the lead), showing `CallerId` (an ExoPhone).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import requests
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import ExotelNumber, Integration
from .providers import EXOTEL_HOSTS, TIMEOUT

PAGE_SIZE = 100


class ExotelError(Exception):
    pass


class ExotelClient:
    def __init__(self, values: dict[str, str]):
        self.sid = values["account_sid"]
        self.auth = (values["api_key"], values["api_token"])
        self.base = f"https://{EXOTEL_HOSTS.get(values.get('region', 'in'), EXOTEL_HOSTS['in'])}"

    def _call(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        try:
            response = requests.request(
                method, f"{self.base}{path}", auth=self.auth, timeout=TIMEOUT, **kwargs
            )
        except requests.RequestException as exc:
            raise ExotelError(_("Could not reach Exotel. Try again in a moment.")) from exc
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code in (401, 403):
            raise ExotelError(_("Exotel refused this API key and token."))
        if response.status_code >= 400:
            message = (
                (body.get("RestException") or {}).get("Message") if isinstance(body, dict) else ""
            )
            raise ExotelError(message or _("Exotel answered with error %s.") % response.status_code)
        return body if isinstance(body, dict) else {}

    def list_numbers(self) -> list[dict[str, Any]]:
        numbers: list[dict[str, Any]] = []
        for page in range(20):  # safety limit: 2000 numbers
            body = self._call(
                "GET",
                f"/v2_beta/Accounts/{self.sid}/IncomingPhoneNumbers",
                params={"page": page, "page_size": PAGE_SIZE},
            )
            batch = body.get("incoming_phone_numbers") or []
            numbers.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
        return numbers

    def call_details(self, call_sid: str) -> dict[str, Any]:
        """Status of a placed call; `Details` holds Leg1Status, Leg2Status and
        ConversationDuration (seconds the two people spoke)."""
        body = self._call(
            "GET", f"/v1/Accounts/{self.sid}/Calls/{call_sid}.json", params={"details": "true"}
        )
        return body.get("Call") or {}

    def connect_call(
        self, *, agent: str, customer: str, caller_id: str, status_callback: str | None = None
    ) -> str:
        data = {"From": agent, "To": customer, "CallerId": caller_id}
        if status_callback:
            data["StatusCallback"] = status_callback
        body = self._call("POST", f"/v1/Accounts/{self.sid}/Calls/connect.json", data=data)
        return str((body.get("Call") or {}).get("Sid") or "")


_factory: Callable[[dict[str, str]], Any] = ExotelClient


def get_exotel(values: dict[str, str]):
    return _factory(values)


def set_exotel_factory(factory: Callable[[dict[str, str]], Any] | None) -> None:
    """Tests swap in a fake; None restores the real client."""
    global _factory
    _factory = factory or ExotelClient


# --- numbers -------------------------------------------------------------------------------
@transaction.atomic
def refresh_numbers(integration: Integration) -> list[ExotelNumber]:
    """Load the ExoPhones from Exotel. Numbers Exotel no longer lists are marked inactive
    (manually added ones stay). The first voice number becomes the default caller ID."""
    remote = get_exotel(integration.values()).list_numbers()
    now = timezone.now()
    seen: set[str] = set()
    for item in remote:
        phone = str(item.get("phone_number") or item.get("PhoneNumber") or "").strip()
        if not phone:
            continue
        seen.add(phone)
        number, created = ExotelNumber.objects.get_or_create(
            tenant_id=integration.tenant_id,
            phone_number=phone,
            defaults={"active_since": now},
        )
        number.sid = str(item.get("sid") or "")[:64]
        number.friendly_name = str(item.get("friendly_name") or "")[:120]
        number.region = str(item.get("region") or "")[:40]
        number.country = str(item.get("country") or "")[:4]
        number.capabilities = item.get("capabilities") or {}
        number.added_manually = False
        if not number.is_active:  # came back: active again from now
            number.active_since = now
        number.is_active = True
        number.last_seen_at = now
        number.save()
    ExotelNumber.objects.filter(
        tenant_id=integration.tenant_id, added_manually=False, is_active=True
    ).exclude(phone_number__in=seen).update(is_active=False)

    integration.synced_at = now
    numbers = list(ExotelNumber.objects.filter(tenant_id=integration.tenant_id, is_active=True))
    if not integration.settings.get("default_caller") and numbers:
        voice = [n for n in numbers if n.capabilities.get("voice", True)]
        integration.settings = {
            **integration.settings,
            "default_caller": (voice or numbers)[0].phone_number,
        }
    integration.save(update_fields=["synced_at", "settings"])
    return numbers
