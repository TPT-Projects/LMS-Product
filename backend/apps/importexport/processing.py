"""Turn imported rows into enquiries through the normal ingestion service.

Mapping targets (spec F4 step 2): standard fields and custom fields.
Dates are read as DD/MM/YYYY (optionally with HH:MM) in the workspace timezone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from django.utils.translation import gettext as _

from apps.accounts.models import Membership
from apps.customfields.models import CustomField
from apps.customfields.values import CustomValueError, coerce
from apps.enquiries.ingestion import EnquiryData
from apps.enquiries.models import Source
from apps.statuses.models import Status
from apps.tenants.models import DedupeKey, Tenant
from common.dates import parse_display_date
from common.phones import normalize_email, normalize_phone

STANDARD_TARGETS = (
    "name",
    "phone",
    "email",
    "status",
    "owner",
    "campaign",
    "adset",
    "ad",
    "form",
    "created_at",
)

# Header words that suggest a target (lower-case, spaces/underscores collapsed).
SUGGESTIONS = {
    "name": ["name", "full name", "fullname", "lead name", "customer name", "contact name"],
    "phone": [
        "phone",
        "phone number",
        "mobile",
        "mobile number",
        "contact number",
        "whatsapp",
        "number",
        "phone_number",
    ],
    "email": ["email", "e-mail", "email address", "mail"],
    "status": ["status", "stage", "lead status"],
    "owner": ["owner", "assigned to", "assignee", "agent", "sales person", "salesperson"],
    "campaign": ["campaign", "campaign name"],
    "adset": ["ad set", "adset", "ad set name", "adset name"],
    "ad": ["ad", "ad name"],
    "form": ["form", "form id", "form name"],
    "created_at": [
        "date",
        "created",
        "created at",
        "created on",
        "date added",
        "lead date",
        "enquiry date",
    ],
}


def _norm(text: str) -> str:
    return re.sub(r"[\s_]+", " ", text.strip().lower())


def suggest_mapping(headers: list[str], fields: list[CustomField]) -> dict[str, str]:
    """Best guess {header: target}; each target is used once."""
    by_word = {word: target for target, words in SUGGESTIONS.items() for word in words}
    for f in fields:
        by_word.setdefault(_norm(f.label), f"cf:{f.key}")
        by_word.setdefault(_norm(f.key), f"cf:{f.key}")
    mapping, used = {}, set()
    for header in headers:
        target = by_word.get(_norm(header))
        if target and target not in used:
            mapping[header] = target
            used.add(target)
    return mapping


@dataclass
class RowContext:
    """Everything needed to read rows, loaded once per import."""

    tenant: Tenant
    mapping: dict[str, str]
    fields: dict[str, CustomField] = field(default_factory=dict)
    statuses: dict[str, Status] = field(default_factory=dict)
    members_by_email: dict[str, int] = field(default_factory=dict)
    members_by_name: dict[str, int] = field(default_factory=dict)

    @classmethod
    def load(cls, tenant: Tenant, mapping: dict[str, str]) -> RowContext:
        ctx = cls(tenant=tenant, mapping=mapping)
        ctx.fields = {f.key: f for f in CustomField.objects.filter(tenant=tenant, is_active=True)}
        ctx.statuses = {s.name.lower(): s for s in Status.objects.filter(tenant=tenant)}
        for m in Membership.objects.filter(tenant=tenant, is_active=True).select_related("user"):
            ctx.members_by_email[m.user.email.lower()] = m.user_id
            ctx.members_by_name[m.user.full_name.strip().lower()] = m.user_id
        return ctx


def validate_mapping(
    mapping: dict[str, str], headers: list[str], fields: list[CustomField]
) -> dict:
    allowed = set(STANDARD_TARGETS) | {f"cf:{f.key}" for f in fields}
    errors = {}
    seen = set()
    for header, target in mapping.items():
        if header not in headers:
            errors[header] = [_("This column is not in the file.")]
        elif target not in allowed:
            errors[header] = [_("Unknown field.")]
        elif target in seen:
            errors[header] = [_("Two columns are mapped to the same field.")]
        seen.add(target)
    if not ({"phone", "email"} & seen):
        errors["mapping"] = [_("Map a column to Phone or Email so people can be matched.")]
    return errors


def _parse_created(value: str, tz: str) -> datetime:
    text = value.strip()
    time_part = None
    if " " in text:
        text, time_part = text.split(" ", 1)
    day = parse_display_date(text)  # ValueError if not DD/MM/YYYY
    hour, minute = 0, 0
    if time_part:
        match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?", time_part.strip())
        if not match:
            raise ValueError
        hour, minute = int(match[1]), int(match[2])
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo(tz))


def row_to_data(ctx: RowContext, row: dict[str, str]) -> tuple[EnquiryData | None, list[str]]:
    """Read one row. Returns (data, []) or (None, ["Field: problem", ...])."""
    values: dict[str, str] = {}
    for header, target in ctx.mapping.items():
        values[target] = (row.get(header) or "").strip()

    errors: list[str] = []
    data = EnquiryData(source=Source.IMPORT)
    data.name = values.get("name", "")[:200]
    data.phone = values.get("phone", "")[:50]
    data.email = values.get("email", "")[:254]
    data.campaign_name = values.get("campaign", "")[:255]
    data.adset_name = values.get("adset", "")[:255]
    data.ad_name = values.get("ad", "")[:255]
    data.form_id = values.get("form", "")[:64]

    if not data.phone and not data.email:
        errors.append(_("Phone or email is required."))
    if data.phone and normalize_phone(data.phone, ctx.tenant.default_country) is None:
        errors.append(_("Phone: not a valid phone number."))
    if data.email and (
        "@" not in data.email or normalize_email(data.email) is None or " " in data.email
    ):
        errors.append(_("Email: not a valid email address."))

    if status_name := values.get("status"):
        status = ctx.statuses.get(status_name.lower())
        if status is None:
            errors.append(_("Status: “%(s)s” does not exist.") % {"s": status_name})
        data.status = status
    if owner := values.get("owner"):
        owner_id = ctx.members_by_email.get(owner.lower()) or ctx.members_by_name.get(owner.lower())
        if owner_id is None:
            errors.append(_("Owner: “%(o)s” is not a member of this workspace.") % {"o": owner})
        data.primary_owner_id = owner_id
    if created := values.get("created_at"):
        try:
            data.created_at = _parse_created(created, ctx.tenant.timezone)
        except ValueError:
            errors.append(_("Date: use DD/MM/YYYY (optionally with HH:MM)."))

    custom: dict[Any, Any] = {}
    for target, raw in values.items():
        if not target.startswith("cf:") or raw == "":
            continue
        cf = ctx.fields.get(target[3:])
        if cf is None:
            continue
        try:
            custom[cf] = coerce(
                cf, [v.strip() for v in raw.split(",")] if cf.type == "multi_select" else raw
            )
        except CustomValueError as exc:
            errors.append(f"{cf.label}: {exc}")
    data.custom_values = custom
    return (None, errors) if errors else (data, [])


def match_key(ctx: RowContext, data: EnquiryData) -> tuple[str, str] | None:
    """The value used to find an existing contact, like ingestion does."""
    phone = normalize_phone(data.phone, ctx.tenant.default_country)
    email = normalize_email(data.email)
    order = (
        [("email_lower", email), ("phone_e164", phone)]
        if ctx.tenant.dedupe_key == DedupeKey.EMAIL
        else [("phone_e164", phone), ("email_lower", email)]
    )
    for column, value in order:
        if value:
            return column, value
    return None
