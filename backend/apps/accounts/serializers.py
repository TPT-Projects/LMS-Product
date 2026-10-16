from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.permissions.roles import Role
from apps.tenants.models import DedupeKey
from apps.tenants.serializers import validate_country, validate_timezone

from .models import Invitation, Membership


class PasswordField(serializers.CharField):
    def __init__(self, **kwargs):
        kwargs.setdefault("write_only", True)
        kwargs.setdefault("trim_whitespace", False)
        kwargs.setdefault("style", {"input_type": "password"})
        super().__init__(**kwargs)


def check_password_strength(password: str) -> str:
    try:
        validate_password(password)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return password


# --- auth -----------------------------------------------------------------
class SignupSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = PasswordField(validators=[check_password_strength])
    workspace_name = serializers.CharField(max_length=120)
    timezone = serializers.CharField(default="Asia/Kolkata", validators=[validate_timezone])
    dedupe_key = serializers.ChoiceField(choices=DedupeKey.choices, default=DedupeKey.PHONE)
    default_country = serializers.CharField(default="IN", validators=[validate_country])


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = PasswordField()
    tenant_id = serializers.IntegerField(required=False, allow_null=True)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class SwitchWorkspaceSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = PasswordField(validators=[check_password_strength])


class AcceptInviteSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = PasswordField()
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True)


# --- users and invites ----------------------------------------------------
class MemberSerializer(serializers.ModelSerializer):
    """A row in the Users table. `id` is the user id, as in `/users/{id}/role`."""

    id = serializers.IntegerField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)
    joined_at = serializers.DateTimeField(source="created_at", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    alternate_phone = serializers.CharField(source="user.alternate_phone", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id", "email", "full_name", "phone", "alternate_phone", "role", "is_active",
            "last_login", "joined_at",
        ]  # fmt: skip


class ProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    alternate_phone = serializers.CharField(max_length=32, required=False, allow_blank=True)


class InviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Role.choices, default=Role.AGENT)


class RoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)


class InvitationSerializer(serializers.ModelSerializer):
    invited_by = serializers.CharField(source="invited_by.full_name", default=None, read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = ["id", "email", "role", "invited_by", "status", "expires_at", "created_at"]

    def get_status(self, obj: Invitation) -> str:
        if obj.accepted_at:
            return "accepted"
        if obj.revoked_at:
            return "revoked"
        return "pending" if obj.is_pending else "expired"
