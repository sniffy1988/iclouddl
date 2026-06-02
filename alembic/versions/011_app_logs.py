"""App logs table and debug_logging_enabled setting

Revision ID: 011
Revises: 010
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("logger_name", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("exception", sa.Text(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="app"),
    )
    op.create_index("ix_app_logs_created_at", "app_logs", ["created_at"])
    op.create_index("ix_app_logs_level", "app_logs", ["level"])

    with op.batch_alter_table("runtime_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "debug_logging_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("runtime_settings", schema=None) as batch_op:
        batch_op.drop_column("debug_logging_enabled")
    op.drop_index("ix_app_logs_level", table_name="app_logs")
    op.drop_index("ix_app_logs_created_at", table_name="app_logs")
    op.drop_table("app_logs")
