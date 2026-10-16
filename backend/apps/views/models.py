from django.conf import settings
from django.db import models

from common.tenancy.models import TenantScopedModel


class SavedView(TenantScopedModel):
    """A named enquiry filter. Private to its owner unless shared with the workspace."""

    name = models.CharField(max_length=80)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    # Same JSON the list endpoint accepts: {"filter": <tree>, "sort": "...", "q": "..."}
    filters = models.JSONField(default=dict, blank=True)
    sort = models.CharField(max_length=40, default="-created_at")
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "saved_views"
        ordering = ["name"]
        indexes = [models.Index(fields=["tenant", "owner"], name="saved_view_owner_idx")]

    def __str__(self) -> str:
        return self.name


class ViewPin(TenantScopedModel):
    """A user pinned a view to their sidebar (pins are per user)."""

    view = models.ForeignKey(SavedView, on_delete=models.CASCADE, related_name="pins")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")

    class Meta:
        db_table = "saved_view_pins"
        constraints = [models.UniqueConstraint(fields=["view", "user"], name="uniq_view_pin")]
