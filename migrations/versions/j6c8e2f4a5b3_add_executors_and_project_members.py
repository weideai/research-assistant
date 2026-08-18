"""Add managed executors and project participant assignments.

Revision ID: j6c8e2f4a5b3
Revises: i5b7c9d1e3f2
"""

from alembic import op
import sqlalchemy as sa


revision = "j6c8e2f4a5b3"
down_revision = "i5b7c9d1e3f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "executor",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_executor_user_name"),
    )
    op.create_index("ix_executor_user_id", "executor", ["user_id"], unique=False)
    op.create_index("ix_executor_is_active", "executor", ["is_active"], unique=False)
    op.create_table(
        "project_executor",
        sa.Column(
            "project_id", sa.Integer(),
            sa.ForeignKey("research_project.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "executor_id", sa.Integer(),
            sa.ForeignKey("executor.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade():
    op.drop_table("project_executor")
    op.drop_index("ix_executor_is_active", table_name="executor")
    op.drop_index("ix_executor_user_id", table_name="executor")
    op.drop_table("executor")
