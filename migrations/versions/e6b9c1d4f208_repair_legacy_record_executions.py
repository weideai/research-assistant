"""Repair missing or invalid experiment record execution ownership.

Revision ID: e6b9c1d4f208
Revises: a4d8f6c2e701
"""

from collections import defaultdict
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "e6b9c1d4f208"
down_revision = "a4d8f6c2e701"
branch_labels = None
depends_on = None


HISTORY_SUMMARY = "由数据迁移自动创建，用于归档缺少有效实验执行归属的历史过程记录。"
HISTORY_CODE = "HISTORY-LEGACY"
BATCH_STATUSES = {"未开始", "进行中", "已完成", "暂停"}


def _batch_status(experiment_status):
    status = "已完成" if experiment_status == "完成" else experiment_status
    return status if status in BATCH_STATUSES else "未开始"


def _next_history_code(connection, batches, experiment_id):
    used_codes = {
        value
        for value in connection.execute(
            sa.select(batches.c.batch_code).where(batches.c.experiment_id == experiment_id)
        ).scalars()
        if value
    }
    if HISTORY_CODE not in used_codes:
        return HISTORY_CODE
    sequence = 2
    while f"{HISTORY_CODE}-{sequence:02d}" in used_codes:
        sequence += 1
    return f"{HISTORY_CODE}-{sequence:02d}"


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
    if experiment is None:
        return None
    result = connection.execute(batches.insert().values(
        experiment_id=experiment_id,
        batch_code=_next_history_code(connection, batches, experiment_id),
        repeat_kind=experiment.get("repeat_kind") or "独立实验",
        repeat_number=experiment.get("repeat_number") or 1,
        group_name=experiment.get("group_name") or "历史数据",
        operator=experiment.get("owner") or "",
        status=_batch_status(experiment.get("status")),
        start_date=experiment.get("start_date"),
        end_date=experiment.get("end_date"),
        summary=HISTORY_SUMMARY,
        conclusion="",
        requires_repeat=False,
        is_deleted=False,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    ))
    return result.inserted_primary_key[0]


def _repair_legacy_records(connection):
    metadata = sa.MetaData()
    metadata.reflect(
        bind=connection,
        only=["experiment", "experiment_batch", "experiment_record"],
    )
    experiments = metadata.tables["experiment"]
    batches = metadata.tables["experiment_batch"]
    records = metadata.tables["experiment_record"]
    joined = records.outerjoin(batches, records.c.batch_id == batches.c.id)
    invalid_rows = connection.execute(
        sa.select(records.c.id, records.c.experiment_id).select_from(joined).where(
            records.c.is_deleted.is_(False),
            sa.or_(
                records.c.batch_id.is_(None),
                batches.c.id.is_(None),
                batches.c.experiment_id != records.c.experiment_id,
                batches.c.is_deleted.is_(True),
            ),
        )
    ).all()
    record_ids_by_experiment = defaultdict(list)
    for record_id, experiment_id in invalid_rows:
        record_ids_by_experiment[experiment_id].append(record_id)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for experiment_id, record_ids in record_ids_by_experiment.items():
        batch_id = _history_batch_id(connection, experiments, batches, experiment_id, now)
        if batch_id is None:
            continue
        connection.execute(
            records.update().where(records.c.id.in_(record_ids)).values(batch_id=batch_id)
        )


def upgrade():
    _repair_legacy_records(op.get_bind())


def downgrade():
    # Reversing this data repair would recreate invalid ownership and risk data loss.
    pass
