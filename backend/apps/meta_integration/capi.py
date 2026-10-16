"""Conversions API for CRM: tell Meta how each lead turned out, so it finds better leads.

Every time a Meta lead's status changes in the LMS (and when the lead arrives), an event named
after the status is sent to the Meta dataset with the lead ID (plus hashed email / phone):
https://developers.facebook.com/documentation/ads-commerce/conversions-api/conversion-leads-integration/payload-specification

In Meta Events Manager, map these status names to your funnel stages (e.g. New -> Lead,
Qualified -> Qualified lead, Closed -> Converted).
"""

from __future__ import annotations

import hashlib
import logging
import time

from django.db import transaction
from django.utils.translation import gettext as _

from common.tenancy.context import tenant_context

from .graph import GraphError, get_graph
from .models import ConnectionStatus, ConversionEvent, MetaConnection

logger = logging.getLogger(__name__)

LEAD_EVENT_SOURCE = "LMS"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def build_event(enquiry, event_name: str) -> dict:
    user_data: dict = {"lead_id": int(enquiry.leadgen_id)}
    if enquiry.email:
        user_data["em"] = [_sha256(enquiry.email)]
    if enquiry.phone_e164:
        user_data["ph"] = [_sha256(enquiry.phone_e164.lstrip("+"))]
    return {
        "event_name": event_name,
        "event_time": int(time.time()),
        "action_source": "system_generated",
        "user_data": user_data,
        "custom_data": {"event_source": "crm", "lead_event_source": LEAD_EVENT_SOURCE},
    }


def _connection(tenant_id: int) -> MetaConnection | None:
    connection = MetaConnection.objects.filter(tenant_id=tenant_id).first()
    if (
        connection is None
        or not connection.capi_enabled
        or not connection.capi_dataset_id
        or not connection.capi_token
    ):
        return None
    return connection


def send(enquiry, event_name: str, *, test_event_code: str = "") -> ConversionEvent | None:
    """Send one stage event now. Only for Meta leads (they have Meta's lead ID)."""
    if not (enquiry.leadgen_id and str(enquiry.leadgen_id).isdigit()):
        return None
    connection = _connection(enquiry.tenant_id)
    if connection is None:
        return None
    event = ConversionEvent(
        tenant_id=enquiry.tenant_id,
        enquiry=enquiry,
        leadgen_id=enquiry.leadgen_id,
        event_name=event_name[:100],
        test=bool(test_event_code),
    )
    try:
        get_graph().send_conversion_events(
            connection.capi_dataset_id,
            connection.capi_token,
            [build_event(enquiry, event_name)],
            test_event_code=test_event_code,
        )
        event.success = True
    except GraphError as exc:
        event.error = str(exc)[:1000]
    event.save()
    return event


def send_after_commit(enquiry_id: int, tenant_id: int, event_name: str) -> None:
    """Status changed / lead arrived: send once the change is saved (failures are logged)."""

    def run():
        from apps.enquiries.models import Enquiry

        try:
            with tenant_context(tenant_id):
                enquiry = Enquiry.objects.filter(pk=enquiry_id).first()
                if enquiry is not None:
                    send(enquiry, event_name)
        except Exception:  # noqa: BLE001 - feedback to Meta must never break the LMS
            logger.exception("Conversions API event for enquiry %s failed", enquiry_id)

    transaction.on_commit(run, robust=True)


def settings_payload(connection: MetaConnection | None) -> dict:
    return {
        "enabled": bool(connection and connection.capi_enabled),
        "dataset_id": connection.capi_dataset_id if connection else "",
        "token_set": bool(connection and connection._capi_token),
        "connected": bool(connection and connection.status == ConnectionStatus.CONNECTED),
    }


def event_payload(event: ConversionEvent) -> dict:
    return {
        "id": event.pk,
        "enquiry_id": event.enquiry_id,
        "leadgen_id": event.leadgen_id,
        "event_name": event.event_name,
        "success": event.success,
        "error": event.error,
        "test": event.test,
        "sent_at": event.sent_at,
    }


def no_lead_error():
    return _("There is no Meta lead to send a test event for yet.")
