from pathlib import Path

from iclouddownloader.db.models import Photo, PhotoSource, PhotoStatus, User
from iclouddownloader.providers.local_files import (
    mark_photo_missing_on_disk,
    path_is_present,
    photo_files_on_disk,
    reconcile_stale_downloads,
    try_adopt_existing_on_disk,
    verify_written_file,
)


def test_path_is_present(tmp_path):
    f = tmp_path / "a.jpg"
    f.write_bytes(b"x")
    assert path_is_present(str(f))
    f.unlink()
    assert not path_is_present(str(f))


def test_mark_photo_missing_on_disk():
    photo = Photo(
        user_id=1,
        source=PhotoSource.icloud,
        provider_asset_id="x",
        filename="a.jpg",
        status=PhotoStatus.downloaded,
        local_path="/gone/a.jpg",
    )
    assert mark_photo_missing_on_disk(photo) is True
    assert photo.status == PhotoStatus.pending
    assert photo.local_path is None
    assert "missing" in (photo.error_message or "").lower()


def test_reconcile_stale_downloads(db_session, tmp_path):
    user = User(apple_id="local@test.com", download_dir=str(tmp_path), sync_interval_seconds=3600)
    db_session.add(user)
    db_session.commit()

    on_disk = Photo(
        user_id=user.id,
        source=PhotoSource.icloud,
        provider_asset_id="ok",
        filename="ok.jpg",
        status=PhotoStatus.downloaded,
    )
    missing = Photo(
        user_id=user.id,
        source=PhotoSource.icloud,
        provider_asset_id="gone",
        filename="gone.jpg",
        status=PhotoStatus.downloaded,
        local_path=str(tmp_path / "nope.jpg"),
    )
    db_session.add_all([on_disk, missing])
    db_session.commit()

    real = tmp_path / "ok.jpg"
    real.write_bytes(b"data")
    on_disk.local_path = str(real)
    db_session.commit()

    n = reconcile_stale_downloads(db_session, user.id, source=PhotoSource.icloud)
    db_session.commit()

    assert n == 1
    db_session.refresh(missing)
    assert missing.status == PhotoStatus.pending
    assert photo_files_on_disk(on_disk)


def test_verify_written_file_raises(tmp_path):
    try:
        verify_written_file(tmp_path / "missing.jpg")
        assert False
    except ValueError as e:
        assert "did not create" in str(e)


def test_try_adopt_existing_on_disk(tmp_path):
    primary = tmp_path / "photo.jpg"
    primary.write_bytes(b"already-here")
    photo = Photo(
        user_id=1,
        source=PhotoSource.icloud,
        provider_asset_id="adopt",
        filename="photo.jpg",
        status=PhotoStatus.pending,
        error_message="Local file missing (deleted or moved)",
    )
    assert try_adopt_existing_on_disk(photo, primary) is True
    assert photo.status == PhotoStatus.downloaded
    assert photo.local_path == str(primary.resolve())
    assert photo.error_message is None
    assert photo.checksum_sha256


def test_try_adopt_requires_companion_when_missing(tmp_path):
    primary = tmp_path / "a.heic"
    primary.write_bytes(b"1")
    photo = Photo(
        user_id=1,
        source=PhotoSource.icloud,
        provider_asset_id="live",
        filename="a.heic",
        status=PhotoStatus.pending,
    )
    companion = tmp_path / "a.mov"
    assert try_adopt_existing_on_disk(photo, primary, companion=companion, require_companion=True) is False
    companion.write_bytes(b"2")
    assert try_adopt_existing_on_disk(
        photo, primary, companion=companion, require_companion=True, companion_media_type="live_video"
    )
    assert photo.companion_local_path == str(companion.resolve())


def test_build_photo_count_skips_reconcile_while_syncing(db_session, tmp_path):
    from iclouddownloader.services.sync_service import SyncService

    user = User(apple_id="sync@test.com", download_dir=str(tmp_path), sync_interval_seconds=3600)
    user.last_sync_status = "syncing"
    db_session.add(user)
    db_session.commit()

    stale = Photo(
        user_id=user.id,
        source=PhotoSource.icloud,
        provider_asset_id="stale",
        filename="stale.jpg",
        status=PhotoStatus.downloaded,
        local_path=str(tmp_path / "gone.jpg"),
    )
    db_session.add(stale)
    db_session.commit()

    result = SyncService(db_session).build_photo_count_result(user)
    db_session.refresh(stale)

    assert stale.status == PhotoStatus.downloaded
    assert result["downloaded_count"] == 1
