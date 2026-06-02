from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class PhotoSource(str, enum.Enum):
    icloud = "icloud"
    google_photos = "google_photos"


class SyncRunScope(str, enum.Enum):
    icloud = "icloud"
    google_photos = "google_photos"
    all = "all"


class PhotoStatus(str, enum.Enum):
    pending = "pending"
    downloaded = "downloaded"
    failed = "failed"
    skipped = "skipped"


class SyncRunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AuthChallengeStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    expired = "expired"
    failed = "failed"


class AuthChallengeType(str, enum.Enum):
    twofa = "2fa"
    twosa = "2sa"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    apple_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    download_dir: Mapped[str] = mapped_column(String(1024), nullable=False)
    sync_interval_seconds: Mapped[int] = mapped_column(Integer, default=21600)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    library_key: Mapped[str] = mapped_column(String(255), default="root")
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(String(64))
    icloud_photos_count: Mapped[int | None] = mapped_column(Integer)
    icloud_photos_count_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    icloud_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    icloud_2fa_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    icloud_session_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    icloud_needs_auth: Mapped[bool] = mapped_column(Boolean, default=True)
    google_account_email: Mapped[str | None] = mapped_column(String(255))
    google_refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    google_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    google_needs_auth: Mapped[bool] = mapped_column(Boolean, default=True)
    google_photos_count: Mapped[int | None] = mapped_column(Integer)
    google_photos_count_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    immich_library_id: Mapped[str | None] = mapped_column(String(36))
    immich_scan_after_sync: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    photos: Mapped[list[Photo]] = relationship(back_populates="user")
    sync_runs: Mapped[list[SyncRun]] = relationship(back_populates="user")
    sync_cursors: Mapped[list[SyncCursor]] = relationship(back_populates="user")
    auth_challenges: Mapped[list[AuthChallenge]] = relationship(back_populates="user")


class SyncCursor(Base):
    __tablename__ = "sync_cursors"
    __table_args__ = (UniqueConstraint("user_id", "library_key", name="uq_sync_cursor_user_library"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    library_key: Mapped[str] = mapped_column(String(255), default="root")
    cursor_value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="sync_cursors")


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "provider_asset_id", name="uq_photo_user_source_asset"),
        Index("ix_photos_user_status", "user_id", "status"),
        Index("ix_photos_user_source_status", "user_id", "source", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[PhotoSource] = mapped_column(
        Enum(PhotoSource, native_enum=False), default=PhotoSource.icloud
    )
    provider_asset_id: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    local_path: Mapped[str | None] = mapped_column(String(2048))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    asset_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    media_type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[PhotoStatus] = mapped_column(
        Enum(PhotoStatus, native_enum=False), default=PhotoStatus.pending
    )
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="photos")
    download_jobs: Mapped[list[DownloadJob]] = relationship(back_populates="photo")


class SyncRun(Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        Index("ix_sync_runs_user_started", "user_id", "started_at"),
        Index("ix_sync_runs_user_status_scope", "user_id", "status", "scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[SyncRunScope] = mapped_column(
        Enum(SyncRunScope, native_enum=False), default=SyncRunScope.all
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[SyncRunStatus] = mapped_column(
        Enum(SyncRunStatus, native_enum=False), default=SyncRunStatus.running
    )
    photos_discovered: Mapped[int] = mapped_column(Integer, default=0)
    photos_downloaded: Mapped[int] = mapped_column(Integer, default=0)
    photos_failed: Mapped[int] = mapped_column(Integer, default=0)
    photos_skipped: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="sync_runs")


class AuthChallenge(Base):
    __tablename__ = "auth_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    challenge_type: Mapped[AuthChallengeType] = mapped_column(
        Enum(AuthChallengeType, native_enum=False)
    )
    status: Mapped[AuthChallengeStatus] = mapped_column(
        Enum(AuthChallengeStatus, native_enum=False), default=AuthChallengeStatus.pending
    )
    prompt_message_id: Mapped[str | None] = mapped_column(String(64))
    submitted_code: Mapped[str | None] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="auth_challenges")


class DownloadJob(Base):
    __tablename__ = "download_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    photo: Mapped[Photo] = relationship(back_populates="download_jobs")


class RuntimeSettings(Base):
    """Single-row app settings (id=1), editable from the web UI."""

    __tablename__ = "runtime_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_bot_token: Mapped[str] = mapped_column(String(512), default="")
    telegram_admin_chat_id: Mapped[str] = mapped_column(String(64), default="")
    telegram_allowed_user_ids: Mapped[str] = mapped_column(String(512), default="")
    download_path_template: Mapped[str] = mapped_column(String(512), default="YYYY/MM/DD/{filename}")
    default_sync_interval_seconds: Mapped[int] = mapped_column(Integer, default=21600)
    max_concurrent_downloads: Mapped[int] = mapped_column(Integer, default=3)
    scheduler_poll_seconds: Mapped[int] = mapped_column(Integer, default=60)
    immich_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    immich_base_url: Mapped[str] = mapped_column(String(512), default="")
    immich_api_key: Mapped[str] = mapped_column(String(512), default="")
    immich_scan_debounce_seconds: Mapped[int] = mapped_column(Integer, default=120)
    admin_password_hash: Mapped[str] = mapped_column(String(256), default="")
    google_oauth_client_id: Mapped[str] = mapped_column(String(512), default="")
    google_oauth_client_secret: Mapped[str] = mapped_column(String(512), default="")
    debug_logging_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    logging_level: Mapped[str] = mapped_column(String(16), default="OFF")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AppLog(Base):
    __tablename__ = "app_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    logger_name: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    exception: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="app")


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
