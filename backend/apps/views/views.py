"""Saved views: /views (own + shared), pin per user, and sidebar counts."""

from django.db.models import Exists, OuterRef, Q
from django.http import Http404
from django.utils.translation import gettext as _
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.enquiries.filters import Ctx, FilterError, build_filter, search_q
from apps.enquiries.selectors import SYSTEM_VIEWS, apply_system_view, visible_enquiries

from .models import SavedView, ViewPin


class SavedViewSerializer(serializers.ModelSerializer):
    owner = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    is_pinned = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = SavedView
        fields = [
            "id",
            "name",
            "filters",
            "sort",
            "is_shared",
            "owner",
            "is_owner",
            "is_pinned",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_owner(self, obj):
        return {"id": obj.owner_id, "full_name": obj.owner.full_name}

    def get_is_owner(self, obj):
        return obj.owner_id == self.context["request"].user.pk

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(_("Enter a name."))
        return value

    def validate_filters(self, value):
        if not isinstance(value, dict) or set(value) - {"filter", "q"}:
            raise serializers.ValidationError(_("Send {filter, q}."))
        request = self.context["request"]
        ctx = Ctx(request.tenant.pk, request.user.pk, request.tenant.timezone)
        try:
            build_filter(value.get("filter"), ctx)  # reject invalid filters up front
        except FilterError as exc:
            raise serializers.ValidationError(str(exc)) from None
        return value


class SavedViewViewSet(viewsets.ModelViewSet):
    """Anyone can create private views. Only the owner edits or deletes a view;
    anyone who can see a view can pin it for themselves."""

    serializer_class = SavedViewSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "options", "head"]

    def get_queryset(self):
        user = self.request.user
        pinned = ViewPin.objects.filter(view=OuterRef("pk"), user=user)
        return (
            SavedView.objects.filter(tenant=self.request.tenant)
            .filter(Q(owner=user) | Q(is_shared=True))
            .select_related("owner")
            .annotate(is_pinned=Exists(pinned))
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        view = serializer.save(tenant=request.tenant, owner=request.user)
        # New views are pinned for their creator.
        ViewPin.objects.create(tenant=request.tenant, view=view, user=request.user)
        fresh = self.get_queryset().get(pk=view.pk)  # with the is_pinned annotation
        return Response(self.get_serializer(fresh).data, status=status.HTTP_201_CREATED)

    def _own(self, view: SavedView) -> None:
        if view.owner_id != self.request.user.pk:
            raise PermissionDenied(_("Only the person who created this view can change it."))

    def perform_update(self, serializer):
        self._own(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._own(instance)
        instance.delete()

    @action(detail=True, methods=["post", "delete"])
    def pin(self, request, pk=None):
        view = self.get_object()
        if request.method == "POST":
            ViewPin.objects.get_or_create(tenant=request.tenant, view=view, user=request.user)
        else:
            ViewPin.objects.filter(view=view, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def counts(self, request):
        """Counts for the sidebar: the system views and the user's pinned views."""
        membership = request.membership
        tz = request.tenant.timezone
        base = visible_enquiries(membership)
        system = {v: apply_system_view(base, v, membership, tz).count() for v in SYSTEM_VIEWS}
        ctx = Ctx(request.tenant.pk, request.user.pk, tz)
        saved = {}
        for view in self.get_queryset().filter(is_pinned=True):
            try:
                qs = base.filter(build_filter(view.filters.get("filter"), ctx))
            except FilterError:
                continue
            if view.filters.get("q"):
                qs = qs.filter(search_q(view.filters["q"], ctx.tenant_id))
            saved[str(view.pk)] = qs.count()
        return Response({"system": system, "saved": saved})

    def get_object(self):
        view = self.get_queryset().filter(pk=self.kwargs["pk"]).first()
        if view is None:
            raise Http404
        return view
