# R/LAB Research Assistant V2.5.3 Installers

本版本主要变更：**导航层级扁平化**——科研项目从独立页面降级为实验计划的筛选标签，导航由 5 步缩短为 3 步（实验计划 → 实验批次 → 过程记录）。侧栏"实验台"更名为"实验计划"，直接进入实验列表页，项目创建/编辑/导出/导入功能迁移到实验计划页内。AI 助手同步移除项目级提案，专注实验计划与批次管理。macOS 安装包首次提供（.dmg 格式）。

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

## macOS

File: `ResearchAssistant-2.5.3.dmg`

macOS 首次提供安装包。双击 `.dmg` 文件，将 `ResearchAssistant.app` 拖入 `Applications` 文件夹。首次启动时，macOS 可能提示"未验证的开发者"——在系统设置 > 隐私与安全性中允许即可。研究数据存储在 `~/Library/Application Support/ResearchAssistant/data`。

Both installers preserve data during upgrades. The application backs up its SQLite database before a pending schema migration and writes a migration report; managed attachments and external linked originals are not moved or deleted by the migration.

## Integrity

Verify downloads against `SHA256SUMS.txt` before installation.

```powershell
Get-FileHash .\ResearchAssistant-Windows-Setup.exe -Algorithm SHA256
```

```bash
sha256sum -c SHA256SUMS.txt
```
