"""Persist record-level selections for AI conversations.

Revision ID: h4c9d2e5f7a1
Revises: g3a8b1c2d4e5
"""

from alembic import op
import sqlalchemy as sa


revision = "h4c9d2e5f7a1"
down_revision = "g3a8b1c2d4e5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ai_conversation") as batch:
        batch.add_column(sa.Column(
            "selected_record_ids_json", sa.Text(), nullable=False, server_default="[]"
        ))


def downgrade():
    with op.batch_alter_table("ai_conversation") as batch:
        batch.drop_column("selected_record_ids_json")
