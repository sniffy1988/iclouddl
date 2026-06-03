from iclouddownloader.google.assets import _media_type, is_motion_photo, media_item_ready


def test_motion_photo_type():
    item = {
        "id": "1",
        "mediaMetadata": {"photo": {"motionPhoto": True}, "status": "READY"},
    }
    assert is_motion_photo(item)
    assert _media_type(item) == "motion_photo"


def test_video_type():
    item = {"id": "2", "mediaMetadata": {"video": {}, "status": "READY"}}
    assert _media_type(item) == "video"


def test_not_ready():
    item = {"id": "3", "mediaMetadata": {"photo": {}, "status": "PROCESSING"}}
    assert media_item_ready(item) is False
