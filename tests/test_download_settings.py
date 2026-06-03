from unittest.mock import MagicMock, patch

from sqlalchemy import select

from iclouddownloader.db.models import Photo, PhotoStatus, User
from iclouddownloader.icloud.sync import PhotoSyncEngine


def _effective(**kwargs):
    defaults = {
        "icloud_download_version": "original",
        "skip_videos": False,
        "skip_live_companions": False,
        "skip_motion_companions": False,
    }
    defaults.update(kwargs)
    return type("S", (), defaults)()


def test_icloud_sync_skips_video_when_configured(db_session, tmp_path):
    user = User(
        apple_id="skip-vid@test.com",
        download_dir=str(tmp_path),
        sync_interval_seconds=3600,
    )
    db_session.add(user)
    db_session.commit()

    engine = PhotoSyncEngine(db_session)
    counters = {"discovered": 0, "downloaded": 0, "failed": 0, "skipped": 0}

    api_photo = MagicMock()
    api_photo.id = "vid-1"
    api_photo.filename = "clip.mov"
    api_photo._master_record = {"fields": {"resVidSmallRes": {"value": {}}}}

    with patch(
        "iclouddownloader.icloud.sync.get_effective_settings",
        return_value=_effective(skip_videos=True),
    ):
        with patch(
            "iclouddownloader.icloud.sync.classify_media_type",
            return_value="video",
        ):
            with patch(
                "iclouddownloader.icloud.sync.asset_media_type",
                return_value="video",
            ):
                result = engine._process_photo(user, api_photo, tmp_path, counters)

    assert result == "skipped"
    assert counters["skipped"] == 1
    record = db_session.scalar(
        select(Photo).where(
            Photo.user_id == user.id,
            Photo.provider_asset_id == "vid-1",
        )
    )
    assert record is not None
    assert record.status == PhotoStatus.skipped
