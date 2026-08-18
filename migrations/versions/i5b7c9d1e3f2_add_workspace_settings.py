"""Add per-user workflow settings.

Revision ID: i5b7c9d1e3f2
Revises: h4c9d2e5f7a1
"""

from alembic import op
import sqlalchemy as sa


revision = "i5b7c9d1e3f2"
down_revision = "h4c9d2e5f7a1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workspace_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("execution_save_mode", sa.String(length=20), nullable=False, server_default="stay"),
        sa.Column("execution_autosave", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("execution_autosave_interval", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("executor_options_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_workspace_setting_user_id"),
    )
    op.create_index("ix_workspace_setting_user_id", "workspace_setting", ["user_id"], unique=True)


def downgrade():
    op.drop_index("ix_workspace_setting_user_id", table_name="workspace_setting")
    op.drop_table("workspace_setting")
