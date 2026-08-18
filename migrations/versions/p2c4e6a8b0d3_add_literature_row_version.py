"""Add optimistic versioning to literature.

Revision ID: p2c4e6a8b0d3
Revises: o1b3d5f7a9c2
"""

from alembic import op
import sqlalchemy as sa


revision = "p2c4e6a8b0d3"
down_revision = "o1b3d5f7a9c2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("literature_item") as batch:
        batch.add_column(sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    with op.batch_alter_table("literature_item") as batch:
        batch.drop_column("row_version")
