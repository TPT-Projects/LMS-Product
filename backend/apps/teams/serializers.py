from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.accounts.models import Membership

from .models import Team, TeamMember


class TeamMemberSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="user.id")
    full_name = serializers.CharField(source="user.full_name")
    email = serializers.EmailField(source="user.email")


class TeamSerializer(serializers.ModelSerializer):
    members = TeamMemberSerializer(many=True, read_only=True)
    member_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )

    class Meta:
        model = Team
        fields = ["id", "name", "members", "member_ids", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value: str) -> str:
        value = value.strip()
        tenant = self.context["request"].tenant
        qs = Team.objects.filter(tenant=tenant, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(_("A team with this name already exists."))
        return value

    def validate_member_ids(self, value: list[int]) -> list[int]:
        ids = set(value)
        tenant = self.context["request"].tenant
        found = set(
            Membership.objects.filter(tenant=tenant, user_id__in=ids, is_active=True).values_list(
                "user_id", flat=True
            )
        )
        if missing := ids - found:
            raise serializers.ValidationError(
                _("Not members of this workspace: %(ids)s") % {"ids": sorted(missing)}
            )
        return sorted(ids)

    @transaction.atomic
    def create(self, validated_data):
        member_ids = validated_data.pop("member_ids", [])
        team = Team.objects.create(**validated_data)
        self._set_members(team, member_ids)
        return team

    @transaction.atomic
    def update(self, instance, validated_data):
        member_ids = validated_data.pop("member_ids", None)
        instance = super().update(instance, validated_data)
        if member_ids is not None:
            self._set_members(instance, member_ids)
        return instance

    @staticmethod
    def _set_members(team: Team, user_ids: list[int]) -> None:
        TeamMember.objects.filter(team=team).exclude(user_id__in=user_ids).delete()
        existing = set(TeamMember.objects.filter(team=team).values_list("user_id", flat=True))
        TeamMember.objects.bulk_create(
            TeamMember(tenant_id=team.tenant_id, team=team, user_id=uid)
            for uid in user_ids
            if uid not in existing
        )
