"""Normalize legacy Chinese status values used by desktop entities.

Revision ID: q3d5f7b9c1e4
Revises: p2c4e6a8b0d3
"""

from alembic import op


revision = "q3d5f7b9c1e4"
down_revision = "p2c4e6a8b0d3"
branch_labels = None
depends_on = None


def upgrade():
    task_status = {"待办": "todo", "进行中": "doing", "受阻": "blocked", "完成": "done", "已完成": "done", "已取消": "cancelled"}
    task_priority = {"低": "low", "中": "medium", "高": "high"}
    task_category = {"实验": "research", "学习": "study", "会议": "meeting", "行政": "administrative"}
    weekly_status = {"待反馈": "draft", "草稿": "draft", "修改中": "submitted", "已确认": "reviewed", "已提交": "submitted", "已批注": "reviewed", "已归档": "archived"}
    for old, new in task_status.items():
        op.execute(f"UPDATE task SET status = '{new}' WHERE status = '{old}'")
    for old, new in task_priority.items():
        op.execute(f"UPDATE task SET priority = '{new}' WHERE priority = '{old}'")
    for old, new in task_category.items():
        op.execute(f"UPDATE task SET category = '{new}' WHERE category = '{old}'")
    for old, new in weekly_status.items():
        op.execute(f"UPDATE weekly_report SET status = '{new}' WHERE status = '{old}'")


def downgrade():
    # Canonical values remain valid for older application versions; a lossy reverse migration is unsafe.
    pass
