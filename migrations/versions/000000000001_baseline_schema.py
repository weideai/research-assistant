"""baseline schema

Revision ID: 000000000001
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = "000000000001"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def upgrade():
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "task",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_task_user_id", "task", ["user_id"])
    op.create_index("ix_task_deadline", "task", ["deadline"])
    op.create_index("ix_task_status", "task", ["status"])

    op.create_table(
        "experiment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_experiment_user_id", "experiment", ["user_id"])
    op.create_index("ix_experiment_status", "experiment", ["status"])

    op.create_table(
        "sample",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("sample_code", sa.String(length=80), nullable=False),
        sa.Column("sample_type", sa.String(length=80), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("location", sa.String(length=180), nullable=True),
        sa.Column("quantity", sa.String(length=60), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_sample_user_id", "sample", ["user_id"])
    op.create_index("ix_sample_sample_code", "sample", ["sample_code"])

    op.create_table(
        "paper",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("journal", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("submission_date", sa.Date(), nullable=True),
        sa.Column("revision_deadline", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_paper_user_id", "paper", ["user_id"])

    op.create_table(
        "api_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("api_url", sa.String(length=500), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_api_setting_user_id", "api_setting", ["user_id"], unique=True)

    op.create_table(
        "experiment_step",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiment.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("is_done", sa.Boolean(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_experiment_step_experiment_id", "experiment_step", ["experiment_id"])

    op.create_table(
        "experiment_record",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiment.id"), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("operator", sa.String(length=80), nullable=True),
        sa.Column("conditions", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_experiment_record_experiment_id", "experiment_record", ["experiment_id"])
    op.create_index("ix_experiment_record_record_date", "experiment_record", ["record_date"])

    op.create_table(
        "reviewer_comment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("paper.id"), nullable=False),
        sa.Column("reviewer", sa.String(length=40), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_reviewer_comment_paper_id", "reviewer_comment", ["paper_id"])


def downgrade():
    for table in ["reviewer_comment", "experiment_record", "experiment_step", "api_setting", "paper", "sample", "experiment", "task", "user"]:
        op.drop_table(table)

