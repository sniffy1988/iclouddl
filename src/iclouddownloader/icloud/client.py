from pathlib import Path

from iclouddownloader.config import get_settings


def cookie_dir_for_user(user_id: int) -> Path:
    settings = get_settings()
    path = settings.cookie_dir / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_dir_for_user(user_id: int, apple_id: str, custom_dir: str | None = None) -> Path:
    if custom_dir:
        path = Path(custom_dir)
    else:
        safe_id = apple_id.replace("@", "_at_").replace(".", "_")
        path = get_settings().base_download_dir / str(user_id) / safe_id
    path.mkdir(parents=True, exist_ok=True)
    return path
