"""GET /contacts and GET /contacts/{id}. Read-only for every role (spec section 5)."""

from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.http import Http404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.enquiries.models import Enquiry
from apps.enquiries.selectors import visibility_q, visible_enquiries, with_list_data
from apps.enquiries.serializers import EnquiryListSerializer
from apps.permissions.matrix import ENQUIRY_SCOPE
from apps.permissions.roles import Scope

from .models import Contact


class ContactSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source="email_lower", allow_null=True)
    enquiry_count = serializers.IntegerField(read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = [
            "id", "name", "phone_e164", "email", "enquiry_count", "status",
            "created_at", "updated_at",
        ]  # fmt: skip

    def get_status(self, contact) -> dict | None:
        """Status of the contact's latest enquiry (the list's Status column)."""
        status_id = getattr(contact, "latest_status_id", None)
        if status_id is None:
            return None
        return {
            "id": status_id,
            "name": contact.latest_status_name,
            "color": contact.latest_status_color,
        }


class ContactViewSet(ReadOnlyModelViewSet):
    serializer_class = ContactSerializer

    def get_queryset(self):
        membership = self.request.membership
        alive = Q(enquiries__deleted_at__isnull=True)
        qs = Contact.objects.filter(tenant=self.request.tenant, deleted_at__isnull=True)
        if ENQUIRY_SCOPE.get(membership.role) != Scope.ALL:
            # Only people behind enquiries this member may see.
            visible = Enquiry.objects.filter(
                contact=OuterRef("pk"), deleted_at__isnull=True
            ).filter(visibility_q(membership))
            qs = qs.filter(Exists(visible))
        if text := self.request.query_params.get("q", "").strip()[:100]:
            match = Q(name__icontains=text) | Q(email_lower__icontains=text.lower())
            digits = "".join(ch for ch in text if ch.isdigit())
            if len(digits) >= 4:
                match |= Q(phone_e164__contains=digits)
            qs = qs.filter(match)
        latest = Enquiry.objects.filter(contact=OuterRef("pk"), deleted_at__isnull=True)
        if ENQUIRY_SCOPE.get(membership.role) != Scope.ALL:
            latest = latest.filter(visibility_q(membership))
        latest = latest.order_by("-created_at", "-id")
        return qs.annotate(
            enquiry_count=Count("enquiries", filter=alive),
            latest_status_id=Subquery(latest.values("status_id")[:1]),
            latest_status_name=Subquery(latest.values("status__name")[:1]),
            latest_status_color=Subquery(latest.values("status__color")[:1]),
        ).order_by("-created_at", "-id")

    def retrieve(self, request, pk=None):
        contact = self.get_queryset().filter(pk=pk).first()
        if contact is None:
            raise Http404
        enquiries = with_list_data(
            visible_enquiries(request.membership).filter(contact=contact)
        ).order_by("-created_at")
        return Response(
            {
                **ContactSerializer(contact).data,
                "enquiries": EnquiryListSerializer(enquiries, many=True).data,
            }
        )
