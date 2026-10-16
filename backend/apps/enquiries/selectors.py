"""Which enquiries a member may see (spec section 5, "See all enquiries").

Owner / Admin   all enquiries
Manager         enquiries owned by (or shared with) members of their teams, their own,
                and unassigned ones (so they can assign them)
Agent           enquiries they own, are a secondary owner of, or created
Viewer          read-only, same team scope as a manager (sharing rules come later)

Enforced in every query, not only in the UI.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Exists, Min, OuterRef, Prefetch, Q, QuerySet, Subquery
from django.utils import timezone

from apps.accounts.models import Membership
from apps.customfields.models import EnquiryCustomValue
from apps.permissions.matrix import ENQUIRY_SCOPE
from apps.permissions.roles import Scope
from apps.teams.models import TeamMember

from .models import CallLog, Enquiry, EnquiryOwner, FollowUp


def team_user_ids(membership: Membership) -> set[int]:
    """The member's own id plus everyone in any team they belong to."""
    team_ids = TeamMember.objects.filter(
        tenant_id=membership.tenant_id, user_id=membership.user_id
    ).values("team_id")
    ids = set(TeamMember.objects.filter(team_id__in=team_ids).values_list("user_id", flat=True))
    ids.add(membership.user_id)
    return ids


def _owned_by_any(user_ids) -> Q:
    shared = EnquiryOwner.objects.filter(enquiry=OuterRef("pk"), user_id__in=user_ids)
    return Q(primary_owner_id__in=user_ids) | Q(Exists(shared))


def visibility_q(membership: Membership) -> Q:
    scope = ENQUIRY_SCOPE.get(membership.role, Scope.OWN)
    user_id = membership.user_id
    if scope == Scope.ALL:
        return Q()
    if scope == Scope.OWN:
        return _owned_by_any([user_id]) | Q(created_by_id=user_id)
    # TEAM (manager) and SHARED (viewer)
    team = team_user_ids(membership)
    q = _owned_by_any(team) | Q(created_by_id=user_id)
    if scope == Scope.TEAM:
        q |= Q(primary_owner__isnull=True)
    return q


def visible_enquiries(membership: Membership) -> QuerySet[Enquiry]:
    return Enquiry.objects.filter(tenant_id=membership.tenant_id, deleted_at__isnull=True).filter(
        visibility_q(membership)
    )


def with_list_data(qs: QuerySet[Enquiry]) -> QuerySet[Enquiry]:
    """Everything a table row needs, in a fixed number of queries."""
    next_open = FollowUp.objects.filter(enquiry=OuterRef("pk"), done_at__isnull=True).order_by(
        "due_at", "id"
    )
    last_call = CallLog.objects.filter(enquiry=OuterRef("pk")).order_by("-called_at", "-id")
    return (
        qs.select_related("status", "primary_owner")
        .annotate(
            next_followup_at=Min("followups__due_at", filter=Q(followups__done_at__isnull=True)),
            next_followup_id=Subquery(next_open.values("id")[:1]),
            next_followup_title=Subquery(next_open.values("title")[:1]),
            # The last call (logged or auto), shown when nothing is scheduled
            last_call_at=Subquery(last_call.values("called_at")[:1]),
            last_call_outcome=Subquery(last_call.values("outcome")[:1]),
            # Exotel: "not connected" is shown on the list's Action badge
            next_followup_call_status=Subquery(next_open.values("auto_call__status")[:1]),
        )
        .prefetch_related(
            Prefetch(
                "custom_values",
                queryset=EnquiryCustomValue.objects.select_related("field"),
            ),
            Prefetch("secondary_owners", queryset=EnquiryOwner.objects.select_related("user")),
        )
    )


def day_bounds(day, tz: str) -> tuple[datetime, datetime]:
    """UTC start/end of a calendar day in the workspace timezone."""
    zone = ZoneInfo(tz)
    start = datetime.combine(day, time.min, tzinfo=zone)
    return start, start + timedelta(days=1)


def today_in(tz: str):
    return timezone.now().astimezone(ZoneInfo(tz)).date()


# --- System smart views (spec section 8) --------------------------------------
SYSTEM_VIEWS = ("all", "mine", "unassigned", "calls-today")


def apply_system_view(qs: QuerySet[Enquiry], view: str, membership: Membership, tz: str):
    if view == "mine":
        return qs.filter(_owned_by_any([membership.user_id]))
    if view == "unassigned":
        return qs.filter(primary_owner__isnull=True)
    if view == "calls-today":
        _, end = day_bounds(today_in(tz), tz)
        # Due today, or overdue and still open.
        due = FollowUp.objects.filter(
            tenant_id=membership.tenant_id, done_at__isnull=True, due_at__lt=end
        ).values("enquiry_id")
        return qs.filter(pk__in=due)
    return qs
