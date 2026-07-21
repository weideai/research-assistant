"""add research traceability

Revision ID: 9b2f6a7c8d01
Revises: 66a025c924fd
Create Date: 2026-07-21 18:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = "9b2f6a7c8d01"
down_revision = "66a025c924fd"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def upgrade():
    with op.batch_alter_table("experiment") as batch_op:
        batch_op.add_column(sa.Column("batch_code", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("repeat_kind", sa.String(length=30), nullable=False, server_default="独立实验"))
        batch_op.add_column(sa.Column("repeat_number", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("group_name", sa.String(length=80), nullable=True))

    with op.batch_alter_table("experiment_attachment") as batch_op:
        batch_op.add_column(sa.Column("sha256", sa.String(length=64), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("tags", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"))
        batch_op.create_index("ix_experiment_attachment_sha256", ["sha256"], unique=False)

    op.create_table(
        "experiment_template",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_experiment_template_user_id", "experiment_template", ["user_id"])

    op.create_table(
        "experiment_template_step",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("experiment_template.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("planned_offset_days", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
    )
    op.create_index("ix_experiment_template_step_template_id", "experiment_template_step", ["template_id"])

    op.create_table(
        "experiment_parameter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiment.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("value", sa.String(length=160), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_experiment_parameter_experiment_id", "experiment_parameter", ["experiment_id"])

    op.create_table(
        "record_parameter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("experiment_record.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("value", sa.String(length=160), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_record_parameter_record_id", "record_parameter", ["record_id"])

    op.create_table(
        "experiment_sample",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiment.id"), nullable=False),
        sa.Column("sample_id", sa.Integer(), sa.ForeignKey("sample.id"), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column("amount_used", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("experiment_id", "sample_id", name="uq_experiment_sample"),
    )
    op.create_index("ix_experiment_sample_experiment_id", "experiment_sample", ["experiment_id"])
    op.create_index("ix_experiment_sample_sample_id", "experiment_sample", ["sample_id"])


def downgrade():
    op.drop_table("experiment_sample")
    op.drop_table("record_parameter")
    op.drop_table("experiment_parameter")
    op.drop_table("experiment_template_step")
    op.drop_table("experiment_template")
    with op.batch_alter_table("experiment_attachment") as batch_op:
        batch_op.drop_index("ix_experiment_attachment_sha256")
        batch_op.drop_column("version_number")
        batch_op.drop_column("description")
        batch_op.drop_column("tags")
        batch_op.drop_column("sha256")
    with op.batch_alter_table("experiment") as batch_op:
        batch_op.drop_column("group_name")
        batch_op.drop_column("repeat_number")
        batch_op.drop_column("repeat_kind")
        batch_op.drop_column("batch_code")
