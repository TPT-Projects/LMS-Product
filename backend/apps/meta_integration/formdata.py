"""MongoDB `lead_form_responses`: the Meta lead exactly as received (spec section 3).

Only this module touches the collection, through the tenant-safe data layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from common.mongo import LEAD_FORM_RESPONSES, TenantCollection

RECEIVED = "received"
FORM_NOT_CONNECTED = "form_not_connected"
SYNCED = "synced"
FAILED = "failed"


def _col(tenant_id: int) -> TenantCollection:
    return TenantCollection(LEAD_FORM_RESPONSES, tenant_id)


def save_raw_event(
    tenant_id: int, *, leadgen_id: str, page_id: str, form_id: str, raw: dict
) -> None:
    """Step 1 of ingestion. A repeat delivery changes nothing (unique tenant + leadgen_id)."""
    _col(tenant_id).update_one(
        {"leadgen_id": leadgen_id},
        {
            "$setOnInsert": {
                "page_id": page_id,
                "form_id": form_id,
                "status": RECEIVED,
                "received_at": datetime.now(UTC),
                "raw_event": raw,
                "field_data": [],
                "unmapped_questions": [],
                "enquiry_id": None,
            }
        },
        upsert=True,
    )


def save_lead(tenant_id: int, *, lead: dict, page_id: str) -> None:
    """Store the full lead from the Graph API (answers exactly as received)."""
    _col(tenant_id).update_one(
        {"leadgen_id": lead["id"]},
        {
            "$set": {
                "page_id": page_id,
                "form_id": lead.get("form_id", ""),
                "created_time": lead.get("created_time"),
                "campaign_name": lead.get("campaign_name", ""),
                "adset_name": lead.get("adset_name", ""),
                "ad_name": lead.get("ad_name", ""),
                "platform": lead.get("platform", ""),
                "field_data": lead.get("field_data", []),
            },
            "$setOnInsert": {"received_at": datetime.now(UTC), "status": RECEIVED},
        },
        upsert=True,
    )


def set_status(
    tenant_id: int,
    leadgen_id: str,
    status: str,
    *,
    enquiry_id: int | None = None,
    unmapped: list[str] | None = None,
    error: str | None = None,
) -> None:
    fields: dict[str, Any] = {"status": status}
    if enquiry_id is not None:
        fields["enquiry_id"] = enquiry_id
    if unmapped is not None:
        fields["unmapped_questions"] = unmapped
    if error is not None:
        fields["error"] = error[:500]
    _col(tenant_id).update_one({"leadgen_id": leadgen_id}, {"$set": fields})


def question_samples(tenant_id: int, form_id: str, per_question: int = 5) -> dict[str, list[str]]:
    """{question name: up to N distinct answers} from stored leads of one form."""
    rows = _col(tenant_id).aggregate(
        [
            {"$match": {"form_id": form_id}},
            {"$sort": {"received_at": -1}},
            {"$limit": 500},
            {"$unwind": "$field_data"},
            {"$unwind": "$field_data.values"},
            {"$group": {"_id": "$field_data.name", "values": {"$addToSet": "$field_data.values"}}},
        ]
    )
    return {row["_id"]: [str(v) for v in row["values"][:per_question]] for row in rows}


def count_by_status(tenant_id: int, form_id: str | None = None) -> dict[str, int]:
    match: dict[str, Any] = {"form_id": form_id} if form_id else {}
    rows = _col(tenant_id).aggregate(
        [{"$match": match}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    )
    return {row["_id"]: row["n"] for row in rows}
