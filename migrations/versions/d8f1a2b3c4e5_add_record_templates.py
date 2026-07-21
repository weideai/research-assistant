"""add independent experiment record templates

Revision ID: d8f1a2b3c4e5
Revises: c4e6f2a8d913
Create Date: 2026-07-21 21:40:00
"""
from alembic import op
import sqlalchemy as sa


revision = "d8f1a2b3c4e5"
down_revision = "c4e6f2a8d913"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "record_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("conditions", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_record_template_user_id", "record_template", ["user_id"])
    op.create_table(
        "record_template_parameter",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("value", sa.String(length=160), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["template_id"], ["record_template.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_record_template_parameter_template_id", "record_template_parameter", ["template_id"])


def downgrade():
    op.drop_index("ix_record_template_parameter_template_id", table_name="record_template_parameter")
    op.drop_table("record_template_parameter")
    op.drop_index("ix_record_template_user_id", table_name="record_template")
    op.drop_table("record_template")
