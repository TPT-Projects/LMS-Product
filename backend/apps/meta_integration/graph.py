"""Thin client for the Meta Graph API. Only the calls the LMS needs.

Every call raises GraphError with Meta's message, so views can show it and
sync logs can record it. Tests replace `get_graph()` with a fake.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import urlencode

import requests
from django.conf import settings

LEAD_FIELDS = (
    "id,created_time,field_data,form_id,ad_id,ad_name,adset_id,adset_name,"
    "campaign_id,campaign_name,platform,is_organic"
)
TIMEOUT = 15


class GraphError(Exception):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class GraphClient:
    def __init__(self, version: str | None = None):
        self.version = version or settings.META_GRAPH_VERSION
        self.base = f"https://graph.facebook.com/{self.version}"

    # --- low level ----------------------------------------------------------------
    def _request(self, method: str, path: str, token: str | None = None, **params) -> dict:
        if token:
            params["access_token"] = token
        try:
            response = requests.request(
                method,
                f"{self.base}/{path.lstrip('/')}",
                params=params if method == "GET" else None,
                data=params if method != "GET" else None,
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            raise GraphError(f"Could not reach Meta: {exc.__class__.__name__}") from exc
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code >= 400 or "error" in body:
            error = body.get("error", {})
            raise GraphError(
                error.get("message") or f"Meta error {response.status_code}", error.get("code")
            )
        return body

    def _paged(self, path: str, token: str, **params) -> list[dict]:
        items, after = [], None
        for _ in range(50):  # safety limit
            if after:
                params["after"] = after
            body = self._request("GET", path, token, **params)
            items.extend(body.get("data", []))
            after = body.get("paging", {}).get("cursors", {}).get("after")
            if not after or not body.get("paging", {}).get("next"):
                break
        return items

    # --- OAuth --------------------------------------------------------------------
    def oauth_url(self, state: str, scopes: list[str] | None = None) -> str:
        query = urlencode(
            {
                "client_id": settings.META_APP_ID,
                "redirect_uri": settings.META_OAUTH_REDIRECT_URI,
                "state": state,
                "scope": ",".join(scopes or settings.META_OAUTH_SCOPES),
                "response_type": "code",
            }
        )
        return f"https://www.facebook.com/{self.version}/dialog/oauth?{query}"

    def exchange_code(self, code: str) -> tuple[str, int | None]:
        """Code -> long-lived user token. Returns (token, expires_at_unix or None)."""
        short = self._request(
            "GET",
            "oauth/access_token",
            client_id=settings.META_APP_ID,
            client_secret=settings.META_APP_SECRET,
            redirect_uri=settings.META_OAUTH_REDIRECT_URI,
            code=code,
        )
        long = self._request(
            "GET",
            "oauth/access_token",
            grant_type="fb_exchange_token",
            client_id=settings.META_APP_ID,
            client_secret=settings.META_APP_SECRET,
            fb_exchange_token=short["access_token"],
        )
        expires_in = long.get("expires_in")
        return long["access_token"], (int(time.time()) + int(expires_in)) if expires_in else None

    # --- Pages, forms, leads ------------------------------------------------------
    def list_pages(self, user_token: str) -> list[dict]:
        """[{id, name, access_token}] of every Page the person can connect, sorted by name.

        `me/accounts` only lists Pages where the person's own profile has a role. Pages
        reached through a Business Manager are missing there, so more Page ids are
        collected from: the Pages ticked in the login popup, the Pages promoted by the
        person's ad accounts, and their businesses' Pages. Each is then looked up to get
        its Page token; Pages without a token (no access) are left out.
        """
        own = self._paged("me/accounts", user_token, fields="id,name,access_token", limit=100)
        pages = {p["id"]: p for p in own if p.get("access_token")}
        candidates = (
            self.granted_page_ids(user_token)
            | self._ad_account_page_ids(user_token)
            | self._business_page_ids(user_token)
        ) - pages.keys()
        for page in self._lookup_pages(sorted(candidates), user_token):
            pages[page["id"]] = page
        return sorted(pages.values(), key=lambda p: p.get("name", "").lower())

    def _ad_account_page_ids(self, user_token: str) -> set[str]:
        """Pages promoted by the person's ad accounts (one request, field expansion)."""
        try:
            accounts = self._paged(
                "me/adaccounts", user_token, fields="promote_pages.limit(100){id}", limit=100
            )
        except GraphError:
            return set()
        return {str(p["id"]) for a in accounts for p in a.get("promote_pages", {}).get("data", [])}

    def _business_page_ids(self, user_token: str) -> set[str]:
        """Needs business_management; without it Meta refuses and nothing is added."""
        try:
            businesses = self._paged(
                "me/businesses",
                user_token,
                fields="owned_pages.limit(100){id},client_pages.limit(100){id}",
                limit=100,
            )
        except GraphError:
            return set()
        return {
            str(p["id"])
            for b in businesses
            for edge in ("owned_pages", "client_pages")
            for p in b.get(edge, {}).get("data", [])
        }

    def _lookup_pages(self, page_ids: list[str], user_token: str) -> list[dict]:
        """Name and Page token for each id (in parallel); ids without access are skipped."""

        def lookup(page_id: str) -> dict | None:
            try:
                return self._request("GET", page_id, user_token, fields="id,name,access_token")
            except GraphError:
                return None

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lookup, page_ids))
        return [p for p in results if p and p.get("access_token")]

    def list_whatsapp_accounts(self, user_token: str) -> list[dict]:
        """WhatsApp Business Accounts the person allowed, each with its phone numbers.

        Ids come from the login's granular scopes (whatsapp_business_management) and, when
        business_management was granted, from their businesses.
        """
        ids = self._granted_ids(user_token, ("whatsapp_business_management",))
        try:
            businesses = self._paged(
                "me/businesses",
                user_token,
                fields="owned_whatsapp_business_accounts{id},client_whatsapp_business_accounts{id}",
                limit=100,
            )
        except GraphError:
            businesses = []
        for business in businesses:
            for edge in ("owned_whatsapp_business_accounts", "client_whatsapp_business_accounts"):
                ids.update(str(w["id"]) for w in business.get(edge, {}).get("data", []))

        def lookup(waba_id: str) -> dict | None:
            try:
                return self._request(
                    "GET",
                    waba_id,
                    user_token,
                    fields=(
                        "id,name,phone_numbers{id,display_phone_number,verified_name,"
                        "quality_rating,status,platform_type,code_verification_status}"
                    ),
                )
            except GraphError:
                return None

        with ThreadPoolExecutor(max_workers=8) as pool:
            found = [a for a in pool.map(lookup, sorted(ids)) if a]
        return [
            {
                "id": str(a["id"]),
                "name": a.get("name", ""),
                "numbers": [
                    {
                        "id": str(n["id"]),
                        "display_phone_number": n.get("display_phone_number", ""),
                        "verified_name": n.get("verified_name", ""),
                        "quality_rating": n.get("quality_rating", ""),
                        "status": n.get("status", ""),
                        # NOT_APPLICABLE = not registered on the Cloud API yet
                        "platform_type": n.get("platform_type", ""),
                    }
                    for n in a.get("phone_numbers", {}).get("data", [])
                ],
            }
            for a in found
        ]

    def exchange_signup_code(self, code: str) -> str:
        """Embedded Signup (JavaScript SDK) code -> the customer's business token."""
        body = self._request(
            "GET",
            "oauth/access_token",
            client_id=settings.META_APP_ID,
            client_secret=settings.META_APP_SECRET,
            code=code,
        )
        return body["access_token"]

    def send_conversion_events(
        self, dataset_id: str, token: str, events: list[dict], test_event_code: str = ""
    ) -> dict:
        """Conversions API: POST /{dataset_id}/events."""
        params = {"data": json.dumps(events)}
        if test_event_code:
            params["test_event_code"] = test_event_code
        return self._request("POST", f"{dataset_id}/events", token, **params)

    def subscribe_waba(self, waba_id: str, token: str) -> None:
        """Webhooks of the WhatsApp Business Account (messages, statuses) come to this app."""
        self._request("POST", f"{waba_id}/subscribed_apps", token)

    def register_phone(self, phone_number_id: str, token: str, pin: str) -> None:
        """Register a number for the Cloud API; `pin` becomes its two-step verification PIN."""
        self._request(
            "POST",
            f"{phone_number_id}/register",
            token,
            messaging_product="whatsapp",
            pin=pin,
        )

    def _granted_ids(self, user_token: str, scopes: tuple[str, ...]) -> set[str]:
        try:
            data = self._request(
                "GET",
                "debug_token",
                f"{settings.META_APP_ID}|{settings.META_APP_SECRET}",
                input_token=user_token,
            ).get("data", {})
        except GraphError:
            return set()
        ids: set[str] = set()
        for grant in data.get("granular_scopes", []):
            if grant.get("scope") in scopes:
                ids.update(str(i) for i in grant.get("target_ids") or [])
        return ids

    def granted_page_ids(self, user_token: str) -> set[str]:
        """Page ids the person ticked in the login popup ("current Pages only" choice)."""
        try:
            data = self._request(
                "GET",
                "debug_token",
                f"{settings.META_APP_ID}|{settings.META_APP_SECRET}",
                input_token=user_token,
            ).get("data", {})
        except GraphError:
            return set()
        ids: set[str] = set()
        for grant in data.get("granular_scopes", []):
            if grant.get("scope") in ("pages_show_list", "leads_retrieval"):
                ids.update(str(i) for i in grant.get("target_ids") or [])
        return ids

    def subscribe_app_webhook(self, callback_url: str, verify_token: str) -> None:
        """Point the app's `leadgen` webhook at this server (Meta calls it to verify first)."""
        self._request(
            "POST",
            f"{settings.META_APP_ID}/subscriptions",
            f"{settings.META_APP_ID}|{settings.META_APP_SECRET}",
            object="page",
            callback_url=callback_url,
            fields="leadgen",
            include_values="true",
            verify_token=verify_token,
        )

    def subscribe_page(self, page_id: str, page_token: str) -> None:
        self._request("POST", f"{page_id}/subscribed_apps", page_token, subscribed_fields="leadgen")

    def unsubscribe_page(self, page_id: str, page_token: str) -> None:
        self._request("DELETE", f"{page_id}/subscribed_apps", page_token)

    def check_leads_access(self, page_id: str, page_token: str) -> None:
        """Raises GraphError if this app cannot read the Page's leads (Leads Access)."""
        self._request("GET", f"{page_id}/leadgen_forms", page_token, limit=1, fields="id")

    def list_forms(self, page_id: str, page_token: str) -> list[dict]:
        return self._paged(
            f"{page_id}/leadgen_forms",
            page_token,
            fields="id,name,status,created_time,leads_count,questions",
            limit=100,
        )

    def get_lead(self, leadgen_id: str, page_token: str) -> dict:
        return self._request("GET", leadgen_id, page_token, fields=LEAD_FIELDS)

    def list_form_leads(self, form_id: str, page_token: str, since_unix: int) -> list[dict]:
        filtering = [{"field": "time_created", "operator": "GREATER_THAN", "value": since_unix}]
        return self._paged(
            f"{form_id}/leads",
            page_token,
            fields=LEAD_FIELDS,
            filtering=json.dumps(filtering),
            limit=100,
        )


_client: Any = None


def get_graph() -> GraphClient:
    global _client
    if _client is None:
        _client = GraphClient()
    return _client


def set_graph(client: Any) -> None:
    """Tests and the simulator swap in a fake client."""
    global _client
    _client = client
