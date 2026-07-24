# R/LAB Research Assistant V2.0.0 Installers

## Windows

File: `ResearchAssistant-Windows-Setup.exe`

Double-click the installer. It installs the application for the current Windows user, creates Desktop and Start Menu shortcuts, and keeps research data under `%LOCALAPPDATA%\ResearchAssistant\data`.

The release installer contains application code only. It does not include the developer's accounts, database, attachments, knowledge-base files, `.env`, API keys, or local credential key. Each installation creates and keeps its own local data directory. The Windows installer opens `http://127.0.0.1:5001`; it does not expose the application to the public internet.

## Linux

File: `ResearchAssistant-Linux-Installer.run`

Linux does not use Windows `.exe` files. Install with:

```bash
chmod +x ResearchAssistant-Linux-Installer.run
./ResearchAssistant-Linux-Installer.run
```

This installer requires Python 3, `python3-venv`, and network access for Python dependencies. Research data is stored under `~/.local/share/research-assistant/data`.

The Linux source payload also excludes `instance/`, `.env`, build output, release output, and local virtual environments.

Both installers preserve data during upgrades. The application backs up its SQLite database before a pending schema migration and writes a migration report; managed attachments and external linked originals are not moved or deleted by the migration.

## Integrity

Verify downloads against `SHA256SUMS.txt` before installation.

```powershell
Get-FileHash .\ResearchAssistant-Windows-Setup.exe -Algorithm SHA256
```

```bash
sha256sum -c SHA256SUMS.txt
```
