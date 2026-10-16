"""/api/v1/auth/* endpoints."""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from .. import services
from ..serializers import (
    AcceptInviteSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    RefreshSerializer,
    ResetPasswordSerializer,
    SignupSerializer,
    SwitchWorkspaceSerializer,
)


class PublicView(APIView):
    """Base for endpoints used before login."""

    authentication_classes: list = []
    permission_classes = [AllowAny]


class SignupView(PublicView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        s = SignupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        user, membership = services.signup(
            full_name=data["full_name"],
            email=data["email"],
            password=data["password"],
            workspace_name=data["workspace_name"],
            timezone_name=data["timezone"],
            dedupe_key=data["dedupe_key"],
            default_country=data["default_country"],
        )
        return Response(services.auth_response(user, membership), status=status.HTTP_201_CREATED)


class LoginView(PublicView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user, membership = services.login(**s.validated_data)
        return Response(services.auth_response(user, membership))


class RefreshView(TokenRefreshView):
    """Rotates the refresh token; the old one is blacklisted."""

    authentication_classes: list = []
    permission_classes = [AllowAny]


class LogoutView(PublicView):
    def post(self, request):
        s = RefreshSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.logout(s.validated_data["refresh"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ForgotPasswordView(PublicView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        s = ForgotPasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.request_password_reset(s.validated_data["email"])
        return Response({"detail": "If the email exists, a reset link has been sent."})


class ResetPasswordView(PublicView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        s = ResetPasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.reset_password(**s.validated_data)
        return Response({"detail": "Password updated. You can now log in."})


class AcceptInviteView(PublicView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def get(self, request):
        """Preview an invite so the page can show the workspace name."""
        return Response(services.invitation_preview(request.query_params.get("token", "")))

    def post(self, request):
        s = AcceptInviteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        user, membership = services.accept_invitation(
            raw_token=data["token"], password=data["password"], full_name=data.get("full_name")
        )
        return Response(services.auth_response(user, membership))


class MeView(APIView):
    def get(self, request):
        return Response(services.build_session(request.user, request.membership))


class SwitchWorkspaceView(APIView):
    def post(self, request):
        s = SwitchWorkspaceSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        membership = services.switch_workspace(
            user=request.user, tenant_id=s.validated_data["tenant_id"]
        )
        return Response(services.auth_response(request.user, membership))
