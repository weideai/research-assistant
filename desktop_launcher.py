import logging
import os
import socket
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw
from werkzeug.serving import make_server


APP_TITLE = "R/LAB Research Assistant"
HOST = "127.0.0.1"
DEFAULT_PORT = 5001


def local_app_root():
    return Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ResearchAssistant"


def instance_dir():
    configured = os.getenv("RESEARCH_ASSISTANT_INSTANCE_DIR", "").strip()
    return Path(configured).expanduser().resolve() if configured else local_app_root() / "data"


def resource_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def configure_environment():
    data_dir = instance_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["RESEARCH_ASSISTANT_INSTANCE_DIR"] = str(data_dir)
    os.environ.setdefault("HOST", HOST)
    os.environ.setdefault("PORT", str(DEFAULT_PORT))
    os.environ.setdefault("ALLOW_OPEN_LOCAL_FOLDERS", "true")
    log_dir = local_app_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "desktop.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )


def service_url():
    port = int(os.getenv("PORT", str(DEFAULT_PORT)))
    return f"http://{HOST}:{port}"


def service_is_ready(url=None):
    try:
        with urllib.request.urlopen(f"{url or service_url()}/healthz", timeout=1.5) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def port_is_available():
    port = int(os.getenv("PORT", str(DEFAULT_PORT)))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((HOST, port))
            return True
        except OSError:
            return False


def create_desktop_app():
    from app import create_app, db
    from app.migration_service import run_migrations_with_backup

    flask_app = create_app()
    migration_dir = resource_root() / "migrations"
    run_migrations_with_backup(flask_app, db, migration_dir)
    return flask_app


def native_message(text, flags=0x10):
    import ctypes

    return ctypes.windll.user32.MessageBoxW(None, text, APP_TITLE, flags)


def tray_image():
    image = Image.new("RGBA", (64, 64), "#14242b")
    draw = ImageDraw.Draw(image)
    draw.rectangle((7, 7, 31, 56), fill="#c8ff36")
    draw.rectangle((35, 7, 56, 56), fill="#ffffff")
    draw.line((39, 20, 52, 20), fill="#2166f3", width=4)
    draw.line((39, 31, 52, 31), fill="#2166f3", width=4)
    draw.line((39, 42, 48, 42), fill="#2166f3", width=4)
    return image


class DesktopRuntime:
    def __init__(self):
        self.server = None
        self.server_thread = None
        self.owns_server = False
        self.ready = threading.Event()
        self.start_error = ""
        self.tray = pystray.Icon(
            APP_TITLE, tray_image(), APP_TITLE,
            menu=pystray.Menu(
                pystray.MenuItem("打开 Research Assistant", self.open_browser, default=True),
                pystray.MenuItem("打开数据目录", self.open_data_dir),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self.stop),
            ),
        )

    def start(self):
        configure_environment()
        if service_is_ready():
            logging.info("Connected to an existing local service at %s", service_url())
        elif not port_is_available():
            native_message("端口 5001 已被其他程序占用，请关闭占用程序后重试。")
            return
        else:
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            if not self.ready.wait(timeout=30):
                native_message("本地服务启动超时。请查看运行日志。")
                return
            if self.start_error:
                native_message(f"本地服务启动失败：\n{self.start_error}\n\n日志：{local_app_root() / 'logs' / 'desktop.log'}")
                return
        self.open_browser()
        self.tray.run()

    def _run_server(self):
        try:
            flask_app = create_desktop_app()
            port = int(os.getenv("PORT", str(DEFAULT_PORT)))
            self.server = make_server(HOST, port, flask_app, threaded=True)
            self.owns_server = True
            logging.info("Desktop service started at %s", service_url())
            self.ready.set()
            self.server.serve_forever()
        except Exception as exc:
            logging.exception("Desktop service failed")
            self.start_error = str(exc)
            self.ready.set()

    def open_browser(self, _icon=None, _item=None):
        if os.getenv("RESEARCH_ASSISTANT_NO_BROWSER", "").strip().lower() not in {"1", "true", "yes"}:
            webbrowser.open(service_url())

    def open_data_dir(self, _icon=None, _item=None):
        target = instance_dir()
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(target)

    def stop(self, _icon=None, _item=None):
        if self.owns_server and self.server:
            self.server.shutdown()
            self.server.server_close()
        self.tray.stop()


def main():
    configure_environment()
    DesktopRuntime().start()


if __name__ == "__main__":
    main()
