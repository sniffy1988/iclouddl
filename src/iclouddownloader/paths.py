from __future__ import annotations

from pathlib import Path

from iclouddownloader.config import get_settings
from iclouddownloader.db.models import PhotoSource, User

# Subfolders under each user's download_dir (user root).
PROVIDER_DOWNLOAD_SUBDIR: dict[PhotoSource, str] = {
    PhotoSource.icloud: "icloud",
    PhotoSource.google_photos: "google_photo",
}


def safe_storage_label(value: str) -> str:
    return value.replace("@", "_at_").replace(".", "_")


def storage_label(
    *,
    user_id: int,
    apple_id: str | None = None,
    google_account_email: str | None = None,
    display_name: str | None = None,
) -> str:
    if apple_id:
        return safe_storage_label(apple_id.strip())
    if google_account_email:
        return safe_storage_label(google_account_email.strip())
    if display_name and display_name.strip():
        return safe_storage_label(display_name.strip())
    return f"user-{user_id}"


def storage_label_for_user(user: User) -> str:
    return storage_label(
        user_id=user.id,
        apple_id=user.apple_id,
        google_account_email=user.google_account_email,
        display_name=user.display_name,
    )


def user_download_root(
    user_id: int,
    label: str | None = None,
    *,
    apple_id: str | None = None,
    google_account_email: str | None = None,
    display_name: str | None = None,
    custom_dir: str | None = None,
) -> Path:
    """User-level directory: {base_download_dir}/{user_id}/{label}/"""
    if custom_dir:
        path = Path(custom_dir)
    else:
        name = label or storage_label(
            user_id=user_id,
            apple_id=apple_id,
            google_account_email=google_account_email,
            display_name=display_name,
        )
        path = get_settings().base_download_dir / str(user_id) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_dir_for_user(
    user_id: int,
    apple_id: str | None = None,
    *,
    google_account_email: str | None = None,
    display_name: str | None = None,
    custom_dir: str | None = None,
) -> Path:
    """Backward-compatible alias for user_download_root."""
    return user_download_root(
        user_id,
        apple_id=apple_id,
        google_account_email=google_account_email,
        display_name=display_name,
        custom_dir=custom_dir,
    )


def provider_download_dir(user: User, source: PhotoSource, *, create: bool = True) -> Path:
    """Provider storage: {user.download_dir}/{icloud|google_photo}/"""
    sub = PROVIDER_DOWNLOAD_SUBDIR[source]
    path = Path(user.download_dir).resolve() / sub
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path
