from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy.orm import Session

from iclouddownloader.admin_auth import set_admin_password
from iclouddownloader.config import EffectiveSettings, get_settings
from iclouddownloader.db.models import RuntimeSettings
from iclouddownloader.logging_setup import normalize_log_level
from iclouddownloader.path_template import validate_path_template


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return "••••••••"
    return "••••••••" + token[-4:]


def _import_legacy_telegram_from_env(row: RuntimeSettings) -> bool:
    """One-time migration for installs that still have TELEGRAM_* in the process environment."""
    if row.telegram_bot_token.strip():
        return False
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False
    row.telegram_bot_token = token
    chat = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()
    if chat:
        row.telegram_admin_chat_id = chat
    allowed = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
    if allowed:
        row.telegram_allowed_user_ids = allowed
    enabled_raw = os.getenv("TELEGRAM_ENABLED", "").strip().lower()
    row.telegram_enabled = enabled_raw in ("1", "true", "yes") or bool(token)
    return True


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
            telegram_enabled=False,
            telegram_bot_token="",
            telegram_admin_chat_id="",
            telegram_allowed_user_ids="",
            download_path_template=env.download_path_template,
            default_sync_interval_seconds=env.default_sync_interval_seconds,
            max_concurrent_downloads=env.max_concurrent_downloads,
            scheduler_poll_seconds=env.scheduler_poll_seconds,
            immich_enabled=env.immich_enabled,
            immich_base_url=env.immich_base_url,
            immich_api_key=env.immich_api_key,
            immich_scan_debounce_seconds=env.immich_scan_debounce_seconds,
            google_oauth_client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip(),
            google_oauth_client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip(),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        if _import_legacy_telegram_from_env(row):
            self.db.commit()
            self.db.refresh(row)
        return row

    def _backfill_immich_from_env(self, row: RuntimeSettings) -> None:
        if row.immich_api_key.strip():
            return
        key = os.getenv("IMMICH_API_KEY", "").strip()
        if key:
            row.immich_api_key = key
            self.db.commit()
            self.db.refresh(row)

    def get_row(self) -> RuntimeSettings:
        row = self._get_or_create_row()
        if _import_legacy_telegram_from_env(row):
            self.db.commit()
            self.db.refresh(row)
        self._backfill_immich_from_env(row)
        return row

    def to_api_dict(self) -> dict:
        row = self.get_row()
        env = get_settings()
        public_base = env.web_public_base_url.rstrip("/")
        return {
            "telegram_enabled": row.telegram_enabled,
            "telegram_bot_token_set": bool(row.telegram_bot_token),
            "telegram_bot_token_masked": _mask_token(row.telegram_bot_token),
            "download_path_template": row.download_path_template
            or env.download_path_template,
            "default_sync_interval_seconds": row.default_sync_interval_seconds,
            "max_concurrent_downloads": row.max_concurrent_downloads,
            "scheduler_poll_seconds": row.scheduler_poll_seconds,
            "base_download_dir": str(env.base_download_dir),
            "immich_enabled": row.immich_enabled,
            "immich_base_url": row.immich_base_url or "",
            "immich_api_key_set": bool(row.immich_api_key),
            "immich_api_key_masked": _mask_token(row.immich_api_key),
            "immich_scan_debounce_seconds": row.immich_scan_debounce_seconds,
            "admin_password_set": bool(row.admin_password_hash),
            "google_oauth_client_id": row.google_oauth_client_id or "",
            "google_oauth_client_secret_set": bool(row.google_oauth_client_secret),
            "google_oauth_client_secret_masked": _mask_token(row.google_oauth_client_secret),
            "web_public_base_url": public_base,
            "google_oauth_redirect_uri": f"{public_base}/api/auth/google/callback",
            "token_encryption_key_set": bool(env.token_encryption_key.strip()),
            "debug_logging_enabled": row.debug_logging_enabled,
            "logging_level": normalize_log_level(row.logging_level),
        }

    def update(self, data: dict) -> RuntimeSettings:
        row = self._get_or_create_row()

        if "telegram_enabled" in data and data["telegram_enabled"] is not None:
            row.telegram_enabled = data["telegram_enabled"]
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
        if "immich_enabled" in data and data["immich_enabled"] is not None:
            row.immich_enabled = data["immich_enabled"]
        if "immich_base_url" in data and data["immich_base_url"] is not None:
            row.immich_base_url = str(data["immich_base_url"]).strip().rstrip("/")
        if "immich_api_key" in data and data["immich_api_key"]:
            token = str(data["immich_api_key"]).strip()
            if token and not token.startswith("••••"):
                row.immich_api_key = token
        if "immich_scan_debounce_seconds" in data and data["immich_scan_debounce_seconds"] is not None:
            row.immich_scan_debounce_seconds = max(int(data["immich_scan_debounce_seconds"]), 0)
        if data.get("admin_password"):
            pwd = str(data["admin_password"]).strip()
            if pwd and not pwd.startswith("••••"):
                set_admin_password(self.db, row, pwd)
        if "google_oauth_client_id" in data and data["google_oauth_client_id"] is not None:
            row.google_oauth_client_id = str(data["google_oauth_client_id"]).strip()
        if "google_oauth_client_secret" in data and data["google_oauth_client_secret"]:
            secret = str(data["google_oauth_client_secret"]).strip()
            if secret and not secret.startswith("••••"):
                row.google_oauth_client_secret = secret
        if "logging_level" in data and data["logging_level"] is not None:
            level = normalize_log_level(data["logging_level"])
            row.logging_level = level
            row.debug_logging_enabled = level == "DEBUG"
        elif "debug_logging_enabled" in data and data["debug_logging_enabled"] is not None:
            row.debug_logging_enabled = bool(data["debug_logging_enabled"])
            row.logging_level = "DEBUG" if row.debug_logging_enabled else "OFF"

        self.db.commit()
        self.db.refresh(row)
        get_effective_settings.cache_clear()
        from iclouddownloader.logging_setup import configure_logging

        configure_logging(force=True)
        return row


def get_effective_settings_from_row(row: RuntimeSettings | None) -> EffectiveSettings:
    env = get_settings()
    merged = env.model_dump()
    if not row:
        return EffectiveSettings(**merged)
    merged.update(
        {
            "telegram_enabled": row.telegram_enabled,
            "telegram_bot_token": row.telegram_bot_token,
            "telegram_admin_chat_id": row.telegram_admin_chat_id,
            "telegram_allowed_user_ids": row.telegram_allowed_user_ids,
            "download_path_template": row.download_path_template,
            "default_sync_interval_seconds": row.default_sync_interval_seconds,
            "max_concurrent_downloads": row.max_concurrent_downloads,
            "scheduler_poll_seconds": row.scheduler_poll_seconds,
            "immich_enabled": row.immich_enabled,
            "immich_base_url": row.immich_base_url,
            "immich_api_key": row.immich_api_key,
            "immich_scan_debounce_seconds": row.immich_scan_debounce_seconds,
            "google_oauth_client_id": row.google_oauth_client_id,
            "google_oauth_client_secret": row.google_oauth_client_secret,
            "debug_logging_enabled": row.debug_logging_enabled,
            "logging_level": normalize_log_level(row.logging_level),
        }
    )
    return EffectiveSettings(**merged)


@lru_cache
def get_effective_settings() -> EffectiveSettings:
    from iclouddownloader.db.session import get_session_factory

    db = get_session_factory()()
    try:
        row = db.get(RuntimeSettings, 1)
        return get_effective_settings_from_row(row)
    finally:
        db.close()
