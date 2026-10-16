"""Business logic for sign up, login, invites and roles.

Views stay thin: they validate input with a serializer and call one function
here. Functions that must cross tenants (no workspace is active yet) use
`rls_bypass()` in the smallest possible block and filter explicitly.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.service import ROLE_CHANGED, USER_INVITED, audit
from apps.permissions.matrix import capabilities_for
from apps.permissions.roles import ROLE_RANK, Role
from apps.statuses.models import create_default_statuses
from apps.tenants.models import Tenant
from common.tenancy.authentication import TENANT_CLAIM
from common.tenancy.context import rls_bypass

from . import emails
from .models import Invitation, Membership, User, hash_token

INVALID_LOGIN = gettext_lazy("Invalid email or password.")


class InvalidCredentials(APIException):
    """Always 401. (DRF turns AuthenticationFailed into 403 on public views.)"""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = INVALID_LOGIN
    default_code = "invalid_credentials"


# --- tokens and session payload -------------------------------------------
def issue_tokens(user: User, tenant_id: int) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    refresh[TENANT_CLAIM] = tenant_id
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def list_workspaces(user: User) -> list[dict]:
    with rls_bypass():
        memberships = (
            Membership.objects.filter(user=user, is_active=True)
            .select_related("tenant")
            .order_by("tenant__name")
        )
        return [{"id": m.tenant_id, "name": m.tenant.name, "role": m.role} for m in memberships]


def build_session(user: User, membership: Membership) -> dict:
    """What the frontend needs to render the app for this user and workspace."""
    tenant = membership.tenant
    return {
        "user": {"id": user.pk, "email": user.email, "full_name": user.full_name},
        "workspace": {
            "id": tenant.pk,
            "name": tenant.name,
            "timezone": tenant.timezone,
            "dedupe_key": tenant.dedupe_key,
            "default_country": tenant.default_country,
            "plan": tenant.plan,
        },
        "role": membership.role,
        "capabilities": sorted(capabilities_for(membership.role)),
        "workspaces": list_workspaces(user),
    }


def auth_response(user: User, membership: Membership) -> dict:
    """Tokens + session for every endpoint that logs someone in."""
    User.objects.filter(pk=user.pk).update(last_login=timezone.now())
    return {**issue_tokens(user, membership.tenant_id), "session": build_session(user, membership)}


# --- sign up and login ----------------------------------------------------
@transaction.atomic
def signup(
    *,
    full_name: str,
    email: str,
    password: str,
    workspace_name: str,
    timezone_name: str,
    dedupe_key: str,
    default_country: str,
) -> tuple[User, Membership]:
    email = email.strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"email": [_("An account with this email already exists.")]})

    user = User.objects.create_user(email=email, password=password, full_name=full_name.strip())
    with rls_bypass():
        tenant = Tenant.objects.create(
            name=workspace_name.strip(),
            timezone=timezone_name,
            dedupe_key=dedupe_key,
            default_country=default_country,
        )
        membership = Membership.objects.create(tenant=tenant, user=user, role=Role.OWNER)
        create_default_statuses(tenant.pk)
    return user, membership


def login(*, email: str, password: str, tenant_id: int | None = None) -> tuple[User, Membership]:
    user = User.objects.filter(email__iexact=email.strip()).first()
    if user is None:
        User().set_password(password)  # same hashing cost, so timing does not reveal the email
        raise InvalidCredentials()
    if not user.check_password(password) or not user.is_active:
        raise InvalidCredentials()

    return user, _pick_membership(user, tenant_id)


def switch_workspace(*, user: User, tenant_id: int) -> Membership:
    return _pick_membership(user, tenant_id)


def _pick_membership(user: User, tenant_id: int | None) -> Membership:
    with rls_bypass():
        qs = Membership.objects.filter(user=user, is_active=True).select_related("tenant")
        if tenant_id is not None:
            qs = qs.filter(tenant_id=tenant_id)
        membership = qs.order_by("created_at").first()
    if membership is None:
        raise InvalidCredentials(_("You are not a member of this workspace."), "no_membership")
    return membership


def logout(refresh: str) -> None:
    try:
        RefreshToken(refresh).blacklist()
    except TokenError:
        pass  # already invalid: nothing to do


def revoke_all_tokens(user: User) -> None:
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


# --- password reset -------------------------------------------------------
def request_password_reset(email: str) -> None:
    """Always succeeds, so the response never reveals whether an email exists."""
    user = User.objects.filter(email__iexact=email.strip(), is_active=True).first()
    if user is None:
        return
    url = emails.frontend_url(
        "/reset-password",
        uid=urlsafe_base64_encode(force_bytes(user.pk)),
        token=default_token_generator.make_token(user),
    )
    emails.send_password_reset_email(to=user.email, url=url)


def reset_password(*, uid: str, token: str, password: str) -> User:
    invalid = ValidationError({"token": [_("This reset link is invalid or has expired.")]})
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)), is_active=True)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        raise invalid from None
    if not default_token_generator.check_token(user, token):
        raise invalid
    user.set_password(password)
    user.save(update_fields=["password"])
    revoke_all_tokens(user)  # sign out every device
    return user


# --- invitations ----------------------------------------------------------
def _ensure_can_grant(actor: Membership, role: str) -> None:
    if role == Role.OWNER and actor.role != Role.OWNER:
        raise PermissionDenied(_("Only an Owner can give the Owner role."))
    if ROLE_RANK[role] > ROLE_RANK[actor.role]:
        raise PermissionDenied(_("You cannot give a role higher than your own."))


@transaction.atomic
def invite_user(*, actor: Membership, email: str, role: str) -> tuple[Invitation, str]:
    """Create an invite and email it. Returns the invite and its accept URL."""
    _ensure_can_grant(actor, role)
    email = email.strip().lower()

    if Membership.objects.filter(
        tenant=actor.tenant, user__email__iexact=email, is_active=True
    ).exists():
        raise ValidationError({"email": [_("This person is already a member.")]})

    # A new invite replaces any older pending one for the same email.
    Invitation.objects.filter(
        tenant=actor.tenant, email=email, accepted_at__isnull=True, revoked_at__isnull=True
    ).update(revoked_at=timezone.now())

    raw_token, token_hash = Invitation.new_token()
    invitation = Invitation.objects.create(
        tenant=actor.tenant,
        email=email,
        role=role,
        token_hash=token_hash,
        invited_by=actor.user,
        expires_at=timezone.now() + timedelta(days=settings.INVITATION_TTL_DAYS),
    )
    audit(
        tenant_id=actor.tenant_id,
        actor=actor.user,
        action=USER_INVITED,
        details={"email": email, "role": role},
    )
    url = emails.frontend_url("/accept-invite", token=raw_token)
    emails.send_invitation_email(
        to=email, workspace_name=actor.tenant.name, inviter_name=actor.user.full_name, url=url
    )
    return invitation, url


def revoke_invitation(*, tenant: Tenant, invitation_id: int) -> None:
    updated = Invitation.objects.filter(
        tenant=tenant, pk=invitation_id, accepted_at__isnull=True, revoked_at__isnull=True
    ).update(revoked_at=timezone.now())
    if not updated:
        raise ValidationError({"detail": _("This invite is not pending.")})


def get_pending_invitation(raw_token: str, *, for_update: bool = False) -> Invitation:
    with rls_bypass():
        qs = Invitation.objects.select_related("tenant", "invited_by")
        if for_update:
            qs = qs.select_for_update(of=("self",))
        invitation = qs.filter(token_hash=hash_token(raw_token)).first()
    if invitation is None or not invitation.is_pending:
        raise ValidationError({"token": [_("This invite is invalid or has expired.")]})
    return invitation


def invitation_preview(raw_token: str) -> dict:
    invitation = get_pending_invitation(raw_token)
    return {
        "email": invitation.email,
        "role": invitation.role,
        "workspace_name": invitation.tenant.name,
        "invited_by": invitation.invited_by.full_name if invitation.invited_by else None,
        "has_account": User.objects.filter(email__iexact=invitation.email).exists(),
    }


@transaction.atomic
def accept_invitation(
    *, raw_token: str, password: str, full_name: str | None = None
) -> tuple[User, Membership]:
    invitation = get_pending_invitation(raw_token, for_update=True)

    user = User.objects.filter(email__iexact=invitation.email).first()
    if user is not None:
        if not user.check_password(password):
            raise ValidationError(
                {"password": [_("An account with this email exists. Enter its password.")]}
            )
    else:
        if not full_name:
            raise ValidationError({"full_name": [_("This field is required.")]})
        user = User.objects.create_user(
            email=invitation.email, password=password, full_name=full_name.strip()
        )

    with rls_bypass():
        membership, _created = Membership.objects.update_or_create(
            tenant=invitation.tenant,
            user=user,
            defaults={"role": invitation.role, "is_active": True},
        )
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["accepted_at"])
        membership = Membership.objects.select_related("tenant").get(pk=membership.pk)
    return user, membership


# --- roles ----------------------------------------------------------------
@transaction.atomic
def change_role(*, actor: Membership, target_user_id: int, role: str) -> Membership:
    target = (
        Membership.objects.select_for_update()
        .select_related("user")
        .filter(tenant=actor.tenant, user_id=target_user_id, is_active=True)
        .first()
    )
    if target is None:
        raise ValidationError({"detail": _("User not found in this workspace.")})
    if target.user_id == actor.user_id:
        raise PermissionDenied(_("You cannot change your own role."))
    if target.role == Role.OWNER and actor.role != Role.OWNER:
        raise PermissionDenied(_("Only an Owner can change another Owner's role."))
    _ensure_can_grant(actor, role)

    previous = target.role
    target.role = role
    target.save(update_fields=["role"])
    audit(
        tenant_id=actor.tenant_id,
        actor=actor.user,
        action=ROLE_CHANGED,
        details={
            "user_id": target.user_id,
            "email": target.user.email,
            "from": previous,
            "to": role,
        },
    )
    return target


# --- profile ----------------------------------------------------------------
def update_profile(*, actor: Membership, target_user_id: int, **changes) -> Membership:
    """Name and phone numbers. Your own, or anyone's with MANAGE_USERS."""
    from apps.permissions.matrix import has_capability
    from apps.permissions.roles import Capability
    from common.phones import normalize_phone

    target = (
        Membership.objects.select_related("user", "tenant")
        .filter(tenant=actor.tenant, user_id=target_user_id, is_active=True)
        .first()
    )
    if target is None:
        raise ValidationError({"detail": _("User not found in this workspace.")})
    if target.user_id != actor.user_id and not has_capability(actor.role, Capability.MANAGE_USERS):
        raise PermissionDenied(_("You can only change your own details."))

    user = target.user
    errors: dict[str, list[str]] = {}
    for field in ("phone", "alternate_phone"):
        if field not in changes:
            continue
        raw = (changes[field] or "").strip()
        if not raw:
            setattr(user, field, "")
            continue
        number = normalize_phone(raw, target.tenant.default_country)
        if not number:
            errors[field] = [_("Enter a valid phone number.")]
        else:
            setattr(user, field, number)
    if name := (changes.get("full_name") or "").strip():
        user.full_name = name
    if errors:
        raise ValidationError(errors)
    user.save(update_fields=["full_name", "phone", "alternate_phone"])
    return target
