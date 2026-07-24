from pathlib import Path
from urllib.error import URLError

from app import create_app, db
from app.migration_service import run_migrations_with_backup
from app.update_service import check_for_update, is_newer_version


def test_semantic_version_comparison():
    assert is_newer_version("v2.1.0", "2.0.0") is True
    assert is_newer_version("2.0.0", "2.0.0") is False
    assert is_newer_version("1.9.9", "2.0.0") is False
    assert is_newer_version("not-a-version", "2.0.0") is False


def test_update_check_uses_cache_and_falls_back_offline(tmp_path, monkeypatch):
    calls = []

    def latest(_repository, timeout=4):
        calls.append(timeout)
        return {
            "latest_version": "2.1.0",
            "release_url": "https://github.com/weideai/research-assistant/releases/tag/v2.1.0",
            "release_name": "V2.1",
            "published_at": "2026-07-23T00:00:00Z",
        }

    monkeypatch.setattr("app.update_service._fetch_latest_release", latest)
    fresh = check_for_update(tmp_path)
    cached = check_for_update(tmp_path)
    assert fresh["update_available"] is True
    assert fresh["cached"] is False
    assert cached["cached"] is True
    assert len(calls) == 1

    monkeypatch.setattr(
        "app.update_service._fetch_latest_release",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("offline")),
    )
    stale = check_for_update(tmp_path, force=True)
    assert stale["update_available"] is True
    assert stale["cached"] is True
    assert stale["stale"] is True


def test_update_route_is_authenticated_and_returns_release(client, auth, monkeypatch):
    assert client.get("/updates/check").status_code == 302
    auth.register()
    monkeypatch.setattr("app.update_service.check_for_update", lambda *_args, **_kwargs: {
        "status": "ok",
        "current_version": "2.0.0",
        "latest_version": "2.1.0",
        "release_url": "https://example.test/release",
        "update_available": True,
    })
    response = client.get("/updates/check")
    assert response.status_code == 200
    assert response.get_json()["update_available"] is True
    assert response.get_json()["enabled"] is True


def test_first_desktop_migration_creates_backup_and_report(tmp_path, monkeypatch):
    instance_dir = tmp_path / "instance"
    database_path = instance_dir / "research.db"
    monkeypatch.setenv("RESEARCH_ASSISTANT_INSTANCE_DIR", str(instance_dir))
    app = create_app({
        "TESTING": True,
        "AUTO_CREATE_DB": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "migration-test-secret",
        "CREDENTIAL_ENCRYPTION_KEY": "migration-test-credential",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
    })
    migration_dir = Path(__file__).resolve().parents[1] / "migrations"
    report = run_migrations_with_backup(app, db, migration_dir)

    assert report["status"] == "success"
    assert report["action"] == "stamp"
    assert report["attachments_changed"] is False
    assert Path(report["backup_path"]).is_file()
    assert list((instance_dir / "migration-reports").glob("migration-*.json"))

    with app.app_context():
        db.session.remove()
        db.engine.dispose()
