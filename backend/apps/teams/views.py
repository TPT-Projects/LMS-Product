from django.db.models import Prefetch
from rest_framework import viewsets

from apps.permissions.drf import read_or_require
from apps.permissions.roles import Capability
from common.tenancy.mixins import TenantScopedViewMixin

from .models import Team, TeamMember
from .serializers import TeamSerializer


class TeamViewSet(TenantScopedViewMixin, viewsets.ModelViewSet):
    """Any member can list teams. Creating and editing needs MANAGE_USERS."""

    serializer_class = TeamSerializer
    permission_classes = [read_or_require(Capability.MANAGE_USERS)]
    http_method_names = ["get", "post", "patch", "delete", "options", "head"]
    queryset = Team.objects.prefetch_related(
        Prefetch("members", queryset=TeamMember.objects.select_related("user"))
    )
