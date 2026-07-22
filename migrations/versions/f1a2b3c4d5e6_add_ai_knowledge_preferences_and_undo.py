"""add AI knowledge bases, preferences, and proposal undo

Revision ID: f1a2b3c4d5e6
Revises: d8f1a2b3c4e5
Create Date: 2026-07-22 12:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "d8f1a2b3c4e5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ai_conversation") as batch_op:
        batch_op.add_column(sa.Column(
            "selected_knowledge_base_ids_json", sa.Text(), nullable=False, server_default="[]"
        ))
    with op.batch_alter_table("ai_message") as batch_op:
        batch_op.add_column(sa.Column("undo_json", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("after_json", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("reverted_at", sa.DateTime(), nullable=True))

    op.create_table(
        "ai_assistant_preference",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("custom_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_ai_assistant_preference_user_id", "ai_assistant_preference", ["user_id"])
    op.create_table(
        "ai_knowledge_base",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("custom_instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_knowledge_base_user_id", "ai_knowledge_base", ["user_id"])
    op.create_table(
        "ai_knowledge_document",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("stored_path", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("mime_type", sa.String(length=160), nullable=False, server_default="text/plain"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("text_content", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["ai_knowledge_base.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_knowledge_document_knowledge_base_id", "ai_knowledge_document", ["knowledge_base_id"])


def downgrade():
    op.drop_index("ix_ai_knowledge_document_knowledge_base_id", table_name="ai_knowledge_document")
    op.drop_table("ai_knowledge_document")
    op.drop_index("ix_ai_knowledge_base_user_id", table_name="ai_knowledge_base")
    op.drop_table("ai_knowledge_base")
    op.drop_index("ix_ai_assistant_preference_user_id", table_name="ai_assistant_preference")
    op.drop_table("ai_assistant_preference")
    with op.batch_alter_table("ai_message") as batch_op:
        batch_op.drop_column("reverted_at")
        batch_op.drop_column("after_json")
        batch_op.drop_column("undo_json")
    with op.batch_alter_table("ai_conversation") as batch_op:
        batch_op.drop_column("selected_knowledge_base_ids_json")
