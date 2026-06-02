"""Store web admin password hash in runtime_settings

Revision ID: 009
Revises: 008
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "runtime_settings",
        sa.Column("admin_password_hash", sa.String(256), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("runtime_settings", "admin_password_hash")
