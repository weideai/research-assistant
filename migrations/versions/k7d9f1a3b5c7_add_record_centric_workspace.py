"""Add the record-centric workspace and complete lab records.

Revision ID: k7d9f1a3b5c7
Revises: j6c8e2f4a5b3
"""

from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa


revision = "k7d9f1a3b5c7"
down_revision = "j6c8e2f4a5b3"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def upgrade():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bind = op.get_bind()
    legacy_user_id = bind.execute(sa.text("SELECT id FROM user ORDER BY id LIMIT 1")).scalar()

    op.create_table(
        "workspace",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_uuid", sa.String(length=36), nullable=False, unique=True),
        sa.Column("legacy_user_id", sa.Integer(), sa.ForeignKey("user.id"), unique=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("schema_generation", sa.String(length=40), nullable=False),
        sa.Column("migration_state", sa.String(length=30), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("id = 1", name="ck_workspace_singleton"),
    )
    op.bulk_insert(
        sa.table(
            "workspace",
            sa.column("id", sa.Integer()),
            sa.column("workspace_uuid", sa.String()),
            sa.column("legacy_user_id", sa.Integer()),
            sa.column("name", sa.String()),
            sa.column("timezone", sa.String()),
            sa.column("schema_generation", sa.String()),
            sa.column("migration_state", sa.String()),
            sa.column("created_at", sa.DateTime()),
            sa.column("updated_at", sa.DateTime()),
        ),
        [{
            "id": 1,
            "workspace_uuid": str(uuid.uuid4()),
            "legacy_user_id": legacy_user_id,
            "name": "R/LAB 工作区",
            "timezone": "Asia/Shanghai",
            "schema_generation": "record-centric-v1",
            "migration_state": "active",
            "created_at": now,
            "updated_at": now,
        }],
    )

    op.add_column("research_project", sa.Column("workspace_id", sa.Integer(), nullable=True))
    op.add_column("research_project", sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"))
    op.execute(sa.text("UPDATE research_project SET workspace_id = 1 WHERE workspace_id IS NULL"))
    with op.batch_alter_table("research_project") as batch:
        batch.alter_column("workspace_id", nullable=False)
        batch.create_foreign_key("fk_research_project_workspace", "workspace", ["workspace_id"], ["id"])
        batch.create_index("ix_research_project_workspace_id", ["workspace_id"])

    op.add_column("executor", sa.Column("workspace_id", sa.Integer(), nullable=True))
    op.add_column("executor", sa.Column("normalized_name", sa.String(length=160), nullable=False, server_default=""))
    op.execute(sa.text("UPDATE executor SET workspace_id = 1 WHERE workspace_id IS NULL"))
    rows = bind.execute(sa.text("SELECT id, name FROM executor ORDER BY id")).mappings().all()
    used = set()
    for row in rows:
        base = " ".join((row["name"] or "").strip().casefold().split()) or f"executor-{row['id']}"
        normalized = base if base not in used else f"{base}#{row['id']}"
        used.add(normalized)
        bind.execute(
            sa.text("UPDATE executor SET normalized_name = :name WHERE id = :id"),
            {"name": normalized, "id": row["id"]},
        )
    with op.batch_alter_table("executor") as batch:
        batch.alter_column("workspace_id", nullable=False)
        batch.create_foreign_key("fk_executor_workspace", "workspace", ["workspace_id"], ["id"])
        batch.create_index("ix_executor_workspace_id", ["workspace_id"])
        batch.create_unique_constraint(
            "uq_executor_workspace_normalized_name", ["workspace_id", "normalized_name"]
        )

    op.create_table(
        "lab_record",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_project.id"), nullable=False),
        sa.Column("record_code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("experiment_date", sa.Date()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("executor_id", sa.Integer(), sa.ForeignKey("executor.id")),
        sa.Column("executor_snapshot", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("location", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("objective", sa.Text(), nullable=False, server_default=""),
        sa.Column("background", sa.Text(), nullable=False, server_default=""),
        sa.Column("hypothesis", sa.Text(), nullable=False, server_default=""),
        sa.Column("design", sa.Text(), nullable=False, server_default=""),
        sa.Column("materials_conditions", sa.Text(), nullable=False, server_default=""),
        sa.Column("expected_result", sa.Text(), nullable=False, server_default=""),
        sa.Column("actual_process_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("actual_result", sa.Text(), nullable=False, server_default=""),
        sa.Column("analysis", sa.Text(), nullable=False, server_default=""),
        sa.Column("conclusion", sa.Text(), nullable=False, server_default=""),
        sa.Column("next_steps", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_finalized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("finalized_at", sa.DateTime()),
        sa.Column("source_kind", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime()),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "record_code", name="uq_lab_record_workspace_code"),
        sa.CheckConstraint("status IN ('draft','in_progress','awaiting_analysis','completed','archived')", name="ck_lab_record_status"),
        sa.CheckConstraint("source_kind IN ('new','migration','import')", name="ck_lab_record_source_kind"),
        sa.CheckConstraint("completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at", name="ck_lab_record_time_range"),
        sa.CheckConstraint("is_finalized = 0 OR finalized_at IS NOT NULL", name="ck_lab_record_finalized_at"),
    )
    op.create_index("ix_lab_record_workspace_id", "lab_record", ["workspace_id"])
    op.create_index("ix_lab_record_project_id", "lab_record", ["project_id"])
    op.create_index("ix_lab_record_status", "lab_record", ["status"])
    op.create_index("ix_lab_record_experiment_date", "lab_record", ["experiment_date"])
    op.create_index("ix_lab_record_executor_id", "lab_record", ["executor_id"])
    op.create_index("ix_lab_record_is_deleted", "lab_record", ["is_deleted"])

    op.create_table(
        "lab_record_step",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("lab_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("instruction", sa.Text(), nullable=False, server_default=""),
        sa.Column("planned_duration_minutes", sa.Integer()),
        sa.Column("checkpoint", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk", sa.Text(), nullable=False, server_default=""),
        sa.Column("planned_executor_id", sa.Integer(), sa.ForeignKey("executor.id")),
        sa.Column("executor_snapshot", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("planned_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("actual_deviation", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_kind", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("source_ai_message_id", sa.Integer(), sa.ForeignKey("ai_message.id")),
        *_timestamps(),
        sa.UniqueConstraint("record_id", "position", name="uq_lab_record_step_position"),
        sa.CheckConstraint("position > 0", name="ck_lab_record_step_position"),
        sa.CheckConstraint("planned_duration_minutes IS NULL OR planned_duration_minutes >= 0", name="ck_lab_record_step_duration"),
    )
    op.create_index("ix_lab_record_step_record_id", "lab_record_step", ["record_id"])

    op.create_table(
        "lab_record_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("lab_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False, server_default="note"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("executor_id", sa.Integer(), sa.ForeignKey("executor.id")),
        sa.Column("executor_snapshot", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("source_kind", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("source_legacy_record_id", sa.Integer(), unique=True),
        *_timestamps(),
    )
    op.create_index("ix_lab_record_event_record_id", "lab_record_event", ["record_id"])
    op.create_index("ix_lab_record_event_occurred_at", "lab_record_event", ["occurred_at"])

    op.create_table(
        "lab_record_parameter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("lab_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("lab_record_event.id", ondelete="SET NULL")),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("phase", sa.String(length=20), nullable=False, server_default="planned"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("value_text", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("unit", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("value_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("confirmed_at", sa.DateTime()),
        sa.Column("source_ai_message_id", sa.Integer(), sa.ForeignKey("ai_message.id")),
        *_timestamps(),
        sa.CheckConstraint("phase <> 'actual' OR value_origin <> 'ai_organized' OR confirmed_at IS NOT NULL", name="ck_lab_record_parameter_ai_actual_confirmed"),
    )
    op.create_index("ix_lab_record_parameter_record_id", "lab_record_parameter", ["record_id"])

    op.create_table(
        "lab_record_material",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("lab_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("kind", sa.String(length=30), nullable=False, server_default="material"),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("identifier", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("planned_amount", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("actual_amount", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("unit", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("legacy_sample_id", sa.Integer(), sa.ForeignKey("sample.id")),
        sa.Column("value_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("confirmed_at", sa.DateTime()),
        *_timestamps(),
        sa.CheckConstraint("value_origin <> 'ai_organized' OR actual_amount = '' OR confirmed_at IS NOT NULL", name="ck_lab_record_material_ai_actual_confirmed"),
    )
    op.create_index("ix_lab_record_material_record_id", "lab_record_material", ["record_id"])

    op.create_table(
        "lab_record_revision",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("lab_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(length=30), nullable=False, server_default="record"),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("after_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("diff_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("actor_kind", sa.String(length=30), nullable=False, server_default="local_user"),
        sa.Column("executor_id", sa.Integer(), sa.ForeignKey("executor.id")),
        sa.Column("source_ai_change_set_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_lab_record_revision_record_id", "lab_record_revision", ["record_id"])


def downgrade():
    for table in (
        "lab_record_revision",
        "lab_record_material",
        "lab_record_parameter",
        "lab_record_event",
        "lab_record_step",
        "lab_record",
    ):
        op.drop_table(table)
    with op.batch_alter_table("executor") as batch:
        batch.drop_constraint("uq_executor_workspace_normalized_name", type_="unique")
        batch.drop_constraint("fk_executor_workspace", type_="foreignkey")
        batch.drop_index("ix_executor_workspace_id")
        batch.drop_column("normalized_name")
        batch.drop_column("workspace_id")
    with op.batch_alter_table("research_project") as batch:
        batch.drop_constraint("fk_research_project_workspace", type_="foreignkey")
        batch.drop_index("ix_research_project_workspace_id")
        batch.drop_column("row_version")
        batch.drop_column("workspace_id")
    op.drop_table("workspace")
