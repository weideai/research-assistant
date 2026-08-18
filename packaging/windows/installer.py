import argparse
import base64
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - keeps pure installer helpers testable off Windows.
    winreg = None

from version_info import APP_VERSION


PRODUCT_NAME = "R/LAB Research Assistant"
SHORTCUT_NAME = "R-LAB Research Assistant"
APP_ID = "ResearchAssistant"
VERSION = APP_VERSION
INSTALL_INFO_NAME = "install-info.json"
MB_ICONERROR = 0x10
MB_ICONQUESTION = 0x20
MB_ICONINFORMATION = 0x40
MB_YESNO = 0x04
IDYES = 6


def native_message(text, flags=MB_ICONINFORMATION):
    return ctypes.windll.user32.MessageBoxW(None, text, PRODUCT_NAME, flags)


def local_app_data():
    return Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))


def install_dir():
    return local_app_data() / "Programs" / APP_ID


def data_dir():
    configured = os.getenv("RESEARCH_ASSISTANT_INSTANCE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return local_app_data() / APP_ID / "data"


def payload_dir():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "payload" / APP_ID


def install_info_path(directory=None):
    return (Path(directory) if directory else install_dir()) / INSTALL_INFO_NAME


def read_install_info(directory=None):
    try:
        payload = json.loads(install_info_path(directory).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def existing_installation(directory=None):
    directory = Path(directory) if directory else install_dir()
    return (directory / "ResearchAssistant.exe").is_file()


def known_folder(folder_id):
    buffer = ctypes.create_unicode_buffer(260)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, folder_id, None, 0, buffer)
    if result != 0:
        raise OSError(f"无法读取 Windows 文件夹：{folder_id}")
    return Path(buffer.value)


def shortcut_paths():
    desktop = known_folder(0x10) / f"{SHORTCUT_NAME}.lnk"
    programs_dir = known_folder(0x02) / SHORTCUT_NAME
    return desktop, programs_dir / f"{SHORTCUT_NAME}.lnk", programs_dir / "卸载 Research Assistant.lnk"


def legacy_shortcut_paths():
    desktop = known_folder(0x10) / "R" / "LAB Research Assistant.lnk"
    programs_dir = known_folder(0x02) / "R" / "LAB Research Assistant"
    return desktop, programs_dir / "R" / "LAB Research Assistant.lnk", programs_dir / "卸载 Research Assistant.lnk"


def remove_shortcuts():
    for shortcut in (*shortcut_paths(), *legacy_shortcut_paths()):
        try:
            shortcut.unlink()
        except FileNotFoundError:
            pass
    cleanup_candidates = {
        shortcut_paths()[1].parent,
        legacy_shortcut_paths()[1].parent,
        legacy_shortcut_paths()[1].parent.parent,
        legacy_shortcut_paths()[0].parent,
    }
    for directory in sorted(cleanup_candidates, key=lambda item: len(item.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def run_powershell(script):
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "PowerShell 执行失败").strip())


def ps_quote(value):
    return str(value).replace("'", "''")


def create_shortcut(shortcut, target, working_dir, arguments=""):
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$shell = New-Object -ComObject WScript.Shell; "
        f"$link = $shell.CreateShortcut('{ps_quote(shortcut)}'); "
        f"$link.TargetPath = '{ps_quote(target)}'; "
        f"$link.WorkingDirectory = '{ps_quote(working_dir)}'; "
        f"$link.Arguments = '{ps_quote(arguments)}'; "
        "$link.Save()"
    )
    run_powershell(script)


def find_source_instance(explicit_source="", legacy_install=None):
    candidates = []
    if explicit_source:
        candidates.append(Path(explicit_source))
    if legacy_install:
        legacy_install = Path(legacy_install)
        candidates.extend([legacy_install / "instance", legacy_install / "data"])
    executable_dir = Path(sys.executable).resolve().parent
    candidates.extend([
        executable_dir.parent.parent / "instance",
        Path.cwd() / "instance",
        Path(__file__).resolve().parents[2] / "instance",
    ])
    for candidate in candidates:
        if (candidate / "research.db").is_file():
            return candidate.resolve()
    return None


def seed_existing_data(explicit_source="", legacy_install=None):
    target = data_dir()
    if (target / "research.db").is_file():
        return False
    source = find_source_instance(explicit_source, legacy_install=legacy_install)
    if not source:
        target.mkdir(parents=True, exist_ok=True)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    return True


def stop_installed_app():
    subprocess.run(
        ["taskkill.exe", "/IM", "ResearchAssistant.exe", "/T", "/F"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )


def install_payload(explicit_source=""):
    payload = payload_dir()
    if not (payload / "ResearchAssistant.exe").is_file():
        raise RuntimeError("安装包中的程序文件不完整。")

    destination = install_dir()
    staging = destination.with_name(f"{destination.name}.installing")
    previous = destination.with_name(f"{destination.name}.previous")
    was_installed = existing_installation(destination)
    previous_info = read_install_info(destination)
    previous_version = str(previous_info.get("version") or "").strip()
    data_path = data_dir()
    data_was_present = data_path.exists()
    stop_installed_app()
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(previous, ignore_errors=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    swap_completed = False
    imported = False
    try:
        # Seed legacy project data before replacing an old application directory.
        # Normal upgrades keep the external data directory untouched.
        imported = seed_existing_data(explicit_source, legacy_install=destination if was_installed else None)
        shutil.copytree(payload, staging)
        setup_copy = staging / "ResearchAssistant-Setup.exe"
        if getattr(sys, "frozen", False):
            shutil.copy2(sys.executable, setup_copy)
        install_info = {
            "version": VERSION,
            "data_dir": str(data_path),
            "install_mode": "upgrade" if was_installed else "fresh",
            "previous_version": previous_version,
            "data_preserved": data_was_present or (data_path / "research.db").is_file(),
            "seeded_data": imported,
            "installed_at": datetime.now(timezone.utc).isoformat(),
        }
        (staging / INSTALL_INFO_NAME).write_text(
            json.dumps(install_info, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if destination.exists():
            destination.replace(previous)
        staging.replace(destination)
        swap_completed = True

        setup_copy = destination / "ResearchAssistant-Setup.exe"
        remove_shortcuts()
        desktop_link, start_link, uninstall_link = shortcut_paths()
        create_shortcut(desktop_link, destination / "ResearchAssistant.exe", destination)
        create_shortcut(start_link, destination / "ResearchAssistant.exe", destination)
        create_shortcut(uninstall_link, setup_copy, destination, "--uninstall")
        register_uninstaller(setup_copy)
        shutil.rmtree(previous, ignore_errors=True)
        return {
            "upgraded": was_installed,
            "previous_version": previous_version,
            "version": VERSION,
            "data_preserved": install_info["data_preserved"],
            "imported": imported,
        }
    except Exception:
        if not swap_completed and previous.exists() and not destination.exists():
            previous.replace(destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def register_uninstaller(setup_path):
    if winreg is None:
        return
    key_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, PRODUCT_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "R/LAB")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir()))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{setup_path}" --uninstall')
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)


def remove_registration():
    if winreg is None:
        return
    key_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}"
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
    except FileNotFoundError:
        pass


def uninstall(quiet=False):
    if not quiet and native_message(
        "确定卸载程序？\n\n实验数据库和附件会保留在本地数据目录，不会删除。",
        MB_YESNO | MB_ICONQUESTION,
    ) != IDYES:
        return
    stop_installed_app()
    remove_shortcuts()
    remove_registration()
    helper = Path(tempfile.gettempdir()) / "research-assistant-remove.ps1"
    helper.write_text(
        f"Start-Sleep -Seconds 2\nRemove-Item -LiteralPath '{ps_quote(install_dir())}' -Recurse -Force -ErrorAction SilentlyContinue\nRemove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue\n",
        encoding="utf-8-sig",
    )
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(helper)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if not quiet:
        native_message(f"程序已卸载。\n科研数据仍保留在：\n{data_dir()}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--source-instance", default="")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.uninstall:
        uninstall(args.quiet)
        return
    if args.quiet:
        install_payload(args.source_instance)
        if args.launch:
            subprocess.Popen([str(install_dir() / "ResearchAssistant.exe")], cwd=install_dir())
        return
    action = "更新" if existing_installation() else "安装"
    previous_info = read_install_info()
    previous_version = str(previous_info.get("version") or "未知版本")
    detail = f"\n检测到已安装版本：v{previous_version}，升级时会保留实验数据和附件。" if action == "更新" else ""
    if native_message(
        f"是否快速{action} {PRODUCT_NAME}？\n\n程序：{install_dir()}\n数据：{data_dir()}{detail}",
        MB_YESNO | MB_ICONQUESTION,
    ) != IDYES:
        return
    try:
        result = install_payload(args.source_instance)
    except Exception as exc:
        native_message(f"安装失败：\n{exc}", MB_ICONERROR)
        return
    detail = "\n已导入当前项目中的账户、实验记录和附件。" if result["imported"] else ""
    action_detail = "更新完成" if result["upgraded"] else "安装完成"
    native_message(f"{action_detail}。桌面和开始菜单已创建快捷方式。{detail}")
    subprocess.Popen([str(install_dir() / "ResearchAssistant.exe")], cwd=install_dir())


if __name__ == "__main__":
    main()
