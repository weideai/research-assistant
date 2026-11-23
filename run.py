"""Run the current R/LAB desktop source with `python run.py`."""

from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent
    scripts, executable = ("Scripts", "python.exe") if sys.platform == "win32" else ("bin", "python")
    environment = root / ".venv"
    local_python = environment / scripts / executable
    if local_python.is_file() and Path(sys.prefix).resolve() != environment.resolve():
        return subprocess.call([str(local_python), str(root / "run.py"), *sys.argv[1:]], cwd=root)

    from app.desktop.runtime import main as desktop_main

    desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())
