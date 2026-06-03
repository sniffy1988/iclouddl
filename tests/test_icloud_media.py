from unittest.mock import MagicMock

from iclouddownloader.icloud.media import (
    classify_media_type,
    has_live_video_component,
    is_video_asset,
    live_video_filename,
)


def _photo_with_fields(fields: dict) -> MagicMock:
    photo = MagicMock()
    photo._master_record = {"fields": fields}
    return photo


def test_classify_video():
    photo = _photo_with_fields({"resVidSmallRes": {"value": {}}})
    assert is_video_asset(photo)
    assert classify_media_type(photo) == "video"


def test_classify_live_photo():
    photo = _photo_with_fields({"resOriginalVidComplRes": {"value": {"downloadURL": "http://x"}}})
    assert has_live_video_component(photo)
    assert classify_media_type(photo) == "live_photo"


def test_classify_still_photo():
    photo = _photo_with_fields({})
    assert classify_media_type(photo) == "photo"


def test_live_video_filename():
    fields = {"resOriginalVidComplFileType": {"value": "com.apple.quicktime-movie"}}
    assert live_video_filename("IMG_0001.HEIC", fields) == "IMG_0001.mov"
