import json

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.crypto import decrypt, encrypt
from common.tenancy.models import TenantScopedModel


class IntegrationStatus(models.TextChoices):
    CONNECTED = "connected", _("Connected")
    ERROR = "error", _("Needs attention")  # the last check failed


class Integration(TenantScopedModel):
    """One connected app (WhatsApp, Exotel, ...) of a workspace. Meta has its own model."""

    app = models.CharField(max_length=32)
    status = models.CharField(
        max_length=16, choices=IntegrationStatus.choices, default=IntegrationStatus.CONNECTED
    )
    config = models.JSONField(default=dict, blank=True)  # non-secret values
    _secrets = models.TextField(db_column="secrets_enc", blank=True)  # encrypted JSON
    account_label = models.CharField(max_length=255, blank=True)
    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    connected_at = models.DateTimeField(default=timezone.now)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    # App settings chosen on its Manage page (default caller ID, auto-calling rules, ...).
    settings = models.JSONField(default=dict, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)  # last refresh of numbers / accounts

    class Meta:
        db_table = "integrations"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "app"], name="uniq_integration_per_app")
        ]

    def __str__(self) -> str:
        return f"{self.app} ({self.tenant_id})"

    @property
    def secrets(self) -> dict[str, str]:
        raw = decrypt(self._secrets)
        return json.loads(raw) if raw else {}

    @secrets.setter
    def secrets(self, value: dict[str, str]) -> None:
        self._secrets = encrypt(json.dumps(value)) if value else ""

    def values(self) -> dict[str, str]:
        return {**self.config, **self.secrets}


class ExotelNumber(TenantScopedModel):
    """An ExoPhone (virtual number) of the connected Exotel account."""

    phone_number = models.CharField(max_length=20)  # E.164 as Exotel returns it
    sid = models.CharField(max_length=64, blank=True)
    friendly_name = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=4, blank=True)
    capabilities = models.JSONField(default=dict, blank=True)  # {"voice": true, "sms": true}
    added_manually = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)  # still listed by Exotel
    active_since = models.DateTimeField(default=timezone.now)  # first seen (stored in UTC)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "exotel_numbers"
        ordering = ["phone_number"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "phone_number"], name="uniq_exotel_number")
        ]


class AutoCallReason(models.TextChoices):
    NEW_LEAD = "new_lead", _("New lead")
    FOLLOWUP = "followup", _("Scheduled call")
    STATUS = "status", _("Status changed")


class AutoCallStatus(models.TextChoices):
    PENDING = "pending", _("Scheduled")
    STARTED = "started", _("Calling")
    COMPLETED = "completed", _("Completed")
    NO_ANSWER = "no_answer", _("No answer")
    BUSY = "busy", _("Busy")
    FAILED = "failed", _("Failed")
    SKIPPED = "skipped", _("Skipped")
    CANCELLED = "cancelled", _("Cancelled")


class AutoCall(TenantScopedModel):
    """A call Exotel places automatically: it rings the agent first, then the lead."""

    enquiry = models.ForeignKey(
        "enquiries.Enquiry", on_delete=models.CASCADE, related_name="auto_calls"
    )
    followup = models.OneToOneField(
        "enquiries.FollowUp",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="auto_call",
    )
    reason = models.CharField(max_length=12, choices=AutoCallReason.choices)
    status = models.CharField(
        max_length=12, choices=AutoCallStatus.choices, default=AutoCallStatus.PENDING
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    agent_phone = models.CharField(max_length=20, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    caller_id = models.CharField(max_length=20, blank=True)
    scheduled_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    call_sid = models.CharField(max_length=64, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auto_calls"
        ordering = ["-scheduled_at"]
        indexes = [models.Index(fields=["status", "scheduled_at"], name="auto_call_due_idx")]


class SheetDirection(models.TextChoices):
    IMPORT = "import", _("Rows become enquiries")
    EXPORT = "export", _("Enquiries are written to the sheet")


class SheetLink(TenantScopedModel):
    """A Google Sheet tab linked to the LMS.

    import: its rows become enquiries (new rows picked up every 5 minutes).
    export: the enquiries of a Meta form (or all) are written to it and kept up to date
    (new leads, status, owner and other changes), about every minute.
    """

    direction = models.CharField(
        max_length=8, choices=SheetDirection.choices, default=SheetDirection.IMPORT
    )
    form = models.ForeignKey(  # export: only this form's leads (empty = every enquiry)
        "meta_integration.MetaForm",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    content_hash = models.CharField(max_length=64, blank=True)  # export: last written content
    spreadsheet_id = models.CharField(max_length=128)
    spreadsheet_name = models.CharField(max_length=255, blank=True)
    sheet_title = models.CharField(max_length=255)
    headers = models.JSONField(default=list, blank=True)
    # {"name": "Full name", "phone": "Mobile", "email": "Email"}: header used for each field
    mapping = models.JSONField(default=dict, blank=True)
    last_row = models.PositiveIntegerField(default=1)  # rows up to here are imported (1 = header)
    rows_imported = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sheet_links"
        ordering = ["spreadsheet_name", "sheet_title"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "spreadsheet_id", "sheet_title"], name="uniq_sheet_link"
            )
        ]
