from rest_framework.permissions import BasePermission


class IsTenantMember(BasePermission):
    """Default permission: an authenticated user acting inside a workspace."""

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request, "membership", None) is not None
        )
