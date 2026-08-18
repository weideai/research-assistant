"""Mirror Zotero collections and optional project mappings.

Revision ID: o1b3d5f7a9c2
Revises: n0a2c4e6f8b1
"""

from alembic import op
import sqlalchemy as sa


revision = "o1b3d5f7a9c2"
down_revision = "n0a2c4e6f8b1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "zotero_collection",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("library_key", sa.String(length=120), nullable=False, server_default="personal"),
        sa.Column("collection_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("parent_key", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_missing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "library_key", "collection_key", name="uq_zotero_collection_identity"),
    )
    op.create_index("ix_zotero_collection_workspace_id", "zotero_collection", ["workspace_id"])
    op.create_index("ix_zotero_collection_library_key", "zotero_collection", ["library_key"])
    op.create_table(
        "zotero_collection_literature",
        sa.Column("collection_id", sa.Integer(), sa.ForeignKey("zotero_collection.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("literature_id", sa.Integer(), sa.ForeignKey("literature_item.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "project_zotero_collection",
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_project.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("collection_id", sa.Integer(), sa.ForeignKey("zotero_collection.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade():
    op.drop_table("project_zotero_collection")
    op.drop_table("zotero_collection_literature")
    op.drop_index("ix_zotero_collection_library_key", table_name="zotero_collection")
    op.drop_index("ix_zotero_collection_workspace_id", table_name="zotero_collection")
    op.drop_table("zotero_collection")
