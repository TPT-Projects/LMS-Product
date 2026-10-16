from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .context import activate_tenant

TENANT_CLAIM = "tid"


class TenantJWTAuthentication(JWTAuthentication):
    """JWT auth that also resolves and activates the workspace (tenant).

    The access token carries the tenant id (`tid`). The membership is read
    from the database on every request, so a removed user or a changed role
    takes effect at once, without waiting for the token to expire.
    """

    def authenticate(self, request):
        # Runs inside the request transaction (ATOMIC_REQUESTS). Start with no
        # tenant so an anonymous request can never see tenant rows.
        activate_tenant(None)

        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result

        tenant_id = token.get(TENANT_CLAIM)
        if not tenant_id:
            raise AuthenticationFailed(_("Token has no workspace."), code="no_workspace")

        activate_tenant(int(tenant_id))

        from apps.accounts.models import Membership

        membership = (
            Membership.objects.select_related("tenant")
            .filter(user=user, tenant_id=tenant_id, is_active=True)
            .first()
        )
        if membership is None:
            activate_tenant(None)
            raise AuthenticationFailed(_("You no longer have access to this workspace."))

        request.tenant = membership.tenant
        request.membership = membership
        # Also expose on the underlying Django request (middleware, logging).
        request._request.tenant = membership.tenant
        request._request.membership = membership
        return user, token
