import os
import tempfile
from unittest.mock import patch

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["BASE_DOWNLOAD_DIR"] = _tmp
os.environ["COOKIE_DIR"] = _tmp + "/cookies"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from iclouddownloader.api.app import create_app
from iclouddownloader.config import get_settings
from iclouddownloader.db.models import Base

get_settings.cache_clear()

import iclouddownloader.db.session as session_mod

_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
session_mod._engine = _test_engine
session_mod._SessionLocal = sessionmaker(bind=_test_engine, autocommit=False, autoflush=False)
Base.metadata.create_all(_test_engine)


def test_health():
    client = TestClient(create_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_and_users_crud():
    app = create_app()
    client = TestClient(app)
    password = get_settings().web_admin_password

    r = client.post("/api/auth/login", json={"password": password})
    assert r.status_code == 200

    r = client.post(
        "/api/users?fetch_count=false",
        json={"apple_id": "api-test@icloud.com", "display_name": "API Test"},
    )
    assert r.status_code == 201
    user = r.json()
    assert user["apple_id"] == "api-test@icloud.com"

    r = client.get("/api/users")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get(f"/api/users/{user['id']}")
    assert r.status_code == 200

    r = client.patch(
        f"/api/users/{user['id']}",
        json={"sync_interval_seconds": 3600, "reschedule_sync": True},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["sync_interval_seconds"] == 3600
    assert updated["next_sync_at"] is not None

    r = client.delete(f"/api/users/{user['id']}")
    assert r.status_code == 204


@patch("iclouddownloader.services.auth_service.get_pyicloud_service")
def test_user_icloud_auth_login(mock_get):
    mock_get.return_value = object()

    client = TestClient(create_app())
    admin_pw = get_settings().web_admin_password
    client.post("/api/auth/login", json={"password": admin_pw})

    r = client.post(
        "/api/users?fetch_count=false",
        json={"apple_id": "auth-login@icloud.com"},
    )
    user_id = r.json()["id"]

    r = client.post(
        f"/api/users/{user_id}/auth/login",
        json={"password": "apple-password"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["status"] == "authenticated"

    r = client.get(f"/api/users/{user_id}")
    body = r.json()
    assert body["icloud_authorized"] is True
    assert body["icloud_needs_auth"] is False
    assert body["icloud_authenticated_at"] is not None
