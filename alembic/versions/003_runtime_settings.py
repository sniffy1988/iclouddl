"""runtime settings table

Revision ID: 003
Revises: 002
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "runtime_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("telegram_bot_token", sa.String(512), nullable=False, server_default=""),
        sa.Column("telegram_admin_chat_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("telegram_allowed_user_ids", sa.String(512), nullable=False, server_default=""),
        sa.Column(
            "download_path_template",
            sa.String(512),
            nullable=False,
            server_default="YYYY/MM/DD/{filename}",
        ),
        sa.Column("default_sync_interval_seconds", sa.Integer(), nullable=False, server_default="21600"),
        sa.Column("max_concurrent_downloads", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("scheduler_poll_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("runtime_settings")
