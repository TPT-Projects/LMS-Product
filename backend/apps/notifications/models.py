from django.conf import settings
from django.db import models

from common.tenancy.models import TenantScopedModel


class Notification(TenantScopedModel):
    """In-app notification (bell). Used for finished imports; @mentions come later."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=500, blank=True)
    link = models.CharField(max_length=300, blank=True)  # app path, e.g. /imports/12
    data = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "user", "read_at", "created_at"], name="notif_user_idx")
        ]
