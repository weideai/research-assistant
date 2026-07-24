from datetime import date, datetime
from importlib import import_module

import sqlalchemy as sa


migration = import_module(
    "migrations.versions.e6b9c1d4f208_repair_legacy_record_executions"
)
hierarchy_migration = import_module(
    "migrations.versions.c9a4e7d2b610_enforce_execution_record_hierarchy"
)


def test_history_execution_status_is_limited_to_execution_statuses():
    assert migration._batch_status("完成") == "已完成"
    assert migration._batch_status("进行中") == "进行中"
    assert migration._batch_status("未知旧状态") == "未开始"


def _legacy_tables(metadata):
    experiments = sa.Table(
        "experiment", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("batch_code", sa.String(80)),
        sa.Column("repeat_kind", sa.String(30)),
        sa.Column("repeat_number", sa.Integer),
        sa.Column("group_name", sa.String(80)),
        sa.Column("owner", sa.String(80)),
        sa.Column("status", sa.String(20)),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    batches = sa.Table(
        "experiment_batch", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("experiment_id", sa.Integer, nullable=False),
        sa.Column("batch_code", sa.String(80)),
        sa.Column("repeat_kind", sa.String(30)),
        sa.Column("repeat_number", sa.Integer),
        sa.Column("group_name", sa.String(80)),
        sa.Column("operator", sa.String(80)),
        sa.Column("status", sa.String(20)),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("summary", sa.Text),
        sa.Column("conclusion", sa.Text),
        sa.Column("requires_repeat", sa.Boolean),
        sa.Column("is_deleted", sa.Boolean),
        sa.Column("deleted_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    records = sa.Table(
        "experiment_record", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("experiment_id", sa.Integer, nullable=False),
        sa.Column("batch_id", sa.Integer),
        sa.Column("record_date", sa.Date),
        sa.Column("is_deleted", sa.Boolean, nullable=False),
    )
    return experiments, batches, records


def test_repair_groups_null_missing_and_cross_experiment_records_idempotently():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    experiments, batches, records = _legacy_tables(metadata)
    metadata.create_all(engine)
    now = datetime(2026, 7, 24, 9, 0)
    with engine.begin() as connection:
        connection.execute(experiments.insert(), [
            {
                "id": 1, "batch_code": "OLD", "repeat_kind": "生物学重复", "repeat_number": 3,
                "group_name": "处理组", "owner": "研究员", "status": "进行中",
                "start_date": date(2026, 7, 1), "end_date": date(2026, 7, 3),
                "created_at": now, "updated_at": now,
            },
            {
                "id": 2, "batch_code": "OTHER", "repeat_kind": "独立实验", "repeat_number": 1,
                "group_name": "对照组", "owner": "另一位研究员", "status": "完成",
                "start_date": date(2026, 7, 2), "end_date": date(2026, 7, 2),
                "created_at": now, "updated_at": now,
            },
        ])
        connection.execute(batches.insert(), [
            {
                "id": 10, "experiment_id": 1, "batch_code": "BATCH-01", "repeat_kind": "独立实验",
                "repeat_number": 1, "group_name": "", "operator": "", "status": "已完成",
                "summary": "", "conclusion": "", "requires_repeat": False, "is_deleted": False,
                "created_at": now, "updated_at": now,
            },
            {
                "id": 11, "experiment_id": 2, "batch_code": "CROSS-01", "repeat_kind": "独立实验",
                "repeat_number": 1, "group_name": "", "operator": "", "status": "已完成",
                "summary": "", "conclusion": "", "requires_repeat": False, "is_deleted": True,
                "created_at": now, "updated_at": now,
            },
            {
                "id": 12, "experiment_id": 1, "batch_code": "HISTORY-LEGACY", "repeat_kind": "独立实验",
                "repeat_number": 1, "group_name": "", "operator": "", "status": "已完成",
                "summary": "用户创建的同名执行", "conclusion": "", "requires_repeat": False,
                "is_deleted": False, "created_at": now, "updated_at": now,
            },
        ])
        connection.execute(records.insert(), [
            {"id": 101, "experiment_id": 1, "batch_id": None, "is_deleted": False},
            {"id": 102, "experiment_id": 1, "batch_id": 999, "is_deleted": False},
            {"id": 103, "experiment_id": 1, "batch_id": 11, "is_deleted": False},
            {"id": 104, "experiment_id": 1, "batch_id": 10, "is_deleted": False},
            {"id": 105, "experiment_id": 2, "batch_id": 11, "is_deleted": False},
            {"id": 106, "experiment_id": 1, "batch_id": None, "is_deleted": True},
        ])

        migration._repair_legacy_records(connection)
        first_batch_count = connection.scalar(sa.select(sa.func.count()).select_from(batches))
        assignments = dict(connection.execute(sa.select(records.c.id, records.c.batch_id)).all())
        repaired_batch_id = assignments[101]
        repaired = connection.execute(
            sa.select(batches).where(batches.c.id == repaired_batch_id)
        ).mappings().one()

        assert assignments[101] == assignments[102] == assignments[103]
        assert assignments[104] == 10
        assert assignments[105] != 11
        assert assignments[106] is None
        assert repaired["experiment_id"] == 1
        assert repaired["batch_code"] == "HISTORY-LEGACY-02"
        assert repaired["repeat_kind"] == "生物学重复"
        assert repaired["repeat_number"] == 3
        assert repaired["group_name"] == "处理组"
        assert repaired["operator"] == "研究员"
        assert repaired["summary"] == migration.HISTORY_SUMMARY
        completed_history = connection.execute(
            sa.select(batches).where(batches.c.id == assignments[105])
        ).mappings().one()
        assert completed_history["experiment_id"] == 2
        assert completed_history["status"] == "已完成"

        migration._repair_legacy_records(connection)
        assert connection.scalar(sa.select(sa.func.count()).select_from(batches)) == first_batch_count
        assert dict(connection.execute(sa.select(records.c.id, records.c.batch_id)).all()) == assignments


def test_hierarchy_normalizer_repairs_deleted_records_and_preserves_legacy_execution_defaults():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    experiments, batches, records = _legacy_tables(metadata)
    metadata.create_all(engine)
    now = datetime(2026, 7, 24, 10, 0)
    with engine.begin() as connection:
        connection.execute(experiments.insert(), [
            {
                "id": 1, "batch_code": "OLD-01", "repeat_kind": "生物学重复",
                "repeat_number": 2, "group_name": "处理组", "owner": "研究员",
                "status": "进行中", "created_at": now, "updated_at": now,
            },
            {
                "id": 2, "batch_code": "", "repeat_kind": "独立实验",
                "repeat_number": 1, "group_name": "", "owner": "研究员",
                "status": "完成", "created_at": now, "updated_at": now,
            },
            {
                "id": 3, "batch_code": "", "repeat_kind": "独立实验",
                "repeat_number": 1, "group_name": "", "owner": "研究员",
                "status": "未开始", "created_at": now, "updated_at": now,
            },
        ])
        connection.execute(batches.insert(), [
            {
                "id": 10, "experiment_id": 2, "batch_code": "DELETED-01",
                "repeat_kind": "独立实验", "repeat_number": 1, "group_name": "",
                "operator": "研究员", "status": "已完成", "summary": "",
                "conclusion": "", "requires_repeat": False, "is_deleted": True,
                "start_date": None, "end_date": None,
                "created_at": now, "updated_at": now,
            },
            {
                "id": 20, "experiment_id": 3, "batch_code": "ACTIVE-01",
                "repeat_kind": "独立实验", "repeat_number": 1, "group_name": "",
                "operator": "研究员", "status": "未开始",
                "start_date": date(2026, 7, 25), "end_date": date(2026, 7, 25),
                "summary": "", "conclusion": "", "requires_repeat": False,
                "is_deleted": False, "created_at": now, "updated_at": now,
            },
        ])
        connection.execute(records.insert(), [
            {"id": 101, "experiment_id": 1, "batch_id": None, "record_date": date(2026, 7, 20), "is_deleted": True},
            {"id": 102, "experiment_id": 2, "batch_id": 10, "record_date": date(2026, 7, 21), "is_deleted": False},
            {"id": 103, "experiment_id": 3, "batch_id": 20, "record_date": date(2026, 7, 24), "is_deleted": False},
        ])

        hierarchy_migration._normalize_data(connection)
        first_batch_count = connection.scalar(sa.select(sa.func.count()).select_from(batches))
        assignments = dict(connection.execute(sa.select(records.c.id, records.c.batch_id)).all())

        assert all(assignments.values())
        for record_id, batch_id in assignments.items():
            record_experiment_id = connection.scalar(
                sa.select(records.c.experiment_id).where(records.c.id == record_id)
            )
            assigned_batch = connection.execute(
                sa.select(batches).where(batches.c.id == batch_id)
            ).mappings().one()
            assert assigned_batch["experiment_id"] == record_experiment_id
            assert assigned_batch["is_deleted"] is False

        preserved = connection.execute(
            sa.select(batches).where(
                batches.c.experiment_id == 1,
                batches.c.summary == "",
            )
        ).mappings().one()
        assert preserved["batch_code"] == "OLD-01"
        assert preserved["repeat_kind"] == "生物学重复"
        assert preserved["repeat_number"] == 2
        assert preserved["group_name"] == "处理组"

        aligned = connection.execute(
            sa.select(batches).where(batches.c.id == 20)
        ).mappings().one()
        assert aligned["status"] == "进行中"
        assert aligned["start_date"] == date(2026, 7, 24)
        assert aligned["end_date"] == date(2026, 7, 25)

        hierarchy_migration._normalize_data(connection)
        assert connection.scalar(sa.select(sa.func.count()).select_from(batches)) == first_batch_count
        assert dict(connection.execute(sa.select(records.c.id, records.c.batch_id)).all()) == assignments
