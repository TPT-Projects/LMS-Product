"""Business rules for working an enquiry. Views validate input and call these."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Membership, User
from apps.activity.service import ActivityType, record
from apps.customfields import services as custom_fields
from apps.integrations import autocall
from apps.permissions.matrix import has_capability
from apps.permissions.roles import Capability
from apps.statuses.models import Status

from .models import Attachment, CallLog, Enquiry, EnquiryOwner, FollowUp, Note, StatusHistory

# Standard fields that may be edited after creation (phone is locked: spec 6.6).
EDITABLE_FIELDS = ("name", "email", "campaign_name", "adset_name", "ad_name")


def _ids(enquiry: Enquiry) -> dict[str, int]:
    return {
        "tenant_id": enquiry.tenant_id,
        "enquiry_id": enquiry.pk,
        "contact_id": enquiry.contact_id,
    }


def can(membership: Membership, capability: Capability) -> bool:
    return has_capability(membership.role, capability)


def require(membership: Membership, capability: Capability) -> None:
    if not can(membership, capability):
        raise PermissionDenied(_("You do not have permission to do this."))


def check_members(tenant_id: int, user_ids) -> None:
    ids = {uid for uid in user_ids if uid is not None}
    if not ids:
        return
    found = set(
        Membership.objects.filter(tenant_id=tenant_id, user_id__in=ids, is_active=True).values_list(
            "user_id", flat=True
        )
    )
    if missing := ids - found:
        raise ValidationError(
            {"owners": [_("Not members of this workspace: %s") % sorted(missing)]}
        )


def get_status(tenant_id: int, status_id: int | None) -> Status | None:
    if status_id is None:
        return None
    status = Status.objects.filter(tenant_id=tenant_id, pk=status_id).first()
    if status is None:
        raise ValidationError({"status_id": [_("Unknown status.")]})
    return status


# --- owners --------------------------------------------------------------------
def resolve_new_owner(membership: Membership, requested: int | None, provided: bool) -> int | None:
    """Owner for a manually created enquiry.

    People who can reassign choose freely. Everyone else becomes the owner,
    otherwise an Agent could create an enquiry they are not allowed to see.
    """
    if can(membership, Capability.REASSIGN_OWNERS):
        return requested if provided else None
    if provided and requested not in (None, membership.user_id):
        raise PermissionDenied(_("You cannot assign enquiries to other people."))
    return membership.user_id


def _set_secondary_owners(enquiry: Enquiry, user_ids: list[int]) -> tuple[list, list]:
    wanted = {uid for uid in user_ids if uid != enquiry.primary_owner_id}
    current = set(enquiry.secondary_owners.values_list("user_id", flat=True))
    removed, added = current - wanted, wanted - current
    EnquiryOwner.objects.filter(enquiry=enquiry, user_id__in=removed).delete()
    EnquiryOwner.objects.bulk_create(
        EnquiryOwner(tenant_id=enquiry.tenant_id, enquiry=enquiry, user_id=uid) for uid in added
    )
    return sorted(added), sorted(removed)


def _user_name(user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = User.objects.filter(pk=user_id).only("full_name").first()
    return user.full_name if user else None


# --- update ----------------------------------------------------------------------
@transaction.atomic
def update_enquiry(*, enquiry: Enquiry, membership: Membership, data: dict[str, Any]) -> Enquiry:
    require(membership, Capability.EDIT_ENQUIRIES)
    actor = membership.user
    enquiry = Enquiry.objects.select_for_update().get(pk=enquiry.pk)
    ids = _ids(enquiry)

    # Plain fields
    changes = []
    for name in EDITABLE_FIELDS:
        if name in data and data[name] != getattr(enquiry, name):
            changes.append({"field": name, "from": getattr(enquiry, name), "to": data[name]})
            setattr(enquiry, name, data[name])

    # Status
    new_status = get_status(enquiry.tenant_id, data.get("status_id"))
    old_status = enquiry.status
    status_changed = new_status is not None and new_status.pk != enquiry.status_id
    if status_changed:
        enquiry.status = new_status

    # Owners
    owner_changed = False
    if "primary_owner_id" in data and data["primary_owner_id"] != enquiry.primary_owner_id:
        require(membership, Capability.REASSIGN_OWNERS)
        check_members(enquiry.tenant_id, [data["primary_owner_id"]])
        old_owner = enquiry.primary_owner_id
        enquiry.primary_owner_id = data["primary_owner_id"]
        owner_changed = True
        # The new primary owner is no longer also a secondary owner.
        EnquiryOwner.objects.filter(enquiry=enquiry, user_id=enquiry.primary_owner_id).delete()

    enquiry.save()

    if status_changed:
        StatusHistory.objects.create(
            tenant_id=enquiry.tenant_id,
            enquiry=enquiry,
            from_status=old_status,
            to_status=new_status,
            changed_by=actor,
        )
        record(
            **ids,
            type=ActivityType.STATUS_CHANGED,
            actor=actor,
            details={"from": old_status.name, "to": new_status.name},
        )
        if enquiry.leadgen_id:  # Meta lead: tell Meta (Conversions API) how it is going
            from apps.meta_integration import capi

            capi.send_after_commit(enquiry.pk, enquiry.tenant_id, new_status.name)
    if owner_changed:
        record(
            **ids,
            type=ActivityType.ASSIGNMENT_CHANGED,
            actor=actor,
            details={"from": _user_name(old_owner), "to": _user_name(enquiry.primary_owner_id)},
        )
    if "secondary_owner_ids" in data:
        require(membership, Capability.REASSIGN_OWNERS)
        check_members(enquiry.tenant_id, data["secondary_owner_ids"])
        added, removed = _set_secondary_owners(enquiry, data["secondary_owner_ids"])
        if added or removed:
            record(
                **ids,
                type=ActivityType.ASSIGNMENT_CHANGED,
                actor=actor,
                details={
                    "secondary_added": [_user_name(u) for u in added],
                    "secondary_removed": [_user_name(u) for u in removed],
                },
            )
    if "custom_fields" in data:
        values = custom_fields.validate_values(enquiry.tenant_id, data["custom_fields"])
        changes += custom_fields.save_values(enquiry, values)
    if changes:
        record(**ids, type=ActivityType.FIELD_CHANGED, actor=actor, details={"changes": changes})
    return enquiry


# --- delete ---------------------------------------------------------------------
@transaction.atomic
def soft_delete(*, enquiry: Enquiry, membership: Membership) -> None:
    """Soft delete. When a Contact has no enquiries left, it is soft-deleted too (spec 6.7)."""
    require(membership, Capability.DELETE_ENQUIRIES)
    now = timezone.now()
    Enquiry.objects.filter(pk=enquiry.pk).update(deleted_at=now)
    contact = enquiry.contact
    if not contact.enquiries.filter(deleted_at__isnull=True).exists():
        contact.deleted_at = now
        contact.save(update_fields=["deleted_at", "updated_at"])
    record(**_ids(enquiry), type=ActivityType.ENQUIRY_DELETED, actor=membership.user)


# --- work items --------------------------------------------------------------------
def _check_voice(audio, duration: int | None) -> str:
    content_type = (audio.content_type or "").split(";")[0].strip().lower()
    if content_type not in settings.VOICE_NOTE_ALLOWED_TYPES:
        raise ValidationError({"audio": [_("This audio format is not supported.")]})
    if audio.size > settings.VOICE_NOTE_MAX_BYTES:
        raise ValidationError({"audio": [_("The recording is too large.")]})
    if duration is not None and duration > settings.VOICE_NOTE_MAX_SECONDS:
        minutes = settings.VOICE_NOTE_MAX_SECONDS // 60
        raise ValidationError(
            {"audio": [_("Recordings can be at most %(m)s minutes.") % {"m": minutes}]}
        )
    return content_type


def add_note(
    *,
    enquiry: Enquiry,
    membership: Membership,
    body: str = "",
    audio=None,
    audio_duration_seconds: int | None = None,
) -> Note:
    """A text note, a voice note (audio upload), or both."""
    require(membership, Capability.EDIT_ENQUIRIES)
    body = (body or "").strip()
    if not body and audio is None:
        raise ValidationError({"body": [_("Write a note or record a voice note.")]})
    note = Note(tenant_id=enquiry.tenant_id, enquiry=enquiry, body=body, author=membership.user)
    if audio is not None:
        note.audio_content_type = _check_voice(audio, audio_duration_seconds)
        note.audio_duration_seconds = audio_duration_seconds
        note.audio.save(audio.name or "voice.webm", audio, save=False)
    note.save()
    record(
        **_ids(enquiry),
        type=ActivityType.NOTE_ADDED,
        actor=membership.user,
        details={
            "note_id": note.pk,
            "preview": body[:140],
            "voice": bool(note.audio),
            "duration_seconds": note.audio_duration_seconds,
        },
    )
    return note


def log_call(*, enquiry: Enquiry, membership: Membership, data: dict[str, Any]) -> CallLog:
    require(membership, Capability.EDIT_ENQUIRIES)
    call = CallLog.objects.create(
        tenant_id=enquiry.tenant_id, enquiry=enquiry, user=membership.user, **data
    )
    record(
        **_ids(enquiry),
        type=ActivityType.CALL_LOGGED,
        actor=membership.user,
        details={
            "call_id": call.pk,
            "outcome": call.outcome,
            "duration_seconds": call.duration_seconds,
            "notes": call.notes[:140],
        },
    )
    return call


def schedule_followup(
    *, enquiry: Enquiry, membership: Membership, data: dict[str, Any]
) -> FollowUp:
    require(membership, Capability.EDIT_ENQUIRIES)
    # Default: the lead's owner (else the person scheduling); anyone can pick someone else.
    assignee_id = data.get("assignee_id") or enquiry.primary_owner_id or membership.user_id
    if assignee_id != membership.user_id:
        check_members(enquiry.tenant_id, [assignee_id])
    followup = FollowUp.objects.create(
        tenant_id=enquiry.tenant_id,
        enquiry=enquiry,
        title=data["title"],
        due_at=data["due_at"],
        assignee_id=assignee_id,
        created_by=membership.user,
    )
    record(
        **_ids(enquiry),
        type=ActivityType.FOLLOWUP_SCHEDULED,
        actor=membership.user,
        details={
            "followup_id": followup.pk,
            "title": followup.title,
            "due_at": followup.due_at.isoformat(),
            "assignee": _user_name(assignee_id),
        },
    )
    # Exotel: call at the scheduled time (unless turned off for this call)
    autocall.on_followup_scheduled(followup, auto_call=data.get("auto_call", True))
    return followup


def set_followup_done(*, followup: FollowUp, membership: Membership, done: bool) -> FollowUp:
    require(membership, Capability.EDIT_ENQUIRIES)
    if done and followup.done_at is None:
        followup.done_at, followup.done_by = timezone.now(), membership.user
        followup.save(update_fields=["done_at", "done_by"])
        record(
            **_ids(followup.enquiry),
            type=ActivityType.FOLLOWUP_COMPLETED,
            actor=membership.user,
            details={"followup_id": followup.pk, "title": followup.title},
        )
        autocall.on_followup_done(followup)
    elif not done and followup.done_at is not None:
        followup.done_at, followup.done_by = None, None
        followup.save(update_fields=["done_at", "done_by"])
    return followup


def reschedule_followup(*, followup: FollowUp, membership: Membership, due_at) -> FollowUp:
    """New time for a scheduled call (e.g. after "Call not connected"). Auto-calls again then."""
    require(membership, Capability.EDIT_ENQUIRIES)
    followup.due_at = due_at
    followup.done_at = followup.done_by = None
    followup.save(update_fields=["due_at", "done_at", "done_by"])
    record(
        **_ids(followup.enquiry),
        type=ActivityType.FOLLOWUP_SCHEDULED,
        actor=membership.user,
        details={
            "followup_id": followup.pk,
            "title": followup.title,
            "due_at": due_at.isoformat(),
            "assignee": _user_name(followup.assignee_id),
            "rescheduled": True,
        },
    )
    autocall.on_followup_rescheduled(followup)
    return followup


def set_followup_auto_call(*, followup: FollowUp, membership: Membership, enabled: bool) -> None:
    require(membership, Capability.EDIT_ENQUIRIES)
    autocall.set_followup_auto_call(followup, enabled)


def add_attachment(*, enquiry: Enquiry, membership: Membership, upload) -> Attachment:
    require(membership, Capability.EDIT_ENQUIRIES)
    if upload.size > settings.ATTACHMENT_MAX_BYTES:
        mb = settings.ATTACHMENT_MAX_BYTES // (1024 * 1024)
        raise ValidationError({"file": [_("Files can be at most %(mb)s MB.") % {"mb": mb}]})
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type not in settings.ATTACHMENT_ALLOWED_TYPES:
        raise ValidationError({"file": [_("This file type is not allowed.")]})
    attachment = Attachment(
        tenant_id=enquiry.tenant_id,
        enquiry=enquiry,
        file_name=upload.name[:255],
        size=upload.size,
        content_type=content_type,
        uploaded_by=membership.user,
    )
    attachment.file.save(upload.name, upload, save=False)
    attachment.save()
    record(
        **_ids(enquiry),
        type=ActivityType.ATTACHMENT_ADDED,
        actor=membership.user,
        details={"attachment_id": attachment.pk, "file_name": attachment.file_name},
    )
    return attachment


# --- bulk actions ------------------------------------------------------------------
BULK_ACTIONS = ("set_status", "assign", "add_secondary_owner", "delete")


def bulk_action(
    *, enquiries: list[Enquiry], membership: Membership, action: str, value: Any
) -> int:
    """Applies one action to many visible enquiries. Each change is logged like a single edit."""
    if action == "set_status":
        status = get_status(membership.tenant_id, value)
        for enquiry in enquiries:
            update_enquiry(enquiry=enquiry, membership=membership, data={"status_id": status.pk})
    elif action == "assign":
        require(membership, Capability.REASSIGN_OWNERS)
        check_members(membership.tenant_id, [value])
        for enquiry in enquiries:
            update_enquiry(enquiry=enquiry, membership=membership, data={"primary_owner_id": value})
    elif action == "add_secondary_owner":
        require(membership, Capability.REASSIGN_OWNERS)
        check_members(membership.tenant_id, [value])
        for enquiry in enquiries:
            current = list(enquiry.secondary_owners.values_list("user_id", flat=True))
            if value not in current and value != enquiry.primary_owner_id:
                update_enquiry(
                    enquiry=enquiry,
                    membership=membership,
                    data={"secondary_owner_ids": [*current, value]},
                )
    elif action == "delete":
        require(membership, Capability.DELETE_ENQUIRIES)
        for enquiry in enquiries:
            soft_delete(enquiry=enquiry, membership=membership)
    else:
        raise ValidationError({"action": [_("Unknown action.")]})
    return len(enquiries)
