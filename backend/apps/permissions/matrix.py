"""The default permission matrix (spec section 5). Change it here, and only here."""

from .roles import Capability as C
from .roles import Role, Scope

ROLE_CAPABILITIES: dict[str, frozenset[C]] = {
    Role.OWNER: frozenset(C),
    Role.ADMIN: frozenset(C) - {C.MANAGE_BILLING},
    Role.MANAGER: frozenset(
        {
            C.EDIT_ENQUIRIES,
            C.DELETE_ENQUIRIES,
            C.REASSIGN_OWNERS,
            C.IMPORT,
            C.EXPORT,
            C.VIEW_REPORTS,
        }
    ),
    Role.AGENT: frozenset({C.EDIT_ENQUIRIES, C.VIEW_REPORTS}),
    Role.VIEWER: frozenset({C.VIEW_REPORTS}),
}

ENQUIRY_SCOPE: dict[str, Scope] = {
    Role.OWNER: Scope.ALL,
    Role.ADMIN: Scope.ALL,
    Role.MANAGER: Scope.TEAM,
    Role.AGENT: Scope.OWN,
    Role.VIEWER: Scope.SHARED,
}

REPORT_SCOPE: dict[str, Scope] = {
    Role.OWNER: Scope.ALL,
    Role.ADMIN: Scope.ALL,
    Role.MANAGER: Scope.TEAM,
    Role.AGENT: Scope.OWN,
    Role.VIEWER: Scope.SHARED,
}


def capabilities_for(role: str) -> frozenset[C]:
    return ROLE_CAPABILITIES.get(role, frozenset())


def has_capability(role: str, capability: C) -> bool:
    return capability in capabilities_for(role)
