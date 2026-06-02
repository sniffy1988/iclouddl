"""Per-user Immich connection; global debounce only in runtime_settings

Revision ID: 006
Revises: 005
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("immich_enabled", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("immich_base_url", sa.String(512), nullable=False, server_default=""),
    )
    op.add_column(
        "users",
        sa.Column("immich_api_key", sa.String(512), nullable=False, server_default=""),
    )

    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.drop_column("immich_enabled")
        batch_op.drop_column("immich_base_url")
        batch_op.drop_column("immich_api_key")
        batch_op.drop_column("immich_library_id")


def downgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.add_column(
            sa.Column("immich_enabled", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("immich_base_url", sa.String(512), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("immich_api_key", sa.String(512), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("immich_library_id", sa.String(36), nullable=False, server_default="")
        )

    op.drop_column("users", "immich_api_key")
    op.drop_column("users", "immich_base_url")
    op.drop_column("users", "immich_enabled")
