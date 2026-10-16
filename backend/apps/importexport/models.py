import uuid
from pathlib import PurePath

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.tenancy.models import TenantScopedModel


def import_path(instance: "ImportJob", filename: str) -> str:
    ext = PurePath(filename).suffix.lower()[:6]
    return f"tenants/{instance.tenant_id}/imports/{uuid.uuid4().hex}{ext}"


class ImportStatus(models.TextChoices):
    UPLOADED = "uploaded", _("Uploaded")
    MAPPED = "mapped", _("Mapped")
    QUEUED = "queued", _("Queued")
    RUNNING = "running", _("Running")
    COMPLETED = "completed", _("Completed")
    COMPLETED_WITH_ERRORS = "completed_with_errors", _("Completed with errors")
    FAILED = "failed", _("Failed")


class ImportMode(models.TextChoices):
    LIVE = "live", _("Live")
    BACKGROUND = "background", _("Background")


class ImportJob(TenantScopedModel):
    """One uploaded file and its journey: upload -> map -> preview -> run -> log."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    file = models.FileField(upload_to=import_path, max_length=500)
    original_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=8)  # csv | xlsx
    headers = models.JSONField(default=list)
    row_count = models.PositiveIntegerField(default=0)
    # {"<column header>": "name" | "phone" | ... | "cf:<key>"}; unmapped columns are left out.
    mapping = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=24, choices=ImportStatus.choices, default=ImportStatus.UPLOADED
    )
    mode = models.CharField(max_length=12, choices=ImportMode.choices, blank=True)
    processed_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)  # new contacts
    linked_count = models.PositiveIntegerField(default=0)  # added to existing contacts (repeat)
    failed_count = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "import_jobs"
        ordering = ["-created_at"]

    @property
    def is_finished(self) -> bool:
        return self.status in (
            ImportStatus.COMPLETED,
            ImportStatus.COMPLETED_WITH_ERRORS,
            ImportStatus.FAILED,
        )


class ImportRowFailed(TenantScopedModel):
    """A row that could not be imported, with the reasons. Downloadable as a fix-up CSV."""

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="failed_rows")
    row_number = models.PositiveIntegerField()  # 1-based, as in the spreadsheet (after header)
    data = models.JSONField(default=dict)  # the original row: {header: value}
    errors = models.JSONField(default=list)  # ["Phone: Enter a valid phone number.", ...]

    class Meta:
        db_table = "import_rows_failed"
        ordering = ["row_number"]
