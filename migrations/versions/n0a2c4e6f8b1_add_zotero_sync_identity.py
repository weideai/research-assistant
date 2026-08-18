"""Add Zotero sync identity, progress, and attachment source keys.

Revision ID: n0a2c4e6f8b1
Revises: m9f1b3d5e7a2
"""

from alembic import op
import sqlalchemy as sa


revision = "n0a2c4e6f8b1"
down_revision = "m9f1b3d5e7a2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("zotero_connection") as batch:
        batch.add_column(sa.Column("server_id", sa.String(length=120), nullable=False, server_default=""))
        batch.add_column(sa.Column("library_version", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("last_full_sync_at", sa.DateTime()))
        batch.add_column(sa.Column("last_incremental_sync_at", sa.DateTime()))
        batch.add_column(sa.Column("sync_state", sa.String(length=24), nullable=False, server_default="idle"))
        batch.add_column(sa.Column("sync_progress", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("sync_stage", sa.String(length=120), nullable=False, server_default=""))
    with op.batch_alter_table("library_item") as batch:
        batch.add_column(sa.Column("source_key", sa.String(length=255)))
        batch.create_unique_constraint(
            "uq_library_workspace_source_key",
            ["workspace_id", "source_key"],
        )


def downgrade():
    with op.batch_alter_table("library_item") as batch:
        batch.drop_constraint("uq_library_workspace_source_key", type_="unique")
        batch.drop_column("source_key")
    with op.batch_alter_table("zotero_connection") as batch:
        batch.drop_column("sync_stage")
        batch.drop_column("sync_progress")
        batch.drop_column("sync_state")
        batch.drop_column("last_incremental_sync_at")
        batch.drop_column("last_full_sync_at")
        batch.drop_column("library_version")
        batch.drop_column("server_id")
