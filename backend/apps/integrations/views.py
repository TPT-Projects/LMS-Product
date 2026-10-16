"""/api/v1/integrations: the workspace's connected apps (Owner and Admin)."""

from urllib.parse import urlencode

from django.conf import settings
from django.http import Http404, HttpResponseRedirect
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Membership
from apps.meta_integration.models import MetaConnection, MetaForm
from apps.permissions.drf import require
from apps.permissions.roles import Capability
from common.phones import normalize_phone
from common.tenancy.context import tenant_context
from common.tenancy.permissions import IsTenantMember

from . import autocall, google, heartbeat, services, whatsapp
from .exotel import ExotelError, refresh_numbers
from .models import AutoCall, ExotelNumber, Integration, SheetLink

MANAGE = [require(Capability.MANAGE_INTEGRATIONS)]


def integration_or_404(request, app: str) -> Integration:
    services.known_app(app)
    integration = Integration.objects.filter(tenant_id=request.tenant.pk, app=app).first()
    if integration is None:
        raise Http404
    return integration


class IntegrationListView(APIView):
    permission_classes = MANAGE

    def get(self, request):
        return Response({"apps": services.overview(request.tenant.pk)})


class IntegrationView(APIView):
    """POST {values: {...}}: connect or update (checked with the provider first). DELETE: remove."""

    permission_classes = MANAGE

    def post(self, request, app: str):
        values = request.data.get("values") if isinstance(request.data, dict) else None
        integration = services.connect(
            request.tenant.pk, app, values, user=request.user, request=request
        )
        return Response(services.payload(integration))

    def delete(self, request, app: str):
        services.disconnect(integration_or_404(request, app), user=request.user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class IntegrationCheckView(APIView):
    """POST: test the stored connection again."""

    permission_classes = MANAGE

    def post(self, request, app: str):
        return Response(services.payload(services.check(integration_or_404(request, app))))


# --- heartbeat ------------------------------------------------------------------------
class HeartbeatView(APIView):
    """POST: run due work now (auto-calls, new leads, sheet rows, daily number refresh).

    Sent by the open LMS about every minute; any member's browser may trigger it.
    """

    permission_classes = [IsTenantMember]

    def post(self, request):
        return Response(heartbeat.run(request.tenant.pk))


class CallingView(APIView):
    """GET: is Exotel auto-calling of scheduled calls on? (any member: the schedule form)."""

    permission_classes = [IsTenantMember]

    def get(self, request):
        integration = autocall.exotel_for(request.tenant.pk)
        return Response(
            {
                "exotel_connected": integration is not None,
                "auto_call_followups": autocall.followups_enabled(request.tenant.pk),
                "call_window": autocall.call_window(integration),
            }
        )


# --- Exotel ------------------------------------------------------------------------
def _number(n: ExotelNumber) -> dict:
    return {
        "id": n.pk,
        "phone_number": n.phone_number,
        "friendly_name": n.friendly_name,
        "region": n.region,
        "country": n.country,
        "capabilities": n.capabilities,
        "added_manually": n.added_manually,
        "is_active": n.is_active,
        "active_since": n.active_since,
        "last_seen_at": n.last_seen_at,
    }


def _exotel_payload(integration: Integration) -> dict:
    numbers = ExotelNumber.objects.filter(tenant_id=integration.tenant_id)
    rules = integration.settings
    return {
        "numbers": [_number(n) for n in numbers],
        "refreshed_at": integration.synced_at,
        "settings": {
            "default_caller": rules.get("default_caller", ""),
            "auto_call_followups": bool(rules.get("auto_call_followups")),
            "new_lead_delay": autocall.new_lead_delay(integration),
            "call_window": autocall.call_window(integration),
            "fallback_agent": rules.get("fallback_agent"),
        },
    }


class ExotelView(APIView):
    """GET: numbers and auto-calling settings. PATCH: change the settings."""

    permission_classes = MANAGE

    def get(self, request):
        return Response(_exotel_payload(integration_or_404(request, "exotel")))

    def patch(self, request):
        integration = integration_or_404(request, "exotel")
        data = request.data if isinstance(request.data, dict) else {}
        rules = dict(integration.settings)
        if "default_caller" in data:
            phone = str(data["default_caller"] or "")
            if (
                phone
                and not ExotelNumber.objects.filter(
                    tenant_id=integration.tenant_id, phone_number=phone, is_active=True
                ).exists()
            ):
                raise ValidationError({"default_caller": [_("Choose one of your active numbers.")]})
            rules["default_caller"] = phone
        if "auto_call_followups" in data:
            rules["auto_call_followups"] = bool(data["auto_call_followups"])
        if "new_lead_delay" in data:
            try:
                delay = int(data["new_lead_delay"])
            except (TypeError, ValueError):
                delay = 0
            if delay not in autocall.NEW_LEAD_DELAYS:
                raise ValidationError({"new_lead_delay": [_("Choose 1, 2 or 5 minutes.")]})
            rules["new_lead_delay"] = delay
        if "call_window" in data and isinstance(data["call_window"], dict):
            rules["call_window"] = autocall.validate_window(data["call_window"])
        if "fallback_agent" in data:
            agent = data["fallback_agent"]
            if (
                agent
                and not Membership.objects.filter(
                    tenant_id=integration.tenant_id, user_id=agent, is_active=True
                ).exists()
            ):
                raise ValidationError({"fallback_agent": [_("Choose a member of this workspace.")]})
            rules["fallback_agent"] = int(agent) if agent else None
        integration.settings = rules
        integration.save(update_fields=["settings"])
        return Response(_exotel_payload(integration))


class ExotelRefreshView(APIView):
    """POST: load the account's numbers from Exotel now."""

    permission_classes = MANAGE

    def post(self, request):
        integration = integration_or_404(request, "exotel")
        try:
            refresh_numbers(integration)
        except ExotelError as exc:
            raise ValidationError({"detail": str(exc)}) from None
        return Response(_exotel_payload(integration))


class ExotelNumbersView(APIView):
    """POST {phone_number, friendly_name?}: add a number Exotel does not list (e.g. new)."""

    permission_classes = MANAGE

    def post(self, request):
        integration = integration_or_404(request, "exotel")
        phone = normalize_phone(
            str(request.data.get("phone_number") or ""), request.tenant.default_country
        )
        if not phone:
            raise ValidationError({"phone_number": [_("Enter a valid phone number.")]})
        number, created = ExotelNumber.objects.get_or_create(
            tenant_id=integration.tenant_id,
            phone_number=phone,
            defaults={
                "friendly_name": str(request.data.get("friendly_name") or "")[:120],
                "added_manually": True,
            },
        )
        if not created and number.is_active:
            raise ValidationError({"phone_number": [_("This number is already in the list.")]})
        number.is_active = True
        number.save()
        return Response(_exotel_payload(integration), status=status.HTTP_201_CREATED)


class ExotelNumberView(APIView):
    permission_classes = MANAGE

    def delete(self, request, number_id: int):
        integration = integration_or_404(request, "exotel")
        number = ExotelNumber.objects.filter(tenant_id=integration.tenant_id, pk=number_id).first()
        if number is None:
            raise Http404
        number.delete()
        if integration.settings.get("default_caller") == number.phone_number:
            integration.settings = {**integration.settings, "default_caller": ""}
            integration.save(update_fields=["settings"])
        return Response(_exotel_payload(integration))


class ExotelFormsView(APIView):
    """GET: the connected Meta forms with their auto-calling switch."""

    permission_classes = MANAGE

    def get(self, request):
        integration_or_404(request, "exotel")
        connection = MetaConnection.objects.filter(tenant_id=request.tenant.pk).first()
        forms = MetaForm.objects.filter(tenant_id=request.tenant.pk, is_connected=True)
        if connection and connection.page_id:
            forms = forms.filter(page_id=connection.page_id)
        return Response(
            {
                "page_name": connection.page_name if connection else "",
                "forms": [
                    {
                        "id": f.pk,
                        "name": f.name or f.form_id,
                        "form_id": f.form_id,
                        "leads_received": f.leads_received,
                        "auto_call": f.auto_call,
                    }
                    for f in forms
                ],
            }
        )


class ExotelFormView(APIView):
    """PATCH {auto_call: bool}: call each new lead of this form automatically."""

    permission_classes = MANAGE

    def patch(self, request, form_id: int):
        integration_or_404(request, "exotel")
        form = MetaForm.objects.filter(tenant_id=request.tenant.pk, pk=form_id).first()
        if form is None:
            raise Http404
        form.auto_call = bool(request.data.get("auto_call"))
        form.save(update_fields=["auto_call"])
        return Response({"id": form.pk, "auto_call": form.auto_call})


class AutoCallListView(APIView):
    """GET: the latest auto-calls (scheduled, placed, skipped) for the Exotel page."""

    permission_classes = MANAGE

    def get(self, request):
        calls = AutoCall.objects.filter(tenant_id=request.tenant.pk).select_related(
            "enquiry", "agent"
        )[:50]
        return Response(
            {
                "results": [
                    {
                        "id": c.pk,
                        "enquiry_id": c.enquiry_id,
                        "enquiry_name": c.enquiry.name,
                        "reason": c.reason,
                        "status": c.status,
                        "agent": getattr(c.agent, "full_name", ""),
                        "customer_phone": c.customer_phone,
                        "scheduled_at": c.scheduled_at,
                        "started_at": c.started_at,
                        "duration_seconds": c.duration_seconds,
                        "error": c.error,
                    }
                    for c in calls
                ]
            }
        )


class ExotelStatusWebhookView(APIView):
    """POST /webhooks/exotel/<token>: Exotel's call result (StatusCallback)."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request, token: str):
        tenant_id = autocall.tenant_from_callback(token)
        if tenant_id is None:
            raise Http404
        with tenant_context(tenant_id):
            autocall.apply_status_callback(tenant_id, request.data)
        return Response({"ok": True})


# --- WhatsApp (Facebook login) -----------------------------------------------------------
def _whatsapp_payload(integration: Integration) -> dict:
    return {
        "accounts": integration.settings.get("accounts", []),
        "phone_number_id": integration.config.get("phone_number_id", ""),
        "token_expires_at": integration.settings.get("token_expires_at"),
        "refreshed_at": integration.synced_at,
        "flow": integration.settings.get("flow", ""),
        "setup_issues": integration.settings.get("setup_issues", []),
        # The two-step verification PIN set when registering (Owners/Admins only see this page).
        "two_step_pin": integration.secrets.get("pin", ""),
    }


class WhatsAppSignupConfigView(APIView):
    """GET: what the browser needs to open Embedded Signup (app and configuration IDs)."""

    permission_classes = MANAGE

    def get(self, request):
        return Response(whatsapp.signup_config())


class WhatsAppEmbeddedView(APIView):
    """POST {code, waba_id?, phone_number_id?, flow: new|coexistence}: finish Embedded Signup."""

    permission_classes = MANAGE

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        if not data.get("code"):
            raise ValidationError({"detail": _("The WhatsApp signup did not finish.")})
        flow = (
            whatsapp.COEXISTENCE
            if data.get("flow") == whatsapp.COEXISTENCE
            else whatsapp.NEW_NUMBER
        )
        integration = whatsapp.complete_embedded(
            request.membership,
            code=str(data["code"]),
            waba_id=str(data.get("waba_id") or ""),
            phone_number_id=str(data.get("phone_number_id") or ""),
            flow=flow,
        )
        return Response(_whatsapp_payload(integration))


class WhatsAppRegisterView(APIView):
    """POST: register a number on the Cloud API (sets its two-step PIN)."""

    permission_classes = MANAGE

    def post(self, request, phone_number_id: str):
        integration = whatsapp.register_number(
            integration_or_404(request, "whatsapp"), phone_number_id
        )
        return Response(_whatsapp_payload(integration))


class WhatsAppConnectView(APIView):
    """POST: the Facebook login URL (opened in a popup)."""

    permission_classes = MANAGE

    def post(self, request):
        return Response({"url": whatsapp.start(request.membership)})


class WhatsAppView(APIView):
    """GET: accounts and numbers. PATCH {phone_number_id}: the number used for sending."""

    permission_classes = MANAGE

    def get(self, request):
        return Response(_whatsapp_payload(integration_or_404(request, "whatsapp")))

    def patch(self, request):
        integration = integration_or_404(request, "whatsapp")
        whatsapp.choose_number(integration, request.data.get("phone_number_id", ""))
        return Response(_whatsapp_payload(integration))


class WhatsAppRefreshView(APIView):
    permission_classes = MANAGE

    def post(self, request):
        integration = whatsapp.refresh(integration_or_404(request, "whatsapp"))
        return Response(_whatsapp_payload(integration))


# --- Google Sheets ------------------------------------------------------------------------
def _link(link: SheetLink) -> dict:
    return {
        "id": link.pk,
        "direction": link.direction,
        "form": link.form_id,
        "form_name": link.form.name if link.form_id else "",
        "spreadsheet_id": link.spreadsheet_id,
        "spreadsheet_name": link.spreadsheet_name,
        "sheet_title": link.sheet_title,
        "headers": link.headers,
        "mapping": link.mapping,
        "rows_imported": link.rows_imported,
        "last_row": link.last_row,
        "is_active": link.is_active,
        "last_synced_at": link.last_synced_at,
        "last_error": link.last_error,
    }


class GoogleConnectView(APIView):
    """POST: the Google login URL (opened in a popup)."""

    permission_classes = MANAGE

    def post(self, request):
        return Response({"url": google.start(request.membership)})


class GoogleCallbackView(APIView):
    """GET /api/integrations/google/callback/: Google returns the login popup here."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request):
        params = request.query_params
        done = f"{settings.FRONTEND_URL.rstrip('/')}/meta/oauth-done"
        code, state = params.get("code"), params.get("state")

        def fail(message: str):
            query = urlencode({"result": "error", "message": message, "app": google.APP})
            return HttpResponseRedirect(f"{done}?{query}")

        if not code or not state:
            return fail(params.get("error") or _("Login was cancelled."))
        try:
            membership = google.membership_from_state(state)
            with tenant_context(membership.tenant_id):
                google.complete(membership, code=code)
        except ValidationError as exc:
            detail = exc.detail.get("detail") if isinstance(exc.detail, dict) else exc.detail
            return fail(str(detail[0] if isinstance(detail, list) else detail))
        return HttpResponseRedirect(f"{done}?{urlencode({'result': 'ok', 'app': google.APP})}")


class SpreadsheetsView(APIView):
    """GET ?q=: the person's spreadsheets (newest first)."""

    permission_classes = MANAGE

    def get(self, request):
        integration = google.google_for(request.tenant.pk)
        query = request.query_params.get("q", "").strip()[:100]
        return Response({"results": google.list_spreadsheets(integration, query)})


class SpreadsheetTabsView(APIView):
    """GET: the tabs of a spreadsheet, each with its header row and a guessed mapping."""

    permission_classes = MANAGE

    def get(self, request, spreadsheet_id: str):
        integration = google.google_for(request.tenant.pk)
        return Response({"results": google.list_tabs(integration, spreadsheet_id)})


class SheetLinksView(APIView):
    """GET: connected sheets. POST: connect a tab (its rows become enquiries)."""

    permission_classes = MANAGE

    def get(self, request):
        links = SheetLink.objects.filter(tenant_id=request.tenant.pk).select_related("form")
        return Response({"results": [_link(link) for link in links]})

    def post(self, request):
        integration = google.google_for(request.tenant.pk)
        data = request.data if isinstance(request.data, dict) else {}
        if not data.get("spreadsheet_id") or not data.get("sheet_title"):
            raise ValidationError({"sheet_title": [_("Choose a spreadsheet and a tab.")]})
        link = google.create_link(
            integration,
            spreadsheet_id=str(data["spreadsheet_id"]),
            spreadsheet_name=str(data.get("spreadsheet_name") or ""),
            sheet_title=str(data["sheet_title"]),
            mapping=data.get("mapping") if isinstance(data.get("mapping"), dict) else None,
            import_existing=data.get("import_existing", True) is not False,
            user=request.user,
        )
        result = google.sync_link(link) if link.last_row == 1 else {"imported": 0}
        link.refresh_from_db()
        return Response({**_link(link), **result}, status=status.HTTP_201_CREATED)


class SheetExportsView(APIView):
    """POST {form: id|null, spreadsheet_id?, new_title?}: write a form's leads (or all
    enquiries) to a sheet and keep it up to date (new leads, status and other changes)."""

    permission_classes = MANAGE

    def post(self, request):
        integration = google.google_for(request.tenant.pk)
        data = request.data if isinstance(request.data, dict) else {}
        form = None
        if data.get("form") not in (None, ""):
            form = MetaForm.objects.filter(tenant_id=request.tenant.pk, pk=data["form"]).first()
            if form is None:
                raise ValidationError({"form": [_("Choose one of your forms.")]})
        link = google.create_export(
            integration,
            form=form,
            spreadsheet_id=str(data.get("spreadsheet_id") or ""),
            new_title=str(data.get("new_title") or ""),
            user=request.user,
        )
        return Response(_link(link), status=status.HTTP_201_CREATED)


class SheetLinkView(APIView):
    """PATCH {is_active}: pause or resume. DELETE: stop syncing (enquiries stay)."""

    permission_classes = MANAGE

    def _get(self, request, link_id: int) -> SheetLink:
        link = SheetLink.objects.filter(tenant_id=request.tenant.pk, pk=link_id).first()
        if link is None:
            raise Http404
        return link

    def patch(self, request, link_id: int):
        link = self._get(request, link_id)
        if "form" in request.data and link.direction == "export":
            form = None
            if request.data["form"] not in (None, ""):
                form = MetaForm.objects.filter(
                    tenant_id=request.tenant.pk, pk=request.data["form"]
                ).first()
                if form is None:
                    raise ValidationError({"form": [_("Choose one of your forms.")]})
            google.change_export_form(link, form, request.user)
        if "is_active" in request.data:
            link.is_active = bool(request.data["is_active"])
            link.save(update_fields=["is_active"])
        return Response(_link(link))

    def delete(self, request, link_id: int):
        self._get(request, link_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SheetLinkSyncView(APIView):
    """POST: import new rows of this sheet now."""

    permission_classes = MANAGE

    def post(self, request, link_id: int):
        link = SheetLink.objects.filter(tenant_id=request.tenant.pk, pk=link_id).first()
        if link is None:
            raise Http404
        if link.direction == "export":
            result = google.sync_export(link, force=True)
            result["imported"] = 0
        else:
            result = google.sync_link(link)
        link.refresh_from_db()
        return Response({**_link(link), **result})
