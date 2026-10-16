from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail


def frontend_url(path: str, **params: str) -> str:
    query = f"?{urlencode(params)}" if params else ""
    return f"{settings.FRONTEND_URL.rstrip('/')}{path}{query}"


def send_invitation_email(*, to: str, workspace_name: str, inviter_name: str, url: str) -> None:
    send_mail(
        subject=f"You are invited to {workspace_name}",
        message=(
            f"{inviter_name} invited you to join {workspace_name} on LMS.\n\n"
            f"Accept the invite: {url}\n\n"
            f"This link expires in {settings.INVITATION_TTL_DAYS} days."
        ),
        from_email=None,
        recipient_list=[to],
    )


def send_password_reset_email(*, to: str, url: str) -> None:
    send_mail(
        subject="Reset your LMS password",
        message=(
            "We received a request to reset your password.\n\n"
            f"Choose a new password: {url}\n\n"
            "If you did not ask for this, you can ignore this email."
        ),
        from_email=None,
        recipient_list=[to],
    )
