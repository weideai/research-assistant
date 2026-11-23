from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
from tempfile import NamedTemporaryFile


class WorkspaceLocationError(ValueError):
    pass


def local_app_root():
    return Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ResearchAssistant"


def workspace_preference_path():
    return local_app_root() / "workspace-location.json"


def saved_workspace_directory():
    try:
        config = json.loads(workspace_preference_path().read_text(encoding="utf-8"))
        path = config["path"]
        if not isinstance(path, str) or not Path(path).is_absolute():
            raise ValueError("Expected an absolute path")
        return Path(path)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise WorkspaceLocationError("无法读取工作区位置设置。") from exc


def inspect_workspace_directory(value):
    path = Path(value).resolve()
    if not path.is_dir():
        raise WorkspaceLocationError("所选工作区文件夹不存在或不可访问。")
    database = path / "research.db"
    has_workspace = database.exists() or database.is_symlink()
    if has_workspace:
        if not database.is_file() or database.is_symlink():
            raise WorkspaceLocationError("文件夹内的 research.db 无法用作 R/LAB 工作区。")
        try:
            with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True, timeout=2)) as db:
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        except sqlite3.Error as exc:
            raise WorkspaceLocationError("无法读取所选文件夹内的 research.db。") from exc
        if "user" not in tables or not tables.intersection({"workspace", "lab_record", "experiment"}):
            raise WorkspaceLocationError("该文件夹中的 research.db 不是有效的 R/LAB 工作区。")
    return {"path": str(path), "has_workspace": has_workspace}


def save_workspace_directory(value):
    selection = inspect_workspace_directory(value)
    preference = workspace_preference_path()
    temporary = None
    try:
        preference.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=preference.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump({"path": selection["path"]}, file, ensure_ascii=False)
        temporary.replace(preference)
    except OSError as exc:
        raise WorkspaceLocationError("无法保存工作区位置。") from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)
    return selection
