"""Google Photos dual-source: users, photos, sync_runs scope, runtime OAuth

Revision ID: 010
Revises: 009
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users: nullable apple_id + Google fields ---
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("apple_id", existing_type=sa.String(255), nullable=True)
        batch_op.add_column(sa.Column("google_account_email", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("google_refresh_token_encrypted", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("google_authenticated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "google_needs_auth",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(sa.Column("google_photos_count", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("google_photos_count_at", sa.DateTime(timezone=True), nullable=True)
        )

    # --- photos: source + provider_asset_id ---
    with op.batch_alter_table("photos", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "source",
                sa.String(32),
                nullable=False,
                server_default="icloud",
            )
        )
        batch_op.add_column(
            sa.Column("provider_asset_id", sa.String(512), nullable=True)
        )

    op.execute("UPDATE photos SET provider_asset_id = icloud_asset_id WHERE provider_asset_id IS NULL")
    with op.batch_alter_table("photos", schema=None) as batch_op:
        batch_op.alter_column("provider_asset_id", nullable=False)
        batch_op.drop_constraint("uq_photo_user_asset", type_="unique")
        batch_op.create_unique_constraint(
            "uq_photo_user_source_asset",
            ["user_id", "source", "provider_asset_id"],
        )
        batch_op.drop_column("icloud_asset_id")

    # --- sync_runs: scope ---
    with op.batch_alter_table("sync_runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("scope", sa.String(32), nullable=False, server_default="all")
        )
        batch_op.create_index(
            "ix_sync_runs_user_status_scope",
            ["user_id", "status", "scope"],
        )

    # --- runtime_settings: Google OAuth client ---
    with op.batch_alter_table("runtime_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("google_oauth_client_id", sa.String(512), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("google_oauth_client_secret", sa.String(512), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("runtime_settings", schema=None) as batch_op:
        batch_op.drop_column("google_oauth_client_secret")
        batch_op.drop_column("google_oauth_client_id")

    with op.batch_alter_table("sync_runs", schema=None) as batch_op:
        batch_op.drop_index("ix_sync_runs_user_status_scope")
        batch_op.drop_column("scope")

    with op.batch_alter_table("photos", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("icloud_asset_id", sa.String(512), nullable=True)
        )
    op.execute("UPDATE photos SET icloud_asset_id = provider_asset_id")
    with op.batch_alter_table("photos", schema=None) as batch_op:
        batch_op.alter_column("icloud_asset_id", nullable=False)
        batch_op.drop_constraint("uq_photo_user_source_asset", type_="unique")
        batch_op.create_unique_constraint(
            "uq_photo_user_asset",
            ["user_id", "icloud_asset_id"],
        )
        batch_op.drop_column("provider_asset_id")
        batch_op.drop_column("source")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("google_photos_count_at")
        batch_op.drop_column("google_photos_count")
        batch_op.drop_column("google_needs_auth")
        batch_op.drop_column("google_authenticated_at")
        batch_op.drop_column("google_refresh_token_encrypted")
        batch_op.drop_column("google_account_email")
        batch_op.alter_column("apple_id", existing_type=sa.String(255), nullable=False)
