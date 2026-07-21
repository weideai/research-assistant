# R/LAB Research Assistant Installers

## Windows

File: `ResearchAssistant-Windows-Setup.exe`

Double-click the installer. It installs the application for the current Windows user, creates Desktop and Start Menu shortcuts, and keeps research data under `%LOCALAPPDATA%\ResearchAssistant\data`.

## Linux

File: `ResearchAssistant-Linux-Installer.run`

Linux does not use Windows `.exe` files. Install with:

```bash
chmod +x ResearchAssistant-Linux-Installer.run
./ResearchAssistant-Linux-Installer.run
```

This installer requires Python 3, `python3-venv`, and network access for Python dependencies. Research data is stored under `~/.local/share/research-assistant/data`.

## Integrity

Verify downloads against `SHA256SUMS.txt` before installation.

```powershell
Get-FileHash .\ResearchAssistant-Windows-Setup.exe -Algorithm SHA256
```

```bash
sha256sum -c SHA256SUMS.txt
```
