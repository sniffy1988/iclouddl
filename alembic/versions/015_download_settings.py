"""Download policy settings on runtime_settings

Revision ID: 015
Revises: 014
Create Date: 2026-06-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("runtime_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "icloud_download_version",
                sa.String(16),
                nullable=False,
                server_default="original",
            )
        )
        batch_op.add_column(
            sa.Column("skip_videos", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "skip_live_companions",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "skip_motion_companions",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("runtime_settings", schema=None) as batch_op:
        batch_op.drop_column("skip_motion_companions")
        batch_op.drop_column("skip_live_companions")
        batch_op.drop_column("skip_videos")
        batch_op.drop_column("icloud_download_version")
