import hashlib
import secrets

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.permissions.roles import Role
from common.tenancy.models import TenantScopedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra):
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """A person who can log in.

    Users are global (one login, many workspaces). What a user can see in a
    workspace is decided by their `Membership`, which is tenant-scoped.
    """

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    # E.164. `phone` is also the number Exotel rings first for this user's auto-calls.
    phone = models.CharField(max_length=20, blank=True)
    alternate_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # platform staff (Django admin) only
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return self.email


class Membership(TenantScopedModel):
    """A user's role in one workspace."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.AGENT)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "memberships"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "user"], name="uniq_membership_tenant_user")
        ]

    def __str__(self) -> str:
        return f"{self.user_id}@{self.tenant_id} ({self.role})"


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class Invitation(TenantScopedModel):
    """An invite to join a workspace. Only the token hash is stored."""

    email = models.EmailField()
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.AGENT)
    token_hash = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "invitations"
        indexes = [models.Index(fields=["tenant", "email"])]

    @staticmethod
    def new_token() -> tuple[str, str]:
        raw = secrets.token_urlsafe(32)
        return raw, hash_token(raw)

    @property
    def is_pending(self) -> bool:
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.expires_at > timezone.now()
        )


class TablePreference(TenantScopedModel):
    """A user's column layout for one table (which columns, in which order)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    table = models.CharField(max_length=40)
    columns = models.JSONField(default=list)  # ordered list of visible column ids
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "table_preferences"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "user", "table"], name="uniq_table_preference"
            )
        ]
