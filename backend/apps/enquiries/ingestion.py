"""Enquiry ingestion: one entry point for manual entry, imports and Meta leads.

Rules (spec section 6, "Contact and Enquiry"):
1. Contacts are matched per workspace by the dedupe key: phone (E.164) by default,
   or email. If the key value is missing, fall back to the other one.
2. Match found: reuse the Contact, create a new Enquiry marked Repeat.
3. Contact info differs: only fill EMPTY contact fields, never overwrite, and log
   `contact_information_updated`. Each Enquiry keeps its own submitted copy.
4. No phone and no email: still create the Enquiry, with a Contact that is never merged.
5. Concurrent requests for the same person cannot create two Contacts: the unique
   partial index rejects the second insert and we re-read the winner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.db import IntegrityError, transaction

from apps.activity.service import ActivityType, record
from apps.contacts.models import Contact
from apps.customfields import services as custom_fields
from apps.statuses.models import Status, default_status
from apps.tenants.models import DedupeKey, Tenant
from common.phones import normalize_email, normalize_phone

from .models import Enquiry, EnquiryOwner, Source, StatusHistory


@dataclass
class EnquiryData:
    name: str = ""
    phone: str = ""
    email: str = ""
    source: str = Source.MANUAL
    campaign_name: str = ""
    adset_name: str = ""
    ad_name: str = ""
    form_id: str = ""
    leadgen_id: str | None = None
    status: Status | None = None
    primary_owner_id: int | None = None
    secondary_owner_ids: list[int] = field(default_factory=list)
    custom_values: dict[Any, Any] = field(default_factory=dict)  # {CustomField: clean value}
    created_at: datetime | None = None
    # Extra facts for the "enquiry created" timeline entry (e.g. import job, Meta form).
    extra_details: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestResult:
    enquiry: Enquiry
    contact: Contact
    is_repeat: bool
    contact_updates: dict[str, str]


def _match_keys(tenant: Tenant, phone: str | None, email: str | None) -> list[tuple[str, str]]:
    """Lookup order, e.g. [("phone_e164", "+91..."), ("email_lower", "a@b.c")]."""
    by_phone = ("phone_e164", phone) if phone else None
    by_email = ("email_lower", email) if email else None
    ordered = [by_email, by_phone] if tenant.dedupe_key == DedupeKey.EMAIL else [by_phone, by_email]
    return [key for key in ordered if key]


def _find_contact(tenant: Tenant, keys: list[tuple[str, str]]) -> Contact | None:
    # Only the primary key decides a match. The fallback is used when the primary value is missing.
    if not keys:
        return None
    column, value = keys[0]
    return (
        Contact.objects.select_for_update()
        .filter(tenant=tenant, deleted_at__isnull=True, **{column: value})
        .first()
    )


def _taken(tenant: Tenant, column: str, value: str | None, exclude_pk: int | None = None) -> bool:
    if not value:
        return False
    qs = Contact.objects.filter(tenant=tenant, deleted_at__isnull=True, **{column: value})
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def _get_or_create_contact(
    tenant: Tenant, name: str, phone_raw: str, phone: str | None, email: str | None
) -> tuple[Contact, bool]:
    keys = _match_keys(tenant, phone, email)
    contact = _find_contact(tenant, keys)
    if contact:
        return contact, False

    # A value already used by another contact cannot be stored again (unique index):
    # the new contact simply goes without it. The enquiry still keeps it.
    values = {
        "name": name,
        "phone_raw": phone_raw,
        "phone_e164": None if _taken(tenant, "phone_e164", phone) else phone,
        "email_lower": None if _taken(tenant, "email_lower", email) else email,
    }
    try:
        with transaction.atomic():
            return Contact.objects.create(tenant=tenant, **values), True
    except IntegrityError:
        # Another request created the same person a moment ago: use it.
        contact = _find_contact(tenant, keys)
        if contact is None:
            raise
        return contact, False


def _fill_empty_fields(
    contact: Contact, name: str, phone_raw: str, phone: str | None, email: str | None
) -> dict[str, str]:
    updates: dict[str, str] = {}
    if not contact.name and name:
        updates["name"] = name
    if not contact.phone_e164 and phone and not _taken(contact.tenant, "phone_e164", phone):
        updates["phone_e164"] = phone
        updates["phone_raw"] = phone_raw
    if not contact.email_lower and email and not _taken(contact.tenant, "email_lower", email):
        updates["email_lower"] = email
    if updates:
        for key, value in updates.items():
            setattr(contact, key, value)
        contact.save(update_fields=[*updates.keys(), "updated_at"])
    return updates


@transaction.atomic
def ingest_enquiry(*, tenant: Tenant, data: EnquiryData, actor=None) -> IngestResult:
    name = (data.name or "").strip()  # junk names exist: trim only, never validate strictly
    phone_raw = (data.phone or "").strip()
    phone = normalize_phone(phone_raw, tenant.default_country)
    email = normalize_email(data.email)

    contact, created = _get_or_create_contact(tenant, name, phone_raw, phone, email)
    is_repeat = not created
    contact_updates = (
        _fill_empty_fields(contact, name, phone_raw, phone, email) if is_repeat else {}
    )

    status = data.status or default_status(tenant.pk)
    enquiry = Enquiry.objects.create(
        tenant=tenant,
        contact=contact,
        leadgen_id=data.leadgen_id or None,
        source=data.source,
        campaign_name=data.campaign_name.strip(),
        adset_name=data.adset_name.strip(),
        ad_name=data.ad_name.strip(),
        form_id=data.form_id.strip(),
        status=status,
        primary_owner_id=data.primary_owner_id,
        is_repeat=is_repeat,
        name=name,
        phone=phone_raw,
        phone_e164=phone or "",
        email=email or "",
        created_by=actor,
        **({"created_at": data.created_at} if data.created_at else {}),
    )
    owner_ids = {uid for uid in data.secondary_owner_ids if uid != data.primary_owner_id}
    EnquiryOwner.objects.bulk_create(
        EnquiryOwner(tenant=tenant, enquiry=enquiry, user_id=uid) for uid in owner_ids
    )
    StatusHistory.objects.create(
        tenant=tenant, enquiry=enquiry, from_status=None, to_status=status, changed_by=actor
    )
    custom_fields.save_values(enquiry, data.custom_values)

    ids = {"tenant_id": tenant.pk, "enquiry_id": enquiry.pk, "contact_id": contact.pk}
    record(
        **ids,
        type=ActivityType.ENQUIRY_CREATED,
        actor=actor,
        details={
            "source": enquiry.source,
            "status": status.name,
            "is_repeat": is_repeat,
            **data.extra_details,
        },
    )
    if is_repeat:
        previous = contact.enquiries.exclude(pk=enquiry.pk).filter(deleted_at__isnull=True)
        record(
            **ids,
            type=ActivityType.REPEAT_ENQUIRY,
            actor=actor,
            details={"previous_enquiries": previous.count()},
        )
    if contact_updates:
        record(
            **ids,
            type=ActivityType.CONTACT_UPDATED,
            actor=actor,
            details={"filled": sorted(k for k in contact_updates if k != "phone_raw")},
        )
    return IngestResult(enquiry, contact, is_repeat, contact_updates)
