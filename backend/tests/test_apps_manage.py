"""Users' phone numbers, Meta forms per Page, Exotel numbers and auto-calling,
WhatsApp via Facebook login and Google Sheets."""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.utils import timezone

from apps.enquiries.models import CallLog, Enquiry
from apps.integrations import autocall, exotel, google
from apps.integrations.models import AutoCall, Integration
from apps.meta_integration.models import MetaForm
from common.tenancy.context import tenant_context

from .conftest import create_enquiry
from .test_meta import SAMPLE_2, connect, lead_value, webhook
from .test_meta import fake_graph as meta_graph  # noqa: F401 (a fixture)

pytestmark = pytest.mark.django_db


# --- users -------------------------------------------------------------------------------------
def test_users_have_phone_numbers(signup, invite_and_join):
    owner = signup()
    agent = invite_and_join(owner, "agent")
    r = owner.client.patch(
        f"/api/v1/users/{agent.user_id}/profile",
        {"phone": "98250 12345", "alternate_phone": "+971 50 123 4567"},
        format="json",
    )
    assert r.status_code == 200, r.data
    assert r.data["phone"] == "+919825012345" and r.data["alternate_phone"] == "+971501234567"
    assert (
        agent.client.patch(
            f"/api/v1/users/{agent.user_id}/profile", {"phone": "12"}, format="json"
        ).status_code
        == 400
    )
    assert (
        agent.client.patch(
            f"/api/v1/users/{owner.user_id}/profile", {"phone": "9825012345"}, format="json"
        ).status_code
        == 403
    )
    row = next(
        u for u in owner.client.get("/api/v1/users").data["results"] if u["id"] == agent.user_id
    )
    assert row["phone"] == "+919825012345" and row["role"] == "agent"


# --- Meta forms --------------------------------------------------------------------------------
def test_forms_list_shows_the_connected_page_only_and_can_be_searched(signup, meta_graph):
    owner = signup()
    connect(owner)
    with tenant_context(owner.tenant_id):  # a form of another Page (connected earlier)
        MetaForm.objects.create(
            tenant_id=owner.tenant_id, form_id="777", name="Old page form", page_id="999"
        )
    names = [f["name"] for f in owner.client.get("/api/v1/meta/forms").data["results"]]
    assert sorted(names) == ["Dubai Properties", "Event 4th-5th July"]
    r = owner.client.get("/api/v1/meta/forms", {"q": "dubai"})
    assert [f["name"] for f in r.data["results"]] == ["Dubai Properties"]


# --- Exotel --------------------------------------------------------------------------------------
class FakeExotel:
    def __init__(self):
        self.numbers = [
            {"sid": "1", "phone_number": "+918047112345", "friendly_name": "Sales",
             "capabilities": {"voice": True, "sms": True}, "country": "IN", "region": "KA"},
            {"sid": "2", "phone_number": "+918047119999", "friendly_name": "Support",
             "capabilities": {"voice": True}, "country": "IN", "region": "KA"},
        ]  # fmt: skip
        self.calls: list[dict] = []
        self.fail = None
        self.results: dict[str, dict] = {}

    def list_numbers(self):
        return list(self.numbers)

    def call_details(self, call_sid):
        return self.results.get(call_sid, {"Status": "in-progress"})

    def connect_call(self, *, agent, customer, caller_id, status_callback=None):
        if self.fail:
            raise exotel.ExotelError(self.fail)
        self.calls.append({"agent": agent, "customer": customer, "caller_id": caller_id})
        return f"CA{len(self.calls)}"


@pytest.fixture
def fake_exotel():
    fake = FakeExotel()
    exotel.set_exotel_factory(lambda values: fake)
    yield fake
    exotel.set_exotel_factory(None)


def connect_exotel(owner) -> dict:
    with tenant_context(owner.tenant_id):
        integration = Integration(
            tenant_id=owner.tenant_id,
            app="exotel",
            config={"region": "in", "account_sid": "pioneer1", "api_key": "key"},
            account_label="pioneer1",
        )
        integration.secrets = {"api_token": "token"}
        integration.save()
    r = owner.client.post("/api/v1/integrations/exotel/refresh")
    assert r.status_code == 200, r.data
    return r.data


def set_phone(session, phone="+919825000001"):
    session.client.patch(
        f"/api/v1/users/{session.user_id}/profile", {"phone": phone}, format="json"
    )


def test_exotel_numbers_refresh_add_and_default_caller(signup, fake_exotel):
    owner = signup()
    data = connect_exotel(owner)
    assert [n["phone_number"] for n in data["numbers"]] == ["+918047112345", "+918047119999"]
    assert data["settings"]["default_caller"] == "+918047112345"
    assert data["refreshed_at"] and data["numbers"][0]["active_since"]

    fake_exotel.numbers.pop()  # released in Exotel
    data = owner.client.post("/api/v1/integrations/exotel/refresh").data
    assert {n["phone_number"]: n["is_active"] for n in data["numbers"]} == {
        "+918047112345": True,
        "+918047119999": False,
    }

    r = owner.client.post(
        "/api/v1/integrations/exotel/numbers", {"phone_number": "080 4711 5555"}, format="json"
    )
    assert r.status_code == 201
    added = next(n for n in r.data["numbers"] if n["added_manually"])
    assert added["phone_number"] == "+918047115555"
    assert (
        owner.client.post(
            "/api/v1/integrations/exotel/numbers", {"phone_number": "+918047115555"}, format="json"
        ).status_code
        == 400
    )

    bad = owner.client.patch(
        "/api/v1/integrations/exotel/manage", {"default_caller": "+918047119999"}, format="json"
    )
    assert bad.status_code == 400  # inactive number
    ok = owner.client.patch(
        "/api/v1/integrations/exotel/manage", {"default_caller": "+918047115555"}, format="json"
    )
    assert ok.data["settings"]["default_caller"] == "+918047115555"
    owner.client.delete(f"/api/v1/integrations/exotel/numbers/{added['id']}")
    assert (
        owner.client.get("/api/v1/integrations/exotel/manage").data["settings"]["default_caller"]
        == ""
    )


def test_numbers_refresh_themselves_once_a_day(signup, fake_exotel):
    owner = signup()
    connect_exotel(owner)
    assert owner.client.post("/api/v1/integrations/heartbeat").data["numbers_refreshed"] is False
    with tenant_context(owner.tenant_id):
        Integration.objects.filter(app="exotel").update(
            synced_at=timezone.now() - timedelta(days=2)
        )
    assert owner.client.post("/api/v1/integrations/heartbeat").data["numbers_refreshed"] is True


def test_new_lead_from_an_auto_call_form_is_called_after_the_delay(
    api, signup, meta_graph, fake_exotel, django_capture_on_commit_callbacks
):
    owner = signup()
    connect(owner)
    connect_exotel(owner)
    set_phone(owner)
    manage = "/api/v1/integrations/exotel/manage"
    assert owner.client.get(manage).data["settings"]["new_lead_delay"] == 2  # default
    assert owner.client.patch(manage, {"new_lead_delay": 3}, format="json").status_code == 400
    owner.client.patch(
        manage, {"fallback_agent": owner.user_id, "new_lead_delay": 5}, format="json"
    )
    forms = owner.client.get("/api/v1/integrations/exotel/forms").data["forms"]
    event_form = next(f for f in forms if f["form_id"] == SAMPLE_2["form_id"])
    r = owner.client.patch(
        f"/api/v1/integrations/exotel/forms/{event_form['id']}", {"auto_call": True}, format="json"
    )
    assert r.data["auto_call"] is True

    with django_capture_on_commit_callbacks(execute=True):
        webhook(api, lead_value(SAMPLE_2))
    assert fake_exotel.calls == []  # not before the delay
    with tenant_context(owner.tenant_id):
        call = AutoCall.objects.get()
    wait = (call.scheduled_at - timezone.now()).total_seconds()
    assert 4 * 60 < wait <= 5 * 60
    assert owner.client.post("/api/v1/integrations/heartbeat").data["calls_started"] == 0

    with tenant_context(owner.tenant_id):
        AutoCall.objects.update(scheduled_at=timezone.now() - timedelta(seconds=5))
    assert owner.client.post("/api/v1/integrations/heartbeat").data["calls_started"] == 1
    placed = fake_exotel.calls[0]
    assert placed["agent"] == "+919825000001" and placed["caller_id"] == "+918047112345"
    listed = owner.client.get("/api/v1/integrations/exotel/calls").data["results"]
    assert listed[0]["status"] == "started" and listed[0]["reason"] == "new_lead"


def test_scheduled_calls_are_placed_when_due(signup, fake_exotel):
    owner = signup()
    connect_exotel(owner)
    set_phone(owner)
    calling = owner.client.get("/api/v1/integrations/calling").data
    assert calling["exotel_connected"] is True and calling["auto_call_followups"] is False
    owner.client.patch(
        "/api/v1/integrations/exotel/manage", {"auto_call_followups": True}, format="json"
    )
    assert owner.client.get("/api/v1/integrations/calling").data["auto_call_followups"] is True
    enquiry = create_enquiry(owner)
    base = f"/api/v1/enquiries/{enquiry['id']}/followups"
    soon = (timezone.now() + timedelta(hours=1)).isoformat()
    r = owner.client.post(base, {"title": "Call back", "due_at": soon}, format="json")
    assert r.data["auto_call_status"] == "pending"
    assert owner.client.post("/api/v1/integrations/heartbeat").data["calls_started"] == 0

    with tenant_context(owner.tenant_id):
        AutoCall.objects.update(scheduled_at=timezone.now() - timedelta(minutes=1))
    assert owner.client.post("/api/v1/integrations/heartbeat").data["calls_started"] == 1
    assert fake_exotel.calls[0]["agent"] == "+919825000001"

    # Marked done before its time: no call
    r = owner.client.post(base, {"title": "Second", "due_at": soon}, format="json")
    owner.client.patch(f"{base}/{r.data['id']}", {"done": True}, format="json")
    # The LMS was closed at the planned time: skipped instead of calling hours late
    owner.client.post(base, {"title": "Third", "due_at": soon}, format="json")
    with tenant_context(owner.tenant_id):
        AutoCall.objects.filter(followup__title="Third").update(
            scheduled_at=timezone.now() - timedelta(hours=2)
        )
    owner.client.post("/api/v1/integrations/heartbeat")
    with tenant_context(owner.tenant_id):
        statuses = dict(AutoCall.objects.values_list("followup__title", "status"))
    assert statuses == {"Call back": "started", "Second": "cancelled", "Third": "skipped"}


def test_auto_call_can_be_switched_off_for_one_scheduled_call(signup, fake_exotel):
    owner = signup()
    connect_exotel(owner)
    owner.client.patch(
        "/api/v1/integrations/exotel/manage", {"auto_call_followups": True}, format="json"
    )
    enquiry = create_enquiry(owner)
    base = f"/api/v1/enquiries/{enquiry['id']}/followups"
    soon = (timezone.now() + timedelta(hours=1)).isoformat()
    r = owner.client.post(
        base, {"title": "Manual call", "due_at": soon, "auto_call": False}, format="json"
    )
    assert r.data["auto_call_status"] is None
    with tenant_context(owner.tenant_id):
        assert not AutoCall.objects.exists()

    on = owner.client.patch(f"{base}/{r.data['id']}", {"auto_call": True}, format="json")
    assert on.data["auto_call_status"] == "pending"
    off = owner.client.patch(f"{base}/{r.data['id']}", {"auto_call": False}, format="json")
    assert off.data["auto_call_status"] == "cancelled"
    again = owner.client.patch(f"{base}/{r.data['id']}", {"auto_call": True}, format="json")
    assert again.data["auto_call_status"] == "pending"


def test_status_changes_do_not_dial(signup, fake_exotel):
    owner = signup()
    connect_exotel(owner)
    contacted = next(
        s for s in owner.client.get("/api/v1/statuses").data if s["name"] == "Contacted"
    )
    enquiry = create_enquiry(owner, primary_owner_id=owner.user_id)
    owner.client.patch(
        f"/api/v1/enquiries/{enquiry['id']}", {"status_id": contacted["id"]}, format="json"
    )
    with tenant_context(owner.tenant_id):
        assert not AutoCall.objects.exists()


def test_exotel_reports_the_result_and_the_call_is_logged(api, signup, fake_exotel):
    owner = signup()
    connect_exotel(owner)
    enquiry = create_enquiry(owner)
    with tenant_context(owner.tenant_id):
        e = Enquiry.objects.get(pk=enquiry["id"])
        AutoCall.objects.create(
            tenant_id=owner.tenant_id,
            enquiry=e,
            reason="followup",
            status="started",
            call_sid="CA9",
        )
    token = autocall.signing.dumps(owner.tenant_id, salt=autocall.CALLBACK_SALT)
    r = api.post(f"/webhooks/exotel/{token}", {"CallSid": "CA9", "Status": "completed",
                                                 "ConversationDuration": "42"})  # fmt: skip
    assert r.status_code == 200
    with tenant_context(owner.tenant_id):
        log = CallLog.objects.get(enquiry_id=enquiry["id"])
        assert AutoCall.objects.get().status == "completed"
    assert log.provider == "exotel" and log.duration_seconds == 42 and log.outcome == "connected"
    assert api.post("/webhooks/exotel/forged", {"CallSid": "CA9"}).status_code == 404


# --- WhatsApp via Facebook login --------------------------------------------------------
ACCOUNTS = [
    {"id": "waba1", "name": "TPS Dubai", "numbers": [
        {"id": "pn1", "display_phone_number": "+91 98250 00000", "verified_name": "TPS Dubai",
         "quality_rating": "GREEN"},
        {"id": "pn2", "display_phone_number": "+971 50 000 0000", "verified_name": "TPS UAE",
         "quality_rating": "GREEN"},
    ]},
]  # fmt: skip


def test_whatsapp_connects_with_the_facebook_popup(api, signup, meta_graph):
    owner = signup()
    meta_graph.list_whatsapp_accounts = lambda token: ACCOUNTS
    url = owner.client.post("/api/v1/integrations/whatsapp/connect").data["url"]
    assert "whatsapp_business_management" in meta_graph.last_scopes
    state = parse_qs(urlparse(url).query)["state"][0]
    r = api.get("/api/meta/callback/", {"code": "abc", "state": state})
    assert parse_qs(urlparse(r["Location"]).query) == {"result": ["ok"], "app": ["whatsapp"]}
    # It did not touch the Meta lead ads connection
    assert owner.client.get("/api/v1/meta/status").data["status"] == "not_connected"

    data = owner.client.get("/api/v1/integrations/whatsapp/manage").data
    assert data["phone_number_id"] == "pn1" and len(data["accounts"][0]["numbers"]) == 2
    r = owner.client.patch(
        "/api/v1/integrations/whatsapp/manage", {"phone_number_id": "pn2"}, format="json"
    )
    assert r.data["phone_number_id"] == "pn2"
    status = next(
        a for a in owner.client.get("/api/v1/integrations").data["apps"] if a["app"] == "whatsapp"
    )
    assert (
        status["status"] == "connected" and status["account_label"] == "+971 50 000 0000 · TPS UAE"
    )
    assert (
        owner.client.patch(
            "/api/v1/integrations/whatsapp/manage", {"phone_number_id": "nope"}, format="json"
        ).status_code
        == 400
    )


def test_whatsapp_without_a_business_account_explains_why(api, signup, meta_graph):
    owner = signup()
    meta_graph.list_whatsapp_accounts = lambda token: []
    url = owner.client.post("/api/v1/integrations/whatsapp/connect").data["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    query = parse_qs(
        urlparse(api.get("/api/meta/callback/", {"code": "x", "state": state})["Location"]).query
    )
    assert query["result"] == ["error"] and "WhatsApp Business Account" in query["message"][0]


def test_whatsapp_embedded_signup_registers_new_numbers(signup, meta_graph, settings):
    settings.META_WHATSAPP_CONFIG_ID = "cfg123"
    owner = signup()
    assert owner.client.get("/api/v1/integrations/whatsapp/signup-config").data["available"] is True
    accounts = [{"id": "waba1", "name": "TPS", "numbers": [
        {"id": "pn1", "display_phone_number": "+91 98250 00000", "verified_name": "TPS",
         "quality_rating": "GREEN", "status": "", "platform_type": "NOT_APPLICABLE"},
    ]}]  # fmt: skip
    calls = {"subscribed": [], "registered": []}
    meta_graph.exchange_signup_code = lambda code: "BUSINESS-TOKEN"
    meta_graph.list_whatsapp_accounts = lambda token: accounts
    meta_graph.subscribe_waba = lambda waba, token: calls["subscribed"].append(waba)
    meta_graph.register_phone = lambda pid, token, pin: calls["registered"].append((pid, pin))

    r = owner.client.post(
        "/api/v1/integrations/whatsapp/embedded",
        {"code": "c", "waba_id": "waba1", "phone_number_id": "pn1", "flow": "new"},
        format="json",
    )
    assert r.status_code == 200, r.data
    assert calls["subscribed"] == ["waba1"]
    assert calls["registered"][0][0] == "pn1" and len(calls["registered"][0][1]) == 6
    assert r.data["two_step_pin"] == calls["registered"][0][1]
    assert r.data["accounts"][0]["numbers"][0]["platform_type"] == "CLOUD_API"
    assert r.data["phone_number_id"] == "pn1" and r.data["setup_issues"] == []


def test_whatsapp_business_app_number_is_not_re_registered(signup, meta_graph):
    owner = signup()
    accounts = [{"id": "waba2", "name": "Shop", "numbers": [
        {"id": "pn9", "display_phone_number": "+91 90000 00000", "verified_name": "Shop",
         "quality_rating": "", "status": "", "platform_type": "NOT_APPLICABLE"},
    ]}]  # fmt: skip
    registered = []
    meta_graph.exchange_signup_code = lambda code: "BUSINESS-TOKEN"
    meta_graph.list_whatsapp_accounts = lambda token: accounts
    meta_graph.subscribe_waba = lambda waba, token: None
    meta_graph.register_phone = lambda pid, token, pin: registered.append(pid)
    r = owner.client.post(
        "/api/v1/integrations/whatsapp/embedded",
        {"code": "c", "waba_id": "waba2", "flow": "coexistence"},
        format="json",
    )
    assert r.status_code == 200 and r.data["flow"] == "coexistence"
    assert registered == []  # the number stays on the WhatsApp Business app too


# --- Google Sheets ------------------------------------------------------------------------
class FakeGoogle:
    def __init__(self):
        self.rows = [
            ["Full Name", "Mobile", "Email", "City"],
            ["Asha Patel", "9825011111", "asha@example.com", "Surat"],
            ["", "", "", "Empty row"],
            ["Ravi Shah", "9825022222", "", "Vadodara"],
        ]

    def oauth_url(self, state):
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    def exchange_code(self, code):
        return {"access_token": "AT", "refresh_token": "RT", "expires_in": 3600}

    def refresh(self, refresh_token):
        return {"access_token": "AT2", "expires_in": 3600}

    def user_email(self, token):
        return "sales@pioneertech.example"

    def list_spreadsheets(self, token, query=""):
        return [{"id": "sheet1", "name": "Expo leads", "modifiedTime": "2026-10-01T10:00:00Z"}]

    def list_tabs(self, token, spreadsheet_id):
        return [{"title": "Leads", "gridProperties": {"rowCount": 1000}}]

    created: list[str] = []
    written: dict = {}

    def create_spreadsheet(self, token, title):
        self.created.append(title)
        return "new-sheet"

    def add_tab(self, token, spreadsheet_id, title):
        self.created.append(f"{spreadsheet_id}:{title}")

    def write_rows(self, token, spreadsheet_id, title, rows):
        self.written[(spreadsheet_id, title)] = rows

    def read_rows(self, token, spreadsheet_id, title, first, last=None):
        rows = self.rows[first - 1 : last]
        while rows and not any(rows[-1]):
            rows.pop()
        return rows


@pytest.fixture
def fake_google(settings):
    settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET = "id", "secret"
    fake = FakeGoogle()
    fake.created, fake.written = [], {}
    google.set_google(fake)
    yield fake
    google.set_google(None)


def test_google_sheets_connect_pick_a_sheet_and_sync_new_rows(api, signup, fake_google):
    owner = signup()
    url = owner.client.post("/api/v1/integrations/google_sheets/connect").data["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    r = api.get("/api/integrations/google/callback/", {"code": "c", "state": state})
    assert parse_qs(urlparse(r["Location"]).query) == {"result": ["ok"], "app": ["google_sheets"]}

    sheets = owner.client.get("/api/v1/integrations/google_sheets/spreadsheets").data["results"]
    assert sheets[0]["name"] == "Expo leads"
    tabs = owner.client.get("/api/v1/integrations/google_sheets/spreadsheets/sheet1/tabs").data
    assert tabs["results"][0]["mapping"] == {
        "name": "Full Name",
        "phone": "Mobile",
        "email": "Email",
    }

    r = owner.client.post(
        "/api/v1/integrations/google_sheets/links",
        {"spreadsheet_id": "sheet1", "spreadsheet_name": "Expo leads", "sheet_title": "Leads"},
        format="json",
    )
    assert r.status_code == 201, r.data
    assert r.data["imported"] == 2 and r.data["last_row"] == 4
    enquiries = owner.client.get("/api/v1/enquiries").data["results"]
    assert {e["name"] for e in enquiries} == {"Asha Patel", "Ravi Shah"}
    assert {e["source"] for e in enquiries} == {"sheets"}

    fake_google.rows.append(["Meera Joshi", "9825033333", "", "Rajkot"])
    link_id = r.data["id"]
    synced = owner.client.post(f"/api/v1/integrations/google_sheets/links/{link_id}/sync").data
    assert synced["imported"] == 1 and synced["rows_imported"] == 3
    assert (
        owner.client.post(
            "/api/v1/integrations/google_sheets/links",
            {"spreadsheet_id": "sheet1", "sheet_title": "Leads"},
            format="json",
        ).status_code
        == 400
    )  # already connected
    paused = owner.client.patch(
        f"/api/v1/integrations/google_sheets/links/{link_id}", {"is_active": False}, format="json"
    )
    assert paused.data["is_active"] is False


def test_google_sheets_needs_the_server_set_up(signup, settings):
    settings.GOOGLE_CLIENT_ID = ""
    r = signup().client.post("/api/v1/integrations/google_sheets/connect")
    assert r.status_code == 400 and "GOOGLE_CLIENT_ID" in r.data["detail"]


def connect_google(api, owner):
    url = owner.client.post("/api/v1/integrations/google_sheets/connect").data["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    api.get("/api/integrations/google/callback/", {"code": "c", "state": state})


def test_leads_are_written_to_a_sheet_and_kept_up_to_date(api, signup, fake_google):
    owner = signup()
    connect_google(api, owner)
    enquiry = create_enquiry(owner, name="Asha Patel")
    r = owner.client.post(
        "/api/v1/integrations/google_sheets/exports",
        {"form": None, "new_title": "Real estate leads"},
        format="json",
    )
    assert r.status_code == 201, r.data
    assert r.data["direction"] == "export" and fake_google.created == ["Real estate leads"]
    rows = fake_google.written[("new-sheet", "Leads")]
    assert rows[0][:6] == ["Enquiry ID", "Created", "Name", "Phone", "Email", "Status"]
    assert rows[1][2] == "Asha Patel" and rows[1][5] == "New"

    # Nothing changed: the sheet is not rewritten
    fake_google.written.clear()
    with tenant_context(owner.tenant_id):
        from apps.integrations.models import SheetLink

        SheetLink.objects.update(last_synced_at=timezone.now() - timedelta(minutes=5))
    owner.client.post("/api/v1/integrations/heartbeat")
    assert fake_google.written == {}

    # A status change shows up in the sheet
    contacted = next(
        s for s in owner.client.get("/api/v1/statuses").data if s["name"] == "Contacted"
    )
    owner.client.patch(
        f"/api/v1/enquiries/{enquiry['id']}", {"status_id": contacted["id"]}, format="json"
    )
    with tenant_context(owner.tenant_id):
        SheetLink.objects.update(last_synced_at=timezone.now() - timedelta(minutes=5))
    owner.client.post("/api/v1/integrations/heartbeat")
    assert fake_google.written[("new-sheet", "Leads")][1][5] == "Contacted"


def test_a_forms_leads_go_to_a_new_tab_of_an_existing_sheet(
    api, signup, fake_google, meta_graph, django_capture_on_commit_callbacks
):
    owner = signup()
    connect(owner)
    connect_google(api, owner)
    with django_capture_on_commit_callbacks(execute=True):
        webhook(api, lead_value(SAMPLE_2))
    create_enquiry(owner, name="Walk-in visitor")  # not from the form
    form = next(
        f
        for f in owner.client.get("/api/v1/meta/forms").data["results"]
        if f["form_id"] == SAMPLE_2["form_id"]
    )
    r = owner.client.post(
        "/api/v1/integrations/google_sheets/exports",
        {"form": form["id"], "spreadsheet_id": "sheet1"},
        format="json",
    )
    assert r.status_code == 201, r.data
    tab = f"LMS - {form['name']}"
    assert fake_google.created == [f"sheet1:{tab}"]
    rows = fake_google.written[("sheet1", tab)]
    assert [row[2] for row in rows[1:]] == ["Aarav Shah"]  # the form's lead only


# --- call results, calling hours, rescheduling -------------------------------------------
def schedule_call(owner, enquiry_id, minutes=60, **extra):
    base = f"/api/v1/enquiries/{enquiry_id}/followups"
    due = (timezone.now() + timedelta(minutes=minutes)).isoformat()
    return owner.client.post(base, {"title": "Call", "due_at": due, **extra}, format="json")


def place_due_call(owner):
    with tenant_context(owner.tenant_id):
        AutoCall.objects.filter(status="pending").update(
            scheduled_at=timezone.now() - timedelta(minutes=1)
        )
    assert owner.client.post("/api/v1/integrations/heartbeat").data["calls_started"] == 1
    with tenant_context(owner.tenant_id):  # Exotel had time to finish the call
        AutoCall.objects.filter(status="started").update(
            started_at=timezone.now() - timedelta(minutes=2)
        )


def test_answered_auto_call_marks_the_scheduled_call_done(signup, fake_exotel):
    owner = signup()
    connect_exotel(owner)
    set_phone(owner)
    owner.client.patch(
        "/api/v1/integrations/exotel/manage", {"auto_call_followups": True}, format="json"
    )
    enquiry = create_enquiry(owner)
    followup = schedule_call(owner, enquiry["id"]).data
    place_due_call(owner)
    fake_exotel.results["CA1"] = {
        "Status": "completed",
        "Details": {
            "Leg1Status": "completed",
            "Leg2Status": "completed",
            "ConversationDuration": 75,
        },
    }
    assert owner.client.post("/api/v1/integrations/heartbeat").data["calls_finished"] == 1
    rows = owner.client.get(f"/api/v1/enquiries/{enquiry['id']}/followups").data
    row = next(
        f
        for f in (rows["results"] if isinstance(rows, dict) else rows)
        if f["id"] == followup["id"]
    )
    assert row["is_done"] is True and row["auto_call_status"] == "completed"
    calls = owner.client.get(f"/api/v1/enquiries/{enquiry['id']}/calls").data
    first = (calls["results"] if isinstance(calls, dict) else calls)[0]
    assert first["outcome"] == "connected" and first["duration_seconds"] == 75


def test_unanswered_auto_call_can_be_rescheduled(signup, fake_exotel):
    owner = signup()
    connect_exotel(owner)
    set_phone(owner)
    owner.client.patch(
        "/api/v1/integrations/exotel/manage", {"auto_call_followups": True}, format="json"
    )
    enquiry = create_enquiry(owner)
    followup = schedule_call(owner, enquiry["id"]).data
    place_due_call(owner)
    # The agent answered, the lead did not
    fake_exotel.results["CA1"] = {
        "Status": "completed",
        "Details": {
            "Leg1Status": "completed",
            "Leg2Status": "no-answer",
            "ConversationDuration": 0,
        },
    }
    owner.client.post("/api/v1/integrations/heartbeat")
    base = f"/api/v1/enquiries/{enquiry['id']}/followups"
    row = next(f for f in owner.client.get(base).data["results"] if f["id"] == followup["id"])
    assert row["is_done"] is False and row["auto_call_status"] == "no_answer"
    listed = owner.client.get("/api/v1/enquiries").data["results"][0]
    assert listed["next_followup"]["auto_call_status"] == "no_answer"

    later = (timezone.now() + timedelta(hours=3)).isoformat()
    r = owner.client.patch(f"{base}/{followup['id']}", {"due_at": later}, format="json")
    assert r.status_code == 200, r.data
    assert r.data["auto_call_status"] == "pending" and r.data["due_at"][:13] == later[:13]


def test_scheduled_calls_go_to_the_lead_owner_by_default(signup, invite_and_join):
    owner = signup()
    agent = invite_and_join(owner, "agent")
    enquiry = create_enquiry(owner, primary_owner_id=agent.user_id)
    r = owner.client.post(
        f"/api/v1/enquiries/{enquiry['id']}/followups",
        {"title": "Call", "due_at": "2030-01-05T10:00:00Z"},
        format="json",
    )
    assert r.data["assignee"]["id"] == agent.user_id
    r = owner.client.post(
        f"/api/v1/enquiries/{enquiry['id']}/followups",
        {"title": "Call", "due_at": "2030-01-05T10:00:00Z", "assignee_id": owner.user_id},
        format="json",
    )
    assert r.data["assignee"]["id"] == owner.user_id


def test_calling_hours(signup, fake_exotel, meta_graph):
    owner = signup()
    connect_exotel(owner)
    manage = "/api/v1/integrations/exotel/manage"
    bad = owner.client.patch(
        manage,
        {"call_window": {"enabled": True, "days": [], "start": "09:00", "end": "18:00"}},
        format="json",
    )
    assert bad.status_code == 400
    # Closed all day today (workspace time zone): only tomorrow onwards
    from zoneinfo import ZoneInfo

    with tenant_context(owner.tenant_id):
        from apps.tenants.models import Tenant

        zone = ZoneInfo(Tenant.objects.get(pk=owner.tenant_id).timezone)
    today = timezone.now().astimezone(zone).weekday()
    days = [d for d in range(7) if d != today]
    window = {"enabled": True, "days": days, "start": "09:00", "end": "18:00"}
    r = owner.client.patch(
        manage, {"call_window": window, "auto_call_followups": True}, format="json"
    )
    assert r.data["settings"]["call_window"]["days"] == days
    assert owner.client.get("/api/v1/integrations/calling").data["call_window"]["start"] == "09:00"

    enquiry = create_enquiry(owner)
    blocked = schedule_call(owner, enquiry["id"], minutes=10)
    assert blocked.status_code == 400 and "calling hours" in str(blocked.data)
    assert schedule_call(owner, enquiry["id"], minutes=10, auto_call=False).status_code == 201

    # A call that became due outside the hours waits for the next opening
    with tenant_context(owner.tenant_id):
        e = Enquiry.objects.get(pk=enquiry["id"])
        AutoCall.objects.create(tenant_id=owner.tenant_id, enquiry=e, reason="new_lead")
    owner.client.post("/api/v1/integrations/heartbeat")
    with tenant_context(owner.tenant_id):
        waiting = AutoCall.objects.get(reason="new_lead")
    local = waiting.scheduled_at.astimezone(zone)
    assert waiting.status == "pending" and local.weekday() != today and local.hour == 9
    assert fake_exotel.calls == []


# --- Conversions API --------------------------------------------------------------------
def test_status_changes_are_sent_to_meta_as_lead_feedback(
    api, signup, meta_graph, django_capture_on_commit_callbacks
):
    owner = signup()
    connect(owner)
    sent = []
    meta_graph.send_conversion_events = lambda dataset, token, events, test_event_code="": (
        sent.append((dataset, token, events, test_event_code))
    )
    assert (
        owner.client.patch("/api/v1/meta/conversions", {"enabled": True}, format="json").status_code
        == 400
    )
    r = owner.client.patch(
        "/api/v1/meta/conversions",
        {"dataset_id": "123456789", "token": "CAPI-TOKEN", "enabled": True},
        format="json",
    )
    assert r.data["enabled"] is True and r.data["token_set"] is True and "token" not in r.data

    with django_capture_on_commit_callbacks(execute=True):
        webhook(api, lead_value(SAMPLE_2))
    assert sent[-1][2][0]["event_name"] == "New"  # the first stage, when the lead arrives
    enquiry = owner.client.get("/api/v1/enquiries").data["results"][0]
    qualified = next(
        s for s in owner.client.get("/api/v1/statuses").data if s["name"] == "Qualified"
    )
    with django_capture_on_commit_callbacks(execute=True):
        owner.client.patch(
            f"/api/v1/enquiries/{enquiry['id']}", {"status_id": qualified["id"]}, format="json"
        )
    dataset, token, events, _ = sent[-1]
    event = events[0]
    assert dataset == "123456789" and token == "CAPI-TOKEN"
    assert event["event_name"] == "Qualified" and event["action_source"] == "system_generated"
    assert event["user_data"]["lead_id"] == int(SAMPLE_2["id"])
    assert event["custom_data"] == {"event_source": "crm", "lead_event_source": "LMS"}
    log = owner.client.get("/api/v1/meta/conversions").data["events"]
    assert [e["event_name"] for e in log[:2]] == ["Qualified", "New"] and log[0]["success"]

    test = owner.client.post(
        "/api/v1/meta/conversions/test", {"test_event_code": "TEST123"}, format="json"
    )
    assert test.status_code == 200 and sent[-1][3] == "TEST123"


def test_manual_enquiries_are_not_sent_to_meta(
    signup, meta_graph, django_capture_on_commit_callbacks
):
    owner = signup()
    connect(owner)
    sent = []
    meta_graph.send_conversion_events = lambda *a, **k: sent.append(a)
    owner.client.patch(
        "/api/v1/meta/conversions",
        {"dataset_id": "1", "token": "T", "enabled": True},
        format="json",
    )
    enquiry = create_enquiry(owner)
    contacted = next(
        s for s in owner.client.get("/api/v1/statuses").data if s["name"] == "Contacted"
    )
    with django_capture_on_commit_callbacks(execute=True):
        owner.client.patch(
            f"/api/v1/enquiries/{enquiry['id']}", {"status_id": contacted["id"]}, format="json"
        )
    assert sent == []


# --- sheets: a form sent to a sheet is switched on -----------------------------------------
def test_sending_a_switched_off_form_switches_it_on(api, signup, fake_google, meta_graph):
    owner = signup()
    connect(owner)
    owner.client.patch("/api/v1/meta/settings", {"auto_connect_forms": False}, format="json")
    forms = owner.client.get("/api/v1/meta/forms").data["results"]
    off = forms[0]
    owner.client.post(f"/api/v1/meta/forms/{off['id']}/disconnect")
    connect_google(api, owner)
    r = owner.client.post(
        "/api/v1/integrations/google_sheets/exports", {"form": off["id"]}, format="json"
    )
    assert r.status_code == 201
    forms = {f["id"]: f for f in owner.client.get("/api/v1/meta/forms").data["results"]}
    assert forms[off["id"]]["is_connected"] is True

    other = next(f for f in forms.values() if f["id"] != off["id"])
    changed = owner.client.patch(
        f"/api/v1/integrations/google_sheets/links/{r.data['id']}",
        {"form": other["id"]},
        format="json",
    )
    assert changed.data["form"] == other["id"] and changed.data["form_name"] == other["name"]
