from datetime import datetime, timedelta, timezone

from iclouddownloader.db.models import AuthChallenge, AuthChallengeStatus, AuthChallengeType, User
from iclouddownloader.services.auth_service import AuthService


def test_auth_and_activity_statuses_separate():
    user = User(
        apple_id="a@b.com",
        download_dir="/tmp",
        icloud_authenticated_at=datetime.now(timezone.utc),
        icloud_2fa_at=datetime.now(timezone.utc),
        icloud_needs_auth=False,
        last_sync_status="counting",
    )
    assert AuthService.auth_status_for_user(user) == "authorized"
    assert AuthService.activity_status_for_user(user) == "counting"

    user.last_sync_status = "auth_required"
    assert AuthService.auth_status_for_user(user) == "authorized"
    assert AuthService.activity_status_for_user(user) == "idle"

    user.icloud_needs_auth = True
    user.last_sync_status = "completed"
    assert AuthService.auth_status_for_user(user) == "reauth_required"
    assert AuthService.activity_status_for_user(user) == "completed"


def test_icloud_auth_status_awaiting_2fa_when_challenge_pending():
    user = User(
        apple_id="a@b.com",
        download_dir="/tmp",
        icloud_authenticated_at=datetime.now(timezone.utc),
        icloud_2fa_at=datetime.now(timezone.utc),
        icloud_needs_auth=False,
    )
    assert AuthService.icloud_auth_status(user) == "authorized"
    assert AuthService.icloud_auth_status(user, pending_challenge=True) == "awaiting_2fa"


def test_user_api_reports_awaiting_2fa(client, db_session):
    from conftest import login_test_admin

    from iclouddownloader.db.models import User as UserModel

    login_test_admin(client)
    user = UserModel(
        apple_id="pending@icloud.com",
        download_dir="/tmp/u",
        icloud_authenticated_at=datetime.now(timezone.utc),
        icloud_2fa_at=datetime.now(timezone.utc),
        icloud_needs_auth=False,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        AuthChallenge(
            user_id=user.id,
            challenge_type=AuthChallengeType.twofa,
            status=AuthChallengeStatus.pending,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
    )
    db_session.commit()

    r = client.get(f"/api/users/{user.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["icloud_auth_status"] == "awaiting_2fa"
    assert data["icloud_pending_challenge"] is True
