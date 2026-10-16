import re

import pytest
from django.core import mail

from .conftest import PASSWORD, session_from

pytestmark = pytest.mark.django_db


def test_signup_creates_workspace_and_owner(signup):
    s = signup(workspace="Acme Realty")
    me = s.client.get("/api/v1/auth/me").data
    assert me["workspace"]["name"] == "Acme Realty"
    assert me["workspace"]["timezone"] == "Asia/Kolkata"
    assert me["workspace"]["dedupe_key"] == "phone"
    assert me["role"] == "owner"
    assert "manage_billing" in me["capabilities"]


def test_signup_rejects_duplicate_email(api, signup):
    signup(email="dup@example.com")
    r = api.post(
        "/api/v1/auth/signup",
        {"full_name": "X", "email": "DUP@example.com", "password": PASSWORD, "workspace_name": "W"},
        format="json",
    )
    assert r.status_code == 400
    assert "email" in r.data["errors"]


def test_signup_rejects_weak_password(api):
    r = api.post(
        "/api/v1/auth/signup",
        {"full_name": "X", "email": "x@example.com", "password": "123", "workspace_name": "W"},
        format="json",
    )
    assert r.status_code == 400
    assert "password" in r.data["errors"]


def test_login_and_wrong_password(api, signup):
    s = signup()
    ok = api.post("/api/v1/auth/login", {"email": s.email, "password": PASSWORD}, format="json")
    assert ok.status_code == 200
    assert ok.data["session"]["workspace"]["id"] == s.tenant_id

    bad = api.post("/api/v1/auth/login", {"email": s.email, "password": "nope"}, format="json")
    assert bad.status_code == 401
    unknown = api.post(
        "/api/v1/auth/login", {"email": "ghost@example.com", "password": "x"}, format="json"
    )
    assert unknown.status_code == 401
    assert bad.data["detail"] == unknown.data["detail"]  # no hint which part was wrong


def test_requests_without_token_are_rejected(api):
    assert api.get("/api/v1/auth/me").status_code == 401
    assert api.get("/api/v1/users").status_code == 401


def test_refresh_rotates_and_old_token_is_blacklisted(api, signup):
    s = signup()
    r = api.post("/api/v1/auth/refresh", {"refresh": s.refresh}, format="json")
    assert r.status_code == 200
    assert r.data["refresh"] != s.refresh
    again = api.post("/api/v1/auth/refresh", {"refresh": s.refresh}, format="json")
    assert again.status_code == 401


def test_logout_blacklists_refresh_token(api, signup):
    s = signup()
    assert api.post("/api/v1/auth/logout", {"refresh": s.refresh}, format="json").status_code == 204
    r = api.post("/api/v1/auth/refresh", {"refresh": s.refresh}, format="json")
    assert r.status_code == 401


def test_forgot_and_reset_password(api, signup):
    s = signup()
    r = api.post("/api/v1/auth/forgot-password", {"email": s.email}, format="json")
    assert r.status_code == 200
    assert len(mail.outbox) == 1
    uid, token = re.search(r"uid=([^&\s]+)&token=([^\s]+)", mail.outbox[0].body).groups()

    new_password = "An0ther-strong-pass!"
    r = api.post(
        "/api/v1/auth/reset-password",
        {"uid": uid, "token": token, "password": new_password},
        format="json",
    )
    assert r.status_code == 200
    login = api.post(
        "/api/v1/auth/login", {"email": s.email, "password": new_password}, format="json"
    )
    assert login.status_code == 200
    # the old refresh token was revoked
    assert (
        api.post("/api/v1/auth/refresh", {"refresh": s.refresh}, format="json").status_code == 401
    )


def test_forgot_password_does_not_reveal_unknown_email(api):
    r = api.post("/api/v1/auth/forgot-password", {"email": "ghost@example.com"}, format="json")
    assert r.status_code == 200
    assert len(mail.outbox) == 0


def test_switch_workspace(api, signup, invite_and_join):
    a = signup(workspace="A")
    b = signup(workspace="B")
    agent = invite_and_join(a, "agent")
    # The same person joins B as a manager (existing account: password is checked)
    r = b.client.post("/api/v1/users", {"email": agent.email, "role": "manager"}, format="json")
    token = r.data["invite_url"].split("token=")[1]
    joined = session_from(
        api.post(
            "/api/v1/auth/accept-invite", {"token": token, "password": PASSWORD}, format="json"
        )
    )
    assert joined.tenant_id == b.tenant_id

    me = joined.client.get("/api/v1/auth/me").data
    assert {w["name"] for w in me["workspaces"]} == {"A", "B"}

    switched = session_from(
        joined.client.post(
            "/api/v1/auth/switch-workspace", {"tenant_id": a.tenant_id}, format="json"
        )
    )
    assert switched.client.get("/api/v1/auth/me").data["role"] == "agent"
