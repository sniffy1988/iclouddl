from datetime import datetime, timedelta, timezone

from iclouddownloader.db.models import User
from iclouddownloader.services.auth_service import AuthService


def test_days_until_2fa_expires():
    user = User(
        apple_id="a@b.com",
        download_dir="/tmp",
        icloud_2fa_at=datetime.now(timezone.utc) - timedelta(days=10),
        icloud_authenticated_at=datetime.now(timezone.utc) - timedelta(days=10),
        icloud_needs_auth=False,
    )
    left = AuthService.days_until_2fa_expires(user)
    assert left is not None and 19 <= left <= 20


def test_is_authorized_false_when_expired():
    user = User(
        apple_id="a@b.com",
        download_dir="/tmp",
        icloud_2fa_at=datetime.now(timezone.utc) - timedelta(days=31),
        icloud_authenticated_at=datetime.now(timezone.utc) - timedelta(days=31),
        icloud_needs_auth=False,
    )
    assert AuthService.is_authorized(user) is False
    assert AuthService.days_until_2fa_expires(user) == 0
