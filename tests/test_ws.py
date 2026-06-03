from __future__ import annotations

import pytest

from conftest import login_test_admin


def test_health_includes_redis(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["redis"] is True


def test_websocket_requires_auth(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/api/ws"):
            pass


def test_websocket_accepts_authenticated_session(client):
    login_test_admin(client)
    with client.websocket_connect("/api/ws") as ws:
        ws.send_text("ping")
