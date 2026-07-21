"""add complete template components and AI history scope

Revision ID: c4e6f2a8d913
Revises: b71c8e4f2a90
Create Date: 2026-07-22 10:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = "c4e6f2a8d913"
down_revision = "b71c8e4f2a90"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ai_conversation") as batch_op:
        batch_op.add_column(sa.Column("selected_experiment_ids_json", sa.Text(), nullable=False, server_default="[]"))

    with op.batch_alter_table("experiment") as batch_op:
        batch_op.add_column(sa.Column("sample_requirements_json", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("record_conditions_template", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("record_content_template", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("record_remark_template", sa.Text(), nullable=True))

    with op.batch_alter_table("experiment_template") as batch_op:
        batch_op.add_column(sa.Column("sample_requirements_json", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("record_conditions_template", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("record_content_template", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("record_remark_template", sa.Text(), nullable=True))

    op.create_table(
        "experiment_template_parameter",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("value", sa.String(length=160), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["template_id"], ["experiment_template.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_experiment_template_parameter_template_id", "experiment_template_parameter", ["template_id"])


def downgrade():
    op.drop_index("ix_experiment_template_parameter_template_id", table_name="experiment_template_parameter")
    op.drop_table("experiment_template_parameter")
    with op.batch_alter_table("experiment_template") as batch_op:
        batch_op.drop_column("record_remark_template")
        batch_op.drop_column("record_content_template")
        batch_op.drop_column("record_conditions_template")
        batch_op.drop_column("sample_requirements_json")
    with op.batch_alter_table("experiment") as batch_op:
        batch_op.drop_column("record_remark_template")
        batch_op.drop_column("record_content_template")
        batch_op.drop_column("record_conditions_template")
        batch_op.drop_column("sample_requirements_json")
    with op.batch_alter_table("ai_conversation") as batch_op:
        batch_op.drop_column("selected_experiment_ids_json")
