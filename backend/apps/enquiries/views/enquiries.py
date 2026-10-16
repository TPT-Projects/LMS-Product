"""/api/v1/enquiries endpoints."""

import json

from django.db.models import Q
from django.http import Http404
from django.utils.translation import gettext as _
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.activity import service as activity
from apps.customfields import services as custom_fields
from apps.permissions.roles import Capability
from apps.views.models import SavedView
from common.mongo import LEAD_FORM_RESPONSES, TenantCollection
from common.pagination import StandardPagination

from .. import services
from ..filters import Ctx, FilterError, build_filter, order_by, search_q
from ..ingestion import EnquiryData, ingest_enquiry
from ..models import Enquiry
from ..selectors import SYSTEM_VIEWS, apply_system_view, visible_enquiries, with_list_data
from ..serializers import (
    BulkActionSerializer,
    EnquiryCreateSerializer,
    EnquiryDetailSerializer,
    EnquiryListSerializer,
    EnquiryUpdateSerializer,
)

# Quick filters (query string) -> filter rules. Combined with AND.
QUICK_FILTERS = {
    "status": ("status", "in"),
    "owner": ("owner", "in"),
    "source": ("source", "in"),
    "campaign": ("campaign", "contains"),
    "form": ("form", "eq"),
}


def filter_context(request) -> Ctx:
    return Ctx(tenant_id=request.tenant.pk, user_id=request.user.pk, tz=request.tenant.timezone)


def quick_rules(params) -> list[dict]:
    rules = []
    for param, (field, operator) in QUICK_FILTERS.items():
        raw = params.get(param)
        if not raw:
            continue
        value = raw.split(",") if operator == "in" else raw
        rules.append({"field": field, "operator": operator, "value": value})
    created_from, created_to = params.get("created_from"), params.get("created_to")
    if created_from or created_to:  # DD/MM/YYYY, both ends inclusive
        rules.append(
            {
                "field": "created_at",
                "operator": "between",
                "value": [created_from or "01/01/1970", created_to or "31/12/2999"],
            }
        )
    return rules


def saved_view_for(request, view_id: str) -> SavedView:
    try:
        pk = int(view_id)
    except ValueError:
        raise ValidationError({"saved_view": [_("Unknown view.")]}) from None
    view = (
        SavedView.objects.filter(tenant=request.tenant, pk=pk)
        .filter(Q(owner=request.user) | Q(is_shared=True))
        .first()
    )
    if view is None:
        raise Http404
    return view


def filtered_enquiries(request, params=None):
    """The visible enquiries after view, saved view, quick filters, filter tree and search.

    Shared by the list and the export, so an export always matches what is on screen.
    `params` defaults to the query string; the export passes its JSON body instead.
    """
    params = request.query_params if params is None else params
    membership = request.membership
    ctx = filter_context(request)
    qs = visible_enquiries(membership)

    view = params.get("view", "all")
    if view not in SYSTEM_VIEWS:
        raise ValidationError({"view": [_("Unknown view.")]})
    qs = apply_system_view(qs, view, membership, ctx.tz)

    sort = params.get("sort")
    trees = []
    search = params.get("q", "")
    if params.get("saved_view"):
        saved = saved_view_for(request, params["saved_view"])
        trees.append(saved.filters.get("filter"))
        search = search or saved.filters.get("q", "")
        sort = sort or saved.sort
    if raw := params.get("filter"):
        try:
            trees.append(json.loads(raw))
        except json.JSONDecodeError:
            raise ValidationError({"filter": [_("Filter must be valid JSON.")]}) from None
    trees.append({"op": "and", "rules": quick_rules(params)})

    try:
        for tree in trees:
            qs = qs.filter(build_filter(tree, ctx))
    except FilterError as exc:
        raise ValidationError({"filter": [str(exc)]}) from None

    if search:
        qs = qs.filter(search_q(search, ctx.tenant_id))
    return qs, order_by(sort)


class EnquiryViewSet(viewsets.ViewSet):
    """List, create, read, update and soft-delete enquiries."""

    def get_object(self, pk) -> Enquiry:
        enquiry = (
            visible_enquiries(self.request.membership)
            .select_related("status", "primary_owner", "created_by", "contact")
            .filter(pk=pk)
            .first()
        )
        if enquiry is None:
            raise Http404
        return enquiry

    def _permissions(self) -> dict[str, bool]:
        m = self.request.membership
        return {
            "can_edit": services.can(m, Capability.EDIT_ENQUIRIES),
            "can_delete": services.can(m, Capability.DELETE_ENQUIRIES),
            "can_reassign": services.can(m, Capability.REASSIGN_OWNERS),
        }

    def _detail(self, enquiry: Enquiry) -> dict:
        fresh = (
            with_list_data(Enquiry.objects.filter(pk=enquiry.pk))
            .select_related("created_by", "contact")
            .get()
        )
        return EnquiryDetailSerializer(fresh, context={"permissions": self._permissions()}).data

    # --- collection -------------------------------------------------------------
    def list(self, request):
        qs, ordering = filtered_enquiries(request)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(with_list_data(qs).order_by(*ordering), request)
        return paginator.get_paginated_response(EnquiryListSerializer(page, many=True).data)

    def create(self, request):
        membership = request.membership
        services.require(membership, Capability.EDIT_ENQUIRIES)
        s = EnquiryCreateSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        data = s.validated_data
        tenant = request.tenant

        owner_id = services.resolve_new_owner(
            membership, data.get("primary_owner_id"), "primary_owner_id" in request.data
        )
        secondary = data["secondary_owner_ids"]
        if secondary:
            services.require(membership, Capability.REASSIGN_OWNERS)
        services.check_members(tenant.pk, [owner_id, *secondary])
        values = custom_fields.validate_values(tenant.pk, data["custom_fields"])
        custom_fields.check_required(tenant.pk, values)

        result = ingest_enquiry(
            tenant=tenant,
            actor=request.user,
            data=EnquiryData(
                name=data["name"],
                phone=data["phone"],
                email=data["email"],
                campaign_name=data["campaign_name"],
                adset_name=data["adset_name"],
                ad_name=data["ad_name"],
                form_id=data["form_id"],
                status=services.get_status(tenant.pk, data.get("status_id")),
                primary_owner_id=owner_id,
                secondary_owner_ids=secondary,
                custom_values=values,
            ),
        )
        if data["note"].strip():
            services.add_note(
                enquiry=result.enquiry, membership=membership, body=data["note"].strip()
            )
        return Response(self._detail(result.enquiry), status=status.HTTP_201_CREATED)

    # --- item --------------------------------------------------------------------------
    def retrieve(self, request, pk=None):
        return Response(self._detail(self.get_object(pk)))

    def partial_update(self, request, pk=None):
        enquiry = self.get_object(pk)
        s = EnquiryUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        enquiry = services.update_enquiry(
            enquiry=enquiry, membership=request.membership, data=s.validated_data
        )
        return Response(self._detail(enquiry))

    def destroy(self, request, pk=None):
        services.soft_delete(enquiry=self.get_object(pk), membership=request.membership)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        """Activity log from MongoDB, newest first, paginated like every list."""
        enquiry = self.get_object(pk)
        paginator = StandardPagination()
        page_size = paginator.get_page_size(request)
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except ValueError:
            page = 1
        total, items = activity.timeline(
            tenant_id=enquiry.tenant_id, enquiry_id=enquiry.pk, page=page, page_size=page_size
        )
        return Response(
            {
                "count": total,
                "next": None,
                "previous": None,
                "page": page,
                "page_size": page_size,
                "total_pages": max(1, -(-total // page_size)),
                "results": items,
            }
        )

    @action(detail=True, methods=["get"], url_path="form-response")
    def form_response(self, request, pk=None):
        """The original Meta form answers (MongoDB). Manual enquiries have none."""
        enquiry = self.get_object(pk)
        doc = TenantCollection(LEAD_FORM_RESPONSES, enquiry.tenant_id).find_one(
            {"enquiry_id": enquiry.pk}, projection={"_id": 0, "raw_event": 0}
        )
        if doc is None:
            raise Http404
        doc["answers"] = [
            {
                "question": item.get("name", ""),
                "label": str(item.get("name", "")).replace("_", " "),
                "values": item.get("values", []),
                "display": ", ".join(str(v).replace("_", " ") for v in item.get("values", [])),
            }
            for item in doc.get("field_data", [])
        ]
        return Response(doc)

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        s = BulkActionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        ids = s.validated_data["ids"]
        enquiries = list(visible_enquiries(request.membership).filter(pk__in=ids))
        updated = services.bulk_action(
            enquiries=enquiries,
            membership=request.membership,
            action=s.validated_data["action"],
            value=s.validated_data.get("value"),
        )
        return Response({"updated": updated, "skipped": len(set(ids)) - updated})
