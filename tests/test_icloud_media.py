from unittest.mock import MagicMock

from pyicloud.exceptions import PyiCloudAPIResponseException

from iclouddownloader.icloud.media import (
    classify_media_type,
    download_asset_to_file,
    has_live_video_component,
    is_stale_download_url_error,
    is_video_asset,
    live_video_filename,
    refresh_photo_asset,
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


def test_is_stale_download_url_error():
    assert is_stale_download_url_error(PyiCloudAPIResponseException("Gone", 410))
    assert not is_stale_download_url_error(ValueError("nope"))


def test_refresh_photo_asset_updates_master_record():
    fresh = MagicMock()
    fresh._master_record = {"fields": {"new": True}}
    fresh._asset_record = {"id": "asset"}

    album = MagicMock()
    album._get_photo.return_value = fresh

    photo = MagicMock()
    photo.id = "abc"
    photo._master_record = {"fields": {"old": True}}
    photo._service.photos.albums.get.return_value = album

    assert refresh_photo_asset(photo) is True
    assert photo._master_record == fresh._master_record
    album._get_photo.assert_called_once_with("abc")


def test_download_asset_to_file_writes_bytes(tmp_path):
    photo = MagicMock()
    photo.download.return_value = b"fake-image-bytes"
    photo.download_url.return_value = None
    photo._master_record = {"fields": {}}
    dest = tmp_path / "subdir" / "photo.jpg"
    download_asset_to_file(photo, dest, version="original")
    assert dest.read_bytes() == b"fake-image-bytes"


def test_master_fields_from_ckrecord_style_object():
    """pyicloud exposes _master_record as a CKRecord pydantic model, not a dict."""

    class FakeToken:
        downloadURL = "https://example.com/asset.mov"

    class FakeField:
        type = "ASSETID"

        def __init__(self):
            self.value = FakeToken()

        def model_dump(self, mode="python"):
            return {
                "type": self.type,
                "value": {"downloadURL": self.value.downloadURL},
            }

    class FakeCKRecord:
        def __init__(self):
            self.fields = {"resVidSmallRes": FakeField()}

    photo = MagicMock()
    photo._master_record = FakeCKRecord()
    assert is_video_asset(photo)
    assert classify_media_type(photo) == "video"
