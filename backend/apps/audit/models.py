from django.conf import settings
from django.db import models

from common.tenancy.models import TenantScopedModel


class AuditLog(TenantScopedModel):
    """Security-relevant actions (spec 3.7): exports, permission changes, Meta connect/disconnect.

    Kept in PostgreSQL (not the MongoDB timeline) so it can be reviewed and retained on its own.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    action = models.CharField(max_length=60)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "action", "created_at"], name="audit_action_idx")]

    def __str__(self) -> str:
        return f"{self.action} by {self.actor_id}"
