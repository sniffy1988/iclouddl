"""Remove per-user telegram_notify; Telegram is global daemon status only

Revision ID: 008
Revises: 007
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "telegram_notify")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_notify", sa.Boolean(), nullable=False, server_default="1"),
    )
