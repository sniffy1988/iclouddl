from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from iclouddownloader.api.serialization import ApiDateTime


class LoginRequest(BaseModel):
    password: str


class SetupAdminRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class AuthStatusResponse(BaseModel):
    needs_setup: bool
    authenticated: bool = False


class UserCreate(BaseModel):
    apple_id: str | None = None
    display_name: str | None = None
    download_dir: str | None = None
    sync_interval_seconds: int | None = None
    library_key: str = "root"


class UserUpdate(BaseModel):
    display_name: str | None = None
    apple_id: str | None = None
    download_dir: str | None = Field(default=None, min_length=1, max_length=1024)
    sync_interval_seconds: int | None = Field(default=None, ge=300, le=2_592_000)
    enabled: bool | None = None
    library_key: str | None = None
    immich_library_id: str | None = None
    immich_scan_after_sync: bool | None = None
    reschedule_sync: bool | None = None


class UserResponse(BaseModel):
    id: int
    apple_id: str | None = None
    display_name: str | None
    account_label: str = ""
    download_dir: str
    sync_interval_seconds: int
    enabled: bool
    library_key: str
    next_sync_at: ApiDateTime | None
    last_sync_at: ApiDateTime | None
    last_sync_status: str | None
    auth_status: str = "not_authorized"
    icloud_auth_status: str = "not_linked"
    google_auth_status: str = "not_linked"
    activity_status: str = "idle"
    icloud_photos_count: int | None = None
    icloud_photos_count_at: ApiDateTime | None = None
    google_photos_count: int | None = None
    google_photos_count_at: ApiDateTime | None = None
    google_account_email: str | None = None
    downloaded_count: int = 0
    icloud_downloaded_count: int = 0
    google_downloaded_count: int = 0
    icloud_remaining: int | None = None
    google_remaining: int | None = None
    remaining_to_download: int | None = None
    icloud_authenticated_at: ApiDateTime | None = None
    icloud_2fa_at: ApiDateTime | None = None
    icloud_session_ok_at: ApiDateTime | None = None
    icloud_needs_auth: bool = True
    icloud_pending_challenge: bool = False
    icloud_authorized: bool = False
    google_authorized: bool = False
    google_needs_auth: bool = True
    google_authenticated_at: ApiDateTime | None = None
    linked_providers: list[str] = []
    active_syncs_by_scope: dict[str, bool] = {}
    icloud_2fa_expires_at: ApiDateTime | None = None
    days_until_2fa_expires: int | None = None
    immich_library_id: str | None = None
    immich_scan_after_sync: bool = False
    created_at: ApiDateTime
    updated_at: ApiDateTime

    model_config = {"from_attributes": True}


class SyncRunResponse(BaseModel):
    id: int
    user_id: int
    scope: str = "all"
    started_at: ApiDateTime
    finished_at: ApiDateTime | None
    status: str
    photos_discovered: int
    photos_downloaded: int
    photos_failed: int
    photos_skipped: int
    error_summary: str | None

    model_config = {"from_attributes": True}


class PhotoResponse(BaseModel):
    id: int
    user_id: int
    source: str
    provider_asset_id: str
    filename: str
    local_path: str | None
    file_size: int | None
    checksum_sha256: str | None
    asset_date: ApiDateTime | None
    media_type: str | None
    companion_local_path: str | None = None
    companion_media_type: str | None = None
    companion_file_size: int | None = None
    companion_checksum_sha256: str | None = None
    status: str
    downloaded_at: ApiDateTime | None
    error_message: str | None

    model_config = {"from_attributes": True}


class UserICloudLoginRequest(BaseModel):
    password: str = Field(min_length=1)


class UserICloudLoginResponse(BaseModel):
    ok: bool
    status: str
    message: str
    challenge_type: str | None = None
    challenge_id: int | None = None


class AuthChallengeRequest(BaseModel):
    code: str = Field(min_length=4, max_length=8)
    challenge_id: int | None = None
    password: str | None = None


class AuthChallengeResponse(BaseModel):
    id: int
    user_id: int
    challenge_type: str
    status: str
    expires_at: ApiDateTime

    model_config = {"from_attributes": True}


class PhotoCountResponse(BaseModel):
    user_id: int
    source: str | None = None
    icloud_photos_count: int | None
    icloud_photos_count_at: ApiDateTime | None
    google_photos_count: int | None = None
    google_photos_count_at: ApiDateTime | None = None
    downloaded_count: int
    tracked_count: int
    icloud_downloaded_count: int = 0
    google_downloaded_count: int = 0
    icloud_remaining: int | None = None
    google_remaining: int | None = None
    remaining_to_download: int | None = None


class FetchCountResponse(BaseModel):
    ok: bool
    message: str
    user_id: int
    source: str | None = None
    already_running: bool = False


class TriggerSyncResponse(BaseModel):
    ok: bool
    message: str
    user_id: int
    source: str | None = None
    scope: str | None = None
    sync_run_id: int | None = None
    already_running: bool = False


class CancelSyncResponse(BaseModel):
    ok: bool
    message: str
    user_id: int
    source: str | None = None
    cancelled_run_ids: list[int] = []


class DashboardStats(BaseModel):
    total_users: int
    enabled_users: int
    total_photos: int
    downloaded_today: int
    active_syncs: int
    failed_syncs: int
    users_due_for_sync: int


PhotoSourceParam = Literal["icloud", "google_photos"]


class SettingsResponse(BaseModel):
    telegram_enabled: bool
    telegram_bot_token_set: bool = False
    telegram_bot_token_masked: str = ""
    download_path_template: str = "YYYY/MM/DD/{filename}"
    default_sync_interval_seconds: int
    max_concurrent_downloads: int
    scheduler_poll_seconds: int
    base_download_dir: str
    immich_enabled: bool = False
    immich_base_url: str = ""
    immich_api_key_set: bool = False
    immich_api_key_masked: str = ""
    immich_scan_debounce_seconds: int = 120
    admin_password_set: bool = False
    google_oauth_client_id: str = ""
    google_oauth_client_secret_set: bool = False
    google_oauth_client_secret_masked: str = ""
    web_public_base_url: str = "http://localhost:8765"
    google_oauth_redirect_uri: str = ""
    token_encryption_key_set: bool = False
    debug_logging_enabled: bool = False
    logging_level: str = "OFF"
    icloud_download_version: str = "original"
    skip_videos: bool = False
    skip_live_companions: bool = False
    skip_motion_companions: bool = False


class AppLogEntry(BaseModel):
    id: int
    created_at: str | None
    level: str
    logger_name: str
    message: str
    exception: str | None = None
    source: str = "app"


class AppLogListResponse(BaseModel):
    items: list[AppLogEntry]
    total: int


class ImmichTestRequest(BaseModel):
    library_id: str | None = None


class SettingsUpdate(BaseModel):
    telegram_enabled: bool | None = None
    telegram_bot_token: str | None = None
    download_path_template: str | None = None
    default_sync_interval_seconds: int | None = Field(default=None, ge=300)
    max_concurrent_downloads: int | None = Field(default=None, ge=1, le=32)
    scheduler_poll_seconds: int | None = Field(default=None, ge=10, le=3600)
    immich_enabled: bool | None = None
    immich_base_url: str | None = None
    immich_api_key: str | None = None
    immich_scan_debounce_seconds: int | None = Field(default=None, ge=0, le=3600)
    admin_password: str | None = None
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    debug_logging_enabled: bool | None = None
    logging_level: str | None = None
    icloud_download_version: str | None = None
    skip_videos: bool | None = None
    skip_live_companions: bool | None = None
    skip_motion_companions: bool | None = None
