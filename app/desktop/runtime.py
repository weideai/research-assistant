from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path
import sys

from app.version import APP_VERSION
from .bridge import DesktopBridge
from .native import NativeCapabilities
from .single_instance import SingleInstance


APP_TITLE = "R/LAB Research Assistant"


def local_app_root():
    return Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ResearchAssistant"


def instance_dir():
    configured = os.getenv("RESEARCH_ASSISTANT_INSTANCE_DIR", "").strip()
    return Path(configured).expanduser().resolve() if configured else local_app_root() / "data"


def resource_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def desktop_page():
    return resource_root() / "app" / "desktop_ui" / "index.html"


def configure_environment():
    data_dir = instance_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["RESEARCH_ASSISTANT_INSTANCE_DIR"] = str(data_dir)
    os.environ.setdefault("LOCAL_MODE", "true")
    os.environ.setdefault("APP_ENV", "production")
    os.environ.setdefault("ALLOW_OPEN_LOCAL_FOLDERS", "true")
    log_dir = local_app_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "desktop.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    return data_dir


def native_message(message, flags=0x10):
    if sys.platform == "win32":
        return ctypes.windll.user32.MessageBoxW(None, message, APP_TITLE, flags)
    print(message, file=sys.stderr)
    return 0


def initialize_application():
    from app import create_app, db
    from app.migration_service import run_migrations_with_backup

    flask_app = create_app()
    run_migrations_with_backup(flask_app, db, resource_root() / "migrations")
    return flask_app


def run_desktop(debug=False):
    data_dir = configure_environment()
    page = desktop_page()
    if not page.is_file():
        native_message(f"桌面界面资源缺失：\n{page}")
        return 2

    instance = SingleInstance()
    if not instance.acquire():
        # A second click on a Windows shortcut starts a second process.  Do
        # not show a modal message box here: it can open behind the existing
        # WebView2 window and make the launch look like a deadlock.  The first
        # instance remains the one the user should continue using.
        logging.info("Duplicate desktop launch ignored; another instance is already running")
        instance.release()
        return 0

    try:
        import webview

        flask_app = initialize_application()
        from app.services.desktop_workspace import DesktopApplicationService

        native = NativeCapabilities(data_dir)
        bridge = DesktopBridge(
            DesktopApplicationService(flask_app),
            native,
            {
                "name": APP_TITLE,
                "version": APP_VERSION,
                "platform": "windows" if sys.platform == "win32" else sys.platform,
                "storage_mode": "local",
                "transport": "in-process-js-bridge",
                "http_listener": False,
            },
        )
        window = webview.create_window(
            APP_TITLE,
            url=f"{page.resolve().as_uri()}#bridge=pywebview",
            js_api=bridge,
            width=1440,
            height=900,
            min_size=(1080, 700),
            background_color="#f2f1f8",
            text_select=True,
        )
        native.attach_window(window)
        logging.info("Starting port-free desktop window from %s", page)
        webview.start(
            gui="edgechromium" if sys.platform == "win32" else None,
            debug=debug,
            http_server=False,
            private_mode=False,
            storage_path=str(local_app_root() / "webview-profile"),
        )
        return 0
    except Exception as exc:
        logging.exception("Desktop startup failed")
        native_message(
            "R/LAB 桌面窗口启动失败。请确认已安装 Microsoft Edge WebView2 Runtime。\n\n"
            f"错误：{exc}\n日志：{local_app_root() / 'logs' / 'desktop.log'}"
        )
        return 3
    finally:
        instance.release()


def main():
    debug = os.getenv("R_LAB_DESKTOP_DEBUG", "").strip().lower() in {"1", "true", "yes"}
    raise SystemExit(run_desktop(debug=debug))
