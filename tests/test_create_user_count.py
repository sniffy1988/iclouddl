from fastapi.testclient import TestClient

from conftest import login_test_admin
from iclouddownloader.db.models import User
from iclouddownloader.services.auth_service import AuthService


def test_fetch_count_requires_icloud_auth(client: TestClient):
    login_test_admin(client)
    r = client.post(
        "/api/users?fetch_count=false",
        json={"apple_id": "nocount@icloud.com"},
    )
    user_id = r.json()["id"]
    r = client.post(f"/api/users/{user_id}/fetch-count?source=icloud")
    assert r.status_code == 400
    assert "Authorize iCloud" in r.json()["detail"]


def test_create_user_fetch_count_without_auth_stays_idle(client: TestClient):
    login_test_admin(client)
    r = client.post(
        "/api/users?fetch_count=true",
        json={"apple_id": "unauth-count@icloud.com", "display_name": "Unauth"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["activity_status"] == "idle"


def test_background_auth_required_clears_counting_status(db_session):
    user = User(
        apple_id="stuck@icloud.com",
        download_dir="/tmp/stuck",
        last_sync_status="counting_icloud",
        icloud_needs_auth=False,
        icloud_authenticated_at=None,
    )
    db_session.add(user)
    db_session.commit()

    AuthService(db_session).handle_background_auth_required(user)
    db_session.refresh(user)
    assert user.last_sync_status == "idle"
    assert user.icloud_needs_auth is True
