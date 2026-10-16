from typing import Any

from .models import AuditLog

# Action names (keep them stable: they are searched in reviews).
EXPORT_ENQUIRIES = "export.enquiries"
ROLE_CHANGED = "user.role_changed"
USER_INVITED = "user.invited"
META_CONNECTED = "meta.connected"
META_DISCONNECTED = "meta.disconnected"
META_FORM_CONNECTED = "meta.form_connected"
META_FORM_DISCONNECTED = "meta.form_disconnected"
INTEGRATION_CONNECTED = "integration.connected"
INTEGRATION_DISCONNECTED = "integration.disconnected"


def client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR")) or None


def audit(
    *, tenant_id: int, actor, action: str, details: dict[str, Any] | None = None, request=None
) -> AuditLog:
    return AuditLog.objects.create(
        tenant_id=tenant_id,
        actor=actor,
        action=action,
        details=details or {},
        ip_address=client_ip(request),
    )
