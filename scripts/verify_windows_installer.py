import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader


REQUIRED_ENTRIES = {
    r"payload\ResearchAssistant\ResearchAssistant.exe",
    r"payload\ResearchAssistant\_internal\app\templates\base.html",
    r"payload\ResearchAssistant\_internal\app\static\css\ide.css",
    r"payload\ResearchAssistant\_internal\app\static\css\skins.css",
    r"payload\ResearchAssistant\_internal\app\static\js\skin.js",
    r"payload\ResearchAssistant\_internal\migrations\alembic.ini",
    r"payload\ResearchAssistant\_internal\scripts\build_weekly_presentation.mjs",
}

PRIVATE_FILE_NAMES = {".env", "credential_key", "research.db", "secret_key"}


def verify(installer_path):
    path = Path(installer_path).resolve()
    if not path.is_file():
        raise SystemExit(f"Installer not found: {path}")
    archive = CArchiveReader(str(path))
    missing = sorted(REQUIRED_ENTRIES.difference(archive.toc))
    if missing:
        raise SystemExit("Installer archive is incomplete: " + ", ".join(missing))
    private_entries = []
    for name in archive.toc:
        normalized = name.replace("\\", "/").lower()
        parts = tuple(part for part in normalized.split("/") if part)
        if "instance" in parts or (parts and parts[-1] in PRIVATE_FILE_NAMES):
            private_entries.append(name)
    if private_entries:
        raise SystemExit(
            "Installer archive contains private local data: "
            + ", ".join(sorted(private_entries))
        )
    print(f"Installer payload verified: {len(archive.toc)} archive entries")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_windows_installer.py <installer.exe>")
    verify(sys.argv[1])
