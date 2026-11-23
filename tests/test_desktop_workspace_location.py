from pathlib import Path
from uuid import uuid4

from app import db
from app.desktop import runtime
from app.desktop.bridge import DesktopBridge


def test_picked_workspace_is_used_on_next_launch(tmp_path, monkeypatch):
    first = tmp_path / "original"
    first.mkdir()
    destination = tmp_path / "演示数据 #02"
    destination.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    monkeypatch.setenv("RESEARCH_ASSISTANT_INSTANCE_DIR", str(first))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(first / 'research.db').as_posix()}")
    monkeypatch.setenv("ALLOW_PRIVATE_API_URLS", "false")
    monkeypatch.setenv("LOCAL_MODE", "true")
    monkeypatch.setenv("AUTO_CREATE_DB", "true")

    class Native:
        instance_dir = first

        def select_directory_dialog(self, payload):
            return [str(destination)]

    bridge = DesktopBridge(object(), Native(), {})

    def invoke(command, **payload):
        return bridge.invoke({"request_id": str(uuid4()), "command": command, "payload": payload})

    assert not invoke("workspace.directory.save", path=str(destination))["ok"]
    chosen = invoke("workspace.directory.choose")["data"]
    assert chosen == {"path": str(destination), "has_workspace": False}
    assert invoke("workspace.directory.save", path=chosen["path"])["ok"]
    assert not (destination / "research.db").exists()

    assert runtime.configure_environment() == destination
    application = runtime.initialize_application()
    with application.app_context():
        assert Path(db.engine.url.database) == destination / "research.db"
        assert Path(application.config["BACKUP_DIR"]) == destination / "backups"
        assert application.config["ALLOW_PRIVATE_API_URLS"] is True
        db.session.remove()
        db.engine.dispose()
    assert (destination / "research.db").exists()
    assert not (first / "research.db").exists()
    assert invoke("workspace.directory.choose")["data"]["has_workspace"] is True
