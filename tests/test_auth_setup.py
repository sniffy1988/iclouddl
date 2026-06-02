import pytest
from fastapi.testclient import TestClient

from iclouddownloader.db.models import RuntimeSettings


@pytest.fixture(autouse=True)
def _no_admin_yet(db_session):
    """Each test in this module starts without an admin account."""
    row = db_session.get(RuntimeSettings, 1)
    if row:
        row.admin_password_hash = ""
        db_session.commit()
    yield


def test_auth_status_needs_setup(client: TestClient):
    r = client.get("/api/auth/status")
    assert r.status_code == 200
    data = r.json()
    assert data["needs_setup"] is True
    assert data["authenticated"] is False


def test_setup_admin_and_login(client: TestClient):
    r = client.post("/api/auth/setup", json={"password": "secure-pass-1"})
    assert r.status_code == 200

    status = client.get("/api/auth/status").json()
    assert status["needs_setup"] is False
    assert status["authenticated"] is True

    r = client.get("/api/auth/me")
    assert r.status_code == 200

    client2 = TestClient(client.app)
    r = client2.post("/api/auth/setup", json={"password": "other-pass-12"})
    assert r.status_code == 403

    r = client2.post("/api/auth/login", json={"password": "wrong-pass-1"})
    assert r.status_code == 401

    r = client2.post("/api/auth/login", json={"password": "secure-pass-1"})
    assert r.status_code == 200


def test_login_blocked_until_setup(client: TestClient):
    r = client.post("/api/auth/login", json={"password": "anything"})
    assert r.status_code == 403


def test_setup_password_min_length(client: TestClient):
    r = client.post("/api/auth/setup", json={"password": "short"})
    assert r.status_code == 422
