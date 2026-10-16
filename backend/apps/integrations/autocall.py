"""Auto-calling through Exotel.

When a call is due, Exotel rings the agent's phone first (their number in Users), then
connects the lead, showing the default ExoPhone as caller ID. Calls are queued as AutoCall rows:

- a new Meta lead from a form with auto-calling on -> call after the chosen delay (1, 2 or 5
  minutes; 2 by default)
- a call is scheduled (follow-up), when "call at the time of a scheduled call" is on and the
  person scheduling kept "Auto-call with Exotel" on for that call -> call at its time

Calls are only placed inside the calling hours (days, start and end time, workspace time zone):
a new-lead call due outside them waits for the next opening; a scheduled call cannot be set
outside them.

After the call: connected (the lead spoke) -> the call is logged and the scheduled call is
marked done. Not connected (no answer, busy, failed) -> logged, and the scheduled call stays open
showing "Call not connected" with Reschedule. The result comes from Exotel's status callback on
a public server, or is fetched from Exotel by the heartbeat (localhost).

Due calls are placed by the heartbeat (about every minute while the LMS is open) and by
Celery Beat in production. A call more than MISSED_AFTER late is skipped, so nobody is rung
hours after the planned time.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from apps.activity.service import ActivityType, record
from apps.enquiries.models import CallLog, CallOutcome, Enquiry, FollowUp
from common.phones import normalize_phone
from common.tenancy.context import tenant_context

from .exotel import ExotelError, get_exotel
from .models import AutoCall, AutoCallReason, AutoCallStatus, Integration, IntegrationStatus

logger = logging.getLogger(__name__)

MISSED_AFTER = timedelta(minutes=15)
RESULT_AFTER = timedelta(seconds=45)  # ask Exotel for the result once the call had time to end
RESULT_GIVE_UP = timedelta(hours=6)
BATCH = 20
CALLBACK_SALT = "exotel-callback"


def exotel_for(tenant_id: int) -> Integration | None:
    return Integration.objects.filter(
        tenant_id=tenant_id, app="exotel", status=IntegrationStatus.CONNECTED
    ).first()


def _rules(integration: Integration) -> dict:
    return integration.settings or {}


# --- calling hours -----------------------------------------------------------------------------
DEFAULT_WINDOW = {"enabled": False, "days": [0, 1, 2, 3, 4, 5], "start": "09:00", "end": "19:00"}


def call_window(integration: Integration | None) -> dict:
    """{"enabled", "days" (0 = Monday), "start", "end"} in the workspace time zone."""
    if integration is None:
        return dict(DEFAULT_WINDOW)
    return {**DEFAULT_WINDOW, **(_rules(integration).get("call_window") or {})}


def validate_window(data: dict) -> dict:
    days = sorted({int(d) for d in data.get("days", []) if str(d).isdigit() and 0 <= int(d) <= 6})
    try:
        start = time.fromisoformat(str(data.get("start", "09:00")))
        end = time.fromisoformat(str(data.get("end", "19:00")))
    except ValueError:
        raise ValidationError({"call_window": [_("Enter times as HH:MM.")]}) from None
    if bool(data.get("enabled")) and not days:
        raise ValidationError({"call_window": [_("Choose at least one day.")]})
    if start >= end:
        raise ValidationError({"call_window": [_("The end time must be after the start time.")]})
    return {
        "enabled": bool(data.get("enabled")),
        "days": days,
        "start": start.strftime("%H:%M"),
        "end": end.strftime("%H:%M"),
    }


def _zone(tenant_id: int) -> ZoneInfo:
    from apps.tenants.models import Tenant

    name = Tenant.objects.filter(pk=tenant_id).values_list("timezone", flat=True).first()
    try:
        return ZoneInfo(name or "UTC")
    except Exception:  # noqa: BLE001 - an unknown zone name falls back to UTC
        return ZoneInfo("UTC")


def next_allowed(tenant_id: int, window: dict, when: datetime) -> datetime:
    """`when` itself if it is inside the calling hours, else the next opening (UTC)."""
    if not window.get("enabled"):
        return when
    zone = _zone(tenant_id)
    local = when.astimezone(zone)
    start, end = time.fromisoformat(window["start"]), time.fromisoformat(window["end"])
    for offset in range(8):
        day = (local + timedelta(days=offset)).date()
        if day.weekday() not in window["days"]:
            continue
        opens = datetime.combine(day, start, tzinfo=zone)
        closes = datetime.combine(day, end, tzinfo=zone)
        if offset == 0 and opens <= local < closes:
            return when
        if opens > local:
            return opens.astimezone(UTC)
    return when


def inside_window(tenant_id: int, window: dict, when: datetime) -> bool:
    return next_allowed(tenant_id, window, when) == when


# --- queueing ----------------------------------------------------------------------------------
def enqueue(
    enquiry: Enquiry,
    *,
    reason: str,
    when=None,
    agent=None,
    followup: FollowUp | None = None,
) -> AutoCall | None:
    integration = exotel_for(enquiry.tenant_id)
    if integration is None:
        return None
    customer = enquiry.phone_e164 or normalize_phone(
        enquiry.phone, enquiry.tenant.default_country if enquiry.tenant_id else "IN"
    )
    agent = agent or enquiry.primary_owner or _fallback_agent(integration)
    call = AutoCall(
        tenant_id=enquiry.tenant_id,
        enquiry=enquiry,
        followup=followup,
        reason=reason,
        agent=agent,
        customer_phone=customer or "",
        scheduled_at=when or timezone.now(),
    )
    if not customer:
        call.status, call.error = AutoCallStatus.SKIPPED, _("The lead has no phone number.")
    call.save()
    return call


def _fallback_agent(integration: Integration):
    from apps.accounts.models import User

    user_id = _rules(integration).get("fallback_agent")
    return User.objects.filter(pk=user_id).first() if user_id else None


NEW_LEAD_DELAYS = (1, 2, 5)  # minutes
DEFAULT_NEW_LEAD_DELAY = 2


def new_lead_delay(integration: Integration) -> int:
    delay = _rules(integration).get("new_lead_delay", DEFAULT_NEW_LEAD_DELAY)
    return delay if delay in NEW_LEAD_DELAYS else DEFAULT_NEW_LEAD_DELAY


def on_new_meta_lead(enquiry: Enquiry, form) -> None:
    """A form with auto-calling on: call the new lead after the chosen delay, within the
    calling hours (outside them: at the next opening)."""
    if not (getattr(form, "auto_call", False) and enquiry.phone_e164):
        return
    integration = exotel_for(enquiry.tenant_id)
    if integration is None:
        return
    when = timezone.now() + timedelta(minutes=new_lead_delay(integration))
    when = next_allowed(enquiry.tenant_id, call_window(integration), when)
    enqueue(enquiry, reason=AutoCallReason.NEW_LEAD, when=when)


def followups_enabled(tenant_id: int) -> bool:
    integration = exotel_for(tenant_id)
    return bool(integration and _rules(integration).get("auto_call_followups"))


def check_followup_time(tenant_id: int, due_at: datetime) -> None:
    """A call that will be auto-called must be inside the calling hours."""
    integration = exotel_for(tenant_id)
    window = call_window(integration)
    if integration and not inside_window(tenant_id, window, due_at):
        raise ValidationError(
            {
                "due_at": [
                    _(
                        "Auto-calls run only in the calling hours (%(start)s-%(end)s on the chosen "
                        "days). Choose a time inside them, or turn off auto-call for this call."
                    )
                    % {"start": window["start"], "end": window["end"]}
                ]
            }
        )


def on_followup_scheduled(followup: FollowUp, *, auto_call: bool = True) -> None:
    """`auto_call`: the person scheduling can turn it off for this one call."""
    if auto_call and followups_enabled(followup.tenant_id):
        check_followup_time(followup.tenant_id, followup.due_at)
        enqueue(
            followup.enquiry,
            reason=AutoCallReason.FOLLOWUP,
            when=followup.due_at,
            agent=followup.assignee,
            followup=followup,
        )


def set_followup_auto_call(followup: FollowUp, enabled: bool) -> None:
    """Turn auto-calling on or off for one scheduled call (this enquiry only)."""
    existing = AutoCall.objects.filter(followup=followup).first()
    if not enabled:
        if existing and existing.status == AutoCallStatus.PENDING:
            existing.status = AutoCallStatus.CANCELLED
            existing.error = _("Auto-call turned off for this call.")
            existing.save(update_fields=["status", "error"])
        return
    if followup.done_at or not followups_enabled(followup.tenant_id):
        return
    check_followup_time(followup.tenant_id, followup.due_at)
    if existing:
        if existing.status == AutoCallStatus.CANCELLED and existing.scheduled_at > timezone.now():
            existing.status, existing.error = AutoCallStatus.PENDING, ""
            existing.save(update_fields=["status", "error"])
        return
    enqueue(
        followup.enquiry,
        reason=AutoCallReason.FOLLOWUP,
        when=followup.due_at,
        agent=followup.assignee,
        followup=followup,
    )


def on_followup_rescheduled(followup: FollowUp) -> None:
    """New time for a scheduled call (e.g. after "Call not connected"): call again then."""
    existing = AutoCall.objects.filter(followup=followup).first()
    if existing is None:
        on_followup_scheduled(followup)
        return
    if not followups_enabled(followup.tenant_id) or existing.status == AutoCallStatus.CANCELLED:
        existing.scheduled_at = followup.due_at
        existing.save(update_fields=["scheduled_at"])
        return
    check_followup_time(followup.tenant_id, followup.due_at)
    existing.status = AutoCallStatus.PENDING
    existing.scheduled_at = followup.due_at
    existing.agent = followup.assignee or existing.agent
    existing.call_sid = existing.error = ""
    existing.started_at = existing.finished_at = None
    existing.duration_seconds = 0
    existing.save()


def on_followup_done(followup: FollowUp) -> None:
    AutoCall.objects.filter(followup=followup, status=AutoCallStatus.PENDING).update(
        status=AutoCallStatus.CANCELLED, error=_("The scheduled call was marked done.")
    )


# --- dialing -----------------------------------------------------------------------------------
def status_callback_url(tenant_id: int) -> str | None:
    """Exotel reports the result here; only possible on a public HTTPS address."""
    base = settings.BACKEND_URL.rstrip("/")
    if not base.startswith("https://") or "localhost" in base or "127.0.0.1" in base:
        return None
    return f"{base}/webhooks/exotel/{signing.dumps(tenant_id, salt=CALLBACK_SALT)}"


def _activity(call: AutoCall, details: dict) -> None:
    record(
        tenant_id=call.tenant_id,
        enquiry_id=call.enquiry_id,
        contact_id=call.enquiry.contact_id,
        type=ActivityType.AUTO_CALL,
        actor=None,
        details={"reason": call.reason, "agent": getattr(call.agent, "full_name", ""), **details},
    )


def process_due(tenant_id: int) -> int:
    """Place the calls that are due now. Returns how many were started.

    Runs in its own tenant context: it is also called by Celery.
    """
    now = timezone.now()
    started = 0
    with tenant_context(tenant_id):
        integration = exotel_for(tenant_id)
        if integration is None:
            return 0
        due = list(
            AutoCall.objects.select_for_update(skip_locked=True, of=("self",))
            .select_related("enquiry", "agent", "followup")
            .filter(tenant_id=tenant_id, status=AutoCallStatus.PENDING, scheduled_at__lte=now)
            .order_by("scheduled_at")[:BATCH]
        )
        if not due:
            return 0
        client = get_exotel(integration.values())
        caller = _rules(integration).get("default_caller", "")
        callback = status_callback_url(tenant_id)
        window = call_window(integration)
        for call in due:
            started += _dial(call, client, caller, callback, now, window)
    return started


def _dial(call: AutoCall, client, caller: str, callback: str | None, now, window: dict) -> int:
    def finish(status: str, error: str) -> int:
        call.status, call.error, call.finished_at = status, error, now
        call.save(update_fields=["status", "error", "finished_at"])
        _activity(call, {"status": status, "error": error})
        return 0

    if call.enquiry.deleted_at:
        return finish(AutoCallStatus.CANCELLED, _("The enquiry was deleted."))
    if call.followup_id and call.followup.done_at:
        return finish(AutoCallStatus.CANCELLED, _("The scheduled call was marked done."))
    if call.scheduled_at < now - MISSED_AFTER:
        return finish(AutoCallStatus.SKIPPED, _("Missed: the LMS was not running at that time."))
    opening = next_allowed(call.tenant_id, window, now)
    if opening != now:  # outside the calling hours (they may have changed): wait for them
        call.scheduled_at = opening
        call.save(update_fields=["scheduled_at"])
        return 0
    agent_phone = getattr(call.agent, "phone", "") if call.agent else ""
    if not call.agent:
        return finish(AutoCallStatus.SKIPPED, _("No one is assigned to this lead."))
    if not agent_phone:
        return finish(
            AutoCallStatus.SKIPPED,
            _("%s has no phone number. Add it under Users.") % call.agent.full_name,
        )
    if not caller:
        return finish(AutoCallStatus.SKIPPED, _("Choose a caller ID number in Exotel settings."))

    call.agent_phone, call.caller_id = agent_phone, caller
    try:
        call.call_sid = client.connect_call(
            agent=agent_phone,
            customer=call.customer_phone,
            caller_id=caller,
            status_callback=callback,
        )
    except ExotelError as exc:
        call.save(update_fields=["agent_phone", "caller_id"])
        return finish(AutoCallStatus.FAILED, str(exc))
    call.status, call.started_at, call.error = AutoCallStatus.STARTED, now, ""
    call.save(
        update_fields=["agent_phone", "caller_id", "call_sid", "status", "started_at", "error"]
    )
    _activity(call, {"status": AutoCallStatus.STARTED})
    return 1


# --- the result -----------------------------------------------------------------------------------
TERMINAL = {"completed", "busy", "no-answer", "failed", "canceled"}
NOT_CONNECTED = {
    "busy": (AutoCallStatus.BUSY, CallOutcome.BUSY),
    "no-answer": (AutoCallStatus.NO_ANSWER, CallOutcome.NO_ANSWER),
    "failed": (AutoCallStatus.FAILED, CallOutcome.NO_ANSWER),
    "canceled": (AutoCallStatus.FAILED, CallOutcome.NO_ANSWER),
}


def _seconds(value) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _finish_call(call: AutoCall, *, status: str, conversation: int, lead_status: str = "") -> None:
    """Connected = the lead spoke (conversation time, or the lead's leg completed)."""
    connected = conversation > 0 or (lead_status == "completed" and status == "completed")
    if connected:
        call_status, outcome = AutoCallStatus.COMPLETED, CallOutcome.CONNECTED
    else:
        key = lead_status if lead_status in NOT_CONNECTED else status
        call_status, outcome = NOT_CONNECTED.get(
            key, (AutoCallStatus.NO_ANSWER, CallOutcome.NO_ANSWER)
        )
    now = timezone.now()
    call.status, call.duration_seconds, call.finished_at = call_status, conversation, now
    call.save(update_fields=["status", "duration_seconds", "finished_at"])
    CallLog.objects.create(
        tenant_id=call.tenant_id,
        enquiry=call.enquiry,
        outcome=outcome,
        duration_seconds=conversation,
        notes=_("Auto call via Exotel (%s)") % call.get_reason_display(),
        user=call.agent,
        provider="exotel",
    )
    _activity(call, {"status": call_status, "duration_seconds": conversation})
    if connected and call.followup_id:
        followup = call.followup
        if followup.done_at is None:
            followup.done_at = now
            followup.save(update_fields=["done_at"])
            record(
                tenant_id=call.tenant_id,
                enquiry_id=call.enquiry_id,
                contact_id=call.enquiry.contact_id,
                type=ActivityType.FOLLOWUP_COMPLETED,
                actor=None,
                details={"followup_id": followup.pk, "title": followup.title, "auto": True},
            )


def tenant_from_callback(token: str) -> int | None:
    try:
        return int(signing.loads(token, salt=CALLBACK_SALT))
    except (signing.BadSignature, TypeError, ValueError):
        return None


def apply_status_callback(tenant_id: int, data) -> bool:
    """Exotel's StatusCallback (public servers): store the result."""
    sid = str(data.get("CallSid") or data.get("Sid") or "")
    call = (
        AutoCall.objects.select_related("enquiry", "agent", "followup")
        .filter(tenant_id=tenant_id, call_sid=sid)
        .first()
    )
    if (
        not sid
        or call is None
        or call.status not in (AutoCallStatus.STARTED, AutoCallStatus.PENDING)
    ):
        return False
    status = str(data.get("Status") or data.get("CallStatus") or "").lower()
    conversation = _seconds(data.get("ConversationDuration") or data.get("DialCallDuration"))
    lead_status = str(data.get("Leg2Status") or "").lower()
    _finish_call(
        call, status=status or "completed", conversation=conversation, lead_status=lead_status
    )
    return True


def poll_results(tenant_id: int) -> int:
    """Heartbeat: ask Exotel how placed calls ended (no callback on localhost). Returns how many
    finished."""
    now = timezone.now()
    finished = 0
    with tenant_context(tenant_id):
        integration = exotel_for(tenant_id)
        if integration is None:
            return 0
        calls = list(
            AutoCall.objects.select_for_update(skip_locked=True, of=("self",))
            .select_related("enquiry", "agent", "followup")
            .filter(
                tenant_id=tenant_id,
                status=AutoCallStatus.STARTED,
                started_at__lte=now - RESULT_AFTER,
            )
            .exclude(call_sid="")[:BATCH]
        )
        if not calls:
            return 0
        client = get_exotel(integration.values())
        for call in calls:
            try:
                with transaction.atomic():
                    details = client.call_details(call.call_sid)
                    status = str(details.get("Status") or "").lower()
                    if status not in TERMINAL:
                        if call.started_at < now - RESULT_GIVE_UP:
                            _finish_call(call, status="failed", conversation=0)
                            finished += 1
                        continue
                    extra = details.get("Details") or {}
                    _finish_call(
                        call,
                        status=status,
                        conversation=_seconds(extra.get("ConversationDuration")),
                        lead_status=str(extra.get("Leg2Status") or "").lower(),
                    )
                    finished += 1
            except ExotelError:
                logger.warning("Could not read the result of call %s", call.call_sid, exc_info=True)
    return finished
