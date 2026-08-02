"""Add the local weekly report library and its update timeline.

Revision ID: g3a8b1c2d4e5
Revises: f2e7a9c4d1b0
"""

from alembic import op
import sqlalchemy as sa


revision = "g3a8b1c2d4e5"
down_revision = "f2e7a9c4d1b0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "weekly_report",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_project.id")),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("period_start", sa.Date()),
        sa.Column("period_end", sa.Date()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="待反馈"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("stored_path", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("folder_path", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("mime_type", sa.String(length=160), nullable=False, server_default="application/octet-stream"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_weekly_report_user_id", "weekly_report", ["user_id"])
    op.create_index("ix_weekly_report_project_id", "weekly_report", ["project_id"])
    op.create_index("ix_weekly_report_report_date", "weekly_report", ["report_date"])
    op.create_index("ix_weekly_report_period_start", "weekly_report", ["period_start"])
    op.create_index("ix_weekly_report_period_end", "weekly_report", ["period_end"])
    op.create_index("ix_weekly_report_status", "weekly_report", ["status"])
    op.create_index("ix_weekly_report_sha256", "weekly_report", ["sha256"])

    op.create_table(
        "weekly_report_update",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("weekly_report.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="修改日常"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="待处理"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_weekly_report_update_report_id", "weekly_report_update", ["report_id"])
    op.create_index("ix_weekly_report_update_user_id", "weekly_report_update", ["user_id"])
    op.create_index("ix_weekly_report_update_entry_date", "weekly_report_update", ["entry_date"])


def downgrade():
    op.drop_table("weekly_report_update")
    op.drop_table("weekly_report")
