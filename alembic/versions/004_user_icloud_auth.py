"""user icloud auth fields

Revision ID: 004
Revises: 003
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("icloud_authenticated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("icloud_2fa_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("icloud_session_ok_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("icloud_needs_auth", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.execute(
        """
        UPDATE users
        SET icloud_needs_auth = 0,
            icloud_authenticated_at = updated_at,
            icloud_2fa_at = updated_at,
            icloud_session_ok_at = updated_at
        WHERE last_sync_status = 'authenticated'
        """
    )


def downgrade() -> None:
    op.drop_column("users", "icloud_needs_auth")
    op.drop_column("users", "icloud_session_ok_at")
    op.drop_column("users", "icloud_2fa_at")
    op.drop_column("users", "icloud_authenticated_at")
