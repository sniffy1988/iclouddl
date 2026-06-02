from datetime import datetime, timezone

import pytest

from iclouddownloader.path_template import apply_path_template, validate_path_template


def test_yyyy_mm_dd_filename():
    dt = datetime(2024, 6, 2, 15, 30, 45, tzinfo=timezone.utc)
    p = apply_path_template("YYYY/MM/DD/{filename}", dt, "IMG_0001.JPG")
    assert str(p) == "2024/06/02/IMG_0001.JPG"


def test_yyyy_mm_dd_without_filename_token():
    dt = datetime(2024, 6, 2, tzinfo=timezone.utc)
    p = apply_path_template("YYYY/MM/DD", dt, "photo.heic")
    assert str(p) == "2024/06/02/photo.heic"


def test_rejects_parent_traversal():
    with pytest.raises(ValueError, match="\\.\\."):
        validate_path_template("YYYY/../DD/{filename}")
