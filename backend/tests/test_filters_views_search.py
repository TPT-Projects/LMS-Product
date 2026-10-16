"""Phase 2: custom fields, filter engine, smart/saved views, search, bulk actions, speed."""

import json
import time
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone

from apps.contacts.models import Contact
from apps.customfields.models import EnquiryCustomValue
from apps.enquiries.models import Enquiry, FollowUp
from apps.statuses.models import Status
from common.tenancy.context import tenant_context

from .conftest import create_enquiry

pytestmark = pytest.mark.django_db


def make_field(session, **data) -> dict:
    r = session.client.post("/api/v1/custom-fields", data, format="json")
    assert r.status_code == 201, r.data
    return r.data


def ids(response) -> set[int]:
    assert response.status_code == 200, response.data
    return {row["id"] for row in response.data["results"]}


def list_with(session, tree=None, **params):
    if tree is not None:
        params["filter"] = json.dumps(tree)
    return session.client.get("/api/v1/enquiries", params)


# --- custom fields -----------------------------------------------------------------
def test_custom_field_types_validate_and_round_trip(signup):
    owner = signup()
    make_field(
        owner, label="Investment budget", type="dropdown", options=["₹5_cr+", "₹1.9_cr_–_₹3_cr"]
    )
    make_field(owner, label="Budget amount", type="currency")
    make_field(owner, label="Visit date", type="date")
    make_field(owner, label="Interests", type="multi_select", options=["villa", "flat"])
    make_field(owner, label="Hot lead", type="checkbox")
    assert (
        owner.client.post(
            "/api/v1/custom-fields", {"label": "Bad", "type": "dropdown"}, format="json"
        ).status_code
        == 400
    )  # dropdown needs options

    e = create_enquiry(
        owner,
        custom_fields={
            "investment_budget": "₹5_cr+",
            "budget_amount": "1,50,00,000",
            "visit_date": "05/07/2026",
            "interests": ["villa"],
            "hot_lead": True,
        },
    )
    assert e["custom_fields"] == {
        "investment_budget": "₹5_cr+",
        "budget_amount": 15000000,
        "visit_date": "05/07/2026",
        "interests": ["villa"],
        "hot_lead": True,
    }

    bad = owner.client.post(
        "/api/v1/enquiries",
        {
            "name": "X",
            "phone": "+919811111111",
            "custom_fields": {"budget_amount": "lots", "visit_date": "2026/13/45", "nope": 1},
        },
        format="json",
    )
    assert bad.status_code == 400
    assert set(bad.data["errors"]["custom_fields"]) == {"budget_amount", "visit_date", "nope"}

    # Edit + clear; change is on the timeline
    r = owner.client.patch(
        f"/api/v1/enquiries/{e['id']}",
        {"custom_fields": {"hot_lead": False, "interests": []}},
        format="json",
    )
    assert r.data["custom_fields"]["hot_lead"] is False
    assert "interests" not in r.data["custom_fields"]
    timeline = owner.client.get(f"/api/v1/enquiries/{e['id']}/timeline").data["results"]
    assert timeline[0]["type"] == "field_changed"


def test_required_custom_field_and_locked_type(signup):
    owner = signup()
    field = make_field(owner, label="City", type="text", is_required=True)
    r = owner.client.post(
        "/api/v1/enquiries", {"name": "X", "phone": "+919811111111"}, format="json"
    )
    assert r.status_code == 400 and "city" in r.data["errors"]["custom_fields"]
    r = owner.client.patch(
        f"/api/v1/custom-fields/{field['id']}", {"type": "number"}, format="json"
    )
    assert r.status_code == 400


def test_agents_cannot_manage_custom_fields(signup, invite_and_join):
    owner = signup()
    agent = invite_and_join(owner, "agent")
    assert agent.client.get("/api/v1/custom-fields").status_code == 200
    r = agent.client.post("/api/v1/custom-fields", {"label": "X", "type": "text"}, format="json")
    assert r.status_code == 403


# --- filter engine -----------------------------------------------------------------
@pytest.fixture
def dataset(signup, invite_and_join):
    owner = signup()
    agent = invite_and_join(owner, "agent")
    make_field(owner, label="Purpose", type="dropdown", options=["investment", "end_use"])
    make_field(owner, label="Budget", type="number")
    rows = {
        "dubai": create_enquiry(
            owner,
            name="Dubai A",
            phone="+919800000001",
            campaign_name="Leads_Dubai Properties_09/06/26",
            custom_fields={"purpose": "investment", "budget": 500},
        ),
        "event": create_enquiry(
            owner,
            name="Event B",
            phone="+919800000002",
            campaign_name="Leads_Event4th5thJuly_10/06/26",
            custom_fields={"purpose": "end_use", "budget": 120},
        ),
        "agent": create_enquiry(
            agent,
            name="Agent C",
            phone="+919800000003",
            email="c@example.com",
            custom_fields={"budget": 80},
        ),
    }
    return owner, agent, rows


def test_and_or_groups_with_custom_fields(dataset):
    owner, _, rows = dataset
    tree = {
        "op": "or",
        "rules": [
            {
                "op": "and",
                "rules": [
                    {"field": "campaign", "operator": "contains", "value": "dubai"},
                    {"field": "cf:purpose", "operator": "eq", "value": "investment"},
                ],
            },
            {"field": "cf:budget", "operator": "lt", "value": 100},
        ],
    }
    assert ids(list_with(owner, tree)) == {rows["dubai"]["id"], rows["agent"]["id"]}

    between = {"field": "cf:budget", "operator": "between", "value": [100, 600]}
    assert ids(list_with(owner, between)) == {rows["dubai"]["id"], rows["event"]["id"]}
    empty = {"field": "cf:purpose", "operator": "is_empty"}
    assert ids(list_with(owner, empty)) == {rows["agent"]["id"]}
    owner_me = {"field": "owner", "operator": "eq", "value": "me"}
    assert ids(list_with(owner, owner_me)) == set()  # owner created them unassigned


def test_quick_filters_dates_and_search(dataset):
    owner, agent, rows = dataset
    with tenant_context(owner.tenant_id):
        Enquiry.objects.filter(pk=rows["event"]["id"]).update(
            created_at=timezone.now() - timedelta(days=40)
        )
    today = timezone.localdate().strftime("%d/%m/%Y")
    assert rows["event"]["id"] not in ids(list_with(owner, created_from=today))
    last_7 = {"field": "created_at", "operator": "last_days", "value": 7}
    assert rows["event"]["id"] not in ids(list_with(owner, last_7))

    assert ids(list_with(owner, owner=str(agent.user_id))) == {rows["agent"]["id"]}
    assert ids(list_with(owner, q="98000 00002")) == {rows["event"]["id"]}  # phone digits
    assert ids(list_with(owner, q="C@EXAMPLE")) == {rows["agent"]["id"]}
    assert ids(list_with(owner, q="end_use")) == {rows["event"]["id"]}  # custom text value


def test_bad_filters_are_rejected_safely(dataset):
    owner, _, rows = dataset
    assert list_with(owner, {"field": "password", "operator": "eq", "value": 1}).status_code == 400
    assert list_with(owner, {"field": "name", "operator": "gt", "value": 1}).status_code == 400
    assert owner.client.get("/api/v1/enquiries", {"filter": "{not json"}).status_code == 400
    injection = {"field": "name", "operator": "contains", "value": "'; DROP TABLE enquiries; --"}
    assert ids(list_with(owner, injection)) == set()
    assert len(ids(owner.client.get("/api/v1/enquiries"))) == 3  # table is fine


def test_system_views(dataset):
    owner, agent, rows = dataset
    assert ids(owner.client.get("/api/v1/enquiries", {"view": "unassigned"})) == {
        rows["dubai"]["id"],
        rows["event"]["id"],
    }
    assert ids(agent.client.get("/api/v1/enquiries", {"view": "mine"})) == {rows["agent"]["id"]}
    owner.client.post(
        f"/api/v1/enquiries/{rows['dubai']['id']}/followups",
        {"title": "Call", "due_at": timezone.now().isoformat()},
        format="json",
    )
    owner.client.post(
        f"/api/v1/enquiries/{rows['event']['id']}/followups",
        {"title": "Later", "due_at": (timezone.now() + timedelta(days=3)).isoformat()},
        format="json",
    )
    assert ids(owner.client.get("/api/v1/enquiries", {"view": "calls-today"})) == {
        rows["dubai"]["id"]
    }


def test_saved_views_share_pin_counts(dataset, invite_and_join):
    owner, agent, rows = dataset
    filters = {"filter": {"field": "cf:purpose", "operator": "eq", "value": "investment"}}
    r = owner.client.post("/api/v1/views", {"name": "Investors", "filters": filters}, format="json")
    assert r.status_code == 201 and r.data["is_pinned"] is True
    view_id = r.data["id"]

    assert ids(owner.client.get("/api/v1/enquiries", {"saved_view": view_id})) == {
        rows["dubai"]["id"]
    }
    counts = owner.client.get("/api/v1/views/counts").data
    assert counts["system"]["all"] == 3 and counts["saved"][str(view_id)] == 1

    # Private until shared
    assert agent.client.get(f"/api/v1/views/{view_id}").status_code == 404
    owner.client.patch(f"/api/v1/views/{view_id}", {"is_shared": True}, format="json")
    assert agent.client.get(f"/api/v1/views/{view_id}").status_code == 200
    # Only the owner edits; anyone can pin for themselves
    assert (
        agent.client.patch(f"/api/v1/views/{view_id}", {"name": "x"}, format="json").status_code
        == 403
    )
    assert agent.client.post(f"/api/v1/views/{view_id}/pin").status_code == 204
    # A shared view still respects the viewer's own visibility
    assert ids(agent.client.get("/api/v1/enquiries", {"saved_view": view_id})) == set()

    bad = {"filter": {"field": "nope", "operator": "eq", "value": 1}}
    assert (
        owner.client.post(
            "/api/v1/views", {"name": "Bad", "filters": bad}, format="json"
        ).status_code
        == 400
    )


def test_global_search(dataset):
    owner, agent, rows = dataset
    r = owner.client.get("/api/v1/search", {"q": "9800000003"})
    assert [e["id"] for e in r.data["enquiries"]] == [rows["agent"]["id"]]
    assert len(r.data["contacts"]) == 1
    assert (
        owner.client.get("/api/v1/search", {"q": "Dubai"}).data["enquiries"][0]["id"]
        == rows["dubai"]["id"]
    )
    assert agent.client.get("/api/v1/search", {"q": "Dubai"}).data["enquiries"] == []  # not visible


def test_bulk_actions(dataset):
    owner, agent, rows = dataset
    all_ids = [r["id"] for r in rows.values()]
    qualified = next(
        s for s in owner.client.get("/api/v1/statuses").data if s["name"] == "Qualified"
    )
    r = owner.client.post(
        "/api/v1/enquiries/bulk",
        {"ids": all_ids, "action": "set_status", "value": qualified["id"]},
        format="json",
    )
    assert r.data == {"updated": 3, "skipped": 0}
    assert ids(owner.client.get("/api/v1/enquiries", {"status": qualified["id"]})) == set(all_ids)

    r = owner.client.post(
        "/api/v1/enquiries/bulk",
        {"ids": all_ids, "action": "assign", "value": agent.user_id},
        format="json",
    )
    assert r.status_code == 200
    assert agent.client.get("/api/v1/enquiries").data["count"] == 3

    r = agent.client.post(
        "/api/v1/enquiries/bulk", {"ids": all_ids, "action": "delete"}, format="json"
    )
    assert r.status_code == 403
    r = owner.client.post(
        "/api/v1/enquiries/bulk", {"ids": all_ids[:2], "action": "delete"}, format="json"
    )
    assert r.data["updated"] == 2
    assert owner.client.get("/api/v1/enquiries").data["count"] == 1


def test_sort_and_page_size(dataset):
    owner, _, rows = dataset
    r = owner.client.get("/api/v1/enquiries", {"sort": "name", "page_size": 50})
    assert [row["name"] for row in r.data["results"]] == ["Agent C", "Dubai A", "Event B"]
    assert r.data["page_size"] == 50
    r = owner.client.get("/api/v1/enquiries", {"sort": "nonsense"})
    assert r.status_code == 200  # falls back to newest first


# --- performance (Phase 2 "Done when") ------------------------------------------------
def test_ten_thousand_enquiries_custom_field_filter_is_fast(signup, django_assert_max_num_queries):
    owner = signup()
    field = make_field(owner, label="Budget", type="number")
    n = 10_000
    with tenant_context(owner.tenant_id):
        status = Status.objects.get(tenant_id=owner.tenant_id, is_default=True)
        contacts = Contact.objects.bulk_create(
            Contact(tenant_id=owner.tenant_id, name=f"Lead {i}", phone_e164=f"+9190000{i:05d}")
            for i in range(n)
        )
        enquiries = Enquiry.objects.bulk_create(
            Enquiry(
                tenant_id=owner.tenant_id,
                contact=c,
                status=status,
                name=c.name,
                phone_e164=c.phone_e164,
                campaign_name=f"Campaign {i % 7}",
            )
            for i, c in enumerate(contacts)
        )
        EnquiryCustomValue.objects.bulk_create(
            EnquiryCustomValue(
                tenant_id=owner.tenant_id, enquiry=e, field_id=field["id"], value_number=Decimal(i)
            )
            for i, e in enumerate(enquiries)
        )
        FollowUp.objects.bulk_create(
            FollowUp(tenant_id=owner.tenant_id, enquiry=e, title="x", due_at=timezone.now())
            for e in enquiries[:500]
        )
        # What autovacuum does after a bulk load in a real database: refresh planner stats.
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE enquiries, contacts, enquiry_custom_values, followups")

    tree = {"field": "cf:budget", "operator": "gte", "value": 9_000}
    started = time.perf_counter()
    r = list_with(owner, tree, page_size=200)
    elapsed = time.perf_counter() - started
    assert r.data["count"] == 1_000
    assert len(r.data["results"]) == 200
    assert elapsed < 2.0, f"custom-field filter took {elapsed:.2f}s"

    # A 200-row page uses a fixed number of queries (no N+1)
    with django_assert_max_num_queries(12):
        r = owner.client.get("/api/v1/enquiries", {"page_size": 200, "page": 3})
    assert r.data["count"] == n and len(r.data["results"]) == 200

    started = time.perf_counter()
    owner.client.get("/api/v1/views/counts")
    assert time.perf_counter() - started < 2.0
