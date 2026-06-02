"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("apple_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("download_dir", sa.String(length=1024), nullable=False),
        sa.Column("sync_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("library_key", sa.String(length=255), nullable=False),
        sa.Column("telegram_notify", sa.Boolean(), nullable=False),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("apple_id"),
    )
    op.create_index("ix_users_apple_id", "users", ["apple_id"])

    op.create_table(
        "sync_cursors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("library_key", sa.String(length=255), nullable=False),
        sa.Column("cursor_value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "library_key", name="uq_sync_cursor_user_library"),
    )

    op.create_table(
        "auth_challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "challenge_type",
            sa.Enum("2fa", "2sa", name="authchallengetype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "completed", "expired", "failed", name="authchallengestatus"),
            nullable=False,
        ),
        sa.Column("prompt_message_id", sa.String(length=64), nullable=True),
        sa.Column("submitted_code", sa.String(length=16), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("running", "completed", "failed", "cancelled", name="syncrunstatus"),
            nullable=False,
        ),
        sa.Column("photos_discovered", sa.Integer(), nullable=False),
        sa.Column("photos_downloaded", sa.Integer(), nullable=False),
        sa.Column("photos_failed", sa.Integer(), nullable=False),
        sa.Column("photos_skipped", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_runs_user_started", "sync_runs", ["user_id", "started_at"])

    op.create_table(
        "photos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("icloud_asset_id", sa.String(length=512), nullable=False),
        sa.Column("filename", sa.String(length=1024), nullable=False),
        sa.Column("local_path", sa.String(length=2048), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("asset_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("media_type", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "downloaded", "failed", "skipped", name="photostatus"),
            nullable=False,
        ),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "icloud_asset_id", name="uq_photo_user_asset"),
    )
    op.create_index("ix_photos_user_status", "photos", ["user_id", "status"])

    op.create_table(
        "download_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_admin_sessions_token_hash", "admin_sessions", ["token_hash"])


def downgrade() -> None:
    op.drop_table("admin_sessions")
    op.drop_table("download_jobs")
    op.drop_table("photos")
    op.drop_table("sync_runs")
    op.drop_table("auth_challenges")
    op.drop_table("sync_cursors")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS photostatus")
    op.execute("DROP TYPE IF EXISTS syncrunstatus")
    op.execute("DROP TYPE IF EXISTS authchallengestatus")
    op.execute("DROP TYPE IF EXISTS authchallengetype")
