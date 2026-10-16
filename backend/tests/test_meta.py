"""Phase 4: Meta integration, replaying the reference leads in docs/reference."""

import hashlib
import hmac
import json
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from django.core import signing
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.meta_integration import graph as graph_module
from apps.meta_integration import services
from apps.meta_integration.graph import GraphError
from apps.meta_integration.models import FailedSyncLog, MetaConnection, MetaForm
from apps.meta_integration.tasks import backfill_connection
from common.mongo import LEAD_FORM_RESPONSES, TenantCollection
from common.tenancy.context import rls_bypass, tenant_context

pytestmark = pytest.mark.django_db
REFERENCE = Path(__file__).resolve().parents[2] / "docs" / "reference"
SAMPLE_1 = json.loads(
    (REFERENCE / "sample_1_Leads_Dubai_Properties_09_06_26.json").read_text("utf-8")
)
SAMPLE_2 = json.loads(
    (REFERENCE / "sample_2_Leads_Event4th5thJuly_10_06_26.json").read_text("utf-8")
)
PAGE_ID = "111222333"
SECRET = "test-app-secret"


class FakeGraph:
    """Stands in for the Graph API. Leads are served from the reference files."""

    def __init__(self):
        self.leads = {SAMPLE_1["id"]: SAMPLE_1, SAMPLE_2["id"]: SAMPLE_2}
        self.pages = [
            {"id": PAGE_ID, "name": "Acme Realty", "access_token": "PAGE-TOKEN-SECRET"},
            {"id": "999", "name": "Other Page", "access_token": "OTHER"},
        ]
        self.fail_lead = False
        self.subscribed: set[str] = set()
        self.form_leads: dict[str, list] = {}
        self.lead_reads: list[str] = []
        self.app_webhook = None

    def oauth_url(self, state, scopes=None):
        self.last_scopes = scopes
        return f"https://www.facebook.com/v21.0/dialog/oauth?state={state}"

    def exchange_code(self, code):
        return "USER-TOKEN-SECRET", None

    def list_pages(self, user_token):
        assert user_token == "USER-TOKEN-SECRET"
        return self.pages

    def subscribe_page(self, page_id, token):
        self.subscribed.add(page_id)

    def unsubscribe_page(self, page_id, token):
        self.subscribed.discard(page_id)

    def check_leads_access(self, page_id, token):
        assert token == "PAGE-TOKEN-SECRET"

    def list_forms(self, page_id, token):
        return [
            {"id": SAMPLE_1["form_id"], "name": "Dubai Properties", "status": "ACTIVE",
             "created_time": "2026-06-09T10:00:00+0000",
             "questions": [{"key": "investment_budget", "label": "Investment budget"},
                           {"key": "purpose_of_purchase", "label": "Purpose of purchase"}]},
            {"id": SAMPLE_2["form_id"], "name": "Event 4th-5th July", "status": "ACTIVE",
             "created_time": "2026-06-10T10:00:00+0000", "questions": []},
        ]  # fmt: skip

    def get_lead(self, leadgen_id, token):
        if self.fail_lead:
            raise GraphError("(#100) Temporary error", 100)
        return self.leads[leadgen_id]

    def list_form_leads(self, form_id, token, since):
        self.lead_reads.append(form_id)
        return self.form_leads.get(form_id, [])

    def subscribe_app_webhook(self, callback_url, verify_token):
        self.app_webhook = (callback_url, verify_token)


@pytest.fixture
def fake_graph(settings):
    settings.META_APP_ID = "app-id"
    settings.META_APP_SECRET = SECRET
    settings.META_WEBHOOK_VERIFY_TOKEN = "verify-me"
    fake = FakeGraph()
    graph_module.set_graph(fake)
    yield fake
    graph_module.set_graph(None)


def facebook_return(api, owner, **params):
    """What Facebook does at the end of the login popup: GET our public return URL."""
    if "state" not in params:
        url = owner.client.post("/api/v1/meta/connect").data["url"]
        params["state"] = parse_qs(urlparse(url).query)["state"][0]
    r = api.get("/api/meta/callback/", {"code": "abc", **params})
    assert r.status_code == 302
    return parse_qs(urlparse(r["Location"]).query)


def connect(owner) -> dict:
    """Run the whole connect flow: Facebook login (popup) -> one Page -> forms."""
    assert facebook_return(APIClient(), owner) == {"result": ["ok"]}
    assert owner.client.get("/api/v1/meta/status").data["status"] == "pending_page"
    r = owner.client.post("/api/v1/meta/page", {"page_id": PAGE_ID}, format="json")
    assert r.status_code == 200, r.data
    return r.data


def webhook(api, value: dict, *, secret=SECRET, page_id=PAGE_ID):
    body = json.dumps(
        {
            "object": "page",
            "entry": [{"id": page_id, "changes": [{"field": "leadgen", "value": value}]}],
        }
    ).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return api.post(
        "/webhooks/meta", body, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=signature
    )


def lead_value(sample: dict, page_id=PAGE_ID) -> dict:
    return {"leadgen_id": sample["id"], "form_id": sample["form_id"], "page_id": page_id}


def custom(question: str, field_key: str) -> dict:
    return {"question": question, "target_type": "custom", "custom_field": field_key}


def forms_by_meta_id(owner) -> dict:
    return {f["form_id"]: f for f in owner.client.get("/api/v1/meta/forms").data["results"]}


# --- connecting ----------------------------------------------------------------------------
def test_connect_flow_one_page_and_encrypted_tokens(signup, fake_graph):
    owner = signup()
    status = connect(owner)
    assert status["status"] == "connected" and status["page_name"] == "Acme Realty"
    assert status["leads_access_ok"] is True
    assert PAGE_ID in fake_graph.subscribed
    forms = forms_by_meta_id(owner)
    assert set(forms) == {SAMPLE_1["form_id"], SAMPLE_2["form_id"]}
    assert all(f["is_connected"] for f in forms.values())  # Auto Sync is on by default

    # Tokens are encrypted at rest
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.rls_bypass', 'on', true)")
        cur.execute("SELECT user_token_enc, page_token_enc FROM meta_connections")
        user_enc, page_enc = cur.fetchone()
    assert "SECRET" not in user_enc and "SECRET" not in page_enc

    # One Page per workspace
    r = owner.client.post("/api/v1/meta/page", {"page_id": "999"}, format="json")
    assert r.status_code == 400 and "Only one Meta Page" in r.data["detail"]
    assert owner.client.post("/api/v1/meta/connect").status_code == 400
    with tenant_context(owner.tenant_id):
        assert AuditLog.objects.filter(action="meta.connected").count() == 1


def test_a_page_belongs_to_one_workspace(signup, fake_graph):
    first, second = signup(), signup()
    connect(first)
    facebook_return(APIClient(), second)
    r = second.client.get("/api/v1/meta/pages")
    available = {p["id"]: p["available"] for p in r.data["pages"]}
    assert available == {PAGE_ID: False, "999": True}
    r = second.client.post("/api/v1/meta/page", {"page_id": PAGE_ID}, format="json")
    assert r.status_code == 400


def test_oauth_return_checks_the_signed_state(api, signup, invite_and_join, fake_graph):
    owner = signup()
    manager = invite_and_join(owner, "manager")
    url = owner.client.post("/api/v1/meta/connect").data["url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    tampered = facebook_return(api, owner, state=state + "x")
    assert tampered["result"] == ["error"] and "expired" in tampered["message"][0]
    cancelled = api.get("/api/meta/callback", {"error": "access_denied", "state": state})
    assert "result=error" in cancelled["Location"]
    assert owner.client.get("/api/v1/meta/status").data["status"] == "not_connected"

    # A state signed for a user who cannot manage Meta is refused
    forged = signing.dumps(
        {"t": owner.tenant_id, "u": manager.user_id, "n": "x"}, salt=services.STATE_SALT
    )
    assert facebook_return(api, owner, state=forged)["result"] == ["error"]
    assert facebook_return(api, owner, state=state) == {"result": ["ok"]}


def test_only_owner_and_admin_manage_meta(signup, invite_and_join, fake_graph):
    owner = signup()
    manager = invite_and_join(owner, "manager")
    endpoints = [
        ("get", "/api/v1/meta/status"),
        ("post", "/api/v1/meta/connect"),
        ("get", "/api/v1/meta/forms"),
        ("get", "/api/v1/meta/sync-logs"),
    ]
    for method, path in endpoints:
        assert getattr(manager.client, method)(path).status_code == 403


# --- webhook --------------------------------------------------------------------------------
def test_webhook_verification(api, fake_graph):
    ok = api.get(
        "/webhooks/meta",
        {"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"},
    )
    assert ok.status_code == 200 and ok.content == b"42"
    bad = api.get(
        "/webhooks/meta",
        {"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"},
    )
    assert bad.status_code == 403


def test_webhook_rejects_bad_signatures(api, signup, fake_graph):
    connect(signup())
    assert webhook(api, lead_value(SAMPLE_2), secret="wrong").status_code == 403


def test_reference_leads_flow_into_enquiries_with_mapping(
    api, signup, fake_graph, django_capture_on_commit_callbacks
):
    """The Phase 4 "Done when": a lead from a connected form appears as an Enquiry with campaign
    data; the original form response comes from MongoDB; mapped answers are filterable."""
    owner = signup()
    connect(owner)
    owner.client.post("/api/v1/custom-fields", {"label": "Purpose", "type": "dropdown",
                      "options": ["investment"]}, format="json")  # fmt: skip
    owner.client.post(
        "/api/v1/custom-fields", {"label": "Event attendance", "type": "text"}, format="json"
    )
    forms = forms_by_meta_id(owner)
    for meta_id in (SAMPLE_1["form_id"], SAMPLE_2["form_id"]):
        assert (
            owner.client.post(f"/api/v1/meta/forms/{forms[meta_id]['id']}/connect").status_code
            == 200
        )

    # Many-to-one: two differently worded questions feed one custom field
    form1, form2 = forms[SAMPLE_1["form_id"]]["id"], forms[SAMPLE_2["form_id"]]["id"]
    owner.client.put(f"/api/v1/meta/forms/{form1}/mapping", {"questions": [
        {"question": "full_name", "target_type": "name"},
        {"question": "phone_number", "target_type": "phone"},
        {"question": "email", "target_type": "email"},
        {"question": "purpose_of_purchase", "target_type": "custom", "custom_field": "purpose"},
    ]}, format="json")  # fmt: skip
    r = owner.client.put(f"/api/v1/meta/forms/{form2}/mapping", {"questions": [
        {"question": "full_name", "target_type": "name"},
        {"question": "phone_number", "target_type": "phone"},
        {"question": "email", "target_type": "email"},
        custom("what_is_your_primary_goal?", "purpose"),
        custom("will_you_attend_the_event?", "event_attendance"),
    ]}, format="json")  # fmt: skip
    assert r.status_code == 200, r.data

    with django_capture_on_commit_callbacks(execute=True):
        assert webhook(api, lead_value(SAMPLE_2)).data == {"queued": 1}
        webhook(api, lead_value(SAMPLE_1))

    enquiries = {e["name"]: e for e in owner.client.get("/api/v1/enquiries").data["results"]}
    karan = enquiries["Aarav Shah"]
    assert karan["source"] == "meta"
    assert karan["campaign_name"] == "Leads_Event4th5thJuly_10/06/26"
    assert karan["adset_name"] == "Ahmedabad+Gnagar" and karan["ad_name"] == "New Leads ad – Copy 2"
    assert karan["form_id"] == SAMPLE_2["form_id"]
    assert karan["custom_fields"] == {"purpose": "investment", "event_attendance": "yes,_5th_july"}
    assert karan["created_at"].startswith("2026-06-29T17:58:13")
    assert enquiries["Rohan Mehta"]["custom_fields"]["purpose"] == "investment"

    # Original form response from MongoDB, underscores shown as spaces
    response = owner.client.get(f"/api/v1/enquiries/{karan['id']}/form-response").data
    answer = next(a for a in response["answers"] if a["question"] == "will_you_attend_the_event?")
    assert answer["values"] == ["yes,_5th_july"] and answer["display"] == "yes, 5th july"

    # Mapped answers are filterable (Phase 2 engine)
    tree = {"field": "cf:purpose", "operator": "in", "value": ["investment"]}
    r = owner.client.get("/api/v1/enquiries", {"filter": json.dumps(tree)})
    assert r.data["count"] == 2

    doc = TenantCollection(LEAD_FORM_RESPONSES, owner.tenant_id).find_one(
        {"leadgen_id": SAMPLE_2["id"]}
    )
    assert doc["status"] == "synced" and doc["enquiry_id"] == karan["id"]

    # Sample answers feed the mapping screen
    mapping = owner.client.get(f"/api/v1/meta/forms/{form2}/mapping").data
    goal = next(q for q in mapping["questions"] if q["question"] == "what_is_your_primary_goal?")
    assert goal["samples"] == ["investment"] and goal["custom_field"] == "purpose"
    assert forms_by_meta_id(owner)[SAMPLE_2["form_id"]]["leads_received"] == 1


def test_duplicates_unconnected_forms_and_other_pages(
    api, signup, fake_graph, django_capture_on_commit_callbacks
):
    owner = signup()
    connect(owner)
    # Auto Sync off: only the forms switched on create enquiries
    owner.client.patch("/api/v1/meta/settings", {"auto_connect_forms": False}, format="json")
    forms = forms_by_meta_id(owner)
    owner.client.post(f"/api/v1/meta/forms/{forms[SAMPLE_1['form_id']]['id']}/disconnect")

    with django_capture_on_commit_callbacks(execute=True):
        webhook(api, lead_value(SAMPLE_2))
        webhook(api, lead_value(SAMPLE_2))  # Meta delivers again
        webhook(api, lead_value(SAMPLE_1))  # form not connected
        assert webhook(api, lead_value(SAMPLE_2, page_id="999"), page_id="999").data == {
            "queued": 0
        }

    assert owner.client.get("/api/v1/enquiries").data["count"] == 1
    statuses = [s["status"] for s in owner.client.get("/api/v1/meta/sync-logs").data["results"]]
    assert sorted(statuses) == ["duplicate", "form_not_connected", "synced"]
    doc = TenantCollection(LEAD_FORM_RESPONSES, owner.tenant_id).find_one(
        {"leadgen_id": SAMPLE_1["id"]}
    )
    assert doc["status"] == "form_not_connected" and doc["enquiry_id"] is None


def test_failed_sync_can_be_retried_without_duplicates(
    api, signup, fake_graph, django_capture_on_commit_callbacks
):
    owner = signup()
    connect(owner)
    form = forms_by_meta_id(owner)[SAMPLE_2["form_id"]]
    owner.client.post(f"/api/v1/meta/forms/{form['id']}/connect")

    fake_graph.fail_lead = True
    with django_capture_on_commit_callbacks(execute=True):
        webhook(api, lead_value(SAMPLE_2))
    failed = owner.client.get("/api/v1/meta/failed-syncs").data["results"]
    assert len(failed) == 1 and "Temporary error" in failed[0]["error"]
    assert owner.client.get("/api/v1/enquiries").data["count"] == 0

    fake_graph.fail_lead = False
    r = owner.client.post(f"/api/v1/meta/failed-syncs/{failed[0]['id']}/retry")
    assert r.data["status"] == "synced"
    r = owner.client.post(f"/api/v1/meta/failed-syncs/{failed[0]['id']}/retry")
    assert r.data["status"] == "duplicate"
    assert owner.client.get("/api/v1/enquiries").data["count"] == 1
    assert owner.client.get("/api/v1/meta/failed-syncs").data["count"] == 0


def test_backfill_recovers_missed_webhooks(signup, fake_graph):
    owner = signup()
    connect(owner)
    form = forms_by_meta_id(owner)[SAMPLE_2["form_id"]]
    owner.client.post(f"/api/v1/meta/forms/{form['id']}/connect")
    fake_graph.form_leads = {SAMPLE_2["form_id"]: [SAMPLE_2]}
    assert backfill_connection(owner.tenant_id) == {
        "checked": 1,
        "added": 1,
        "restored": 0,
        "errors": [],
    }
    assert backfill_connection(owner.tenant_id) == {
        "checked": 1,
        "added": 0,
        "restored": 0,
        "errors": [],
    }
    assert owner.client.get("/api/v1/enquiries").data["count"] == 1


def test_disconnect_keeps_enquiries(api, signup, fake_graph, django_capture_on_commit_callbacks):
    owner = signup()
    connect(owner)
    form = forms_by_meta_id(owner)[SAMPLE_2["form_id"]]
    owner.client.post(f"/api/v1/meta/forms/{form['id']}/connect")
    with django_capture_on_commit_callbacks(execute=True):
        webhook(api, lead_value(SAMPLE_2))
    assert owner.client.delete("/api/v1/meta/connection").status_code == 204
    assert PAGE_ID not in fake_graph.subscribed
    assert owner.client.get("/api/v1/meta/status").data["status"] == "disconnected"
    assert owner.client.get("/api/v1/enquiries").data["count"] == 1
    # The Page is free again for any workspace
    with rls_bypass():
        assert not MetaConnection.objects.filter(page_id=PAGE_ID).exists()


def test_meta_data_is_isolated_between_workspaces(signup, fake_graph):
    owner, other = signup(), signup()
    connect(owner)
    assert other.client.get("/api/v1/meta/status").data["status"] == "not_connected"
    assert other.client.get("/api/v1/meta/forms").data["count"] == 0
    form = forms_by_meta_id(owner)[SAMPLE_2["form_id"]]
    assert other.client.post(f"/api/v1/meta/forms/{form['id']}/connect").status_code in (400, 404)
    with tenant_context(other.tenant_id):  # RLS: unscoped query sees nothing
        assert MetaForm.objects.count() == 0 and FailedSyncLog.objects.count() == 0


def test_mapping_rejects_two_phone_questions(signup, fake_graph):
    owner = signup()
    connect(owner)
    form = forms_by_meta_id(owner)[SAMPLE_2["form_id"]]
    r = owner.client.put(f"/api/v1/meta/forms/{form['id']}/mapping", {"questions": [
        {"question": "phone_number", "target_type": "phone"},
        {"question": "whatsapp_number", "target_type": "phone"},
    ]}, format="json")  # fmt: skip
    assert r.status_code == 400


# --- auto-connect forms and "Sync leads now" ---------------------------------------------
def test_auto_connect_forms_and_sync_now(signup, fake_graph):
    owner = signup()
    connect(owner)
    # A new Page starts with Auto Sync on: every form is connected
    assert owner.client.get("/api/v1/meta/status").data["auto_connect_forms"] is True
    assert all(f["is_connected"] for f in forms_by_meta_id(owner).values())

    # A form Meta reports later is connected as soon as it is seen
    with tenant_context(owner.tenant_id):
        MetaForm.objects.filter(form_id=SAMPLE_2["form_id"]).delete()
    fake_graph.form_leads[SAMPLE_2["form_id"]] = [SAMPLE_2]
    assert owner.client.post("/api/v1/meta/sync", {"days": 90}, format="json").status_code == 400
    r = owner.client.post("/api/v1/meta/sync", {"days": 30}, format="json")
    assert r.status_code == 200 and r.data == {
        "checked": 1,
        "added": 1,
        "restored": 0,
        "errors": [],
    }
    assert forms_by_meta_id(owner)[SAMPLE_2["form_id"]]["is_connected"] is True
    assert owner.client.get("/api/v1/enquiries").data["count"] == 1

    # Manual mode: new forms wait for a click
    owner.client.patch("/api/v1/meta/settings", {"auto_connect_forms": False}, format="json")
    assert all(f["is_connected"] for f in forms_by_meta_id(owner).values())  # nothing undone


def test_log_out_before_choosing_a_page(signup, fake_graph):
    owner = signup()
    facebook_return(APIClient(), owner)
    assert owner.client.delete("/api/v1/meta/connection").status_code == 204
    assert owner.client.get("/api/v1/meta/status").data["status"] == "disconnected"
    assert owner.client.post("/api/v1/meta/connect").status_code == 200


def test_sync_now_reports_forms_meta_refused(signup, fake_graph, monkeypatch):
    owner = signup()
    connect(owner)
    owner.client.patch("/api/v1/meta/settings", {"auto_connect_forms": True}, format="json")

    def refuse(form_id, token, since):
        raise GraphError("Error validating access token", 190)

    monkeypatch.setattr(fake_graph, "list_form_leads", refuse)
    r = owner.client.post("/api/v1/meta/sync", {"days": 1}, format="json")
    assert r.data["checked"] == 0 and len(r.data["errors"]) == 2
    assert "Dubai Properties: " in " ".join(r.data["errors"])


def test_sync_now_restores_meta_leads_deleted_in_the_lms(
    api, signup, fake_graph, django_capture_on_commit_callbacks
):
    """Deleting enquiries in the LMS, then clicking "Sync leads", must bring them back."""
    owner = signup()
    connect(owner)
    with django_capture_on_commit_callbacks(execute=True):
        webhook(api, lead_value(SAMPLE_2))
    enquiry_id = owner.client.get("/api/v1/enquiries").data["results"][0]["id"]
    assert owner.client.delete(f"/api/v1/enquiries/{enquiry_id}").status_code == 204
    assert owner.client.get("/api/v1/enquiries").data["count"] == 0

    # Automatic syncs respect the delete
    fake_graph.form_leads[SAMPLE_2["form_id"]] = [SAMPLE_2]
    backfill_connection(owner.tenant_id)
    with django_capture_on_commit_callbacks(execute=True):
        webhook(api, lead_value(SAMPLE_2))
    assert owner.client.get("/api/v1/enquiries").data["count"] == 0

    r = owner.client.post("/api/v1/meta/sync", {"days": 7}, format="json")
    assert r.data["restored"] == 1 and r.data["added"] == 0
    listed = owner.client.get("/api/v1/enquiries").data
    assert listed["count"] == 1 and listed["results"][0]["id"] == enquiry_id
    assert owner.client.get("/api/v1/contacts").data["count"] == 1  # its contact is back too
    # A second click changes nothing
    assert owner.client.post("/api/v1/meta/sync", {"days": 7}, format="json").data["restored"] == 0


def test_pages_reached_through_business_manager_are_listed(monkeypatch):
    """me/accounts misses Business Manager Pages ("all Pages" grants carry no Page ids):
    Pages ticked in the popup, promoted by ad accounts or owned by businesses are added."""
    client = graph_module.GraphClient()
    pages = {
        "557": "TPS Dubai", "320": "Hari Group", "170": "The PioneerTech", "436": "Shrivi",
    }  # fmt: skip

    def fake_request(method, path, token=None, **params):
        responses = {
            "me/accounts": {"data": [{"id": "557", "name": "TPS Dubai", "access_token": "T"}]},
            "debug_token": {"data": {"granular_scopes": [
                {"scope": "pages_show_list", "target_ids": ["320"]},
            ]}},
            "me/adaccounts": {"data": [
                {"promote_pages": {"data": [{"id": "170"}, {"id": "557"}, {"id": "999"}]}},
                {},  # an ad account without Pages
            ]},
            "me/businesses": {"data": [{"owned_pages": {"data": [{"id": "436"}]}}]},
        }  # fmt: skip
        if path in responses:
            return responses[path]
        if path in pages:
            return {"id": path, "name": pages[path], "access_token": "T"}
        raise GraphError("(#200) Missing Permission", 200)

    monkeypatch.setattr(client, "_request", fake_request)
    names = [p["name"] for p in client.list_pages("USER")]
    assert names == ["Hari Group", "Shrivi", "The PioneerTech", "TPS Dubai"]


# --- automatic sync and near-live leads ----------------------------------------------------------
def test_poll_brings_new_leads_at_most_once_a_minute(signup, fake_graph):
    owner = signup()
    connect(owner)  # Auto Sync: both forms connected
    fake_graph.form_leads[SAMPLE_2["form_id"]] = [SAMPLE_2]
    with tenant_context(owner.tenant_id):  # an archived form gets no new leads: not polled
        MetaForm.objects.filter(form_id=SAMPLE_1["form_id"]).update(status_on_meta="ARCHIVED")
    fake_graph.form_leads[SAMPLE_1["form_id"]] = [SAMPLE_1]

    r = owner.client.post("/api/v1/meta/poll")
    assert r.data == {"polled": True, "checked": 1, "added": 1}
    assert fake_graph.lead_reads == [SAMPLE_2["form_id"]]
    assert owner.client.post("/api/v1/meta/poll").data == {"polled": False}  # too soon

    with tenant_context(owner.tenant_id):
        MetaConnection.objects.update(last_polled_at=timezone.now() - timedelta(minutes=2))
    assert owner.client.post("/api/v1/meta/poll").data["added"] == 0  # nothing new, no duplicate
    assert owner.client.get("/api/v1/enquiries").data["count"] == 1


def test_any_member_can_poll_but_nothing_happens_without_meta(signup, invite_and_join, fake_graph):
    owner = signup()
    agent = invite_and_join(owner, "agent")
    assert agent.client.post("/api/v1/meta/poll").data == {"polled": False}
    connect(owner)
    assert agent.client.post("/api/v1/meta/poll").data["polled"] is True


def test_automatic_sync_skips_deleted_and_can_target_one_form(
    api, signup, fake_graph, django_capture_on_commit_callbacks
):
    owner = signup()
    connect(owner)
    owner.client.patch("/api/v1/meta/settings", {"auto_connect_forms": False}, format="json")
    forms = forms_by_meta_id(owner)
    owner.client.post(f"/api/v1/meta/forms/{forms[SAMPLE_1['form_id']]['id']}/disconnect")
    fake_graph.form_leads = {SAMPLE_1["form_id"]: [SAMPLE_1], SAMPLE_2["form_id"]: [SAMPLE_2]}

    # Switching a form on syncs only that form
    form1 = forms[SAMPLE_1["form_id"]]["id"]
    owner.client.post(f"/api/v1/meta/forms/{form1}/connect")
    r = owner.client.post(
        "/api/v1/meta/sync",
        {"days": 30, "restore_deleted": False, "form": form1},
        format="json",
    )
    assert r.data["added"] == 1 and fake_graph.lead_reads == [SAMPLE_1["form_id"]]

    # The automatic sync never brings back what the team deleted
    enquiry_id = owner.client.get("/api/v1/enquiries").data["results"][0]["id"]
    owner.client.delete(f"/api/v1/enquiries/{enquiry_id}")
    r = owner.client.post(
        "/api/v1/meta/sync", {"days": 30, "restore_deleted": False}, format="json"
    )
    assert r.data["restored"] == 0 and r.data["added"] == 1  # SAMPLE_2 only
    assert owner.client.get("/api/v1/enquiries").data["count"] == 1
    bad = owner.client.post("/api/v1/meta/sync", {"days": 30, "form": 999999}, format="json")
    assert bad.status_code == 400


def test_public_https_server_registers_the_webhook_itself(settings, signup, fake_graph):
    settings.BACKEND_URL = "https://crm.example.com"
    connect(signup())
    assert fake_graph.app_webhook == ("https://crm.example.com/webhooks/meta", "verify-me")


def test_localhost_does_not_register_a_webhook(settings, signup, fake_graph):
    settings.BACKEND_URL = "http://localhost:8000"
    connect(signup())
    assert fake_graph.app_webhook is None


def test_contacts_show_their_latest_enquiry_status(
    api, signup, fake_graph, django_capture_on_commit_callbacks
):
    owner = signup()
    connect(owner)
    with django_capture_on_commit_callbacks(execute=True):
        webhook(api, lead_value(SAMPLE_2))
    contact = owner.client.get("/api/v1/contacts").data["results"][0]
    assert contact["status"]["name"] == "New" and contact["status"]["color"]
