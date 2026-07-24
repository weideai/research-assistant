"""Make experiment executions the single owner of process records.

Revision ID: c9a4e7d2b610
Revises: 7c3d9a1e5f42
"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "c9a4e7d2b610"
down_revision = "7c3d9a1e5f42"
branch_labels = None
depends_on = None


HISTORY_SUMMARY = "由数据迁移自动创建，用于归档缺少有效实验执行归属的历史过程记录。"
HISTORY_CODE = "HISTORY-LEGACY"
BATCH_STATUSES = {"未开始", "进行中", "已完成", "暂停"}


def _batch_status(experiment_status):
    status = "已完成" if experiment_status == "完成" else experiment_status
    return status if status in BATCH_STATUSES else "未开始"


def _next_code(connection, batches, experiment_id, preferred):
    used = {
        value for value in connection.execute(
            sa.select(batches.c.batch_code).where(batches.c.experiment_id == experiment_id)
        ).scalars() if value
    }
    if preferred not in used:
        return preferred
    sequence = 2
    while f"{preferred}-{sequence:02d}" in used:
        sequence += 1
    return f"{preferred}-{sequence:02d}"


def _create_batch(connection, batches, experiment, now, *, history=False):
    preferred_code = HISTORY_CODE if history else (experiment.get("batch_code") or "BATCH-01")
    result = connection.execute(batches.insert().values(
        experiment_id=experiment["id"],
        batch_code=_next_code(connection, batches, experiment["id"], preferred_code),
        repeat_kind=experiment.get("repeat_kind") or "独立实验",
        repeat_number=experiment.get("repeat_number") or 1,
        group_name=experiment.get("group_name") or ("历史数据" if history else ""),
        operator=experiment.get("owner") or "",
        status=_batch_status(experiment.get("status")),
        start_date=experiment.get("start_date"),
        end_date=experiment.get("end_date"),
        summary=HISTORY_SUMMARY if history else "",
        conclusion="",
        requires_repeat=False,
        is_deleted=False,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    ))
    return result.inserted_primary_key[0]


def _history_batch_id(connection, experiments, batches, experiment_id, now):
    existing = connection.execute(
        sa.select(batches.c.id).where(
            batches.c.experiment_id == experiment_id,
            batches.c.summary == HISTORY_SUMMARY,
            batches.c.is_deleted.is_(False),
        ).order_by(batches.c.id)
    ).scalar()
    if existing is not None:
        return existing
    experiment = connection.execute(
        sa.select(experiments).where(experiments.c.id == experiment_id)
    ).mappings().first()
    return _create_batch(connection, batches, experiment, now, history=True) if experiment else None


def _preserve_legacy_execution_defaults(connection, experiments, batches, now):
    rows = connection.execute(sa.select(experiments)).mappings().all()
    for experiment in rows:
        has_execution = connection.execute(
            sa.select(batches.c.id).where(
                batches.c.experiment_id == experiment["id"],
                batches.c.is_deleted.is_(False),
            ).limit(1)
        ).scalar()
        has_legacy_values = bool(
            experiment.get("batch_code") or experiment.get("group_name")
            or (experiment.get("repeat_kind") not in {None, "", "独立实验"})
            or (experiment.get("repeat_number") not in {None, 1})
        )
        if has_execution is None and has_legacy_values:
            _create_batch(connection, batches, experiment, now)


def _repair_all_record_ownership(connection, experiments, batches, records, now):
    joined = records.outerjoin(batches, records.c.batch_id == batches.c.id)
    invalid_rows = connection.execute(
        sa.select(records.c.id, records.c.experiment_id).select_from(joined).where(
            sa.or_(
                records.c.batch_id.is_(None),
                batches.c.id.is_(None),
                batches.c.experiment_id != records.c.experiment_id,
                batches.c.is_deleted.is_(True),
            )
        )
    ).all()
    history_by_experiment = {}
    for record_id, experiment_id in invalid_rows:
        if experiment_id not in history_by_experiment:
            history_by_experiment[experiment_id] = _history_batch_id(
                connection, experiments, batches, experiment_id, now
            )
        batch_id = history_by_experiment[experiment_id]
        if batch_id is not None:
            connection.execute(
                records.update().where(records.c.id == record_id).values(batch_id=batch_id)
            )
    remaining = connection.execute(
        sa.select(records.c.id).where(records.c.batch_id.is_(None)).limit(8)
    ).scalars().all()
    if remaining:
        identifiers = ", ".join(str(record_id) for record_id in remaining)
        raise RuntimeError(f"Cannot assign experiment execution for records: {identifiers}")


def _align_execution_timelines(connection, batches, records):
    timelines = connection.execute(
        sa.select(
            records.c.batch_id,
            sa.func.min(records.c.record_date),
            sa.func.max(records.c.record_date),
        ).group_by(records.c.batch_id)
    ).all()
    for batch_id, first_record_date, last_record_date in timelines:
        if batch_id is None:
            continue
        batch = connection.execute(
            sa.select(batches).where(batches.c.id == batch_id)
        ).mappings().first()
        if not batch:
            continue
        values = {}
        if batch.get("status") == "未开始":
            values["status"] = "进行中"
        if first_record_date and (
                batch.get("start_date") is None or batch["start_date"] > first_record_date):
            values["start_date"] = first_record_date
        if last_record_date and batch.get("end_date") and batch["end_date"] < last_record_date:
            values["end_date"] = last_record_date
        if values:
            connection.execute(
                batches.update().where(batches.c.id == batch_id).values(**values)
            )


def _normalize_data(connection):
    metadata = sa.MetaData()
    metadata.reflect(
        bind=connection,
        only=["experiment", "experiment_batch", "experiment_record"],
    )
    experiments = metadata.tables["experiment"]
    batches = metadata.tables["experiment_batch"]
    records = metadata.tables["experiment_record"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    _preserve_legacy_execution_defaults(connection, experiments, batches, now)
    _repair_all_record_ownership(connection, experiments, batches, records, now)
    _align_execution_timelines(connection, batches, records)


def upgrade():
    _normalize_data(op.get_bind())
    with op.batch_alter_table("experiment_record") as batch:
        batch.alter_column("batch_id", existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table("experiment") as batch:
        batch.drop_column("group_name")
        batch.drop_column("repeat_number")
        batch.drop_column("repeat_kind")
        batch.drop_column("batch_code")


def downgrade():
    with op.batch_alter_table("experiment") as batch:
        batch.add_column(sa.Column("batch_code", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("repeat_kind", sa.String(length=30), nullable=False, server_default="独立实验"))
        batch.add_column(sa.Column("repeat_number", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("group_name", sa.String(length=80), nullable=True))
    with op.batch_alter_table("experiment_record") as batch:
        batch.alter_column("batch_id", existing_type=sa.Integer(), nullable=True)
