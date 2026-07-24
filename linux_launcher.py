import argparse
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from werkzeug.serving import make_server


HOST = "127.0.0.1"
DEFAULT_PORT = 5001
APP_NAME = "research-assistant"


def data_root():
    configured = os.getenv("RESEARCH_ASSISTANT_HOME", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    xdg_data = os.getenv("XDG_DATA_HOME", "").strip()
    base = Path(xdg_data).expanduser() if xdg_data else Path.home() / ".local" / "share"
    return base / APP_NAME


def instance_dir():
    return data_root() / "data"


def log_path():
    return data_root() / "logs" / "desktop.log"


def pid_path():
    return data_root() / "research-assistant.pid"


def resource_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def service_url():
    return f"http://{HOST}:{int(os.getenv('PORT', str(DEFAULT_PORT)))}"


def configure_environment():
    instance_dir().mkdir(parents=True, exist_ok=True)
    log_path().parent.mkdir(parents=True, exist_ok=True)
    os.environ["RESEARCH_ASSISTANT_INSTANCE_DIR"] = str(instance_dir())
    os.environ.setdefault("HOST", HOST)
    os.environ.setdefault("PORT", str(DEFAULT_PORT))
    os.environ.setdefault("ALLOW_OPEN_LOCAL_FOLDERS", "false")
    logging.basicConfig(
        filename=log_path(), level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8",
    )


def service_is_ready():
    try:
        with urllib.request.urlopen(f"{service_url()}/healthz", timeout=1.5) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def read_pid():
    try:
        return int(pid_path().read_text(encoding="ascii").strip())
    except (FileNotFoundError, TypeError, ValueError):
        return None


def process_is_running(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    command_path = Path(f"/proc/{pid}/cmdline")
    if not command_path.is_file():
        return True
    try:
        command = command_path.read_bytes().replace(b"\0", b" ").decode("utf-8", errors="replace")
    except OSError:
        return False
    return "ResearchAssistant" in command or "linux_launcher.py" in command


def executable_command(*arguments):
    if getattr(sys, "frozen", False):
        return [sys.executable, *arguments]
    return [sys.executable, str(Path(__file__).resolve()), *arguments]


def open_browser():
    if os.getenv("RESEARCH_ASSISTANT_NO_BROWSER", "").strip().lower() in {"1", "true", "yes"}:
        return
    if os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"):
        webbrowser.open(service_url())


def create_linux_app():
    from app import create_app, db
    from app.migration_service import run_migrations_with_backup

    flask_app = create_app()
    migration_dir = resource_root() / "migrations"
    run_migrations_with_backup(flask_app, db, migration_dir)
    return flask_app


def run_foreground():
    configure_environment()
    server = make_server(HOST, int(os.getenv("PORT", str(DEFAULT_PORT))), create_linux_app(), threaded=True)
    pid_path().write_text(str(os.getpid()), encoding="ascii")

    def stop_server(_signal_number, _frame):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop_server)
    signal.signal(signal.SIGINT, stop_server)
    logging.info("Linux service started at %s", service_url())
    try:
        server.serve_forever()
    finally:
        try:
            pid_path().unlink()
        except FileNotFoundError:
            pass
        server.server_close()


def start_background():
    configure_environment()
    if service_is_ready():
        open_browser()
        print(f"Research Assistant is already running at {service_url()}")
        return 0
    pid = read_pid()
    if process_is_running(pid):
        print(f"Research Assistant process {pid} is starting.")
        return 0
    with log_path().open("a", encoding="utf-8") as log_file:
        subprocess.Popen(
            executable_command("--foreground"),
            stdin=subprocess.DEVNULL, stdout=log_file, stderr=log_file,
            start_new_session=True, close_fds=True,
            env=os.environ.copy(),
        )
    for _attempt in range(60):
        if service_is_ready():
            open_browser()
            print(f"Research Assistant started at {service_url()}")
            return 0
        time.sleep(0.25)
    print(f"Startup timed out. Check {log_path()}", file=sys.stderr)
    return 1


def stop_background():
    configure_environment()
    pid = read_pid()
    if not process_is_running(pid):
        try:
            pid_path().unlink()
        except FileNotFoundError:
            pass
        print("Research Assistant is not running.")
        return 0
    os.kill(pid, signal.SIGTERM)
    for _attempt in range(40):
        if not process_is_running(pid):
            print("Research Assistant stopped.")
            return 0
        time.sleep(0.25)
    print(f"Process {pid} did not stop in time.", file=sys.stderr)
    return 1


def status():
    configure_environment()
    if service_is_ready():
        print(f"running {service_url()}")
        return 0
    print("stopped")
    return 1


def parse_args():
    parser = argparse.ArgumentParser(description="R/LAB Research Assistant Linux launcher")
    parser.add_argument("--foreground", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--open", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.foreground:
        run_foreground()
        return 0
    if args.stop:
        return stop_background()
    if args.status:
        return status()
    if args.open and service_is_ready():
        open_browser()
        return 0
    return start_background()


if __name__ == "__main__":
    raise SystemExit(main())
