from datetime import datetime, timedelta, timezone

import os
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from conftest import login_test_admin
from iclouddownloader.db.models import (
    AuthChallenge,
    AuthChallengeStatus,
    AuthChallengeType,
    User,
)
from iclouddownloader.services.auth_service import AuthService


def test_disconnect_icloud_clears_session_and_cookies(db_session, tmp_path, monkeypatch):
    from iclouddownloader import config

    class _Settings:
        cookie_dir = tmp_path / "cookies"
        icloud_trusted_session_days = 30

    settings = _Settings()
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(
        "iclouddownloader.services.auth_service.get_settings", lambda: settings
    )

    user = User(
        apple_id="disconnect@icloud.com",
        download_dir="/tmp/dl",
        icloud_authenticated_at=datetime.now(timezone.utc),
        icloud_2fa_at=datetime.now(timezone.utc),
        icloud_needs_auth=False,
        last_sync_status="counting_icloud",
    )
    db_session.add(user)
    db_session.flush()
    cookie_dir = tmp_path / "cookies" / str(user.id)
    cookie_dir.mkdir(parents=True)
    (cookie_dir / "session").write_text("x", encoding="utf-8")

    challenge = AuthChallenge(
        user_id=user.id,
        challenge_type=AuthChallengeType.twofa,
        status=AuthChallengeStatus.pending,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(challenge)
    db_session.commit()

    AuthService(db_session).disconnect_icloud(user)
    db_session.refresh(user)

    assert user.icloud_authenticated_at is None
    assert user.icloud_2fa_at is None
    assert user.icloud_needs_auth is True
    assert user.last_sync_status == "idle"
    assert not cookie_dir.exists()
    pending = db_session.scalars(
        select(AuthChallenge).where(
            AuthChallenge.user_id == user.id,
            AuthChallenge.status == AuthChallengeStatus.pending,
        )
    ).all()
    assert pending == []


def test_disconnect_icloud_api(client: TestClient):
    login_test_admin(client)
    r = client.post(
        "/api/users?fetch_count=false",
        json={"apple_id": "api-disconnect@icloud.com"},
    )
    assert r.status_code == 201
    user_id = r.json()["id"]

    cookie_dir = Path(os.environ["COOKIE_DIR"]) / str(user_id)
    cookie_dir.mkdir(parents=True, exist_ok=True)
    (cookie_dir / "session").write_text("x", encoding="utf-8")

    from iclouddownloader.db.session import get_session_factory

    db = get_session_factory()()
    try:
        user = db.get(User, user_id)
        user.icloud_authenticated_at = datetime.now(timezone.utc)
        user.icloud_needs_auth = False
        db.commit()
    finally:
        db.close()

    r = client.post(f"/api/users/{user_id}/auth/icloud/disconnect")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert not cookie_dir.exists()

    r = client.get(f"/api/users/{user_id}")
    body = r.json()
    assert body["icloud_authorized"] is False
    assert body["icloud_needs_auth"] is True


def test_disconnect_icloud_without_apple_id_fails(db_session):
    user = User(download_dir="/tmp/x")
    db_session.add(user)
    db_session.commit()
    try:
        AuthService(db_session).disconnect_icloud(user)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "not linked" in str(e).lower()
