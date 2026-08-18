from pathlib import Path
import time
import uuid

from app.desktop.bridge import DesktopBridge
from app.desktop.native import NativeCapabilities, NativeCapabilityError
from app.desktop.protocol import PROTOCOL_VERSION


class FakeService:
    def dashboard(self):
        return {"projects": [], "recent_records": [], "counts": {}}

    def list_projects(self, payload):
        return []

    def create_project(self, payload):
        return payload

    def list_records(self, payload):
        return []

    def get_record(self, payload):
        return payload

    def create_record(self, payload):
        return payload

    def update_record(self, payload, expected_row_version):
        return {**payload, "row_version": expected_row_version + 1}

    def import_weekly_file(self, payload, expected_row_version):
        return {**payload, "row_version": (expected_row_version or 0) + 1}

    def weekly_file_path(self, payload):
        return {"path": "C:\\weekly\\report.pdf", "file_id": payload.get("file_id", 1)}

    def weekly_directory_path(self, payload):
        return {"path": "C:\\weekly"}

    def export_weekly_file(self, payload):
        return {"path": payload["path"], "size_bytes": 10}

    def ai_history(self, payload):
        return {"items": [], "pagination": {"page": 1, "pages": 1, "per_page": 5, "total": 0}}

    def zotero_sync(self, payload):
        cancel_event = payload.get("_cancel_event")
        if cancel_event and cancel_event.is_set():
            return {"cancelled": True}
        return {"added": 1, "updated": 0, "attachments": 0}

    def zotero_status(self, payload):
        return {"sync_state": "completed", "sync_progress": 100, "sync_stage": "同步完成"}

    def zotero_collections_sync(self, payload):
        return {"collections": 2, "memberships": 3}


class FakeNative:
    def open_file_dialog(self, payload):
        return []

    def select_directory_dialog(self, payload):
        return []

    def save_file_dialog(self, payload):
        return []

    def open_trusted_path(self, payload):
        return {"opened": True}

    def open_external_url(self, payload):
        return {"opened": True}

    def window_command(self, command):
        return {"accepted": True, "command": command}

    def assert_trusted_path(self, path, must_exist=False):
        return path

    def open_authorized_path(self, path):
        return {"opened": True, "path": str(path)}


def request(command, payload=None, **extra):
    return {
        "request_id": str(uuid.uuid4()),
        "command": command,
        "payload": payload or {},
        **extra,
    }


def test_bridge_exposes_one_allowlisted_dispatch_contract():
    bridge = DesktopBridge(FakeService(), FakeNative(), {"http_listener": False})

    response = bridge.invoke(request("system.ping"))

    assert response == {
        "ok": True,
        "data": {"status": "ok"},
        "error": None,
        "field_errors": {},
        "request_id": response["request_id"],
    }
    assert set(name for name in dir(bridge) if not name.startswith("_")) == {"invoke"}


def test_app_info_publishes_versioned_capabilities_and_deprecations():
    bridge = DesktopBridge(FakeService(), FakeNative(), {"http_listener": False})

    response = bridge.invoke(request("system.app_info"))

    assert response["ok"] is True
    info = response["data"]
    assert info["protocol_version"] == PROTOCOL_VERSION == 1
    assert info["protocol_compatibility"] == {"minimum": 1, "maximum": 1}
    assert info["capabilities"] == ["ai.changesets", "records.batch_export", "zotero.jobs"]
    assert "record.export.batch" in info["commands"]
    assert "record.export_batch" in info["commands"]
    assert info["deprecated_commands"]["record.export_batch"] == {
        "replacement": "record.export.batch",
        "remove_in_protocol": 2,
    }


def test_app_info_does_not_mutate_runtime_metadata_input():
    runtime_info = {"http_listener": False}
    bridge = DesktopBridge(FakeService(), FakeNative(), runtime_info)

    bridge.invoke(request("system.app_info"))

    assert runtime_info == {"http_listener": False}


def test_bridge_rejects_unknown_command_and_bad_request_id():
    bridge = DesktopBridge(FakeService(), FakeNative(), {})

    unknown = bridge.invoke(request("python.eval", {"code": "2 + 2"}))
    invalid_id = bridge.invoke({"request_id": "not-a-uuid", "command": "system.ping", "payload": {}})

    assert unknown["ok"] is False
    assert unknown["error"]["code"] == "invalid_native_request"
    assert invalid_id["ok"] is False
    assert invalid_id["error"]["code"] == "invalid_native_request"


def test_bridge_forwards_expected_row_version():
    bridge = DesktopBridge(FakeService(), FakeNative(), {})

    response = bridge.invoke(request("record.update", {"id": 7}, expected_row_version=4))

    assert response["ok"] is True
    assert response["data"]["row_version"] == 5


def test_bridge_exposes_read_only_ai_prompt_history():
    bridge = DesktopBridge(FakeService(), FakeNative(), {})

    response = bridge.invoke(request("ai.history", {"page": 1, "per_page": 5}))

    assert response["ok"] is True
    assert response["data"]["pagination"]["total"] == 0


def test_bridge_runs_zotero_sync_as_queryable_background_job():
    bridge = DesktopBridge(FakeService(), FakeNative(), {})

    started = bridge.invoke(request("zotero.sync.start"))
    assert started["ok"] is True
    job_id = started["data"]["job_id"]
    for _ in range(50):
        status = bridge.invoke(request("zotero.sync.status", {"job_id": job_id}))
        if status["data"]["state"] == "completed":
            break
        time.sleep(0.01)

    assert status["data"]["state"] == "completed"
    assert status["data"]["result"]["added"] == 1
    assert status["data"]["result"]["collections"] == {"collections": 2, "memberships": 3}
    assert status["data"]["sync"]["sync_progress"] == 100


def test_bridge_keeps_weekly_file_paths_behind_native_and_service_authorization():
    bridge = DesktopBridge(FakeService(), FakeNative(), {})

    imported = bridge.invoke(request(
        "weekly.import_file", {"path": "C:\\selected\\report.pdf"}, expected_row_version=3,
    ))
    opened = bridge.invoke(request("weekly.open_file", {"report_id": 2, "file_id": 9}))
    directory = bridge.invoke(request("weekly.open_directory", {"report_id": 2}))

    assert imported["data"]["row_version"] == 4
    assert opened["data"] == {"opened": True, "path": "C:\\weekly\\report.pdf"}
    assert directory["data"] == {"opened": True, "path": "C:\\weekly"}


def test_native_adapter_rejects_untrusted_paths_and_unsafe_urls(tmp_path):
    native = NativeCapabilities(tmp_path / "instance")

    try:
        native.open_trusted_path({"path": str(tmp_path / "outside.txt")})
    except NativeCapabilityError as exc:
        assert "原生对话框" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Untrusted path was accepted")

    for url in ("http://127.0.0.1:5001", "file:///C:/Windows/System32", "javascript:alert(1)"):
        try:
            native.open_external_url({"url": url})
        except NativeCapabilityError:
            pass
        else:  # pragma: no cover
            raise AssertionError(f"Unsafe URL was accepted: {url}")


def test_initial_directory_must_stay_under_user_or_instance_root(tmp_path, monkeypatch):
    home = tmp_path / "home"
    instance = home / "AppData" / "ResearchAssistant"
    outside = tmp_path / "outside"
    for path in (home, instance, outside):
        path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    native = NativeCapabilities(instance)

    assert native._initial_directory(home) == str(home.resolve())
    try:
        native._initial_directory(outside)
    except NativeCapabilityError as exc:
        assert "允许范围" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Path outside the allowed roots was accepted")
