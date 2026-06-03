from iclouddownloader.db.models import User
from iclouddownloader.services.user_service import UserService


def test_immich_fields_ignored_when_integration_disabled(db_session, monkeypatch):
    monkeypatch.setattr(
        "iclouddownloader.services.user_service.get_effective_settings",
        lambda: type("S", (), {"immich_enabled": False})(),
    )
    user = User(
        apple_id="immich@test.com",
        download_dir="/tmp/dl",
        sync_interval_seconds=3600,
        immich_scan_after_sync=False,
    )
    db_session.add(user)
    db_session.commit()

    updated = UserService(db_session).update_user(
        user.id,
        immich_scan_after_sync=True,
        immich_library_id="lib-uuid",
    )
    assert updated.immich_scan_after_sync is False
    assert updated.immich_library_id is None
