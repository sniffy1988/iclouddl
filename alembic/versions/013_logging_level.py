"""Add logging_level to runtime_settings

Revision ID: 013
Revises: 012
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("runtime_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("logging_level", sa.String(length=16), nullable=False, server_default="OFF")
        )
    op.execute(
        "UPDATE runtime_settings SET logging_level = 'DEBUG' WHERE debug_logging_enabled = 1"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE runtime_settings SET debug_logging_enabled = 1 WHERE logging_level = 'DEBUG'"
    )
    with op.batch_alter_table("runtime_settings", schema=None) as batch_op:
        batch_op.drop_column("logging_level")
