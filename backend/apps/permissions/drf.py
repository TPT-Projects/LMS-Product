from functools import cache

from rest_framework.permissions import SAFE_METHODS, BasePermission

from common.tenancy.permissions import IsTenantMember

from .matrix import has_capability
from .roles import Capability


@cache
def require(capability: Capability) -> type[BasePermission]:
    """Permission class factory: `permission_classes = [require(Capability.MANAGE_USERS)]`."""

    class _HasCapability(IsTenantMember):
        message = "You do not have permission to do this."

        def has_permission(self, request, view) -> bool:
            return super().has_permission(request, view) and has_capability(
                request.membership.role, capability
            )

    _HasCapability.__name__ = f"Requires_{capability.value}"
    return _HasCapability


@cache
def read_or_require(capability: Capability) -> type[BasePermission]:
    """Any member may read (GET/HEAD/OPTIONS); writing needs `capability`."""

    write_permission = require(capability)

    class _ReadOrCapability(IsTenantMember):
        message = write_permission.message

        def has_permission(self, request, view) -> bool:
            if request.method in SAFE_METHODS:
                return super().has_permission(request, view)
            return write_permission().has_permission(request, view)

    _ReadOrCapability.__name__ = f"ReadOr_{capability.value}"
    return _ReadOrCapability
