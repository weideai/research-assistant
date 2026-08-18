from __future__ import annotations

import os
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
import webbrowser


class NativeCapabilityError(ValueError):
    pass


class NativeCapabilities:
    def __init__(self, instance_dir):
        self.instance_dir = Path(instance_dir).resolve()
        self.window = None
        self._trusted_paths = set()
        self._trusted_directories = set()

    def attach_window(self, window):
        self.window = window

    def _require_window(self):
        if self.window is None:
            raise NativeCapabilityError("桌面窗口尚未就绪。")
        return self.window

    def _initial_directory(self, value):
        if not value:
            return str(Path.home())
        candidate = Path(str(value)).expanduser().resolve()
        allowed_roots = (Path.home().resolve(), self.instance_dir)
        if not candidate.is_dir() or not any(candidate == root or root in candidate.parents for root in allowed_roots):
            raise NativeCapabilityError("初始目录不在允许范围内。")
        return str(candidate)

    @staticmethod
    def _dialog_constant(webview, modern_name, legacy_name):
        modern = getattr(webview, "FileDialog", None)
        if modern is not None and hasattr(modern, modern_name):
            return getattr(modern, modern_name)
        return getattr(webview, legacy_name)

    def _remember(self, paths):
        normalized = []
        for value in paths or ():
            path = Path(value).expanduser().resolve()
            self._trusted_paths.add(str(path).casefold())
            normalized.append(str(path))
        return normalized

    def assert_trusted_path(self, value, *, must_exist=False):
        path = Path(str(value or "")).expanduser().resolve()
        normalized = str(path).casefold()
        trusted = normalized in self._trusted_paths or any(
            path == root or root in path.parents
            for root in (Path(value) for value in self._trusted_directories)
        )
        if not trusted:
            raise NativeCapabilityError("该路径不是本次会话中由原生对话框选择的路径。")
        if must_exist and not path.exists():
            raise NativeCapabilityError("所选路径已不存在。")
        return str(path)

    def open_file_dialog(self, payload):
        import webview

        kinds = {
            "documents": ("文档 (*.pdf;*.docx;*.md;*.txt)", "全部文件 (*.*)"),
            "reports": (
                "周报文件 (*.doc;*.docx;*.pdf;*.ppt;*.pptx;*.odp;*.key;*.xls;*.xlsx;*.csv;*.ods;*.md;*.txt;*.zip)",
                "全部文件 (*.*)",
            ),
            "data": ("数据文件 (*.csv;*.tsv;*.xlsx;*.json)", "全部文件 (*.*)"),
            "images": ("图像 (*.png;*.jpg;*.jpeg;*.tif;*.tiff)", "全部文件 (*.*)"),
            "any": ("全部文件 (*.*)",),
        }
        kind = str(payload.get("kind") or "any")
        if kind not in kinds:
            raise NativeCapabilityError("不支持的文件筛选类型。")
        selected = self._require_window().create_file_dialog(
            self._dialog_constant(webview, "OPEN", "OPEN_DIALOG"),
            directory=self._initial_directory(payload.get("initial_directory")),
            allow_multiple=bool(payload.get("multiple")),
            file_types=kinds[kind],
        )
        return self._remember(selected)

    def select_directory_dialog(self, payload):
        import webview

        selected = self._require_window().create_file_dialog(
            self._dialog_constant(webview, "FOLDER", "FOLDER_DIALOG"),
            directory=self._initial_directory(payload.get("initial_directory")),
            allow_multiple=False,
        )
        values = self._remember([selected] if isinstance(selected, str) else selected)
        for value in values:
            self._trusted_directories.add(str(Path(value).resolve()).casefold())
        return values

    def save_file_dialog(self, payload):
        import webview

        suggested = Path(str(payload.get("suggested_name") or "R-LAB-export.json")).name
        suggested = re.sub(r"[^\w\-. ()\u4e00-\u9fff]", "_", suggested)[:180]
        if not suggested:
            suggested = "R-LAB-export.json"
        selected = self._require_window().create_file_dialog(
            self._dialog_constant(webview, "SAVE", "SAVE_DIALOG"),
            directory=self._initial_directory(payload.get("initial_directory")),
            save_filename=suggested,
            file_types=(
                "PowerPoint (*.pptx)", "Word (*.docx)", "PDF (*.pdf)",
                "JSON (*.json)", "Markdown (*.md)", "全部文件 (*.*)",
            ),
        )
        values = [selected] if isinstance(selected, str) else selected
        return self._remember(values)

    def open_trusted_path(self, payload):
        path = Path(self.assert_trusted_path(payload.get("path"), must_exist=True))
        return self.open_authorized_path(path)

    @staticmethod
    def open_authorized_path(value):
        """Open a path resolved by a trusted service method, never raw JS input."""
        path = Path(value).expanduser().resolve()
        if not path.exists():
            raise NativeCapabilityError("要打开的文件或目录不存在。")
        if sys.platform != "win32":
            raise NativeCapabilityError("当前桌面适配器仅支持 Windows 路径打开。")
        os.startfile(path)
        return {"opened": True}

    @staticmethod
    def open_external_url(payload):
        url = str(payload.get("url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "mailto", "zotero"}:
            raise NativeCapabilityError("只允许打开 HTTPS、mailto 或 Zotero 链接。")
        webbrowser.open(url)
        return {"opened": True}

    def window_command(self, command):
        window = self._require_window()
        if command == "window.minimize":
            window.minimize()
        elif command == "window.maximize":
            window.maximize()
        elif command == "window.restore":
            window.restore()
        elif command == "window.close":
            window.destroy()
        else:
            raise NativeCapabilityError("不支持的窗口命令。")
        return {"accepted": True}
