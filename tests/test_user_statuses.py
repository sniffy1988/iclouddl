from datetime import datetime, timedelta, timezone

from iclouddownloader.db.models import User
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
