"""Remove the paper and reviewer module from the product.

Revision ID: f2e7a9c4d1b0
Revises: d1f3a5b7c902
"""

from alembic import op
import sqlalchemy as sa


revision = "f2e7a9c4d1b0"
down_revision = "d1f3a5b7c902"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("reviewer_comment"):
        op.drop_table("reviewer_comment")
    if inspector.has_table("paper"):
        op.drop_table("paper")
    if inspector.has_table("task"):
        op.execute(sa.text("DELETE FROM task WHERE category = '论文'"))
    if inspector.has_table("presentation_skill"):
        op.execute(sa.text("DELETE FROM presentation_skill WHERE theme = 'paper'"))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("paper"):
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
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_paper_user_id", "paper", ["user_id"])
    if not inspector.has_table("reviewer_comment"):
        op.create_table(
            "reviewer_comment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("paper.id"), nullable=False),
            sa.Column("reviewer", sa.String(length=40), nullable=False),
            sa.Column("comment", sa.Text(), nullable=False),
            sa.Column("response", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_reviewer_comment_paper_id", "reviewer_comment", ["paper_id"])
