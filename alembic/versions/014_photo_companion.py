"""Photo companion file columns for live/motion video parts

Revision ID: 014
Revises: 013
Create Date: 2026-06-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("photos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("companion_local_path", sa.String(2048), nullable=True))
        batch_op.add_column(sa.Column("companion_media_type", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("companion_file_size", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("companion_checksum_sha256", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("photos", schema=None) as batch_op:
        batch_op.drop_column("companion_checksum_sha256")
        batch_op.drop_column("companion_file_size")
        batch_op.drop_column("companion_media_type")
        batch_op.drop_column("companion_local_path")
