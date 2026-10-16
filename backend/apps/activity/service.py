"""Activity timeline (MongoDB `activity_logs`, spec section 3).

Entries are append-only. They are written after the PostgreSQL transaction
commits, so a rolled-back change never leaves a timeline entry behind.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from django.db import transaction

from common.mongo import ACTIVITY_LOGS, TenantCollection

logger = logging.getLogger(__name__)


class ActivityType(StrEnum):
    ENQUIRY_CREATED = "enquiry_created"
    REPEAT_ENQUIRY = "repeat_enquiry"
    CONTACT_UPDATED = "contact_information_updated"
    STATUS_CHANGED = "status_changed"
    FIELD_CHANGED = "field_changed"
    ASSIGNMENT_CHANGED = "assignment_changed"
    NOTE_ADDED = "note_added"
    CALL_LOGGED = "call_logged"
    FOLLOWUP_SCHEDULED = "followup_scheduled"
    FOLLOWUP_COMPLETED = "followup_completed"
    ATTACHMENT_ADDED = "attachment_added"
    ENQUIRY_DELETED = "enquiry_deleted"
    ENQUIRY_RESTORED = "enquiry_restored"
    AUTO_CALL = "auto_call"  # Exotel auto-call started / finished / failed
    MENTION = "mention"
    IMPORT_CREATED = "import_created"
    META_SYNC_FAILED = "meta_sync_failed"


def actor_of(user) -> dict[str, Any]:
    if user is None:
        return {"type": "system", "id": None, "name": "System"}
    return {"type": "user", "id": user.pk, "name": user.full_name or user.email}


def _defer(write: Callable[[], None]) -> None:
    """Run after commit. Tests replace this to run immediately."""
    transaction.on_commit(write, robust=True)


def record(
    *,
    tenant_id: int,
    type: ActivityType,
    actor=None,
    enquiry_id: int | None = None,
    contact_id: int | None = None,
    details: dict[str, Any] | None = None,
    at: datetime | None = None,
) -> None:
    document = {
        "enquiry_id": enquiry_id,
        "contact_id": contact_id,
        "type": str(type),
        "actor": actor_of(actor),
        "created_at": at or datetime.now(UTC),
        "details": details or {},
    }

    def write() -> None:
        try:
            TenantCollection(ACTIVITY_LOGS, tenant_id).insert_one(document)
        except Exception:  # never fail the user's action because the log store is down
            logger.exception("Could not write activity log %s", document["type"])

    _defer(write)


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    created = doc["created_at"]
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return {
        "id": str(doc["_id"]),
        "type": doc["type"],
        "actor": doc.get("actor") or actor_of(None),
        "created_at": created.isoformat(),
        "details": doc.get("details") or {},
        "enquiry_id": doc.get("enquiry_id"),
    }


def timeline(
    *,
    tenant_id: int,
    enquiry_id: int | None = None,
    contact_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[int, list[dict[str, Any]]]:
    """Newest first. Returns (total count, page of entries)."""
    query: dict[str, Any] = {}
    if enquiry_id is not None:
        query["enquiry_id"] = enquiry_id
    if contact_id is not None:
        query["contact_id"] = contact_id
    logs = TenantCollection(ACTIVITY_LOGS, tenant_id)
    total = logs.count_documents(query)
    docs = logs.find(
        query,
        sort=[("created_at", -1), ("_id", -1)],
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    return total, [_serialize(d) for d in docs]
