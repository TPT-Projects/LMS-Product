"""Connected apps (header "Apps" menu): WhatsApp and Exotel connect with checked credentials."""

import pytest
from django.db import connection

from apps.audit.models import AuditLog
from apps.integrations import providers
from apps.meta_integration.models import MetaConnection
from common.tenancy.context import tenant_context

pytestmark = pytest.mark.django_db

WHATSAPP = {
    "phone_number_id": "106540352242922",
    "business_account_id": "102290129340398",
    "access_token": "EAAG-very-secret-whatsapp-token-123",
}
EXOTEL = {
    "region": "in",
    "account_sid": "pioneertech1",
    "api_key": "key-abc123",
    "api_token": "token-very-secret-456",
    "caller_id": "+91 80471 12345",
}


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}

    def json(self):
        return self._body


@pytest.fixture
def provider_http(monkeypatch):
    """Answers the providers' HTTP checks. Set `.response`; calls are recorded."""

    class Http:
        response = FakeResponse(
            body={"display_phone_number": "+91 98250 00000", "verified_name": "TPS Dubai"}
        )
        calls: list[dict] = []

        def get(self, url, params=None, auth=None, timeout=None):
            self.calls.append({"url": url, "params": params or {}, "auth": auth})
            return self.response

    http = Http()
    http.calls = []
    monkeypatch.setattr(providers.requests, "get", http.get)
    return http


def apps_by_key(session) -> dict:
    return {a["app"]: a for a in session.client.get("/api/v1/integrations").data["apps"]}


def test_only_owner_and_admin_manage_apps(signup, invite_and_join):
    owner = signup()
    assert invite_and_join(owner, "admin").client.get("/api/v1/integrations").status_code == 200
    manager = invite_and_join(owner, "manager")
    assert manager.client.get("/api/v1/integrations").status_code == 403
    r = manager.client.post("/api/v1/integrations/whatsapp", {"values": WHATSAPP}, format="json")
    assert r.status_code == 403


def test_overview_lists_every_connectable_app(signup):
    apps = apps_by_key(signup())
    assert set(apps) == {"meta", "whatsapp", "exotel", "google_sheets"}
    assert {a["status"] for a in apps.values()} == {"not_connected"}


def test_connect_whatsapp_checks_first_and_encrypts_the_token(signup, provider_http):
    owner = signup()
    missing = owner.client.post(
        "/api/v1/integrations/whatsapp", {"values": {"phone_number_id": "abc"}}, format="json"
    )
    assert missing.status_code == 400
    assert set(missing.data["errors"]["values"]) == {"phone_number_id", "access_token"}
    assert provider_http.calls == []  # nothing is sent to Meta until the form is valid

    r = owner.client.post("/api/v1/integrations/whatsapp", {"values": WHATSAPP}, format="json")
    assert r.status_code == 200, r.data
    assert r.data["status"] == "connected"
    assert r.data["account_label"] == "+91 98250 00000 · TPS Dubai"
    assert r.data["secrets_set"] == ["access_token"]
    assert "access_token" not in r.data["config"]
    assert provider_http.calls[0]["url"].endswith("/106540352242922")
    assert provider_http.calls[0]["params"]["access_token"] == WHATSAPP["access_token"]

    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.rls_bypass', 'on', true)")
        cur.execute("SELECT secrets_enc FROM integrations")
        (stored,) = cur.fetchone()
    assert stored and "very-secret" not in stored
    with tenant_context(owner.tenant_id):
        assert AuditLog.objects.filter(action="integration.connected").count() == 1


def test_refused_credentials_are_not_saved(signup, provider_http):
    owner = signup()
    provider_http.response = FakeResponse(401)
    r = owner.client.post("/api/v1/integrations/exotel", {"values": EXOTEL}, format="json")
    assert r.status_code == 400
    assert "refused" in r.data["detail"]
    assert "api_token" in r.data["errors"]["values"]
    assert provider_http.calls[0]["url"] == (
        "https://api.in.exotel.com/v1/Accounts/pioneertech1/Calls.json"
    )
    assert provider_http.calls[0]["auth"] == ("key-abc123", "token-very-secret-456")
    assert apps_by_key(owner)["exotel"]["status"] == "not_connected"


def test_edit_keeps_the_stored_secret_and_check_reports_problems(signup, provider_http):
    owner = signup()
    provider_http.response = FakeResponse(200, {"Calls": []})
    owner.client.post("/api/v1/integrations/exotel", {"values": EXOTEL}, format="json")

    # Edit without re-typing the token: the stored one is used
    edited = {**EXOTEL, "api_token": "", "region": "sg", "caller_id": ""}
    r = owner.client.post("/api/v1/integrations/exotel", {"values": edited}, format="json")
    assert r.status_code == 200, r.data
    assert provider_http.calls[-1]["auth"] == ("key-abc123", "token-very-secret-456")
    assert provider_http.calls[-1]["url"].startswith("https://api.exotel.com/")
    assert r.data["config"]["region"] == "sg" and r.data["account_label"] == "pioneertech1"

    # "Test connection" with a token Exotel no longer accepts
    provider_http.response = FakeResponse(401)
    r = owner.client.post("/api/v1/integrations/exotel/check")
    assert r.data["status"] == "error" and "refused" in r.data["last_error"]
    provider_http.response = FakeResponse(200, {"Calls": []})
    r = owner.client.post("/api/v1/integrations/exotel/check")
    assert r.data["status"] == "connected" and r.data["last_error"] == ""


def test_disconnect_removes_the_details(signup, provider_http):
    owner = signup()
    owner.client.post("/api/v1/integrations/whatsapp", {"values": WHATSAPP}, format="json")
    assert owner.client.delete("/api/v1/integrations/whatsapp").status_code == 204
    assert apps_by_key(owner)["whatsapp"]["status"] == "not_connected"
    assert owner.client.delete("/api/v1/integrations/whatsapp").status_code == 404
    assert owner.client.post("/api/v1/integrations/slack", {}, format="json").status_code == 404


def test_apps_are_private_to_each_workspace(signup, provider_http):
    first, second = signup(), signup()
    first.client.post("/api/v1/integrations/whatsapp", {"values": WHATSAPP}, format="json")
    assert apps_by_key(first)["whatsapp"]["status"] == "connected"
    assert apps_by_key(second)["whatsapp"]["status"] == "not_connected"
    assert second.client.post("/api/v1/integrations/whatsapp/check").status_code == 404


def test_meta_status_comes_from_the_meta_connection(signup):
    owner = signup()
    with tenant_context(owner.tenant_id):
        MetaConnection.objects.create(tenant_id=owner.tenant_id)  # logged in, no Page yet
    assert apps_by_key(owner)["meta"]["status"] == "needs_setup"
    with tenant_context(owner.tenant_id):
        MetaConnection.objects.filter(tenant_id=owner.tenant_id).update(
            status="connected", page_id="557", page_name="TPS Dubai"
        )
    meta = apps_by_key(owner)["meta"]
    assert meta["account_label"] == "TPS Dubai"
    assert meta["status"] in ("connected", "error")  # error only when the token expired
