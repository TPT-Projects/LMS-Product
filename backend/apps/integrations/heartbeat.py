"""The heartbeat: work that must happen on time, run about every minute.

Called by the open LMS (POST /integrations/heartbeat, so it works on localhost without Redis)
and by Celery Beat in production. Each part is independent: one failing does not stop others.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.meta_integration.services import poll_new_leads

from . import autocall, google
from .models import Integration, IntegrationStatus

logger = logging.getLogger(__name__)

EXOTEL_REFRESH_EVERY = timedelta(days=1)


def _safely(name: str, fn, *args):
    try:
        with transaction.atomic():
            return fn(*args)
    except Exception:  # noqa: BLE001 - one broken app must not stop the others
        logger.exception("Heartbeat step %s failed", name)
        return None


def refresh_exotel_if_due(tenant_id: int) -> bool:
    """Exotel numbers are refreshed automatically once a day."""
    from .exotel import refresh_numbers

    now = timezone.now()
    due = Q(synced_at__isnull=True) | Q(synced_at__lt=now - EXOTEL_REFRESH_EVERY)
    claimed = (
        Integration.objects.filter(
            tenant_id=tenant_id, app="exotel", status=IntegrationStatus.CONNECTED
        )
        .filter(due)
        .update(synced_at=now)
    )
    if not claimed:
        return False
    refresh_numbers(Integration.objects.get(tenant_id=tenant_id, app="exotel"))
    return True


def run(tenant_id: int) -> dict:
    meta = _safely("meta", poll_new_leads, tenant_id) or {}
    return {
        "leads_added": meta.get("added", 0),
        "numbers_refreshed": bool(_safely("exotel", refresh_exotel_if_due, tenant_id)),
        "calls_started": _safely("calls", autocall.process_due, tenant_id) or 0,
        "calls_finished": _safely("call results", autocall.poll_results, tenant_id) or 0,
        "sheet_rows": _safely("sheets", google.sync_due, tenant_id) or 0,
    }
