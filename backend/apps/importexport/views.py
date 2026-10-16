"""/imports (wizard + log) and /exports (CSV of the current list)."""

import csv
import io
import json

from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.service import EXPORT_ENQUIRIES, audit
from apps.customfields.models import CustomField
from apps.customfields.values import to_api
from apps.enquiries.selectors import with_list_data
from apps.enquiries.views.enquiries import filtered_enquiries
from apps.permissions.drf import require
from apps.permissions.roles import Capability
from common.dates import format_date, format_datetime
from common.tenancy.context import tenant_context

from . import services
from .models import ImportJob
from .processing import STANDARD_TARGETS


class ImportJobSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.full_name", default=None)

    class Meta:
        model = ImportJob
        fields = [
            "id", "original_name", "file_type", "headers", "row_count", "mapping", "status",
            "mode", "processed_count", "created_count", "linked_count", "failed_count", "error",
            "created_by", "started_at", "finished_at", "created_at",
        ]  # fmt: skip


def get_job(request, job_id: int) -> ImportJob:
    job = ImportJob.objects.filter(tenant=request.tenant, pk=job_id).first()
    if job is None:
        raise Http404
    return job


class ImportListView(generics.ListAPIView):
    """GET: import log. POST: upload a CSV/Excel file (step 1)."""

    serializer_class = ImportJobSerializer
    permission_classes = [require(Capability.IMPORT)]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return ImportJob.objects.filter(tenant=self.request.tenant).select_related("created_by")

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": [_("Choose a file.")]})
        job = services.create_job(tenant=request.tenant, user=request.user, upload=upload)
        fields = CustomField.objects.filter(tenant=request.tenant, is_active=True)
        return Response(
            {
                **ImportJobSerializer(job).data,
                "sample": services.sample_rows(job),
                "targets": [*STANDARD_TARGETS, *[f"cf:{f.key}" for f in fields]],
            },
            status=status.HTTP_201_CREATED,
        )


class ImportDetailView(APIView):
    permission_classes = [require(Capability.IMPORT)]

    def get(self, request, job_id: int):
        job = get_job(request, job_id)
        failed = job.failed_rows.all()[:50]
        return Response(
            {
                **ImportJobSerializer(job).data,
                "failed_rows": [
                    {"row_number": f.row_number, "errors": f.errors, "data": f.data} for f in failed
                ],
            }
        )


class MappingSerializer(serializers.Serializer):
    mapping = serializers.DictField(child=serializers.CharField(allow_blank=True))


class ImportMapView(APIView):
    """Step 2: {"mapping": {"<column header>": "phone" | "cf:city" | ""}}."""

    permission_classes = [require(Capability.IMPORT)]
    parser_classes = [JSONParser]

    def post(self, request, job_id: int):
        s = MappingSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        job = services.set_mapping(get_job(request, job_id), s.validated_data["mapping"])
        return Response(ImportJobSerializer(job).data)


class ImportPreviewView(APIView):
    """Step 3: nothing is saved."""

    permission_classes = [require(Capability.IMPORT)]

    def get(self, request, job_id: int):
        return Response(services.preview(get_job(request, job_id)))


class ImportRunView(APIView):
    """Step 4: up to 100 rows run now; more run in the background with a notification."""

    permission_classes = [require(Capability.IMPORT)]

    def post(self, request, job_id: int):
        job = services.start(get_job(request, job_id))
        return Response(ImportJobSerializer(job).data)


class ImportFailedReportView(APIView):
    permission_classes = [require(Capability.IMPORT)]

    def get(self, request, job_id: int):
        job = get_job(request, job_id)
        response = HttpResponse(
            services.failed_report_csv(job), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = f'attachment; filename="import-{job.pk}-failed-rows.csv"'
        return response


class ImportTemplateView(APIView):
    """A ready-to-fill CSV with the standard columns and the workspace's custom fields."""

    permission_classes = [require(Capability.IMPORT)]

    def get(self, request):
        fields = CustomField.objects.filter(tenant=request.tenant, is_active=True)
        labels = [f.label for f in fields]
        today = timezone.localdate().strftime("%d/%m/%Y")
        rows = [
            ["Name", "Phone", "Email", "Status", "Owner", "Campaign", "Date", *labels],
            [
                "Aarav Shah",
                "+919876543210",
                "karan@example.com",
                "New",
                "",
                "Diwali offer",
                today,
            ]
            + ["" for _ in labels],
        ]
        out = io.StringIO()
        out.write("\ufeff")
        csv.writer(out).writerows(rows)
        response = HttpResponse(out.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="enquiries-import-template.csv"'
        return response


# --- export ---------------------------------------------------------------------------------
EXPORT_COLUMNS = {
    "name": "Name",
    "phone": "Phone",
    "email": "Email",
    "status": "Status",
    "owner": "Owner",
    "secondary_owners": "Secondary owners",
    "source": "Source",
    "campaign": "Campaign",
    "adset": "Ad set",
    "ad": "Ad",
    "form": "Form ID",
    "next_followup": "Next follow-up",
    "repeat": "Repeat enquiry",
    "created": "Created",
    "updated": "Updated",
}


class _Echo:
    def write(self, value):
        return value


class ExportView(APIView):
    """POST /exports with the list's filters (+ optional columns) -> CSV download.

    The export is not limited by page size. Permission-gated and written to the audit log.
    """

    permission_classes = [require(Capability.EXPORT)]
    parser_classes = [JSONParser]

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        params = {}
        for key in (
            "view",
            "saved_view",
            "q",
            "created_from",
            "created_to",
            "sort",
            "campaign",
            "form",
        ):
            if body.get(key) not in (None, ""):
                params[key] = str(body[key])
        for key in ("status", "owner", "source"):
            if body.get(key):
                params[key] = ",".join(str(v) for v in body[key])
        if body.get("filter"):
            params["filter"] = json.dumps(body["filter"])

        qs, ordering = filtered_enquiries(request, params)
        tz = request.tenant.timezone
        fields = list(CustomField.objects.filter(tenant=request.tenant, is_active=True))
        all_columns = list(EXPORT_COLUMNS) + [f"cf:{f.key}" for f in fields]
        columns = [
            c for c in (body.get("columns") or all_columns) if c in all_columns
        ] or all_columns
        labels = {**EXPORT_COLUMNS, **{f"cf:{f.key}": f.label for f in fields}}
        by_key = {f.key: f for f in fields}
        total = qs.count()

        def cell(e, column: str) -> str:
            match column:
                case "name":
                    return e.name
                case "phone":
                    return e.phone_e164 or e.phone
                case "email":
                    return e.email
                case "status":
                    return e.status.name
                case "owner":
                    return e.primary_owner.full_name if e.primary_owner else ""
                case "secondary_owners":
                    return ", ".join(o.user.full_name for o in e.secondary_owners.all())
                case "source":
                    return e.get_source_display()
                case "campaign":
                    return e.campaign_name
                case "adset":
                    return e.adset_name
                case "ad":
                    return e.ad_name
                case "form":
                    return e.form_id
                case "next_followup":
                    return format_datetime(e.next_followup_at, tz) if e.next_followup_at else ""
                case "repeat":
                    return "Yes" if e.is_repeat else "No"
                case "created":
                    return format_date(e.created_at, tz)
                case "updated":
                    return format_datetime(e.updated_at, tz)
            field = by_key[column[3:]]
            value = next((v for v in e.custom_values.all() if v.field_id == field.pk), None)
            raw = to_api(field, value.get_value()) if value else None
            if isinstance(raw, list):
                return ", ".join(raw)
            if isinstance(raw, bool):
                return "Yes" if raw else "No"
            return "" if raw is None else str(raw)

        writer = csv.writer(_Echo())
        rows_qs = with_list_data(qs).order_by(*ordering)

        tenant_id = request.tenant.pk

        def stream():
            # The response streams after the request transaction has ended, so the
            # tenant (and with it PostgreSQL RLS) must be set again for the reads.
            with tenant_context(tenant_id):
                yield "\ufeff"  # BOM: Excel reads UTF-8 (₹, –, Gujarati, Hindi) correctly
                yield writer.writerow([labels[c] for c in columns])
                for e in rows_qs.iterator(chunk_size=1000):
                    yield writer.writerow([cell(e, c) for c in columns])

        audit(
            tenant_id=request.tenant.pk,
            actor=request.user,
            action=EXPORT_ENQUIRIES,
            details={"rows": total, "columns": columns, "params": params},
            request=request,
        )
        stamp = timezone.localtime().strftime("%d-%m-%Y")
        response = StreamingHttpResponse(stream(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="enquiries-{stamp}.csv"'
        response["X-Total-Count"] = str(total)
        return response
