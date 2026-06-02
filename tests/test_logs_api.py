from datetime import datetime, timezone

from fastapi.testclient import TestClient

from conftest import login_test_admin
from iclouddownloader.db.models import AppLog


def test_logs_list_clear_and_debug_setting(client: TestClient, db_session):
    login_test_admin(client)

    db_session.add(
        AppLog(
            created_at=datetime.now(timezone.utc),
            level="INFO",
            logger_name="tests",
            message="hello from test",
            exception=None,
            source="test",
        )
    )
    db_session.commit()

    r = client.get("/api/logs")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(item["message"] == "hello from test" for item in body["items"])

    r = client.delete("/api/logs")
    assert r.status_code == 200
    assert r.json()["deleted"] >= 1

    r = client.get("/api/logs")
    assert r.json()["total"] == 0

    r = client.patch("/api/settings", json={"debug_logging_enabled": True})
    assert r.status_code == 200
    assert r.json()["debug_logging_enabled"] is True

    r = client.get("/api/health")
    assert r.json()["debug_logging_enabled"] is True


def test_logs_requires_auth(client: TestClient):
    assert client.get("/api/logs").status_code == 401
