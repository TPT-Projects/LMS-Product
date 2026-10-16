"""/api/v1/users and /api/v1/invitations endpoints."""

from django.db.models import Q
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permissions.drf import read_or_require, require
from apps.permissions.roles import Capability

from .. import services
from ..models import Invitation, Membership
from ..serializers import (
    InvitationSerializer,
    InviteSerializer,
    MemberSerializer,
    ProfileUpdateSerializer,
    RoleUpdateSerializer,
)


class UserListView(generics.ListAPIView):
    """GET: members of the workspace. POST: invite a user (MANAGE_USERS)."""

    serializer_class = MemberSerializer
    permission_classes = [read_or_require(Capability.MANAGE_USERS)]

    def get_queryset(self):
        qs = (
            Membership.objects.filter(tenant=self.request.tenant, is_active=True)
            .select_related("user")
            .order_by("user__full_name")
        )
        params = self.request.query_params
        if role := params.get("role"):
            qs = qs.filter(role=role)
        if q := params.get("q", "").strip():
            qs = qs.filter(Q(user__full_name__icontains=q) | Q(user__email__icontains=q))
        return qs

    def post(self, request):
        s = InviteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        invitation, url = services.invite_user(actor=request.membership, **s.validated_data)
        body = InvitationSerializer(invitation).data
        body["invite_url"] = url  # lets the admin copy the link if email is not set up
        return Response(body, status=status.HTTP_201_CREATED)


class UserRoleView(APIView):
    permission_classes = [require(Capability.MANAGE_USERS)]

    def patch(self, request, user_id: int):
        s = RoleUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        membership = services.change_role(
            actor=request.membership, target_user_id=user_id, role=s.validated_data["role"]
        )
        return Response(MemberSerializer(membership).data)


class UserProfileView(APIView):
    """PATCH {full_name?, phone?, alternate_phone?}: your own details, or anyone's with
    MANAGE_USERS. Phones are stored in E.164 (the workspace's country is the default)."""

    def patch(self, request, user_id: int):
        s = ProfileUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        membership = services.update_profile(
            actor=request.membership, target_user_id=user_id, **s.validated_data
        )
        return Response(MemberSerializer(membership).data)


class InvitationListView(generics.ListAPIView):
    serializer_class = InvitationSerializer
    permission_classes = [require(Capability.MANAGE_USERS)]

    def get_queryset(self):
        qs = Invitation.objects.filter(tenant=self.request.tenant).select_related("invited_by")
        if self.request.query_params.get("status") == "pending":
            qs = qs.filter(accepted_at__isnull=True, revoked_at__isnull=True)
        return qs.order_by("-created_at")


class InvitationDetailView(APIView):
    permission_classes = [require(Capability.MANAGE_USERS)]

    def delete(self, request, invitation_id: int):
        services.revoke_invitation(tenant=request.tenant, invitation_id=invitation_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
