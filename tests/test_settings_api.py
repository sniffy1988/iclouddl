from fastapi.testclient import TestClient

from conftest import login_test_admin


def test_settings_get_and_patch(client: TestClient):
    login_test_admin(client)
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert "download_path_template" in r.json()

    r = client.patch(
        "/api/settings",
        json={
            "telegram_enabled": True,
            "telegram_bot_token": "123456789:TESTTOKEN",
            "telegram_admin_chat_id": "-1001",
            "download_path_template": "YYYY/MM/DD/{filename}",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["telegram_enabled"] is True
    assert data["telegram_bot_token_set"] is True
    assert data["download_path_template"] == "YYYY/MM/DD/{filename}"
