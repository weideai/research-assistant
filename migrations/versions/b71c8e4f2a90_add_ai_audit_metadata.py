"""add AI audit metadata

Revision ID: b71c8e4f2a90
Revises: 9b2f6a7c8d01
Create Date: 2026-07-21 20:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = "b71c8e4f2a90"
down_revision = "9b2f6a7c8d01"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ai_message") as batch_op:
        batch_op.add_column(sa.Column("model_name", sa.String(length=160), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("prompt_snapshot", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("context_snapshot_json", sa.Text(), nullable=False, server_default="{}"))
        batch_op.add_column(sa.Column("requires_human_review", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table("ai_message") as batch_op:
        batch_op.drop_column("requires_human_review")
        batch_op.drop_column("context_snapshot_json")
        batch_op.drop_column("prompt_snapshot")
        batch_op.drop_column("model_name")
