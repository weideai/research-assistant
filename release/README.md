# R/LAB Research Assistant V2.5.2 Installers

本版本包含实验工作台、本地实验文件中心、实验报告卡片与翻页阅读、单条记录 PDF/Word 导出、周报资料库、AI 助手响应式界面，以及按实验执行组织的完整 ZIP 归档。文件中心支持分页、全选本页、全选全部匹配结果、批量编辑、批量下载和批量移入回收站；周报与回收站列表也已改为分页加载。实验报告导出的文字和表头对比度已增强，原始数据区域最多展示两张无文件名的核心缩略图，其余内容只以一个完整实验文件夹摘要呈现；PDF 和 Word 均不写入具体附件名称。论文与统计模块已移除。

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
