from django.db import transaction
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.permissions.drf import read_or_require
from apps.permissions.roles import Capability
from common.tenancy.mixins import TenantScopedViewMixin

from .models import Status
from .serializers import StatusSerializer


class ReorderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


class StatusViewSet(TenantScopedViewMixin, viewsets.ModelViewSet):
    """GET/POST/PATCH /statuses. Any member reads; MANAGE_SETTINGS edits.

    Statuses are never deleted: enquiries and status history point at them.
    """

    queryset = Status.objects.all()
    serializer_class = StatusSerializer
    permission_classes = [read_or_require(Capability.MANAGE_SETTINGS)]
    pagination_class = None  # a workspace has a handful of statuses
    http_method_names = ["get", "post", "patch", "options", "head"]

    def perform_create(self, serializer):
        last = Status.objects.filter(tenant=self.request.tenant).order_by("-order").first()
        serializer.save(tenant=self.request.tenant, order=(last.order + 1) if last else 0)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def reorder(self, request):
        """POST /statuses/reorder {ids: [...]} sets the order to the list order."""
        s = ReorderSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        ids = s.validated_data["ids"]
        statuses = {st.pk: st for st in self.get_queryset().filter(pk__in=ids)}
        if len(statuses) != len(set(ids)):
            return Response({"detail": "Unknown status id."}, status=status.HTTP_400_BAD_REQUEST)
        for index, pk in enumerate(ids):
            statuses[pk].order = index
        Status.objects.bulk_update(statuses.values(), ["order"])
        return Response(StatusSerializer(self.get_queryset(), many=True).data)
