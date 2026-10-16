"""Phase 1: contacts, enquiries, duplicate handling, timeline and work items."""

import json
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction

from apps.contacts.models import Contact
from apps.enquiries.ingestion import EnquiryData, ingest_enquiry
from apps.enquiries.models import Enquiry, StatusHistory
from apps.tenants.models import Tenant
from common.dates import parse_meta_time
from common.tenancy.context import tenant_context

from .conftest import create_enquiry

pytestmark = pytest.mark.django_db
REFERENCE = Path(__file__).resolve().parents[2] / "docs" / "reference"


def timeline_types(session, enquiry_id) -> list[str]:
    r = session.client.get(f"/api/v1/enquiries/{enquiry_id}/timeline")
    assert r.status_code == 200
    return [item["type"] for item in r.data["results"]]


# --- the Phase 1 "Done when" ---------------------------------------------------------
def test_create_then_repeat_same_phone_links_to_one_contact(signup):
    owner = signup()
    first = create_enquiry(owner, phone="+919800022222")
    assert first["status"]["name"] == "New"
    assert first["is_repeat"] is False
    assert first["contact"]["phone_e164"] == "+919800022222"

    # Same person, typed differently: still one contact.
    second = create_enquiry(owner, name="Aarav S", phone="098000 22222")
    assert second["contact"]["id"] == first["contact"]["id"]
    assert second["is_repeat"] is True
    assert second["contact"]["enquiry_count"] == 2
    assert second["name"] == "Aarav S"  # each enquiry keeps what it submitted

    assert timeline_types(owner, first["id"]) == ["enquiry_created"]
    assert set(timeline_types(owner, second["id"])) == {"enquiry_created", "repeat_enquiry"}

    contact = owner.client.get(f"/api/v1/contacts/{first['contact']['id']}").data
    assert {e["id"] for e in contact["enquiries"]} == {first["id"], second["id"]}


def test_repeat_fills_only_empty_contact_fields(signup):
    owner = signup()
    first = create_enquiry(owner, name="Riya", email="")
    second = create_enquiry(owner, name="Riya Shah", email="Riya@Example.com")
    contact = owner.client.get(f"/api/v1/contacts/{first['contact']['id']}").data
    assert contact["name"] == "Riya"  # never overwritten
    assert contact["email"] == "riya@example.com"  # blank field filled, lowercased
    assert "contact_information_updated" in timeline_types(owner, second["id"])


def test_email_dedupe_workspace_and_phone_fallback(signup):
    owner = signup()
    owner.client.patch("/api/v1/workspace", {"dedupe_key": "email"}, format="json")
    a = create_enquiry(owner, phone="+919800011111", email="pl@example.com")
    b = create_enquiry(owner, phone="+919000000001", email="PL@example.com")
    assert a["contact"]["id"] == b["contact"]["id"]
    # No email: falls back to phone.
    c = create_enquiry(owner, phone="+919800011111", email="")
    assert c["contact"]["id"] == a["contact"]["id"]


def test_lead_without_phone_or_email_gets_its_own_contact(signup):
    owner = signup()
    with tenant_context(owner.tenant_id):
        tenant = Tenant.objects.get(pk=owner.tenant_id)
        one = ingest_enquiry(tenant=tenant, data=EnquiryData(name="Unknown"))
        two = ingest_enquiry(tenant=tenant, data=EnquiryData(name="Unknown"))
        assert one.contact.pk != two.contact.pk
        assert not one.is_repeat and not two.is_repeat


def test_unique_index_blocks_duplicate_contacts(signup):
    owner = signup()
    with tenant_context(owner.tenant_id):
        Contact.objects.create(tenant_id=owner.tenant_id, phone_e164="+919800022222")
        with pytest.raises(IntegrityError), transaction.atomic():
            Contact.objects.create(tenant_id=owner.tenant_id, phone_e164="+919800022222")


def test_reference_meta_lead_maps_correctly(signup):
    """Sample lead 2 from docs/reference (spec section 4, worked example)."""
    lead = json.loads(
        (REFERENCE / "sample_2_Leads_Event4th5thJuly_10_06_26.json").read_text("utf-8")
    )
    answers = {f["name"]: f["values"][0] for f in lead["field_data"]}
    owner = signup()
    with tenant_context(owner.tenant_id):
        tenant = Tenant.objects.get(pk=owner.tenant_id)
        result = ingest_enquiry(
            tenant=tenant,
            data=EnquiryData(
                name=answers["full_name"],
                phone=answers["phone_number"],
                email=answers["email"],
                source="meta",
                campaign_name=lead["campaign_name"],
                adset_name=lead["adset_name"],
                ad_name=lead["ad_name"],
                form_id=lead["form_id"],
                leadgen_id=lead["id"],
                created_at=parse_meta_time(lead["created_time"]),
            ),
        )
        e = result.enquiry
        assert result.contact.phone_e164 == "+919800022222"
        assert result.contact.email_lower == "aarav.shah@example.com"
        assert e.ad_name == "New Leads ad – Copy 2"  # en dash kept
        assert e.campaign_name == "Leads_Event4th5thJuly_10/06/26"
        assert e.status.name == "New" and e.primary_owner_id is None  # Unassigned
        # leadgen_id is unique per workspace (idempotency key)
        with pytest.raises(IntegrityError), transaction.atomic():
            Enquiry.objects.create(
                tenant=tenant, contact=result.contact, status=e.status, leadgen_id=lead["id"]
            )


# --- editing ---------------------------------------------------------------------------
def test_status_and_field_changes_are_tracked(signup):
    owner = signup()
    e = create_enquiry(owner)
    statuses = owner.client.get("/api/v1/statuses").data
    contacted = next(s for s in statuses if s["name"] == "Contacted")

    r = owner.client.patch(
        f"/api/v1/enquiries/{e['id']}",
        {"status_id": contacted["id"], "campaign_name": "Diwali"},
        format="json",
    )
    assert r.status_code == 200
    assert r.data["status"]["name"] == "Contacted"
    with tenant_context(owner.tenant_id):
        history = list(StatusHistory.objects.filter(enquiry_id=e["id"]).order_by("changed_at"))
        assert [h.to_status.name for h in history] == ["New", "Contacted"]
    types = timeline_types(owner, e["id"])
    assert types[:2] == ["field_changed", "status_changed"] or set(types) >= {
        "status_changed",
        "field_changed",
    }


def test_phone_is_locked_after_creation(signup):
    owner = signup()
    e = create_enquiry(owner)
    r = owner.client.patch(
        f"/api/v1/enquiries/{e['id']}", {"phone": "+919999999999"}, format="json"
    )
    assert r.status_code == 400


def test_invalid_phone_and_missing_contact_details(signup):
    owner = signup()
    r = owner.client.post("/api/v1/enquiries", {"name": "X", "phone": "12"}, format="json")
    assert r.status_code == 400 and "phone" in r.data["errors"]
    r = owner.client.post("/api/v1/enquiries", {"name": "X"}, format="json")
    assert r.status_code == 400


def test_soft_delete_hides_enquiry_and_auto_deletes_contact(signup):
    owner = signup()
    e = create_enquiry(owner)
    assert owner.client.delete(f"/api/v1/enquiries/{e['id']}").status_code == 204
    assert owner.client.get(f"/api/v1/enquiries/{e['id']}").status_code == 404
    assert owner.client.get(f"/api/v1/contacts/{e['contact']['id']}").status_code == 404
    with tenant_context(owner.tenant_id):
        assert Enquiry.objects.get(pk=e["id"]).deleted_at is not None  # soft, not hard
    # The same phone later starts a fresh contact
    again = create_enquiry(owner)
    assert again["contact"]["id"] != e["contact"]["id"]
    assert again["is_repeat"] is False


# --- roles -------------------------------------------------------------------------------
def test_agent_owns_what_they_create_and_sees_only_their_own(signup, invite_and_join):
    owner = signup()
    agent_a = invite_and_join(owner, "agent")
    agent_b = invite_and_join(owner, "agent")
    mine = create_enquiry(agent_a, phone="+919811111111")
    assert mine["primary_owner"]["id"] == agent_a.user_id

    other = create_enquiry(owner, phone="+919822222222")  # unassigned
    assert agent_a.client.get(f"/api/v1/enquiries/{other['id']}").status_code == 404
    assert agent_b.client.get(f"/api/v1/enquiries/{mine['id']}").status_code == 404
    assert agent_a.client.get("/api/v1/enquiries").data["count"] == 1
    assert owner.client.get("/api/v1/enquiries").data["count"] == 2

    # Agents cannot reassign or delete
    r = agent_a.client.patch(
        f"/api/v1/enquiries/{mine['id']}", {"primary_owner_id": agent_b.user_id}, format="json"
    )
    assert r.status_code == 403
    assert agent_a.client.delete(f"/api/v1/enquiries/{mine['id']}").status_code == 403

    # Contacts are scoped the same way, and read-only for everyone
    assert agent_a.client.get("/api/v1/contacts").data["count"] == 1
    assert owner.client.post("/api/v1/contacts", {"name": "x"}, format="json").status_code == 405


def test_secondary_owner_can_see_and_manager_sees_team(signup, invite_and_join):
    owner = signup()
    agent = invite_and_join(owner, "agent")
    manager = invite_and_join(owner, "manager")
    outsider = invite_and_join(owner, "agent")
    owner.client.post(
        "/api/v1/teams",
        {"name": "North", "member_ids": [agent.user_id, manager.user_id]},
        format="json",
    )
    shared = create_enquiry(
        owner,
        phone="+919833333333",
        primary_owner_id=outsider.user_id,
        secondary_owner_ids=[agent.user_id],
    )
    assert agent.client.get(f"/api/v1/enquiries/{shared['id']}").status_code == 200
    team_lead = create_enquiry(agent, phone="+919844444444")
    unassigned = create_enquiry(owner, phone="+919855555555")
    outsider_only = create_enquiry(outsider, phone="+919866666666")

    seen = {e["id"] for e in manager.client.get("/api/v1/enquiries").data["results"]}
    assert {shared["id"], team_lead["id"], unassigned["id"]} <= seen
    assert outsider_only["id"] not in seen


def test_viewer_is_read_only(signup, invite_and_join):
    owner = signup()
    viewer = invite_and_join(owner, "viewer")
    r = viewer.client.post(
        "/api/v1/enquiries", {"name": "X", "phone": "+919877777777"}, format="json"
    )
    assert r.status_code == 403


# --- work items --------------------------------------------------------------------------
def test_notes_calls_followups_and_timeline(signup):
    owner = signup()
    e = create_enquiry(owner)
    base = f"/api/v1/enquiries/{e['id']}"

    assert (
        owner.client.post(f"{base}/notes", {"body": "Wants a 2BHK"}, format="json").status_code
        == 201
    )
    r = owner.client.post(
        f"{base}/calls",
        {"outcome": "connected", "duration_seconds": 95, "notes": "Call back Friday"},
        format="json",
    )
    assert r.status_code == 201 and r.data["user"]["id"] == owner.user_id
    assert owner.client.post(f"{base}/calls", {"outcome": "nope"}, format="json").status_code == 400

    r = owner.client.post(
        f"{base}/followups", {"title": "Call back", "due_at": "2030-01-05T10:00:00Z"}, format="json"
    )
    assert r.status_code == 201 and r.data["assignee"]["id"] == owner.user_id
    fid = r.data["id"]
    r = owner.client.patch(f"{base}/followups/{fid}", {"done": True}, format="json")
    assert r.data["is_done"] is True

    assert owner.client.get(f"{base}/notes").data["count"] == 1
    assert owner.client.get(f"{base}/calls").data["count"] == 1
    assert set(timeline_types(owner, e["id"])) == {
        "enquiry_created",
        "note_added",
        "call_logged",
        "followup_scheduled",
        "followup_completed",
    }
    # list shows the next open follow-up
    listed = owner.client.get("/api/v1/enquiries").data["results"][0]
    assert listed["next_followup_at"] is None  # the only one is done


def test_attachments_upload_validate_and_download(signup, settings):
    owner = signup()
    e = create_enquiry(owner)
    base = f"/api/v1/enquiries/{e['id']}/attachments"
    pdf = SimpleUploadedFile("brochure.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    r = owner.client.post(base, {"file": pdf}, format="multipart")
    assert r.status_code == 201 and r.data["file_name"] == "brochure.pdf"

    exe = SimpleUploadedFile("run.exe", b"MZ", content_type="application/x-msdownload")
    assert owner.client.post(base, {"file": exe}, format="multipart").status_code == 400
    settings.ATTACHMENT_MAX_BYTES = 5
    big = SimpleUploadedFile("big.pdf", b"0123456789", content_type="application/pdf")
    assert owner.client.post(base, {"file": big}, format="multipart").status_code == 400

    download = owner.client.get(f"{base}/{r.data['id']}/download")
    assert download.status_code == 200
    assert b"".join(download.streaming_content) == b"%PDF-1.4 test"


def test_form_response_is_404_for_manual_enquiries(signup):
    owner = signup()
    e = create_enquiry(owner)
    assert owner.client.get(f"/api/v1/enquiries/{e['id']}/form-response").status_code == 404


# --- isolation -------------------------------------------------------------------------------
def test_other_workspace_cannot_reach_enquiries_or_children(signup):
    a, b = signup(), signup()
    e = create_enquiry(a)
    for path in ("", "/timeline", "/notes", "/calls", "/followups", "/attachments"):
        assert b.client.get(f"/api/v1/enquiries/{e['id']}{path}").status_code == 404
    assert (
        b.client.post(
            f"/api/v1/enquiries/{e['id']}/notes", {"body": "x"}, format="json"
        ).status_code
        == 404
    )
    assert b.client.get(f"/api/v1/contacts/{e['contact']['id']}").status_code == 404
    # Same phone in another workspace is a different contact
    other = create_enquiry(b)
    assert other["contact"]["id"] != e["contact"]["id"] and other["is_repeat"] is False
    with tenant_context(b.tenant_id):  # RLS: unscoped query sees only B
        assert set(Enquiry.objects.values_list("id", flat=True)) == {other["id"]}
        assert Contact.objects.count() == 1


# --- voice notes, list extras and column preferences -----------------------------------------
def test_voice_note_upload_and_private_playback(signup):
    owner = signup()
    other = signup()
    e = create_enquiry(owner)
    base = f"/api/v1/enquiries/{e['id']}/notes"
    voice = SimpleUploadedFile("voice.webm", b"\x1aE\xdf\xa3fake-webm", content_type="audio/webm")
    r = owner.client.post(base, {"audio": voice, "audio_duration_seconds": 12}, format="multipart")
    assert r.status_code == 201, r.data
    assert r.data["has_audio"] is True and r.data["audio_duration_seconds"] == 12
    note_id = r.data["id"]

    played = owner.client.get(f"{base}/{note_id}/audio")
    assert played.status_code == 200
    assert b"".join(played.streaming_content).endswith(b"fake-webm")
    assert other.client.get(f"{base}/{note_id}/audio").status_code == 404

    # Empty note and wrong format are refused
    assert owner.client.post(base, {"body": "  "}, format="multipart").status_code == 400
    exe = SimpleUploadedFile("x.exe", b"MZ", content_type="application/x-msdownload")
    assert owner.client.post(base, {"audio": exe}, format="multipart").status_code == 400
    timeline = owner.client.get(f"/api/v1/enquiries/{e['id']}/timeline").data["results"]
    assert timeline[0]["details"]["voice"] is True


def test_list_rows_carry_next_followup_for_the_action_badge(signup):
    owner = signup()
    e = create_enquiry(owner)
    base = f"/api/v1/enquiries/{e['id']}/followups"
    owner.client.post(base, {"title": "Later", "due_at": "2031-01-05T10:00:00Z"}, format="json")
    owner.client.post(base, {"title": "First", "due_at": "2030-01-05T10:00:00Z"}, format="json")
    row = owner.client.get("/api/v1/enquiries").data["results"][0]
    assert row["next_followup"]["title"] == "First"
    assert row["adset_name"] == "" and row["secondary_owners"] == []


def test_table_preferences_are_per_user(signup, invite_and_join):
    owner = signup()
    agent = invite_and_join(owner, "agent")
    url = "/api/v1/preferences/tables/enquiries"
    assert owner.client.get(url).data["columns"] == []
    r = owner.client.put(url, {"columns": ["campaign", "phone", "phone", "cf:city"]}, format="json")
    assert r.data["columns"] == ["campaign", "phone", "cf:city"]
    assert owner.client.get(url).data["columns"] == ["campaign", "phone", "cf:city"]
    assert agent.client.get(url).data["columns"] == []  # not shared
    assert owner.client.get("/api/v1/preferences/tables/nope").status_code == 404
