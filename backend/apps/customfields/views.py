from rest_framework import viewsets

from apps.permissions.drf import read_or_require
from apps.permissions.roles import Capability
from common.tenancy.mixins import TenantScopedViewMixin

from .models import CustomField
from .serializers import CustomFieldSerializer


class CustomFieldViewSet(TenantScopedViewMixin, viewsets.ModelViewSet):
    """GET/POST/PATCH /custom-fields. Fields are deactivated, never deleted (keeps history)."""

    queryset = CustomField.objects.all()
    serializer_class = CustomFieldSerializer
    permission_classes = [read_or_require(Capability.MANAGE_SETTINGS)]
    pagination_class = None
    http_method_names = ["get", "post", "patch", "options", "head"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("active") == "1":
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        last = CustomField.objects.filter(tenant=self.request.tenant).order_by("-order").first()
        serializer.save(tenant=self.request.tenant, order=(last.order + 1) if last else 0)
