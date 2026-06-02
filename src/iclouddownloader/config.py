from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment / infrastructure settings only (no Telegram — see Settings UI + DB)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./data/iclouddownloader.db"
    base_download_dir: Path = Path("./data/downloads")
    cookie_dir: Path = Path("./data/cookies")

    default_sync_interval_seconds: int = 21600
    max_concurrent_downloads: int = 3
    scheduler_poll_seconds: int = 60
    download_path_template: str = "YYYY/MM/DD/{filename}"

    web_host: str = "0.0.0.0"
    web_port: int = 8765
    web_session_secret: str = "change-this-secret-key"
    web_session_ttl_hours: int = 168
    web_public_base_url: str = "http://localhost:8765"
    token_encryption_key: str = ""

    icloud_2fa_delivery: str = "trusted_device"
    icloud_trusted_session_days: int = 30

    immich_enabled: bool = False
    immich_base_url: str = ""
    immich_api_key: str = ""
    immich_scan_debounce_seconds: int = 120


class EffectiveSettings(Settings):
    """Env settings merged with runtime_settings row (Telegram, Immich, sync defaults)."""

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_admin_chat_id: str = ""
    telegram_allowed_user_ids: str = ""
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    debug_logging_enabled: bool = False

    @property
    def telegram_allowed_ids(self) -> list[int]:
        if not self.telegram_allowed_user_ids.strip():
            return []
        return [int(x.strip()) for x in self.telegram_allowed_user_ids.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
