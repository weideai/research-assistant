from datetime import date, datetime
from pathlib import Path

import sqlalchemy as sa
from flask_migrate import downgrade, upgrade

from app import create_app, db


def test_execution_step_migration_backfills_and_downgrades_from_latest_snapshot(tmp_path):
    database_path = tmp_path / "execution-step-migration.db"
    app = create_app({
        "TESTING": True,
        "AUTO_CREATE_DB": False,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
        "SECRET_KEY": "migration-secret",
        "CREDENTIAL_ENCRYPTION_KEY": "migration-credential",
    })
    migration_dir = Path(__file__).resolve().parents[1] / "migrations"
    with app.app_context():
        upgrade(directory=str(migration_dir), revision="c9a4e7d2b610")
        metadata = sa.MetaData()
        metadata.reflect(bind=db.engine)
        users = metadata.tables["user"]
        experiments = metadata.tables["experiment"]
        batches = metadata.tables["experiment_batch"]
        plan_steps = metadata.tables["experiment_step"]
        first_created = datetime(2026, 7, 20, 8, 0)
        second_created = datetime(2026, 7, 21, 8, 0)
        with db.engine.begin() as connection:
            user_id = connection.execute(users.insert().values(
                name="迁移用户", email="migration@example.test", password_hash="hash",
                created_at=first_created, updated_at=first_created,
            )).inserted_primary_key[0]
            experiment_id = connection.execute(experiments.insert().values(
                user_id=user_id, title="旧步骤实验", status="进行中",
                created_at=first_created, updated_at=first_created,
            )).inserted_primary_key[0]
            step_id = connection.execute(plan_steps.insert().values(
                experiment_id=experiment_id, position=1, title="旧计划步骤",
                is_done=True, completed_date=date(2026, 7, 20),
                created_at=first_created, updated_at=first_created,
            )).inserted_primary_key[0]
            first_batch_id = connection.execute(batches.insert().values(
                experiment_id=experiment_id, batch_code="RUN-OLD-01",
                repeat_number=1, status="已完成", requires_repeat=False,
                is_deleted=False, created_at=first_created, updated_at=first_created,
            )).inserted_primary_key[0]
            second_batch_id = connection.execute(batches.insert().values(
                experiment_id=experiment_id, batch_code="RUN-OLD-02",
                repeat_number=2, status="进行中", requires_repeat=False,
                is_deleted=False, created_at=second_created, updated_at=second_created,
            )).inserted_primary_key[0]

        upgrade(directory=str(migration_dir), revision="head")
        inspector = sa.inspect(db.engine)
        assert {column["name"] for column in inspector.get_columns("experiment_step")}.isdisjoint({
            "is_done", "completed_date",
        })
        with db.engine.begin() as connection:
            execution_steps = sa.Table("batch_step", sa.MetaData(), autoload_with=connection)
            rows = connection.execute(
                sa.select(execution_steps).order_by(execution_steps.c.batch_id)
            ).mappings().all()
            assert [row["batch_id"] for row in rows] == [first_batch_id, second_batch_id]
            assert all(row["source_step_id"] == step_id for row in rows)
            assert all(row["is_done"] is True for row in rows)
            assert all(row["completed_date"] == date(2026, 7, 20) for row in rows)
            connection.execute(
                execution_steps.update()
                .where(execution_steps.c.batch_id == second_batch_id)
                .values(is_done=False, completed_date=None)
            )

        downgrade(directory=str(migration_dir), revision="d2f8a1c7b604")
        with db.engine.connect() as connection:
            legacy_steps = sa.Table("experiment_step", sa.MetaData(), autoload_with=connection)
            restored = connection.execute(
                sa.select(legacy_steps).where(legacy_steps.c.id == step_id)
            ).mappings().one()
            assert restored["is_done"] is False
            assert restored["completed_date"] is None
        db.session.remove()
        db.engine.dispose()
