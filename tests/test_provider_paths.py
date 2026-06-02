from pathlib import Path

from iclouddownloader.db.models import PhotoSource, User
from iclouddownloader.paths import (
    PROVIDER_DOWNLOAD_SUBDIR,
    download_dir_for_user,
    provider_download_dir,
    storage_label,
)


def test_storage_label_from_apple_id():
    assert storage_label(user_id=1, apple_id="sniffy1988@gmail.com") == "sniffy1988_at_gmail_com"


def test_provider_download_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("BASE_DOWNLOAD_DIR", str(tmp_path / "downloads"))
    from iclouddownloader.config import get_settings

    get_settings.cache_clear()

    root = download_dir_for_user(1, apple_id="sniffy1988@gmail.com")
    assert root == tmp_path / "downloads" / "1" / "sniffy1988_at_gmail_com"

    user = User(id=1, apple_id="sniffy1988@gmail.com", download_dir=str(root))
    icloud = provider_download_dir(user, PhotoSource.icloud)
    google = provider_download_dir(user, PhotoSource.google_photos)

    assert icloud == Path(user.download_dir) / PROVIDER_DOWNLOAD_SUBDIR[PhotoSource.icloud]
    assert google == Path(user.download_dir) / PROVIDER_DOWNLOAD_SUBDIR[PhotoSource.google_photos]
    assert icloud.name == "icloud"
    assert google.name == "google_photo"
    assert icloud.is_dir()
    assert google.is_dir()
