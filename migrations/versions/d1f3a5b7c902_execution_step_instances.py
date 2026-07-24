"""Move step completion state from plans to execution snapshots.

Revision ID: d1f3a5b7c902
Revises: d2f8a1c7b604
"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "d1f3a5b7c902"
down_revision = "d2f8a1c7b604"
branch_labels = None
depends_on = None


def _clone_existing_execution_steps(connection):
    metadata = sa.MetaData()
    metadata.reflect(
        bind=connection,
        only=["experiment_step", "experiment_batch", "batch_step"],
    )
    plan_steps = metadata.tables["experiment_step"]
    batches = metadata.tables["experiment_batch"]
    execution_steps = metadata.tables["batch_step"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    rows = connection.execute(
        sa.select(
            batches.c.id.label("batch_id"),
            plan_steps.c.id.label("source_step_id"),
            plan_steps.c.position,
            plan_steps.c.title,
            plan_steps.c.description,
            plan_steps.c.operator,
            plan_steps.c.planned_date,
            plan_steps.c.completed_date,
            plan_steps.c.is_done,
            plan_steps.c.created_at,
        ).select_from(
            batches.join(
                plan_steps,
                batches.c.experiment_id == plan_steps.c.experiment_id,
            )
        ).order_by(batches.c.id, plan_steps.c.position, plan_steps.c.id)
    ).mappings().all()
    for row in rows:
        connection.execute(execution_steps.insert().values(
            batch_id=row["batch_id"],
            source_step_id=row["source_step_id"],
            position=row["position"],
            title=row["title"],
            description=row["description"] or "",
            operator=row["operator"] or "",
            planned_date=row["planned_date"],
            completed_date=row["completed_date"],
            is_done=bool(row["is_done"]),
            created_at=row["created_at"] or now,
            updated_at=now,
        ))


def _restore_latest_completion_state(connection):
    metadata = sa.MetaData()
    metadata.reflect(
        bind=connection,
        only=["experiment_step", "experiment_batch", "batch_step"],
    )
    plan_steps = metadata.tables["experiment_step"]
    batches = metadata.tables["experiment_batch"]
    execution_steps = metadata.tables["batch_step"]

    for source_step_id in connection.execute(
        sa.select(plan_steps.c.id).order_by(plan_steps.c.id)
    ).scalars():
        latest = connection.execute(
            sa.select(execution_steps.c.is_done, execution_steps.c.completed_date)
            .select_from(
                execution_steps.join(batches, execution_steps.c.batch_id == batches.c.id)
            )
            .where(execution_steps.c.source_step_id == source_step_id)
            .order_by(batches.c.created_at.desc(), batches.c.id.desc())
            .limit(1)
        ).mappings().first()
        if latest:
            connection.execute(
                plan_steps.update().where(plan_steps.c.id == source_step_id).values(
                    is_done=bool(latest["is_done"]),
                    completed_date=latest["completed_date"],
                )
            )


def upgrade():
    op.create_table(
        "batch_step",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("experiment_batch.id"), nullable=False),
        sa.Column(
            "source_step_id", sa.Integer(),
            sa.ForeignKey("experiment_step.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("operator", sa.String(length=80), nullable=True),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("batch_id", "source_step_id", name="uq_batch_step_source"),
    )
    op.create_index("ix_batch_step_batch_id", "batch_step", ["batch_id"])
    op.create_index("ix_batch_step_source_step_id", "batch_step", ["source_step_id"])
    _clone_existing_execution_steps(op.get_bind())
    with op.batch_alter_table("experiment_step") as batch:
        batch.drop_column("completed_date")
        batch.drop_column("is_done")


def downgrade():
    with op.batch_alter_table("experiment_step") as batch:
        batch.add_column(sa.Column(
            "is_done", sa.Boolean(), nullable=False, server_default=sa.false()
        ))
        batch.add_column(sa.Column("completed_date", sa.Date(), nullable=True))
    _restore_latest_completion_state(op.get_bind())
    op.drop_index("ix_batch_step_source_step_id", table_name="batch_step")
    op.drop_index("ix_batch_step_batch_id", table_name="batch_step")
    op.drop_table("batch_step")
