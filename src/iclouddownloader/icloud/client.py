from pathlib import Path

from iclouddownloader.config import get_settings
from iclouddownloader.paths import download_dir_for_user

__all__ = ["cookie_dir_for_user", "download_dir_for_user"]


def cookie_dir_for_user(user_id: int) -> Path:
    settings = get_settings()
    path = settings.cookie_dir / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path
