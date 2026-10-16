import pytest
from django.core import mail

from apps.permissions.matrix import capabilities_for, has_capability
from apps.permissions.roles import Capability, Role

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


# --- the "Done when" flow: sign up, invite, log in with a role ------------------------
def test_owner_invites_user_who_logs_in_with_role(api, signup):
    owner = signup(workspace="Acme")
    r = owner.client.post(
        "/api/v1/users", {"email": "riya@example.com", "role": "manager"}, format="json"
    )
    assert r.status_code == 201
    assert r.data["status"] == "pending"
    assert len(mail.outbox) == 1 and "Acme" in mail.outbox[0].subject

    token = r.data["invite_url"].split("token=")[1]
    preview = api.get("/api/v1/auth/accept-invite", {"token": token})
    assert preview.data["workspace_name"] == "Acme"
    assert preview.data["has_account"] is False

    r = api.post(
        "/api/v1/auth/accept-invite",
        {"token": token, "password": PASSWORD, "full_name": "Riya Shah"},
        format="json",
    )
    assert r.status_code == 200

    login = api.post(
        "/api/v1/auth/login", {"email": "riya@example.com", "password": PASSWORD}, format="json"
    )
    assert login.status_code == 200
    assert login.data["session"]["role"] == "manager"
    assert login.data["session"]["workspace"]["name"] == "Acme"

    # invite links are single-use
    again = api.post(
        "/api/v1/auth/accept-invite", {"token": token, "password": PASSWORD}, format="json"
    )
    assert again.status_code == 400


def test_users_list_is_paginated(signup, invite_and_join):
    owner = signup()
    invite_and_join(owner, "agent")
    r = owner.client.get("/api/v1/users")
    assert r.status_code == 200
    assert r.data["count"] == 2
    assert r.data["page_size"] == 25
    assert {u["role"] for u in r.data["results"]} == {"owner", "agent"}


def test_agent_cannot_invite_or_change_roles(signup, invite_and_join):
    owner = signup()
    agent = invite_and_join(owner, "agent")
    assert agent.client.get("/api/v1/users").status_code == 200  # reading is allowed
    r = agent.client.post("/api/v1/users", {"email": "x@example.com"}, format="json")
    assert r.status_code == 403
    r = agent.client.patch(f"/api/v1/users/{owner.user_id}/role", {"role": "viewer"}, format="json")
    assert r.status_code == 403


def test_admin_cannot_grant_or_change_owner(signup, invite_and_join):
    owner = signup()
    admin = invite_and_join(owner, "admin")
    r = admin.client.post(
        "/api/v1/users", {"email": "o2@example.com", "role": "owner"}, format="json"
    )
    assert r.status_code == 403
    r = admin.client.patch(f"/api/v1/users/{owner.user_id}/role", {"role": "agent"}, format="json")
    assert r.status_code == 403


def test_owner_changes_role_but_not_own(signup, invite_and_join):
    owner = signup()
    agent = invite_and_join(owner, "agent")
    r = owner.client.patch(
        f"/api/v1/users/{agent.user_id}/role", {"role": "manager"}, format="json"
    )
    assert r.status_code == 200 and r.data["role"] == "manager"
    # the change applies to the next request, even with the old access token
    assert "import" in agent.client.get("/api/v1/auth/me").data["capabilities"]

    r = owner.client.patch(f"/api/v1/users/{owner.user_id}/role", {"role": "agent"}, format="json")
    assert r.status_code == 403


def test_revoked_invite_cannot_be_accepted(api, signup):
    owner = signup()
    r = owner.client.post("/api/v1/users", {"email": "z@example.com"}, format="json")
    token = r.data["invite_url"].split("token=")[1]
    assert owner.client.delete(f"/api/v1/invitations/{r.data['id']}").status_code == 204
    r = api.post(
        "/api/v1/auth/accept-invite",
        {"token": token, "password": PASSWORD, "full_name": "Z"},
        format="json",
    )
    assert r.status_code == 400


def test_teams_crud_and_member_validation(signup, invite_and_join):
    owner = signup()
    agent = invite_and_join(owner, "agent")
    other = signup()

    r = owner.client.post(
        "/api/v1/teams", {"name": "Sales", "member_ids": [agent.user_id]}, format="json"
    )
    assert r.status_code == 201
    assert [m["id"] for m in r.data["members"]] == [agent.user_id]

    # cannot add someone from another workspace
    r = owner.client.post(
        "/api/v1/teams", {"name": "Ops", "member_ids": [other.user_id]}, format="json"
    )
    assert r.status_code == 400

    assert agent.client.get("/api/v1/teams").data["count"] == 1
    assert agent.client.post("/api/v1/teams", {"name": "X"}, format="json").status_code == 403


def test_workspace_settings_permissions(signup, invite_and_join):
    owner = signup()
    manager = invite_and_join(owner, "manager")
    r = owner.client.patch("/api/v1/workspace", {"timezone": "Asia/Dubai"}, format="json")
    assert r.status_code == 200 and r.data["timezone"] == "Asia/Dubai"
    assert (
        owner.client.patch(
            "/api/v1/workspace", {"timezone": "Mars/Base"}, format="json"
        ).status_code
        == 400
    )
    assert manager.client.get("/api/v1/workspace").status_code == 200
    assert (
        manager.client.patch("/api/v1/workspace", {"name": "X"}, format="json").status_code == 403
    )


@pytest.mark.parametrize(
    ("role", "capability", "expected"),
    [
        (Role.OWNER, Capability.MANAGE_BILLING, True),
        (Role.ADMIN, Capability.MANAGE_BILLING, False),
        (Role.ADMIN, Capability.MANAGE_META, True),
        (Role.MANAGER, Capability.MANAGE_USERS, False),
        (Role.MANAGER, Capability.EXPORT, True),
        (Role.AGENT, Capability.EDIT_ENQUIRIES, True),
        (Role.AGENT, Capability.DELETE_ENQUIRIES, False),
        (Role.AGENT, Capability.IMPORT, False),
        (Role.VIEWER, Capability.EDIT_ENQUIRIES, False),
    ],
)
def test_permission_matrix(role, capability, expected):
    assert has_capability(role, capability) is expected


def test_every_role_has_an_entry():
    for role in Role:
        assert capabilities_for(role) is not None
