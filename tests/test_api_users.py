from unittest.mock import patch

from fastapi.testclient import TestClient

from conftest import login_test_admin


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_and_users_crud(client: TestClient):
    login_test_admin(client)

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
def test_user_icloud_auth_login(mock_get, client: TestClient):
    mock_get.return_value = object()
    login_test_admin(client)

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
