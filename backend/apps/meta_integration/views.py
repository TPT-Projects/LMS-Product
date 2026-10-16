"""/api/v1/meta/* (Owner and Admin only) and the public webhook /webhooks/meta."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.utils.translation import gettext as _
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permissions.drf import require
from apps.permissions.roles import Capability
from common.tenancy.context import rls_bypass, tenant_context
from common.tenancy.permissions import IsTenantMember

from . import capi, formdata, services
from .leads import handle_webhook_change
from .models import (
    ConnectionStatus,
    ConversionEvent,
    FailedSyncLog,
    MetaConnection,
    MetaForm,
    SyncLog,
    SyncSource,
)

logger = logging.getLogger(__name__)
MANAGE_META = [require(Capability.MANAGE_META)]


def connection_or_404(request) -> MetaConnection:
    connection = services.connection_for(request.tenant.pk)
    if connection is None:
        raise Http404
    return connection


def connected(request) -> MetaConnection:
    connection = connection_or_404(request)
    if connection.status != ConnectionStatus.CONNECTED:
        raise ValidationError({"detail": _("Connect a Page first.")})
    return connection


# --- connection ---------------------------------------------------------------------------
class StatusView(APIView):
    permission_classes = MANAGE_META

    def get(self, request):
        data = services.status_payload(services.connection_for(request.tenant.pk))
        data["app_configured"] = bool(settings.META_APP_ID and settings.META_APP_SECRET)
        data["webhook_url"] = request.build_absolute_uri("/webhooks/meta")
        data["redirect_uri"] = settings.META_OAUTH_REDIRECT_URI
        return Response(data)


class ConnectView(APIView):
    """Step 1: returns the Facebook login URL."""

    permission_classes = MANAGE_META

    def post(self, request):
        if not (settings.META_APP_ID and settings.META_APP_SECRET):
            raise ValidationError(
                {"detail": _("The Meta app is not set up yet (META_APP_ID / META_APP_SECRET).")}
            )
        return Response({"url": services.start_oauth(request.membership)})


def _done_url(done: str, message: str, app: str = "") -> str:
    return f"{done}?{urlencode({'result': 'error', 'message': message, 'app': app})}"


class OAuthReturnView(APIView):
    """GET /api/meta/callback/ : Facebook returns the login popup here.

    The browser carries no API token on this redirect, so the signed `state`
    (tenant + user, 15 minutes) identifies who started the login. The popup is
    then sent to a small frontend page that tells the main window and closes.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request):
        params = request.query_params
        done = f"{settings.FRONTEND_URL.rstrip('/')}/meta/oauth-done"
        code, state = params.get("code"), params.get("state")
        purpose = services.state_purpose(state) if state else "meta"
        app = "" if purpose == "meta" else purpose
        if not code or not state:
            reason = params.get("error_description") or _("Login was cancelled.")
            return HttpResponseRedirect(_done_url(done, reason, app))
        try:
            membership = services.membership_from_state(state)
            with tenant_context(membership.tenant_id):
                if purpose == "whatsapp":
                    from apps.integrations import whatsapp

                    whatsapp.complete(membership, code=code)
                else:
                    services.complete_oauth(membership, code=code, state=state)
        except ValidationError as exc:
            detail = exc.detail.get("detail") if isinstance(exc.detail, dict) else exc.detail
            message = str(detail[0] if isinstance(detail, list) else detail)
            return HttpResponseRedirect(_done_url(done, message, app))
        return HttpResponseRedirect(f"{done}?{urlencode({'result': 'ok', 'app': app})}")


class PagesView(APIView):
    permission_classes = MANAGE_META

    def get(self, request):
        return Response({"pages": services.list_pages(connection_or_404(request))})


class PageView(APIView):
    """Step 3: choose ONE Page."""

    permission_classes = MANAGE_META

    def post(self, request):
        page_id = str(request.data.get("page_id") or "")
        if not page_id:
            raise ValidationError({"page_id": [_("Choose a Page.")]})
        connection = services.select_page(
            connection_or_404(request), page_id=page_id, user=request.user
        )
        return Response(services.status_payload(connection))


class CheckAccessView(APIView):
    """Step 4: "Check again" after granting Leads Access in Business Suite."""

    permission_classes = MANAGE_META

    def post(self, request):
        return Response(services.status_payload(services.check_access(connected(request))))


class ConnectionView(APIView):
    permission_classes = MANAGE_META

    def delete(self, request):
        services.disconnect(connection_or_404(request), user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SettingsView(APIView):
    permission_classes = MANAGE_META

    def patch(self, request):
        connection = connection_or_404(request)
        if "detect_ad_details" in request.data:
            connection.detect_ad_details = bool(request.data["detect_ad_details"])
            connection.save(update_fields=["detect_ad_details"])
        if "auto_connect_forms" in request.data:
            services.set_auto_connect(
                connection, bool(request.data["auto_connect_forms"]), user=request.user
            )
        return Response(services.status_payload(connection))


def _flag(value, default: bool) -> bool:
    if value is None:
        return default
    return value is True or str(value).lower() in ("1", "true", "yes")


class SyncNowView(APIView):
    """POST {days: 1|7|30, restore_deleted?: bool, form?: id}: pull recent leads now.

    restore_deleted defaults to true (the "Sync leads" button). The automatic sync after
    connecting a Page or switching a form on sends false, and `form` for a single form.
    """

    permission_classes = MANAGE_META

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        try:
            days = int(data.get("days", 7))
        except (TypeError, ValueError):
            raise ValidationError({"days": [_("Choose 1, 7 or 30 days.")]}) from None
        form = None
        if data.get("form") not in (None, ""):
            form = MetaForm.objects.filter(pk=data["form"], is_connected=True).first()
            if form is None:
                raise ValidationError({"form": [_("Connect this form first.")]})
        result = services.sync_leads(
            connected(request),
            days=days,
            restore_deleted=_flag(data.get("restore_deleted"), True),
            form=form,
        )
        return Response(result)


class ConversionsView(APIView):
    """GET / PATCH {enabled, dataset_id, token}: Conversions API settings (lead feedback)."""

    permission_classes = MANAGE_META

    def get(self, request):
        connection = services.connection_for(request.tenant.pk)
        events = ConversionEvent.objects.filter(tenant_id=request.tenant.pk)[:30]
        return Response(
            {**capi.settings_payload(connection), "events": [capi.event_payload(e) for e in events]}
        )

    def patch(self, request):
        connection = connection_or_404(request)
        data = request.data if isinstance(request.data, dict) else {}
        if "dataset_id" in data:
            dataset = str(data["dataset_id"] or "").strip()
            if dataset and not dataset.isdigit():
                raise ValidationError({"dataset_id": [_("The dataset ID is a number.")]})
            connection.capi_dataset_id = dataset
        if data.get("token"):
            connection.capi_token = str(data["token"]).strip()
        if "enabled" in data:
            enabled = bool(data["enabled"])
            if enabled and not (connection.capi_dataset_id and connection._capi_token):
                raise ValidationError(
                    {"detail": _("Enter the dataset ID and the access token first.")}
                )
            connection.capi_enabled = enabled
        connection.save(update_fields=["capi_dataset_id", "_capi_token", "capi_enabled"])
        return self.get(request)


class ConversionTestView(APIView):
    """POST {test_event_code}: send the latest Meta lead's status to Meta's Test Events."""

    permission_classes = MANAGE_META

    def post(self, request):
        from apps.enquiries.models import Enquiry

        enquiry = (
            Enquiry.objects.filter(tenant_id=request.tenant.pk, deleted_at__isnull=True)
            .exclude(leadgen_id__isnull=True)
            .exclude(leadgen_id="")
            .select_related("status")
            .order_by("-created_at")
            .first()
        )
        if enquiry is None:
            raise ValidationError({"detail": capi.no_lead_error()})
        event = capi.send(
            enquiry,
            enquiry.status.name,
            test_event_code=str(request.data.get("test_event_code") or ""),
        )
        if event is None:
            raise ValidationError(
                {"detail": _("Turn on lead feedback and save the settings first.")}
            )
        return Response(capi.event_payload(event))


class PollView(APIView):
    """POST: quick check for new leads, sent by the open LMS about every minute.

    Any member's browser may trigger it; the server runs at most one check per minute.
    """

    permission_classes = [IsTenantMember]

    def post(self, request):
        return Response(services.poll_new_leads(request.tenant.pk))


# --- forms ----------------------------------------------------------------------------------
class MetaFormSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = MetaForm
        fields = [
            "id", "form_id", "name", "status_on_meta", "created_time", "is_connected",
            "connected_at", "leads_received", "last_lead_at", "question_count",
        ]  # fmt: skip

    def get_question_count(self, obj) -> int:
        return len(obj.questions)


class FormListView(generics.ListAPIView):
    permission_classes = MANAGE_META
    serializer_class = MetaFormSerializer

    def get_queryset(self):
        """Forms of the connected Page only, optionally searched by name or form id."""
        connection = services.connection_for(self.request.tenant.pk)
        forms = MetaForm.objects.filter(tenant=self.request.tenant).exclude(
            name="", is_connected=False
        )
        if connection and connection.page_id:
            mine = forms.filter(page_id=connection.page_id)
            if not mine.exists() and connection.status == ConnectionStatus.CONNECTED:
                try:  # forms saved before Pages were recorded: look them up once
                    services.refresh_forms(connection)
                except ValidationError:
                    pass
            forms = forms.filter(page_id=connection.page_id)
        if q := self.request.query_params.get("q", "").strip()[:100]:
            forms = forms.filter(Q(name__icontains=q) | Q(form_id__icontains=q))
        return forms


class FormRefreshView(APIView):
    permission_classes = MANAGE_META

    def post(self, request):
        forms = services.refresh_forms(connected(request))
        return Response({"refreshed": len(forms)})


def form_or_404(request, form_pk: int) -> MetaForm:
    form = MetaForm.objects.filter(tenant=request.tenant, pk=form_pk).first()
    if form is None:
        raise Http404
    return form


class FormConnectView(APIView):
    permission_classes = MANAGE_META
    connect = True

    def post(self, request, form_pk: int):
        if self.connect:
            connected(request)
        form = services.set_form_connected(
            form_or_404(request, form_pk), connected=self.connect, user=request.user
        )
        return Response(MetaFormSerializer(form).data)


class FormMappingView(APIView):
    """GET: questions + sample answers + mapping. PUT: [{question, target_type, custom_field}]."""

    permission_classes = MANAGE_META

    def get(self, request, form_pk: int):
        return Response(services.mapping_for(form_or_404(request, form_pk)))

    def put(self, request, form_pk: int):
        rows = request.data.get("questions") if isinstance(request.data, dict) else None
        if not isinstance(rows, list):
            raise ValidationError({"questions": [_("Send a list of questions.")]})
        return Response(services.save_mapping(form_or_404(request, form_pk), rows))


# --- sync history ---------------------------------------------------------------------------
class SyncLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncLog
        fields = [
            "id",
            "leadgen_id",
            "form_id",
            "status",
            "source",
            "enquiry_id",
            "message",
            "created_at",
        ]


class FailedSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = FailedSyncLog
        fields = [
            "id", "leadgen_id", "form_id", "error", "attempts", "resolved_at",
            "last_attempt_at", "created_at",
        ]  # fmt: skip


class SyncLogListView(generics.ListAPIView):
    permission_classes = MANAGE_META
    serializer_class = SyncLogSerializer

    def get_queryset(self):
        qs = SyncLog.objects.filter(tenant=self.request.tenant)
        if value := self.request.query_params.get("status"):
            qs = qs.filter(status=value)
        return qs

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data["stored_by_status"] = formdata.count_by_status(request.tenant.pk)
        return response


class FailedSyncListView(generics.ListAPIView):
    permission_classes = MANAGE_META
    serializer_class = FailedSyncSerializer

    def get_queryset(self):
        qs = FailedSyncLog.objects.filter(tenant=self.request.tenant)
        if self.request.query_params.get("all") != "1":
            qs = qs.filter(resolved_at__isnull=True)
        return qs


class RetryView(APIView):
    """Retry one failed lead now. Never creates a duplicate (leadgen_id is unique)."""

    permission_classes = MANAGE_META

    def post(self, request, failed_id: int):
        failed = FailedSyncLog.objects.filter(tenant=request.tenant, pk=failed_id).first()
        if failed is None:
            raise Http404
        result = handle_webhook_change(request.tenant.pk, failed.payload, source=SyncSource.RETRY)
        return Response(
            {"status": result.status, "enquiry_id": result.enquiry_id, "message": result.message}
        )


# --- webhook -------------------------------------------------------------------------------------
def valid_signature(body: bytes, header: str) -> bool:
    secret = settings.META_APP_SECRET
    if not secret or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


class MetaWebhookView(APIView):
    """GET: Meta's verification handshake. POST: lead events (signature checked).

    Replies at once; the work happens in a background job (idempotent on leadgen_id).
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request):
        params = request.query_params
        token = settings.META_WEBHOOK_VERIFY_TOKEN
        if (
            params.get("hub.mode") == "subscribe"
            and token
            and hmac.compare_digest(params.get("hub.verify_token", ""), token)
        ):
            return HttpResponse(params.get("hub.challenge", ""), content_type="text/plain")
        return HttpResponse(status=403)

    def post(self, request):
        body = request._request.body
        if not valid_signature(body, request.headers.get("X-Hub-Signature-256", "")):
            return HttpResponse(status=403)
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return HttpResponse(status=400)

        from .tasks import process_lead

        queued = 0
        for entry in payload.get("entry", []) if payload.get("object") == "page" else []:
            for change in entry.get("changes", []):
                value = change.get("value") or {}
                if change.get("field") != "leadgen" or not value.get("leadgen_id"):
                    continue
                page_id = str(value.get("page_id") or entry.get("id") or "")
                value["page_id"] = page_id
                # Which workspace owns this Page? (a Page belongs to one workspace only)
                with rls_bypass():
                    tenant_id = (
                        MetaConnection.objects.filter(
                            page_id=page_id, status=ConnectionStatus.CONNECTED
                        )
                        .values_list("tenant_id", flat=True)
                        .first()
                    )
                if tenant_id is None:
                    continue  # events from any other Page are ignored
                formdata.save_raw_event(
                    tenant_id,
                    leadgen_id=str(value["leadgen_id"]),
                    page_id=page_id,
                    form_id=str(value.get("form_id", "")),
                    raw=change,
                )
                transaction.on_commit(
                    lambda t=tenant_id, v=dict(value): process_lead.delay(t, v, SyncSource.WEBHOOK)
                )
                queued += 1
        return Response({"queued": queued})
