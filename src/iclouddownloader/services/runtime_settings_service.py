from __future__ import annotations

from sqlalchemy.orm import Session

from iclouddownloader.config import Settings, get_settings
from iclouddownloader.db.models import RuntimeSettings
from iclouddownloader.path_template import validate_path_template


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return "••••••••"
    return "••••••••" + token[-4:]


class RuntimeSettingsService:
    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_row(self) -> RuntimeSettings:
        row = self.db.get(RuntimeSettings, 1)
        if row:
            return row
        env = get_settings()
        row = RuntimeSettings(
            id=1,
            telegram_enabled=env.telegram_enabled,
            telegram_bot_token=env.telegram_bot_token,
            telegram_admin_chat_id=env.telegram_admin_chat_id,
            telegram_allowed_user_ids=env.telegram_allowed_user_ids,
            download_path_template=env.download_path_template,
            default_sync_interval_seconds=env.default_sync_interval_seconds,
            max_concurrent_downloads=env.max_concurrent_downloads,
            scheduler_poll_seconds=env.scheduler_poll_seconds,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_row(self) -> RuntimeSettings:
        return self._get_or_create_row()

    def to_api_dict(self) -> dict:
        row = self.get_row()
        env = get_settings()
        return {
            "telegram_enabled": row.telegram_enabled,
            "telegram_bot_token_set": bool(row.telegram_bot_token),
            "telegram_bot_token_masked": _mask_token(row.telegram_bot_token),
            "telegram_admin_chat_id": row.telegram_admin_chat_id or "",
            "telegram_allowed_user_ids": row.telegram_allowed_user_ids or "",
            "download_path_template": row.download_path_template
            or env.download_path_template,
            "default_sync_interval_seconds": row.default_sync_interval_seconds,
            "max_concurrent_downloads": row.max_concurrent_downloads,
            "scheduler_poll_seconds": row.scheduler_poll_seconds,
            "base_download_dir": str(env.base_download_dir),
        }

    def update(self, data: dict) -> RuntimeSettings:
        row = self._get_or_create_row()

        if "telegram_enabled" in data and data["telegram_enabled"] is not None:
            row.telegram_enabled = data["telegram_enabled"]
        if "telegram_admin_chat_id" in data and data["telegram_admin_chat_id"] is not None:
            row.telegram_admin_chat_id = data["telegram_admin_chat_id"].strip()
        if "telegram_allowed_user_ids" in data and data["telegram_allowed_user_ids"] is not None:
            row.telegram_allowed_user_ids = data["telegram_allowed_user_ids"].strip()
        if "telegram_bot_token" in data and data["telegram_bot_token"]:
            token = data["telegram_bot_token"].strip()
            if token and not token.startswith("••••"):
                row.telegram_bot_token = token
        if "download_path_template" in data and data["download_path_template"] is not None:
            row.download_path_template = validate_path_template(data["download_path_template"])
        if "default_sync_interval_seconds" in data and data["default_sync_interval_seconds"] is not None:
            row.default_sync_interval_seconds = int(data["default_sync_interval_seconds"])
        if "max_concurrent_downloads" in data and data["max_concurrent_downloads"] is not None:
            row.max_concurrent_downloads = int(data["max_concurrent_downloads"])
        if "scheduler_poll_seconds" in data and data["scheduler_poll_seconds"] is not None:
            row.scheduler_poll_seconds = int(data["scheduler_poll_seconds"])

        self.db.commit()
        self.db.refresh(row)
        get_effective_settings.cache_clear()
        return row


def get_effective_settings_from_row(row: RuntimeSettings | None) -> Settings:
    env = get_settings()
    if not row:
        return env
    return Settings(
        **{
            **env.model_dump(),
            "telegram_enabled": row.telegram_enabled,
            "telegram_bot_token": row.telegram_bot_token,
            "telegram_admin_chat_id": row.telegram_admin_chat_id,
            "telegram_allowed_user_ids": row.telegram_allowed_user_ids,
            "download_path_template": row.download_path_template,
            "default_sync_interval_seconds": row.default_sync_interval_seconds,
            "max_concurrent_downloads": row.max_concurrent_downloads,
            "scheduler_poll_seconds": row.scheduler_poll_seconds,
        }
    )


from functools import lru_cache


@lru_cache
def get_effective_settings() -> Settings:
    from iclouddownloader.db.session import get_session_factory

    db = get_session_factory()()
    try:
        row = db.get(RuntimeSettings, 1)
        return get_effective_settings_from_row(row)
    finally:
        db.close()
