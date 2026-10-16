import itertools
from dataclasses import dataclass

import pytest
from rest_framework.test import APIClient

from common import mongo

PASSWORD = "Str0ng-test-pass!"
_counter = itertools.count(1)


@dataclass
class Session:
    client: APIClient
    tenant_id: int
    user_id: int
    access: str
    refresh: str
    email: str


def _client_with(access: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def session_from(response) -> Session:
    assert response.status_code in (200, 201), response.data
    body = response.data
    return Session(
        client=_client_with(body["access"]),
        tenant_id=body["session"]["workspace"]["id"],
        user_id=body["session"]["user"]["id"],
        access=body["access"],
        refresh=body["refresh"],
        email=body["session"]["user"]["email"],
    )


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def signup(api):
    """Create a new workspace and return a logged-in Owner session."""

    def _signup(workspace: str | None = None, email: str | None = None) -> Session:
        n = next(_counter)
        response = api.post(
            "/api/v1/auth/signup",
            {
                "full_name": f"Owner {n}",
                "email": email or f"owner{n}@example.com",
                "password": PASSWORD,
                "workspace_name": workspace or f"Workspace {n}",
            },
            format="json",
        )
        return session_from(response)

    return _signup


@pytest.fixture
def invite_and_join(api):
    """Invite `email` with `role` into the inviter's workspace and accept it."""

    def _invite(inviter: Session, role: str, email: str | None = None) -> Session:
        email = email or f"{role}{next(_counter)}@example.com"
        r = inviter.client.post("/api/v1/users", {"email": email, "role": role}, format="json")
        assert r.status_code == 201, r.data
        token = r.data["invite_url"].split("token=")[1]
        r = api.post(
            "/api/v1/auth/accept-invite",
            {"token": token, "password": PASSWORD, "full_name": f"{role.title()} User"},
            format="json",
        )
        return session_from(r)

    return _invite


@pytest.fixture(autouse=True)
def clean_mongo():
    yield
    mongo.get_client().drop_database(mongo.get_database().name)


@pytest.fixture(autouse=True)
def activity_writes_now(monkeypatch, settings, tmp_path):
    """Tests run inside one transaction that never commits, so write timeline
    entries immediately instead of on commit. Uploaded files go to a temp dir."""
    from apps.activity import service

    monkeypatch.setattr(service, "_defer", lambda write: write())
    settings.MEDIA_ROOT = tmp_path


def create_enquiry(session: Session, **data) -> dict:
    """POST /enquiries with sensible defaults; returns the response body."""
    payload = {"name": "Aarav Shah", "phone": "+919800022222", **data}
    r = session.client.post("/api/v1/enquiries", payload, format="json")
    assert r.status_code == 201, r.data
    return r.data
