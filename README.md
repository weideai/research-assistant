# R/LAB Research Assistant

R/LAB 是面向个人科研实验人员的本地桌面应用，用来集中管理项目、实验记录、文献、文件、任务、日历和周期报告。应用采用 `pywebview + WebView2`，前端通过进程内 JavaScript Bridge 调用本地 Python 服务，正式桌面入口不会启动 HTTP Server 或监听 TCP 端口。

## 主要功能

- 项目工作台：集中查看项目概况、近期实验、任务、资料和报告。
- 实验记录：记录实验目的、背景、假设、材料、条件、步骤、过程、结果、分析、结论和下一步；允许先建立简要记录，后续逐步补充。
- 修订历史：定稿后继续修改会保留修订时间；修订原因可以选填。
- 文献与资料库：管理文献、笔记、附件和项目文件，支持 Zotero 本地同步、筛选、分页、跨页选择和批量操作。
- 任务与日历：按项目、状态和日期管理待办事项，在日历中查看实验安排和事件详情。
- 周报管理：以用户上传和整理的内容为中心管理周报，保留文件版本，并支持个人批注或指导意见。
- 导出与归档：支持 Word、PDF、Markdown 和 JSON 导出；导出中心提供查询、分页、跨页选择和批量导出，适合打印和实验室规范归档。
- 全局搜索与回收站：跨模块检索内容，并为常见删除操作提供恢复入口。
- 可选 AI 助手：配置服务后可辅助整理项目、实验记录、任务、日历、笔记和报告；未配置时不影响其他本地功能。
- 多套界面主题：内置明亮、深色、Swiss 和 Soft Lab 等界面风格。

## Windows 安装

推荐直接使用发布目录中的安装包：

1. 下载 `release/ResearchAssistant-Windows-Setup.exe`。
2. 双击安装，按提示完成操作。
3. 从桌面或开始菜单打开 R/LAB。

升级时直接运行新版本安装包，不要先卸载。安装器只替换程序文件，保留现有数据库和托管附件。安装前可校验文件完整性：

```powershell
Get-FileHash .\release\ResearchAssistant-Windows-Setup.exe -Algorithm SHA256
Get-Content .\release\SHA256SUMS.txt
```

## 从源码运行

环境要求：

- Windows 10/11
- Python 3.11 或更高版本
- Microsoft Edge WebView2 Runtime

在 PowerShell 中执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe desktop_main.py
```

`desktop_launcher.py` 是为旧快捷方式和构建脚本保留的兼容入口，新开发应使用 `desktop_main.py`。

## 快速使用

### 1. 建立项目

打开“项目”，新建一个研究项目并填写名称、研究目标和必要说明。项目是实验记录、文献、任务和报告的主要归属单位。

### 2. 建立实验记录

进入项目后选择“实验记录”，先填写标题、日期和最必要的实验信息即可保存。文件、下一步和修订原因不是强制项，可在实验推进过程中继续补充。

### 3. 整理资料

在“文献”“笔记”或“文件”中导入材料，并按项目关联。内容较多时可使用搜索、筛选、分页和批量选择。

### 4. 管理任务和日程

将下一步工作添加为任务或日历事件，设置项目、状态和日期。首页会显示近期任务及本周日程。

### 5. 制作周报或其他报告

进入“周报”，上传或选择本周材料，整理报告名称、周期、项目归属、正文和个人批注。替换文件时会保存为新版本，不会静默覆盖原文件。

### 6. 导出、打印和归档

在实验记录或导出中心选择目标内容和格式。实验室规范报告适合打印归档；Markdown 和 JSON 更适合长期备份或后续数据处理。

## 数据与隐私

R/LAB 默认采用本地优先模式。数据库、托管文件、日志和 WebView 配置保存在当前 Windows 用户目录：

| 内容 | 默认位置 |
|---|---|
| 数据库与托管资料 | `%LOCALAPPDATA%\ResearchAssistant\data` |
| 桌面日志 | `%LOCALAPPDATA%\ResearchAssistant\logs\desktop.log` |
| WebView 配置 | `%LOCALAPPDATA%\ResearchAssistant\webview-profile` |

- 发布包不包含用户数据库、附件、API Key、`.env` 或本地凭据。
- AI 功能默认不会在未配置服务的情况下运行；启用外部 AI 服务前，请自行确认数据使用和隐私政策。
- 不要把 `instance/`、`.env`、本地备份、实验附件或对话数据提交到 Git。
- 建议定期备份 `%LOCALAPPDATA%\ResearchAssistant\data`。

## 开发与测试

运行完整测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

检查桌面前端 JavaScript：

```powershell
node --check app\desktop_ui\desktop.js
node --check app\desktop_ui\desktop_research.js
node --check app\desktop_ui\desktop_resources.js
node --check app\desktop_ui\desktop_planning.js
node --check app\desktop_ui\desktop_system.js
```

构建 Windows 安装包：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\scripts\build_windows_installer.ps1
```

构建产物位于 `dist\windows\ResearchAssistant-Setup.exe`。

## 常见问题

### 应用无法打开

确认已安装 WebView2 Runtime，并检查 `%LOCALAPPDATA%\ResearchAssistant\logs\desktop.log`。从源码运行时，还应确认虚拟环境依赖安装完整。

### 升级后数据不见了

不要先卸载旧版本。确认当前 Windows 用户与之前一致，并检查 `%LOCALAPPDATA%\ResearchAssistant\data`。数据库迁移前应用会创建备份和迁移报告。

### AI 功能不可用

AI 是可选能力。进入设置页配置受支持的服务与密钥；如果不配置，项目、实验记录、资料、任务、报告和导出功能仍可正常使用。

### 如何备份或迁移

关闭应用后备份整个 `%LOCALAPPDATA%\ResearchAssistant\data` 目录。恢复时先保留现有目录副本，再将备份放回相同位置。

## 技术结构

- `desktop_main.py`：正式桌面入口。
- `app/desktop/`：原生窗口、单实例、运行时和 Bridge 协议。
- `app/desktop_ui/`：桌面界面与交互逻辑。
- `app/services/`：与界面无关的业务服务。
- `app/models.py`：数据模型。
- `migrations/`：数据库迁移。
- `packaging/windows/`：Windows 安装与升级逻辑。
- `tests/`：单元测试和集成测试。

## 许可证与第三方组件

仓库内第三方前端资源保留各自许可证说明，例如 `app/static/vendor/LUCIDE-LICENSE.txt`。项目发布或再分发前，请确认所有依赖许可证符合你的使用场景。
