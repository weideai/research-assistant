"""Persist execution-level selections for AI conversations.

Revision ID: d2f8a1c7b604
Revises: c9a4e7d2b610
"""

from alembic import op
import sqlalchemy as sa


revision = "d2f8a1c7b604"
down_revision = "c9a4e7d2b610"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ai_conversation") as batch:
        batch.add_column(sa.Column(
            "selected_batch_ids_json", sa.Text(), nullable=False, server_default="[]"
        ))


def downgrade():
    with op.batch_alter_table("ai_conversation") as batch:
        batch.drop_column("selected_batch_ids_json")
