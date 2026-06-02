from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # File database (default): sqlite:///./data/iclouddownloader.db
    # Docker: sqlite:////data/iclouddownloader.db with ./data mounted to /data
    database_url: str = "sqlite:///./data/iclouddownloader.db"
    base_download_dir: Path = Path("./data/downloads")
    cookie_dir: Path = Path("./data/cookies")

    default_sync_interval_seconds: int = 21600
    max_concurrent_downloads: int = 3
    scheduler_poll_seconds: int = 60
    # Relative path under each user's download_dir; tokens: YYYY MM DD HH mm ss {filename}
    download_path_template: str = "YYYY/MM/DD/{filename}"

    web_host: str = "0.0.0.0"
    web_port: int = 8765
    web_admin_password: str = "change-me-in-production"
    web_session_secret: str = "change-this-secret-key"
    web_session_ttl_hours: int = 168

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_admin_chat_id: str = ""
    telegram_allowed_user_ids: str = ""

    # How to deliver Apple 2FA codes on login: trusted_device (popup only), sms, or both
    icloud_2fa_delivery: str = "trusted_device"
    # Apple trusted-browser session lifetime after 2FA (days)
    icloud_trusted_session_days: int = 30

    @property
    def telegram_allowed_ids(self) -> list[int]:
        if not self.telegram_allowed_user_ids.strip():
            return []
        return [int(x.strip()) for x in self.telegram_allowed_user_ids.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
