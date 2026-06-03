from datetime import datetime, timedelta, timezone

from iclouddownloader.db.models import User
from iclouddownloader.services.user_service import UserService


def test_users_due_for_sync(db_session):
    now = datetime.now(timezone.utc)
    due = User(
        apple_id="due@icloud.com",
        download_dir="/tmp/a",
        sync_interval_seconds=3600,
        enabled=True,
        next_sync_at=now - timedelta(hours=1),
    )
    not_due = User(
        apple_id="later@icloud.com",
        download_dir="/tmp/b",
        sync_interval_seconds=3600,
        enabled=True,
        next_sync_at=now + timedelta(hours=1),
    )
    disabled = User(
        apple_id="off@icloud.com",
        download_dir="/tmp/c",
        sync_interval_seconds=3600,
        enabled=False,
        next_sync_at=now - timedelta(hours=1),
    )
    db_session.add_all([due, not_due, disabled])
    db_session.commit()

    result = UserService(db_session).users_due_for_sync()
    ids = {u.apple_id for u in result}
    assert "due@icloud.com" in ids
    assert "later@icloud.com" not in ids
    assert "off@icloud.com" not in ids


def test_users_with_no_schedule_never_due(db_session):
    manual = User(
        apple_id="manual@icloud.com",
        download_dir="/tmp/m",
        sync_interval_seconds=3600,
        enabled=True,
        next_sync_at=None,
    )
    db_session.add(manual)
    db_session.commit()

    result = UserService(db_session).users_due_for_sync()
    assert "manual@icloud.com" not in {u.apple_id for u in result}


def test_schedule_next_sync(db_session):
    user = User(
        apple_id="u@icloud.com",
        download_dir="/tmp",
        sync_interval_seconds=7200,
        enabled=True,
    )
    db_session.add(user)
    db_session.commit()

    UserService(db_session).schedule_next_sync(user)
    db_session.refresh(user)
    assert user.next_sync_at is not None
