import json
import importlib.util
from pathlib import Path

import pytest



_INSTALLER_PATH = Path(__file__).resolve().parents[1] / "packaging" / "windows" / "installer.py"
_INSTALLER_SPEC = importlib.util.spec_from_file_location("research_assistant_windows_installer", _INSTALLER_PATH)
installer = importlib.util.module_from_spec(_INSTALLER_SPEC)
assert _INSTALLER_SPEC.loader is not None
_INSTALLER_SPEC.loader.exec_module(installer)


def _configure_installer(monkeypatch, tmp_path, payload):
    local_app_data = tmp_path / "local-app-data"
    monkeypatch.setattr(installer, "local_app_data", lambda: local_app_data)
    monkeypatch.setattr(installer, "payload_dir", lambda: payload)
    monkeypatch.setattr(installer, "stop_installed_app", lambda: None)
    monkeypatch.setattr(installer, "remove_shortcuts", lambda: None)
    monkeypatch.setattr(installer, "create_shortcut", lambda *args, **kwargs: None)
    monkeypatch.setattr(installer, "register_uninstaller", lambda *args, **kwargs: None)
    return local_app_data


def _payload(tmp_path, marker):
    payload = tmp_path / "payload" / installer.APP_ID
    payload.mkdir(parents=True)
    (payload / "ResearchAssistant.exe").write_text(marker, encoding="utf-8")
    (payload / "_internal").mkdir()
    (payload / "_internal" / "marker.txt").write_text(marker, encoding="utf-8")
    return payload


def test_installer_seeds_data_on_fresh_install_and_records_state(tmp_path, monkeypatch):
    payload = _payload(tmp_path, "fresh-build")
    local_app_data = _configure_installer(monkeypatch, tmp_path, payload)
    source = tmp_path / "source-instance"
    source.mkdir()
    (source / "research.db").write_text("database", encoding="utf-8")
    (source / "uploads").mkdir()
    (source / "uploads" / "result.txt").write_text("attachment", encoding="utf-8")

    result = installer.install_payload(str(source))

    assert result == {
        "upgraded": False,
        "previous_version": "",
        "version": installer.VERSION,
        "data_preserved": True,
        "imported": True,
    }
    install_root = local_app_data / "Programs" / installer.APP_ID
    assert (install_root / "ResearchAssistant.exe").read_text(encoding="utf-8") == "fresh-build"
    assert (local_app_data / installer.APP_ID / "data" / "research.db").read_text(encoding="utf-8") == "database"
    info = json.loads((install_root / installer.INSTALL_INFO_NAME).read_text(encoding="utf-8"))
    assert info["install_mode"] == "fresh"
    assert info["seeded_data"] is True
    assert info["previous_version"] == ""


def test_installer_replaces_program_files_without_overwriting_existing_data(tmp_path, monkeypatch):
    payload = _payload(tmp_path, "new-build")
    local_app_data = _configure_installer(monkeypatch, tmp_path, payload)
    install_root = local_app_data / "Programs" / installer.APP_ID
    install_root.mkdir(parents=True)
    (install_root / "ResearchAssistant.exe").write_text("old-build", encoding="utf-8")
    (install_root / installer.INSTALL_INFO_NAME).write_text(
        json.dumps({"version": "2.4.0"}), encoding="utf-8"
    )
    data_root = local_app_data / installer.APP_ID / "data"
    data_root.mkdir(parents=True)
    (data_root / "research.db").write_text("user-database", encoding="utf-8")
    (data_root / "attachment.txt").write_text("user-file", encoding="utf-8")

    result = installer.install_payload()

    assert result["upgraded"] is True
    assert result["previous_version"] == "2.4.0"
    assert result["data_preserved"] is True
    assert result["imported"] is False
    assert (install_root / "ResearchAssistant.exe").read_text(encoding="utf-8") == "new-build"
    assert (data_root / "research.db").read_text(encoding="utf-8") == "user-database"
    assert (data_root / "attachment.txt").read_text(encoding="utf-8") == "user-file"
    info = json.loads((install_root / installer.INSTALL_INFO_NAME).read_text(encoding="utf-8"))
    assert info["install_mode"] == "upgrade"
    assert info["previous_version"] == "2.4.0"
    assert not install_root.with_name(f"{install_root.name}.previous").exists()


def test_installer_uses_configured_instance_dir_for_upgrade_data(tmp_path, monkeypatch):
    payload = _payload(tmp_path, "configured-data-build")
    local_app_data = _configure_installer(monkeypatch, tmp_path, payload)
    configured_data = tmp_path / "custom-workspace"
    monkeypatch.setenv("RESEARCH_ASSISTANT_INSTANCE_DIR", str(configured_data))
    configured_data.mkdir()
    (configured_data / "research.db").write_text("custom-database", encoding="utf-8")
    install_root = local_app_data / "Programs" / installer.APP_ID
    install_root.mkdir(parents=True)
    (install_root / "ResearchAssistant.exe").write_text("old-build", encoding="utf-8")

    result = installer.install_payload()

    assert result["upgraded"] is True
    assert result["data_preserved"] is True
    assert (configured_data / "research.db").read_text(encoding="utf-8") == "custom-database"
    assert not (local_app_data / installer.APP_ID / "data").exists()


def test_incomplete_payload_does_not_touch_existing_install(tmp_path, monkeypatch):
    payload = tmp_path / "payload" / installer.APP_ID
    payload.mkdir(parents=True)
    local_app_data = _configure_installer(monkeypatch, tmp_path, payload)
    install_root = local_app_data / "Programs" / installer.APP_ID
    install_root.mkdir(parents=True)
    executable = install_root / "ResearchAssistant.exe"
    executable.write_text("known-good", encoding="utf-8")

    with pytest.raises(RuntimeError, match="程序文件不完整"):
        installer.install_payload()

    assert executable.read_text(encoding="utf-8") == "known-good"
