from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.crypto import decrypt, encrypt
from common.tenancy.models import TenantScopedModel


class ConnectionStatus(models.TextChoices):
    PENDING_PAGE = "pending_page", _("Choose a Page")
    CONNECTED = "connected", _("Connected")
    DISCONNECTED = "disconnected", _("Disconnected")


class MetaConnection(TenantScopedModel):
    """The workspace's link to Meta. Rules (spec 6, Meta connection rules):

    - one connection per workspace (unique tenant),
    - one Page per workspace (single page_id),
    - one Page can belong to only one workspace (unique page_id across all workspaces).
    """

    status = models.CharField(
        max_length=16, choices=ConnectionStatus.choices, default=ConnectionStatus.PENDING_PAGE
    )
    page_id = models.CharField(max_length=64, null=True, blank=True)
    page_name = models.CharField(max_length=255, blank=True)
    _user_token = models.TextField(db_column="user_token_enc", blank=True)
    _page_token = models.TextField(db_column="page_token_enc", blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    leads_access_ok = models.BooleanField(default=False)
    leads_access_error = models.CharField(max_length=500, blank=True)
    leads_access_checked_at = models.DateTimeField(null=True, blank=True)
    detect_ad_details = models.BooleanField(default=True)  # save campaign / ad set / ad names
    # Auto Sync: every form of the Page (also ones created later) is connected automatically.
    # Off: forms are switched on one by one.
    auto_connect_forms = models.BooleanField(default=True)
    last_backfill_at = models.DateTimeField(null=True, blank=True)
    # The browser asks for new leads about every minute; at most one check runs per minute.
    last_polled_at = models.DateTimeField(null=True, blank=True)
    # Conversions API for CRM: LMS statuses go back to Meta as lead-quality feedback.
    capi_enabled = models.BooleanField(default=False)
    capi_dataset_id = models.CharField(max_length=64, blank=True)
    _capi_token = models.TextField(db_column="capi_token_enc", blank=True)
    forms_refreshed_at = models.DateTimeField(null=True, blank=True)
    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    connected_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meta_connections"
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="uniq_meta_connection_tenant"),
            models.UniqueConstraint(
                fields=["page_id"], condition=Q(page_id__isnull=False), name="uniq_meta_page_global"
            ),
        ]

    # Tokens are only ever stored encrypted.
    @property
    def user_token(self) -> str:
        return decrypt(self._user_token)

    @user_token.setter
    def user_token(self, value: str) -> None:
        self._user_token = encrypt(value)

    @property
    def capi_token(self) -> str:
        return decrypt(self._capi_token)

    @capi_token.setter
    def capi_token(self, value: str) -> None:
        self._capi_token = encrypt(value)

    @property
    def page_token(self) -> str:
        return decrypt(self._page_token)

    @page_token.setter
    def page_token(self, value: str) -> None:
        self._page_token = encrypt(value)

    @property
    def token_state(self) -> str:
        """ok | expiring (within 7 days) | expired | none."""
        if not self._user_token:
            return "none"
        if self.token_expires_at is None:
            return "ok"  # long-lived page tokens do not expire
        left = self.token_expires_at - timezone.now()
        if left.total_seconds() <= 0:
            return "expired"
        return "expiring" if left.days < 7 else "ok"


class ConversionEvent(TenantScopedModel):
    """One lead-stage event sent to Meta's Conversions API (the log on the Meta page)."""

    enquiry = models.ForeignKey(
        "enquiries.Enquiry", null=True, on_delete=models.SET_NULL, related_name="+"
    )
    leadgen_id = models.CharField(max_length=64)
    event_name = models.CharField(max_length=100)  # the LMS status name
    success = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    test = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "meta_conversion_events"
        ordering = ["-sent_at"]


class MetaForm(TenantScopedModel):
    """An Instant Form of the connected Page. Only connected forms create enquiries."""

    form_id = models.CharField(max_length=64)
    page_id = models.CharField(max_length=64, blank=True)  # forms of other Pages are hidden
    name = models.CharField(max_length=255, blank=True)
    status_on_meta = models.CharField(max_length=20, blank=True)  # ACTIVE, ARCHIVED, ...
    created_time = models.DateTimeField(null=True, blank=True)
    questions = models.JSONField(default=list, blank=True)  # [{key, label, type}]
    is_connected = models.BooleanField(default=False)
    auto_call = models.BooleanField(default=False)  # Exotel calls each new lead at once
    connected_at = models.DateTimeField(null=True, blank=True)
    leads_received = models.PositiveIntegerField(default=0)
    last_lead_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "meta_forms"
        ordering = ["name", "id"]  # stable: switching a form on must not move it
        constraints = [models.UniqueConstraint(fields=["tenant", "form_id"], name="uniq_meta_form")]


class TargetType(models.TextChoices):
    NAME = "name", _("Name")
    PHONE = "phone", _("Phone")
    EMAIL = "email", _("Email")
    CUSTOM = "custom", _("Custom field")
    IGNORE = "ignore", _("Don't import")


class FormFieldMapping(TenantScopedModel):
    """Which LMS field a form question feeds. Many questions may feed one custom field."""

    form = models.ForeignKey(MetaForm, on_delete=models.CASCADE, related_name="mappings")
    question_name = models.CharField(max_length=255)
    target_type = models.CharField(max_length=10, choices=TargetType.choices)
    custom_field = models.ForeignKey(
        "customfields.CustomField",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )

    class Meta:
        db_table = "form_field_mappings"
        constraints = [
            models.UniqueConstraint(fields=["form", "question_name"], name="uniq_form_question")
        ]


class SyncStatus(models.TextChoices):
    SYNCED = "synced", _("Synced")
    DUPLICATE = "duplicate", _("Already synced")
    FORM_NOT_CONNECTED = "form_not_connected", _("Form not connected")
    # No longer produced (the campaign filter was removed); kept so older log rows still display.
    CAMPAIGN_NOT_SELECTED = "campaign_not_selected", _("Campaign not selected")
    RESTORED = "restored", _("Restored")  # deleted in the LMS, brought back by "Sync leads"
    FAILED = "failed", _("Failed")


class SyncSource(models.TextChoices):
    WEBHOOK = "webhook", _("Webhook")
    BACKFILL = "backfill", _("Backfill")
    RETRY = "retry", _("Retry")
    TEST = "test", _("Test")
    MANUAL = "manual", _("Sync now")  # the "Sync leads" button


class SyncLog(TenantScopedModel):
    """Lead sync history: one row per lead delivery."""

    leadgen_id = models.CharField(max_length=64)
    form_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=24, choices=SyncStatus.choices)
    source = models.CharField(max_length=10, choices=SyncSource.choices)
    enquiry = models.ForeignKey(
        "enquiries.Enquiry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "sync_logs"
        ordering = ["-created_at"]


class FailedSyncLog(TenantScopedModel):
    """A lead that could not be synced yet. Retry from the UI; backfill also retries."""

    leadgen_id = models.CharField(max_length=64)
    form_id = models.CharField(max_length=64, blank=True)
    page_id = models.CharField(max_length=64, blank=True)
    error = models.CharField(max_length=500)
    attempts = models.PositiveIntegerField(default=1)
    payload = models.JSONField(default=dict, blank=True)  # the webhook change value
    resolved_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "failed_sync_logs"
        ordering = ["-last_attempt_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "leadgen_id"], name="uniq_failed_sync_lead")
        ]
