from enum import StrEnum

from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    OWNER = "owner", _("Owner")
    ADMIN = "admin", _("Admin")
    MANAGER = "manager", _("Manager")
    AGENT = "agent", _("Agent")
    VIEWER = "viewer", _("Viewer")


class Capability(StrEnum):
    """One entry per row of the permission matrix in spec section 5."""

    MANAGE_BILLING = "manage_billing"  # billing, plan, delete workspace
    MANAGE_USERS = "manage_users"  # invite users, set roles, manage teams
    MANAGE_SETTINGS = "manage_settings"  # workspace, statuses, custom fields, assignment rules
    MANAGE_META = "manage_meta"  # connect Meta Page, manage forms, field mapping
    MANAGE_INTEGRATIONS = "manage_integrations"  # connect apps (WhatsApp, Exotel, ...)
    EDIT_ENQUIRIES = "edit_enquiries"  # create / edit enquiries, notes, calls, follow-ups
    DELETE_ENQUIRIES = "delete_enquiries"  # soft delete
    REASSIGN_OWNERS = "reassign_owners"
    IMPORT = "import"
    EXPORT = "export"
    VIEW_REPORTS = "view_reports"


class Scope(StrEnum):
    """How much data a role can see (enquiries, reports)."""

    ALL = "all"
    TEAM = "team"  # enquiries of the manager's teams
    OWN = "own"  # own and assigned only
    SHARED = "shared"  # read-only, per share


# Rank used for "can this user change that user's role" checks.
ROLE_RANK: dict[str, int] = {
    Role.OWNER: 50,
    Role.ADMIN: 40,
    Role.MANAGER: 30,
    Role.AGENT: 20,
    Role.VIEWER: 10,
}
