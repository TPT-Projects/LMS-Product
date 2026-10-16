from django.conf import settings
from django.db import models

from common.tenancy.models import TenantScopedModel


class Team(TenantScopedModel):
    name = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "teams"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_team_tenant_name")
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class TeamMember(TenantScopedModel):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")

    class Meta:
        db_table = "team_members"
        constraints = [models.UniqueConstraint(fields=["team", "user"], name="uniq_team_member")]
