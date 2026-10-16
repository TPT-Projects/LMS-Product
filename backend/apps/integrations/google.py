"""Google Sheets: log in with Google (popup), pick a spreadsheet tab, and its rows become
enquiries. New rows added at the bottom are picked up every few minutes.

Google APIs used (read-only): Drive file list (spreadsheets only), Sheets values.
"""

from __future__ import annotations

import logging
import re
import secrets
import time
from datetime import timedelta
from typing import Any
from urllib.parse import quote, urlencode

import requests
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Membership
from apps.audit.service import INTEGRATION_CONNECTED, audit
from apps.enquiries.ingestion import EnquiryData, ingest_enquiry
from apps.enquiries.models import Source
from apps.tenants.models import Tenant

from .models import Integration, IntegrationStatus, SheetLink

logger = logging.getLogger(__name__)

APP = "google_sheets"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/drive.metadata.readonly",  # list spreadsheets
    "https://www.googleapis.com/auth/spreadsheets",  # read rows, write leads to a sheet
]
STATE_SALT = "google-oauth"
STATE_MAX_AGE = 15 * 60
TIMEOUT = 20
SYNC_EVERY = timedelta(minutes=5)
MAX_ROWS_PER_SYNC = 2000


class GoogleError(Exception):
    pass


class GoogleClient:
    def _call(self, method: str, url: str, token: str | None = None, **kwargs) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            response = requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            raise GoogleError(_("Could not reach Google. Try again in a moment.")) from exc
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code >= 400:
            error = body.get("error") if isinstance(body, dict) else None
            message = (
                (error.get("message") if isinstance(error, dict) else body.get("error_description"))
                if isinstance(body, dict)
                else None
            )
            raise GoogleError(message or str(error or f"Google error {response.status_code}"))
        return body

    def oauth_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "access_type": "offline",  # a refresh token, so syncing keeps working
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            }
        )
        return f"{AUTH_URL}?{query}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        return self._call(
            "POST",
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        return self._call(
            "POST",
            TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
            },
        )

    def user_email(self, token: str) -> str:
        return self._call("GET", "https://www.googleapis.com/oauth2/v3/userinfo", token).get(
            "email", ""
        )

    def list_spreadsheets(self, token: str, query: str = "") -> list[dict[str, Any]]:
        q = "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
        if query:
            safe = query.replace("\\", "").replace("'", "\\'")
            q += f" and name contains '{safe}'"
        body = self._call(
            "GET",
            "https://www.googleapis.com/drive/v3/files",
            token,
            params={
                "q": q,
                "fields": "files(id,name,modifiedTime,owners(displayName))",
                "orderBy": "modifiedTime desc",
                "pageSize": 100,
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },
        )
        return body.get("files", [])

    def list_tabs(self, token: str, spreadsheet_id: str) -> list[dict[str, Any]]:
        body = self._call(
            "GET",
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}",
            token,
            params={"fields": "properties(title),sheets(properties(sheetId,title,gridProperties))"},
        )
        return [s.get("properties", {}) for s in body.get("sheets", [])]

    def read_rows(
        self, token: str, spreadsheet_id: str, title: str, first: int, last: int | None = None
    ) -> list[list[str]]:
        """Rows `first`..`last` (1-based) of a tab; trailing empty rows are not returned."""
        escaped = title.replace("'", "''")
        cells = f"A{first}:ZZ{last}" if last else f"A{first}:ZZ"
        rng = quote(f"'{escaped}'!{cells}", safe="")
        body = self._call(
            "GET",
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{rng}",
            token,
            params={"valueRenderOption": "FORMATTED_VALUE"},
        )
        return [[str(c) for c in row] for row in body.get("values", [])]

    def create_spreadsheet(self, token: str, title: str) -> str:
        body = self._call(
            "POST",
            "https://sheets.googleapis.com/v4/spreadsheets",
            token,
            json={"properties": {"title": title}},
        )
        return body["spreadsheetId"]

    def add_tab(self, token: str, spreadsheet_id: str, title: str) -> None:
        self._call(
            "POST",
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}:batchUpdate",
            token,
            json={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        )

    def write_rows(self, token: str, spreadsheet_id: str, title: str, rows: list[list]) -> None:
        """Replace the tab's content with `rows` (row 1 = header)."""
        tab = "'" + title.replace("'", "''") + "'"
        base = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values"
        self._call("POST", f"{base}/{quote(tab, safe='')}:clear", token, json={})
        self._call(
            "PUT",
            f"{base}/{quote(tab + '!A1', safe='')}",
            token,
            params={"valueInputOption": "RAW"},
            json={"values": rows},
        )


_client: Any = None


def get_google():
    global _client
    if _client is None:
        _client = GoogleClient()
    return _client


def set_google(client: Any) -> None:
    """Tests swap in a fake; None restores the real client."""
    global _client
    _client = client


def configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


# --- login -----------------------------------------------------------------------------------
def start(membership: Membership) -> str:
    if not configured():
        raise ValidationError(
            {"detail": _("Google is not set up on the server yet (GOOGLE_CLIENT_ID / SECRET).")}
        )
    state = signing.dumps(
        {"t": membership.tenant_id, "u": membership.user_id, "n": secrets.token_urlsafe(8)},
        salt=STATE_SALT,
    )
    return get_google().oauth_url(state)


def membership_from_state(state: str) -> Membership:
    from apps.permissions.matrix import has_capability
    from apps.permissions.roles import Capability
    from common.tenancy.context import rls_bypass

    try:
        data = signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE)
    except signing.BadSignature:
        raise ValidationError(
            {"detail": _("This login link expired. Please connect again.")}
        ) from None
    with rls_bypass():
        membership = (
            Membership.objects.select_related("user", "tenant")
            .filter(tenant_id=data.get("t"), user_id=data.get("u"), is_active=True)
            .first()
        )
    if membership is None or not has_capability(membership.role, Capability.MANAGE_INTEGRATIONS):
        raise ValidationError({"detail": _("Only an Owner or Admin can connect apps.")})
    return membership


@transaction.atomic
def complete(membership: Membership, *, code: str) -> Integration:
    client = get_google()
    try:
        tokens = client.exchange_code(code)
        email = client.user_email(tokens["access_token"])
    except (GoogleError, KeyError) as exc:
        raise ValidationError({"detail": _("Google said: %s") % exc}) from None
    integration = Integration.objects.filter(tenant_id=membership.tenant_id, app=APP).first()
    if integration is None:
        integration = Integration(
            tenant_id=membership.tenant_id, app=APP, connected_by=membership.user
        )
    stored = integration.secrets if integration.pk else {}
    integration.secrets = {
        # Google sends a refresh token only on the first consent: keep the old one otherwise.
        "refresh_token": tokens.get("refresh_token") or stored.get("refresh_token", ""),
        "access_token": tokens["access_token"],
        "expires_at": str(int(time.time()) + int(tokens.get("expires_in", 3600)) - 60),
    }
    integration.config = {"email": email}
    integration.account_label = email
    integration.status = IntegrationStatus.CONNECTED
    integration.last_checked_at = timezone.now()
    integration.last_error = ""
    integration.save()
    audit(
        tenant_id=membership.tenant_id,
        actor=membership.user,
        action=INTEGRATION_CONNECTED,
        details={"app": APP, "account": email},
    )
    return integration


def access_token(integration: Integration) -> str:
    """A valid access token, refreshed with the stored refresh token when it expired."""
    stored = integration.secrets
    if stored.get("access_token") and int(stored.get("expires_at") or 0) > time.time():
        return stored["access_token"]
    if not stored.get("refresh_token"):
        raise ValidationError({"detail": _("Google access expired. Connect Google Sheets again.")})
    try:
        tokens = get_google().refresh(stored["refresh_token"])
    except GoogleError as exc:
        raise ValidationError({"detail": _("Google said: %s") % exc}) from None
    integration.secrets = {
        **stored,
        "access_token": tokens["access_token"],
        "expires_at": str(int(time.time()) + int(tokens.get("expires_in", 3600)) - 60),
    }
    integration.save(update_fields=["_secrets"])
    return tokens["access_token"]


def google_for(tenant_id: int) -> Integration:
    integration = Integration.objects.filter(tenant_id=tenant_id, app=APP).first()
    if integration is None:
        raise ValidationError({"detail": _("Connect Google Sheets first.")})
    return integration


def _google_call(fn, *args):
    try:
        return fn(*args)
    except GoogleError as exc:
        raise ValidationError({"detail": _("Google said: %s") % exc}) from None


def list_spreadsheets(integration: Integration, query: str = "") -> list[dict]:
    files = _google_call(get_google().list_spreadsheets, access_token(integration), query)
    return [
        {
            "id": f["id"],
            "name": f.get("name", ""),
            "modified_at": f.get("modifiedTime"),
            "owner": ((f.get("owners") or [{}])[0]).get("displayName", ""),
        }
        for f in files
    ]


def list_tabs(integration: Integration, spreadsheet_id: str) -> list[dict]:
    token = access_token(integration)
    tabs = _google_call(get_google().list_tabs, token, spreadsheet_id)
    result = []
    for tab in tabs:
        title = tab.get("title", "")
        header = _google_call(get_google().read_rows, token, spreadsheet_id, title, 1, 1)
        headers = [h.strip() for h in (header[0] if header else [])]
        result.append(
            {
                "title": title,
                "rows": tab.get("gridProperties", {}).get("rowCount"),
                "headers": headers,
                "mapping": detect_mapping(headers),
            }
        )
    return result


# --- mapping and sync ---------------------------------------------------------------------------
PATTERNS = {
    "name": (
        r"^(full[\s_-]*name|name|customer[\s_-]*name|lead[\s_-]*name"
        r"|client[\s_-]*name|first[\s_-]*name)$"
    ),
    "phone": r"(phone|mobile|contact[\s_-]*(no|number)?|whats\s*app|number|cell)",
    "email": r"(e-?mail)",
}


def detect_mapping(headers: list[str]) -> dict[str, str]:
    """Which column holds the name, phone and email, guessed from the header row."""
    mapping: dict[str, str] = {}
    for field, pattern in PATTERNS.items():
        for header in headers:
            if header and header not in mapping.values() and re.search(pattern, header.lower()):
                mapping[field] = header
                break
    return mapping


def create_link(
    integration: Integration,
    *,
    spreadsheet_id: str,
    spreadsheet_name: str,
    sheet_title: str,
    mapping: dict | None,
    import_existing: bool,
    user,
) -> SheetLink:
    token = access_token(integration)
    header = _google_call(get_google().read_rows, token, spreadsheet_id, sheet_title, 1, 1)
    headers = [h.strip() for h in (header[0] if header else [])]
    if not headers:
        raise ValidationError({"sheet_title": [_("The first row must hold the column names.")]})
    chosen = {k: v for k, v in (mapping or detect_mapping(headers)).items() if v in headers}
    if not chosen.get("phone") and not chosen.get("email"):
        raise ValidationError(
            {"mapping": [_("Choose the column with the phone number or the email.")]}
        )
    last_row = 1
    if not import_existing:  # only rows added from now on
        existing = _google_call(get_google().read_rows, token, spreadsheet_id, sheet_title, 2)
        last_row = 1 + len(existing)
    link, created = SheetLink.objects.get_or_create(
        tenant_id=integration.tenant_id,
        spreadsheet_id=spreadsheet_id,
        sheet_title=sheet_title,
        defaults={"last_row": last_row, "created_by": user},
    )
    if not created:
        raise ValidationError({"sheet_title": [_("This sheet is already connected.")]})
    link.spreadsheet_name = spreadsheet_name[:255]
    link.headers = headers
    link.mapping = chosen
    link.save()
    return link


def sync_link(link: SheetLink) -> dict:
    """Import rows added since the last sync. Returns {"imported": n}."""
    integration = google_for(link.tenant_id)
    token = access_token(integration)
    first = link.last_row + 1
    try:
        rows = get_google().read_rows(
            token, link.spreadsheet_id, link.sheet_title, first, first + MAX_ROWS_PER_SYNC - 1
        )
    except GoogleError as exc:
        link.last_error = str(exc)
        link.last_synced_at = timezone.now()
        link.save(update_fields=["last_error", "last_synced_at"])
        return {"imported": 0, "error": str(exc)}

    tenant = Tenant.objects.get(pk=link.tenant_id)
    index = {h: i for i, h in enumerate(link.headers)}
    imported = 0
    for offset, row in enumerate(rows):
        values = {h: (row[i].strip() if i < len(row) else "") for h, i in index.items()}

        def cell(field: str, values=values) -> str:
            return values.get(link.mapping.get(field, ""), "")

        if not (cell("phone") or cell("email")):
            continue  # empty or incomplete row
        data = EnquiryData(
            name=cell("name"),
            phone=cell("phone"),
            email=cell("email"),
            source=Source.GOOGLE_SHEETS,
            campaign_name=link.spreadsheet_name[:255],
            extra_details={
                "sheet": f"{link.spreadsheet_name} › {link.sheet_title}",
                "row": first + offset,
                "values": {k: v for k, v in values.items() if v},
            },
        )
        with transaction.atomic():
            ingest_enquiry(tenant=tenant, data=data, actor=None)
        imported += 1
    link.last_row = first + len(rows) - 1 if rows else link.last_row
    link.rows_imported += imported
    link.last_synced_at = timezone.now()
    link.last_error = ""
    link.save(update_fields=["last_row", "rows_imported", "last_synced_at", "last_error"])
    return {"imported": imported}


# --- export: enquiries -> sheet -----------------------------------------------------------------
EXPORT_EVERY = timedelta(minutes=1)
EXPORT_MAX_ROWS = 10_000


def _export_rows(link: SheetLink) -> list[list[str]]:
    from apps.customfields.models import CustomField
    from apps.enquiries.models import Enquiry

    fields = list(CustomField.objects.filter(tenant_id=link.tenant_id).order_by("order", "id"))
    header = [
        str(_("Enquiry ID")), str(_("Created")), str(_("Name")), str(_("Phone")),
        str(_("Email")), str(_("Status")), str(_("Owner")), str(_("Source")),
        str(_("Campaign")), str(_("Ad set")), str(_("Ad")), str(_("Form")),
        *[f.label for f in fields],
    ]  # fmt: skip
    enquiries = (
        Enquiry.objects.filter(tenant_id=link.tenant_id, deleted_at__isnull=True)
        .select_related("status", "primary_owner")
        .order_by("created_at", "id")
    )
    if link.form_id:
        enquiries = enquiries.filter(form_id=link.form.form_id)
    values = _custom_values(link.tenant_id, fields)
    form_name = link.form.name if link.form_id else ""
    rows = [header]
    for e in enquiries[:EXPORT_MAX_ROWS]:
        own = values.get(e.pk, {})
        rows.append(
            [
                str(e.pk),
                timezone.localtime(e.created_at).strftime("%d/%m/%Y %H:%M"),
                e.name,
                e.phone_e164 or e.phone,
                e.email,
                e.status.name if e.status_id else "",
                e.primary_owner.full_name if e.primary_owner_id else "",
                e.get_source_display(),
                e.campaign_name,
                e.adset_name,
                e.ad_name,
                form_name or e.form_id,
                *[own.get(f.pk, "") for f in fields],
            ]
        )
    return rows


def _custom_values(tenant_id: int, fields) -> dict[int, dict[int, str]]:
    """{enquiry_id: {field_id: text}} for the export (one query)."""
    from apps.customfields.models import EnquiryCustomValue

    result: dict[int, dict[int, str]] = {}
    for v in EnquiryCustomValue.objects.filter(tenant_id=tenant_id, field__in=fields):
        if v.value_list:
            text = ", ".join(str(item) for item in v.value_list)
        elif v.value_date:
            text = v.value_date.strftime("%d/%m/%Y")
        elif v.value_bool is not None:
            text = str(_("Yes")) if v.value_bool else str(_("No"))
        elif v.value_number is not None:
            text = f"{v.value_number:g}"
        else:
            text = v.value_text or ""
        result.setdefault(v.enquiry_id, {})[v.field_id] = text
    return result


def create_export(
    integration: Integration,
    *,
    form,
    spreadsheet_id: str = "",
    new_title: str = "",
    user,
) -> SheetLink:
    """Send leads to a sheet: a new spreadsheet, or a new tab in an existing one (never
    overwriting a tab that already holds data)."""
    token = access_token(integration)
    ensure_form_connected(form, user)
    label = form.name if form else str(_("All enquiries"))
    tab = f"LMS - {label}"[:90]
    client = get_google()
    try:
        if spreadsheet_id:
            client.add_tab(token, spreadsheet_id, tab)
            name = next(
                (s["name"] for s in list_spreadsheets(integration) if s["id"] == spreadsheet_id),
                spreadsheet_id,
            )
        else:
            name = (new_title or f"LMS - {label}")[:200]
            spreadsheet_id = client.create_spreadsheet(token, name)
            tabs = client.list_tabs(token, spreadsheet_id)
            # write into the new spreadsheet's first (empty) tab
            tab = tabs[0]["title"] if tabs else "Sheet1"
    except GoogleError as exc:
        message = str(exc)
        if "insufficient" in message.lower() or "permission" in message.lower():
            message = str(_("Google did not allow editing sheets. Log in to Google again."))
        raise ValidationError({"detail": _("Google said: %s") % message}) from None
    link = SheetLink.objects.create(
        tenant_id=integration.tenant_id,
        direction="export",
        form=form,
        spreadsheet_id=spreadsheet_id,
        spreadsheet_name=name,
        sheet_title=tab,
        created_by=user,
    )
    sync_export(link)
    return link


def ensure_form_connected(form, user) -> None:
    """A form sent to a sheet must be switched on, or its leads never reach the LMS."""
    if form is not None and not form.is_connected:
        from apps.meta_integration.services import set_form_connected

        set_form_connected(form, connected=True, user=user)


def change_export_form(link: SheetLink, form, user) -> SheetLink:
    ensure_form_connected(form, user)
    link.form = form
    link.content_hash = ""  # rewrite the sheet with the new form's leads
    link.save(update_fields=["form", "content_hash"])
    sync_export(link, force=True)
    return link


def sync_export(link: SheetLink, *, force: bool = False) -> dict:
    """Write the enquiries to the sheet when something changed since the last write."""
    import hashlib
    import json

    rows = _export_rows(link)
    digest = hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()
    now = timezone.now()
    if digest == link.content_hash and not force:
        link.last_synced_at = now
        link.save(update_fields=["last_synced_at"])
        return {"written": 0}
    try:
        get_google().write_rows(
            access_token(google_for(link.tenant_id)),
            link.spreadsheet_id,
            link.sheet_title,
            rows,
        )
    except GoogleError as exc:
        link.last_error, link.last_synced_at = str(exc), now
        link.save(update_fields=["last_error", "last_synced_at"])
        return {"written": 0, "error": str(exc)}
    link.content_hash = digest
    link.rows_imported = len(rows) - 1  # rows in the sheet
    link.last_row = len(rows)
    link.last_synced_at, link.last_error = now, ""
    link.save(
        update_fields=["content_hash", "rows_imported", "last_row", "last_synced_at", "last_error"]
    )
    return {"written": len(rows) - 1}


def sync_due(tenant_id: int) -> int:
    """Heartbeat: import sheets every SYNC_EVERY, export sheets every EXPORT_EVERY."""
    now = timezone.now()
    export_due = Q(direction="export") & (
        Q(last_synced_at__isnull=True) | Q(last_synced_at__lt=now - EXPORT_EVERY)
    )
    for link_id in (
        SheetLink.objects.filter(tenant_id=tenant_id, is_active=True)
        .filter(export_due)
        .values_list("id", flat=True)
    ):
        if SheetLink.objects.filter(pk=link_id).filter(export_due).update(last_synced_at=now):
            try:
                with transaction.atomic():
                    sync_export(SheetLink.objects.select_related("form").get(pk=link_id))
            except ValidationError as exc:
                logger.warning("Sheet export %s failed: %s", link_id, exc)
    due = Q(direction="import") & (
        Q(last_synced_at__isnull=True) | Q(last_synced_at__lt=now - SYNC_EVERY)
    )
    total = 0
    for link_id in (
        SheetLink.objects.filter(tenant_id=tenant_id, is_active=True)
        .filter(due)
        .values_list("id", flat=True)
    ):
        claimed = SheetLink.objects.filter(pk=link_id).filter(due).update(last_synced_at=now)
        if not claimed:
            continue
        try:
            with transaction.atomic():
                total += sync_link(SheetLink.objects.get(pk=link_id))["imported"]
        except ValidationError as exc:
            logger.warning("Sheet sync %s failed: %s", link_id, exc)
    return total
