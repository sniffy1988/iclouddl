"""Immich settings and per-user library overrides

Revision ID: 005
Revises: 004
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "runtime_settings",
        sa.Column("immich_enabled", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "runtime_settings",
        sa.Column("immich_base_url", sa.String(512), nullable=False, server_default=""),
    )
    op.add_column(
        "runtime_settings",
        sa.Column("immich_api_key", sa.String(512), nullable=False, server_default=""),
    )
    op.add_column(
        "runtime_settings",
        sa.Column("immich_library_id", sa.String(36), nullable=False, server_default=""),
    )
    op.add_column(
        "runtime_settings",
        sa.Column("immich_scan_debounce_seconds", sa.Integer(), nullable=False, server_default="120"),
    )
    op.add_column(
        "users",
        sa.Column("immich_library_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("immich_scan_after_sync", sa.Boolean(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("users", "immich_scan_after_sync")
    op.drop_column("users", "immich_library_id")
    op.drop_column("runtime_settings", "immich_scan_debounce_seconds")
    op.drop_column("runtime_settings", "immich_library_id")
    op.drop_column("runtime_settings", "immich_api_key")
    op.drop_column("runtime_settings", "immich_base_url")
    op.drop_column("runtime_settings", "immich_enabled")
