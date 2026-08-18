"""Add optimistic locking to calendar events.

Revision ID: m9f1b3d5e7a2
Revises: l8e0a2c4d6f8
"""

from alembic import op
import sqlalchemy as sa


revision = "m9f1b3d5e7a2"
down_revision = "l8e0a2c4d6f8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("calendar_event") as batch:
        batch.add_column(sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    with op.batch_alter_table("calendar_event") as batch:
        batch.drop_column("row_version")
