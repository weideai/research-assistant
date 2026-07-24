import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from flask_migrate import stamp, upgrade
from sqlalchemy import inspect, text


def _current_revision(db):
    tables = set(inspect(db.engine).get_table_names())
    if "alembic_version" not in tables:
        return None, tables
    revision = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    return revision, tables


def _head_revision(migration_dir):
    config = Config()
    config.set_main_option("script_location", str(migration_dir))
    return ScriptDirectory.from_config(config).get_current_head()


def _sqlite_database_path(db):
    if db.engine.url.get_backend_name() != "sqlite":
        return None
    database = db.engine.url.database
    if not database or database == ":memory:":
        return None
    return Path(database).expanduser().resolve()


def _backup_sqlite(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_db, sqlite3.connect(destination) as backup_db:
        source_db.backup(backup_db)
    try:
        shutil.copystat(source, destination)
    except OSError:
        pass


def run_migrations_with_backup(flask_app, db, migration_dir):
    migration_dir = Path(migration_dir).resolve()
    if not migration_dir.is_dir():
        return None

    with flask_app.app_context():
        old_revision, tables = _current_revision(db)
        target_revision = _head_revision(migration_dir)
        if old_revision == target_revision:
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        report_dir = Path(flask_app.instance_path) / "migration-reports"
        report_path = report_dir / f"migration-{timestamp}.json"
        database_path = _sqlite_database_path(db)
        backup_path = None
        report = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "database": str(database_path) if database_path else db.engine.url.get_backend_name(),
            "from_revision": old_revision or "unversioned",
            "to_revision": target_revision,
            "backup_path": "",
            "attachments_changed": False,
        }
        report_dir.mkdir(parents=True, exist_ok=True)

        try:
            if database_path and database_path.is_file():
                backup_path = Path(flask_app.instance_path) / "migration-backups" / (
                    f"research-before-{old_revision or 'stamp'}-{timestamp}.db"
                )
                db.session.remove()
                db.engine.dispose()
                _backup_sqlite(database_path, backup_path)
                report["backup_path"] = str(backup_path)

            if "alembic_version" in tables:
                upgrade(directory=str(migration_dir))
                action = "upgrade"
            else:
                stamp(directory=str(migration_dir), revision="head")
                action = "stamp"
            new_revision, _tables = _current_revision(db)
            report.update({
                "status": "success",
                "action": action,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "applied_revision": new_revision,
            })
        except Exception as exc:
            report.update({
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            })
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            recovery = f" Database backup: {backup_path}" if backup_path else ""
            raise RuntimeError(f"Database migration failed.{recovery} Report: {report_path}") from exc

        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
