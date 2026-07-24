"""Persist capability evidence for the selected API preset model.

Revision ID: 7c3d9a1e5f42
Revises: e6b9c1d4f208
"""

from alembic import op
import sqlalchemy as sa


revision = "7c3d9a1e5f42"
down_revision = "e6b9c1d4f208"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("api_preset") as batch:
        batch.add_column(sa.Column(
            "model_capabilities_json", sa.Text(), nullable=False, server_default="{}"
        ))


def downgrade():
    with op.batch_alter_table("api_preset") as batch:
        batch.drop_column("model_capabilities_json")
