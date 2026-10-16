"""Tenant isolation (spec sections 0.7 and 11).

Proves that one workspace cannot read or write another workspace's data:
- through the API (ORM scoping + permissions),
- directly in PostgreSQL (Row Level Security, even with unscoped queries),
- in MongoDB (see test_mongo_isolation.py).
"""

import pytest
from django.db import connection
from django.db.utils import ProgrammingError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Invitation, Membership, User
from apps.teams.models import Team
from apps.tenants.models import Tenant
from common.tenancy.context import rls_bypass, set_db_tenant, tenant_context

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_workspaces(signup, invite_and_join):
    a = signup(workspace="Tenant A")
    b = signup(workspace="Tenant B")
    a_agent = invite_and_join(a, "agent")
    b_agent = invite_and_join(b, "agent")
    a_team = a.client.post("/api/v1/teams", {"name": "A Team"}, format="json").data
    b_team = b.client.post("/api/v1/teams", {"name": "B Team"}, format="json").data
    return {
        "a": a,
        "b": b,
        "a_agent": a_agent,
        "b_agent": b_agent,
        "a_team": a_team,
        "b_team": b_team,
    }


# --- API layer ---------------------------------------------------------------------
def test_api_lists_only_own_tenant(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    a_users = {u["id"] for u in a.client.get("/api/v1/users").data["results"]}
    assert two_workspaces["b_agent"].user_id not in a_users
    assert b.user_id not in a_users

    a_teams = [t["name"] for t in a.client.get("/api/v1/teams").data["results"]]
    assert a_teams == ["A Team"]
    assert a.client.get("/api/v1/workspace").data["name"] == "Tenant A"


def test_api_cannot_read_or_write_other_tenant_objects(two_workspaces):
    a, b_team = two_workspaces["a"], two_workspaces["b_team"]
    assert a.client.get(f"/api/v1/teams/{b_team['id']}").status_code == 404
    assert (
        a.client.patch(f"/api/v1/teams/{b_team['id']}", {"name": "x"}, format="json").status_code
        == 404
    )
    assert a.client.delete(f"/api/v1/teams/{b_team['id']}").status_code == 404

    b_agent = two_workspaces["b_agent"]
    r = a.client.patch(f"/api/v1/users/{b_agent.user_id}/role", {"role": "viewer"}, format="json")
    assert r.status_code == 400  # not found in this workspace
    with rls_bypass():
        assert Membership.objects.get(user_id=b_agent.user_id).role == "agent"


def test_token_for_a_workspace_the_user_is_not_in_is_rejected(api, two_workspaces):
    """A forged/stale token pointing at another tenant must not work."""
    a, b = two_workspaces["a"], two_workspaces["b"]
    user = User.objects.get(pk=a.user_id)
    refresh = RefreshToken.for_user(user)
    refresh["tid"] = b.tenant_id
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    assert api.get("/api/v1/users").status_code == 401
    assert api.get("/api/v1/workspace").status_code == 401


def test_switch_to_foreign_workspace_is_rejected(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    r = a.client.post("/api/v1/auth/switch-workspace", {"tenant_id": b.tenant_id}, format="json")
    assert r.status_code == 401


# --- PostgreSQL Row Level Security -------------------------------------------------
def test_app_connects_without_rls_bypass_rights():
    """Superusers and BYPASSRLS roles ignore RLS, so the app must not be one."""
    with connection.cursor() as cur:
        cur.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        assert cur.fetchone() == (False, False)


def test_rls_hides_other_tenant_rows_even_without_filters(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    with tenant_context(a.tenant_id):
        # Deliberately unscoped queries: RLS alone must hide tenant B.
        assert set(Team.objects.values_list("name", flat=True)) == {"A Team"}
        assert set(Tenant.objects.values_list("id", flat=True)) == {a.tenant_id}
        assert set(Membership.objects.values_list("tenant_id", flat=True)) == {a.tenant_id}
        assert set(Invitation.objects.values_list("tenant_id", flat=True)) == {a.tenant_id}
        assert not Team.objects.filter(pk=two_workspaces["b_team"]["id"]).exists()
        # Writes to another tenant's rows silently affect nothing
        assert Team.objects.filter(tenant_id=b.tenant_id).update(name="hacked") == 0

    with tenant_context(b.tenant_id):
        assert set(Team.objects.values_list("name", flat=True)) == {"B Team"}


def test_rls_denies_everything_without_a_tenant(two_workspaces):
    with tenant_context(two_workspaces["a"].tenant_id):
        set_db_tenant(None)
        assert Team.objects.count() == 0
        assert Membership.objects.count() == 0
        assert Tenant.objects.count() == 0


def test_rls_blocks_insert_into_another_tenant(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    with pytest.raises(ProgrammingError, match="row-level security"):
        with tenant_context(a.tenant_id):
            Team.objects.create(tenant_id=b.tenant_id, name="Sneaky")
