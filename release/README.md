# R/LAB Research Assistant V2.5.2 Windows 安装包

当前安装包提供独立 WebView2 桌面应用，使用进程内 JavaScript Bridge，不启动浏览器，也不监听 HTTP/TCP 端口。产品核心层级为“项目 -> 实验记录”，并包含文献与 Zotero 本地同步、资料库、笔记、任务、日历、周报文件管理、PPTX、悬浮 AI 助手、全文搜索、导出、回收站和设置。实验记录在独立记录编辑页中编辑；导出中心支持查询、分页、跨页选择以及 Word/PDF/Markdown/JSON 批量导出。项目、文献、任务与周报支持筛选、分页、跨页选择和批量操作。首页会直接显示本周日程，点击日期可进入对应日历。

AI 助手可写入项目、实验记录、任务、日历事件、笔记、周报正文和周报批注。选中字段后直接应用，不设置风险确认层；每次应用均保留变更记录并可撤销。

界面内置 `ide-light`、`ide-dark`、`swiss` 和 `soft-lab` 四套皮肤。

## Windows

File: `ResearchAssistant-Windows-Setup.exe`

双击安装包即可为当前 Windows 用户安装，并创建桌面和开始菜单快捷方式。研究数据保存在 `%LOCALAPPDATA%\ResearchAssistant\data`。

发布包只包含应用程序，不包含开发者账号、数据库、附件、知识库文件、`.env`、API Key 或本地凭据密钥。每次安装都会创建并使用自己的本地数据目录。

升级已有版本时直接运行新的安装包，不要先卸载。安装器会停止本机应用进程、暂存新程序文件、只替换程序目录、保留数据目录并重建快捷方式。`install-info.json` 会记录本次是新安装还是升级，以及升级前版本。

升级流程保留研究数据。应用会在待执行的 SQLite Schema 迁移前备份数据库并生成迁移报告；托管附件和外部链接原件不会被迁移过程移动或删除。

## Integrity

安装前请使用 `SHA256SUMS.txt` 校验文件：

```powershell
Get-FileHash .\ResearchAssistant-Windows-Setup.exe -Algorithm SHA256
```
