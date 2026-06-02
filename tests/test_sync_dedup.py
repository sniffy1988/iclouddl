from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from iclouddownloader.db.models import Photo, PhotoStatus, User
from iclouddownloader.icloud.sync import PhotoSyncEngine, _asset_id, _sha256


def test_asset_id_from_photo():
    photo = MagicMock()
    photo.id = "abc-123"
    photo.filename = "IMG.jpg"
    assert _asset_id(photo) == "abc-123"


def test_photo_skip_when_downloaded(db_session, tmp_path):
    user = User(
        apple_id="test@icloud.com",
        download_dir=str(tmp_path),
        sync_interval_seconds=3600,
    )
    db_session.add(user)
    db_session.flush()

    local_file = tmp_path / "2024" / "01" / "photo.jpg"
    local_file.parent.mkdir(parents=True)
    local_file.write_bytes(b"testdata")

    existing = Photo(
        user_id=user.id,
        icloud_asset_id="asset-1",
        filename="photo.jpg",
        status=PhotoStatus.downloaded,
        local_path=str(local_file),
    )
    db_session.add(existing)
    db_session.commit()

    engine = PhotoSyncEngine(db_session)
    from iclouddownloader.db.models import SyncRun, SyncRunStatus

    sync_run = SyncRun(user_id=user.id, status=SyncRunStatus.running)
    db_session.add(sync_run)
    db_session.commit()

    api_photo = MagicMock()
    api_photo.id = "asset-1"
    api_photo.filename = "photo.jpg"

    result = engine._process_photo(user, api_photo, tmp_path, sync_run)
    assert result == "skipped"
    assert sync_run.photos_skipped == 1


def test_sha256(tmp_path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"hello")
    assert len(_sha256(f)) == 64
