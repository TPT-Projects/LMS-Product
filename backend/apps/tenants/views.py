from rest_framework import generics

from apps.permissions.drf import read_or_require
from apps.permissions.roles import Capability

from .serializers import WorkspaceSerializer


class WorkspaceView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /workspace: the current workspace. Editing needs MANAGE_SETTINGS."""

    serializer_class = WorkspaceSerializer
    permission_classes = [read_or_require(Capability.MANAGE_SETTINGS)]
    http_method_names = ["get", "patch", "options", "head"]

    def get_object(self):
        return self.request.tenant
