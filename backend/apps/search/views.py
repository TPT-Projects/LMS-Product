"""GET /search?q= : global search across enquiries and contacts the member can see.

Matches name, email, phone (digits, any format), campaign, form id and text
custom fields. Phone search ignores spaces, dashes and the country code prefix.
"""

from django.db.models import Count, Exists, OuterRef, Q
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.contacts.models import Contact
from apps.enquiries.filters import search_q
from apps.enquiries.models import Enquiry
from apps.enquiries.selectors import visibility_q, visible_enquiries

LIMIT = 8


class SearchView(APIView):
    def get(self, request):
        text = request.query_params.get("q", "").strip()[:100]
        if len(text) < 2:
            return Response({"q": text, "enquiries": [], "contacts": []})
        membership = request.membership

        enquiries = (
            visible_enquiries(membership)
            .filter(search_q(text, request.tenant.pk))
            .select_related("status")
            .order_by("-created_at")[:LIMIT]
        )

        visible = Enquiry.objects.filter(contact=OuterRef("pk"), deleted_at__isnull=True).filter(
            visibility_q(membership)
        )
        match = Q(name__icontains=text) | Q(email_lower__icontains=text.lower())
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) >= 4:
            match |= Q(phone_e164__contains=digits)
        contacts = (
            Contact.objects.filter(tenant=request.tenant, deleted_at__isnull=True)
            .filter(Exists(visible))
            .filter(match)
            .annotate(
                enquiry_count=Count("enquiries", filter=Q(enquiries__deleted_at__isnull=True))
            )
            .order_by("-created_at")[:LIMIT]
        )

        return Response(
            {
                "q": text,
                "enquiries": [
                    {
                        "id": e.pk,
                        "name": e.name,
                        "phone_e164": e.phone_e164,
                        "email": e.email,
                        "campaign_name": e.campaign_name,
                        "status": {
                            "id": e.status_id,
                            "name": e.status.name,
                            "color": e.status.color,
                        },
                        "created_at": e.created_at,
                    }
                    for e in enquiries
                ],
                "contacts": [
                    {
                        "id": c.pk,
                        "name": c.name,
                        "phone_e164": c.phone_e164,
                        "email": c.email_lower,
                        "enquiry_count": c.enquiry_count,
                    }
                    for c in contacts
                ],
            }
        )
