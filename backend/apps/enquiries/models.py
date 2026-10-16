import uuid
from pathlib import PurePath

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models import Q
from django.db.models.functions import Upper
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.tenancy.models import TenantQuerySet, TenantScopedModel

User = settings.AUTH_USER_MODEL


class Source(models.TextChoices):
    MANUAL = "manual", _("Manual")
    META = "meta", _("Meta")
    IMPORT = "import", _("Import")
    GOOGLE_SHEETS = "sheets", _("Google Sheets")


class EnquiryQuerySet(TenantQuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class Enquiry(TenantScopedModel):
    """One submission or request from a Contact. The module the team works in."""

    contact = models.ForeignKey(
        "contacts.Contact", on_delete=models.PROTECT, related_name="enquiries"
    )
    # Meta's lead id: the idempotency key for ingestion (unique per workspace).
    leadgen_id = models.CharField(max_length=64, null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    campaign_name = models.CharField(max_length=255, blank=True)
    adset_name = models.CharField(max_length=255, blank=True)
    ad_name = models.CharField(max_length=255, blank=True)
    form_id = models.CharField(max_length=64, blank=True)

    status = models.ForeignKey("statuses.Status", on_delete=models.PROTECT, related_name="+")
    primary_owner = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_repeat = models.BooleanField(default=False)

    # What this enquiry submitted (the Contact may hold different, older values).
    name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=50, blank=True)  # as submitted
    phone_e164 = models.CharField(max_length=20, blank=True)
    email = models.CharField(max_length=254, blank=True)

    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = EnquiryQuerySet.as_manager()

    class Meta:
        db_table = "enquiries"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "leadgen_id"],
                condition=Q(leadgen_id__isnull=False),
                name="uniq_enquiry_leadgen",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "deleted_at", "created_at"], name="enq_list_idx"),
            models.Index(fields=["tenant", "status"], name="enq_status_idx"),
            models.Index(fields=["tenant", "primary_owner"], name="enq_owner_idx"),
            models.Index(fields=["tenant", "campaign_name"], name="enq_campaign_idx"),
            models.Index(fields=["tenant", "form_id"], name="enq_form_idx"),
            models.Index(fields=["tenant", "phone_e164"], name="enq_phone_idx"),
            GinIndex(OpClass(Upper("name"), name="gin_trgm_ops"), name="enq_name_trgm"),
            GinIndex(OpClass(Upper("email"), name="gin_trgm_ops"), name="enq_email_trgm"),
            GinIndex(
                OpClass(Upper("campaign_name"), name="gin_trgm_ops"), name="enq_campaign_trgm"
            ),
        ]

    def __str__(self) -> str:
        return self.name or f"Enquiry {self.pk}"


class EnquiryOwner(TenantScopedModel):
    """Secondary owners (the primary owner is on the enquiry)."""

    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="secondary_owners")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")

    class Meta:
        db_table = "enquiry_owners"
        constraints = [
            models.UniqueConstraint(fields=["enquiry", "user"], name="uniq_enquiry_owner")
        ]
        indexes = [models.Index(fields=["tenant", "user"], name="enq_owner_user_idx")]


class StatusHistory(TenantScopedModel):
    """Every status change. Kept in PostgreSQL because the conversion report needs it."""

    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.ForeignKey(
        "statuses.Status", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    to_status = models.ForeignKey("statuses.Status", on_delete=models.PROTECT, related_name="+")
    changed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "status_history"
        indexes = [
            models.Index(fields=["tenant", "to_status", "changed_at"], name="status_hist_idx")
        ]


def note_audio_path(instance: "Note", filename: str) -> str:
    ext = PurePath(filename).suffix.lower()[:8] or ".webm"
    folder = f"tenants/{instance.tenant_id}/enquiries/{instance.enquiry_id}/voice"
    return f"{folder}/{uuid.uuid4().hex}{ext}"


class Note(TenantScopedModel):
    """A text note, a voice note, or both (text can describe the recording)."""

    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="notes")
    body = models.TextField(blank=True)
    audio = models.FileField(upload_to=note_audio_path, max_length=500, blank=True)
    audio_content_type = models.CharField(max_length=60, blank=True)
    audio_duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    author = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notes"
        ordering = ["-created_at"]


class FollowUp(TenantScopedModel):
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="followups")
    title = models.CharField(max_length=200)
    due_at = models.DateTimeField()
    assignee = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "followups"
        ordering = ["done_at", "due_at"]
        indexes = [
            models.Index(
                fields=["tenant", "assignee", "done_at", "due_at"], name="followup_due_idx"
            ),
            models.Index(fields=["tenant", "done_at", "due_at"], name="followup_open_idx"),
        ]

    @property
    def is_done(self) -> bool:
        return self.done_at is not None


class CallOutcome(models.TextChoices):
    CONNECTED = "connected", _("Connected")
    NO_ANSWER = "no_answer", _("No answer")
    BUSY = "busy", _("Busy")
    CALLBACK = "callback_requested", _("Call back later")
    NOT_INTERESTED = "not_interested", _("Not interested")
    WRONG_NUMBER = "wrong_number", _("Wrong number")


class CallLog(TenantScopedModel):
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="calls")
    outcome = models.CharField(max_length=24, choices=CallOutcome.choices)
    duration_seconds = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    called_at = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    # Set later by an auto-calling integration (spec: keep a nullable provider column).
    provider = models.CharField(max_length=32, null=True, blank=True)

    class Meta:
        db_table = "call_logs"
        ordering = ["-called_at"]


def attachment_path(instance: "Attachment", filename: str) -> str:
    safe = PurePath(filename).name[-120:] or "file"
    return f"tenants/{instance.tenant_id}/enquiries/{instance.enquiry_id}/{uuid.uuid4().hex}/{safe}"


class Attachment(TenantScopedModel):
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=attachment_path, max_length=500)
    file_name = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    content_type = models.CharField(max_length=120)
    uploaded_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attachments"
        ordering = ["-created_at"]
