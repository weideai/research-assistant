# R/LAB Research Assistant

一个面向医学研究生和实验室工作的科研助手，可在 Windows 本地运行，也可用 Docker 部署到公网。它不是简单的 Todo List，而是把任务、实验计划、实验记录、样本库存、论文返修和 AI 笔记整理放进同一个工作台。

仓库内已生成可分发安装文件：Windows 使用 `release/ResearchAssistant-Windows-Setup.exe`，Linux 使用 `release/ResearchAssistant-Linux-Installer.run`。安装说明和 SHA-256 校验值位于 `release/README.md`。

## 已实现功能

- 用户注册、登录、数据按账户隔离
- 任务增删改查、完成状态、优先级、分类与截止日期筛选
- 实验计划、含执行人/说明/完成日期的步骤管理，以及可查看和编辑的结构化实验记录
- 实验步骤、计划参数、关联样本和实验记录支持勾选、全选、批量修改与批量删除
- 步骤模板和记录模板彼此独立，可分别在对应页面创建、查看、编辑和调用
- 样本与实验双向追溯，记录样本用途、使用量和备注
- 实验计划参数与单次记录参数，可按“名称 / 数值 / 单位 / 说明”结构化保存
- 单个实验可自由选择导出 Markdown、Word、Excel、JSON，或包含报告、结构化数据、清单和原始文件的 ZIP 完整归档
- 每条实验记录可批量导入图片、任意格式文件或整个文件夹，并按实验和日期分类管理
- 附件支持 SHA-256 完整性校验、标签、说明和同路径版本号
- 科研、科技、极简和可爱四套主题，可独立切换日间/夜间模式并上传个人背景
- 样本编号、来源、数量、精确存放位置、状态、搜索与 CSV 导出
- 论文状态、投稿/返修日期、Reviewer 意见与回复草稿
- 任务完成率、实验状态、本月实验结果统计
- 可在网页中自由配置 API URL、API Key 和模型，支持读取模型列表
- AI 对话可自由勾选一个或多个历史实验，并仅基于所选记录、参数和附件说明进行比较、总结与引用
- 每个账号可创建多个私人知识库，上传任意格式文件或添加文本资料；对话时可自由勾选知识库，并通过 `[K编号]` 查看引用来源
- 科研助手提示词可按账号自定义并随时重置为默认值；固定的安全规则、人工核验和确认后写入机制不能被自定义提示词覆盖
- AI 可统一管理当前实验的信息、步骤、参数、样本关联和记录，也可管理记录参数及附件元数据；所有写入先展示差异并确认，页面已变化时拒绝覆盖
- AI 输入框支持 Enter 发送、Shift+Enter 换行；助手可拖动、缩放、左右停靠、最大化或弹出为独立窗口，关闭悬浮窗后当前请求继续运行，完成时显示页内提醒
- AI 对话采用双栏工作区，可新建、搜索、切换、重命名和删除历史聊天；回复支持复制、引用、删除与重新生成，最后一轮用户提问可编辑后重发
- 修改提案可逐项勾选确认，已应用且页面未再次变化的提案可以撤销
- 可按日期和实验生成可编辑的 Office PowerPoint 周报，自动排版进展、参数证据、结果图片和人工核验清单
- API Key 加密保存；未启用外部 API 时自动使用本地规则
- 响应式桌面/移动端界面、CSRF 防护和关键流程测试
- 邀请制注册、密码重置、登录锁定、会话撤销和审计日志
- 管理员后台、角色权限、PostgreSQL 迁移和 Docker/Caddy 公网部署

## 在 VS Code 中运行

1. 用 VS Code 打开 `research_assistant` 文件夹。
2. 安装 Microsoft Python 扩展。
3. 在 VS Code 终端执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

如果 PowerShell 阻止激活脚本，可以不激活，直接执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

4. 按 `F5` 并选择“运行 Research Assistant”，或执行 `python run.py`。
5. 浏览器打开 <http://127.0.0.1:5001>，先创建本地账户。

数据库会在首次运行时自动创建于 `instance/research.db`。

### 本地端口

项目当前统一使用 `5001` 作为本地开发端口，完整地址是 <http://127.0.0.1:5001>。

- 使用 `python run.py` 启动时，默认端口定义在 `run.py`，也可以在项目根目录的 `.env` 中设置 `PORT=5001`。
- 使用 VS Code 的 `F5` 启动时，端口位于 `.vscode/launch.json` 的 `--port` 参数。
- 服务启动后，终端中的 `Running on http://127.0.0.1:端口` 就是实际访问地址。
- Windows 也可以执行 `netstat -ano | findstr :5001`，检查该端口是否正在监听。

如需改成 `5050`，请将 `.env` 写为 `PORT=5050`，并把 `.vscode/launch.json` 中的 `--port` 同步改为 `5050`。修改端口后需要停止并重新启动服务。

## Windows EXE 安装版

项目可以构建为 Windows 本地安装程序。安装版仍在本机运行，通过浏览器打开 `127.0.0.1:5001`，不会把数据上传到网络。

安装后的目录：

- 程序：`%LOCALAPPDATA%\Programs\ResearchAssistant`
- 数据库、附件和本地密钥：`%LOCALAPPDATA%\ResearchAssistant\data`
- 运行日志：`%LOCALAPPDATA%\ResearchAssistant\logs\desktop.log`

构建安装包：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\scripts\build_windows_installer.ps1
```

生成的安装程序位于 `dist\windows\ResearchAssistant-Setup.exe`。双击后选择“快速安装”，程序会创建桌面和开始菜单快捷方式。如果从当前项目的 `dist\windows` 目录直接安装，并且安装数据目录还是空的，安装程序会自动复制当前 `instance` 中的账户、实验记录、附件和密钥；重复安装或升级不会覆盖已经存在的安装版数据。

启动后会自动打开网页，并在 Windows 右下角显示 R/LAB 托盘图标。托盘菜单可重新打开网页、打开数据目录或退出本地服务。Windows“已安装的应用”中可以卸载程序；卸载默认保留科研数据，避免误删实验记录。

## Linux 安装包

Linux 不使用 Windows `.exe` 格式。项目生成以下两种 Linux x86-64 产物：

- `research-assistant_1.0.0_amd64.deb`：适用于 Ubuntu、Debian、Linux Mint 等 Debian 系发行版。
- `research-assistant_1.0.0_linux_amd64.tar.gz`：包含独立可执行文件，适用于其他常见 x86-64 Linux 发行版。
- `ResearchAssistant-Linux-Installer.run`：可在 Windows 上预先生成的 Linux 安装器；在目标 Linux 中创建独立 Python 环境，适合暂时没有 Linux 构建机时使用，需要目标电脑安装 Python 3、`python3-venv` 并能下载 Python 依赖。

必须在 Linux 环境中构建，因为 PyInstaller 不支持从 Windows 交叉生成 Linux 二进制文件：

```bash
python3 -m venv .venv-linux
source .venv-linux/bin/activate
python -m pip install -r requirements.txt PyInstaller==6.16.0
chmod +x scripts/build_linux_packages.sh
./scripts/build_linux_packages.sh
```

安装 `.deb`：

```bash
sudo apt install ./dist/linux/research-assistant_1.0.0_amd64.deb
research-assistant
```

Linux 版默认后台运行并打开 <http://127.0.0.1:5001>。可使用 `research-assistant --status` 查看状态，使用 `research-assistant --stop` 停止服务。数据保存在 `~/.local/share/research-assistant/data`，卸载程序不会删除该目录。

在 Windows 上生成可交付给 Linux 的 `.run` 安装器：

```powershell
.\scripts\build_linux_source_installer.ps1
```

复制到 Linux 后安装：

```bash
chmod +x ResearchAssistant-Linux-Installer.run
./ResearchAssistant-Linux-Installer.run
```

仓库中的 `.github/workflows/build-desktop-installers.yml` 会在 GitHub Actions 中同时生成 Windows 安装包和 Linux `.deb`/压缩包。进入 GitHub 仓库的 Actions 页面，手动运行 `Build desktop installers` 即可下载两个平台的构建产物。

## 本地备份与恢复

创建完整备份：

```powershell
.\.venv\Scripts\python.exe -m flask --app run.py backup-local
```

备份默认保存在 `instance/backups/`，包含 SQLite 数据库、实验附件、AI 附件、背景和本地密钥。该 ZIP 包含账户及科研数据，必须存放在受保护的位置，不要上传到公开 GitHub 仓库。

恢复前先停止正在运行的 Flask 服务，然后执行：

```powershell
.\.venv\Scripts\python.exe -m flask --app run.py restore-local --archive "instance\backups\research-assistant-时间.zip"
```

恢复前程序会自动在 `instance/` 中保留一份当前数据库副本。恢复完成后重新启动服务并登录。

## 配置 AI（可选）

登录后打开侧栏的“API 设置”，可以为当前账户填写：

- API 根地址，例如 `https://api.openai.com/v1`
- 完整 Chat Completions 地址，例如 `http://127.0.0.1:1234/v1/chat/completions`
- API Key；无需鉴权的本地服务可以留空
- 模型名称，也可以通过“测试并读取模型”获取建议列表

网页配置按账户保存，优先级高于环境变量。API Key 使用独立的 `CREDENTIAL_ENCRYPTION_KEY` 加密，页面不会回显明文。本地开发未提供该变量时，程序会使用 `instance/credential_key`；修改或删除密钥后，需要重新输入已保存的 API Key。备份本地数据库时也应同时备份这个文件。生产环境必须显式配置 `CREDENTIAL_ENCRYPTION_KEY`，且不能与 `SECRET_KEY` 相同。

环境变量仍可作为全局后备配置。复制 `.env.example` 为 `.env`，然后填写：

```dotenv
SECRET_KEY=请替换为随机长字符串
CREDENTIAL_ENCRYPTION_KEY=请替换为另一段随机长字符串
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-5.6-terra
```

也可以使用兼容 `/v1/chat/completions` 的其他服务。本项目为了兼容多种服务使用 Chat Completions；OpenAI 官方对全新的 OpenAI 专用项目更推荐 Responses API。实验笔记可能包含敏感科研或患者信息，请确认所用服务符合课题组、医院和伦理要求；不要上传可识别患者身份的信息。

## 架构说明

一次典型请求会按以下路径流动：

```text
浏览器表单
   ↓
Flask Blueprint 路由（auth.py / main.py / admin.py）
   ↓
SQLAlchemy 模型（models.py） ──→ 本地 SQLite / 生产 PostgreSQL
   ↓
Jinja 模板 + CSS/JavaScript 返回页面
```

AI 请求在业务层之外多一层服务封装：

```text
AI 页面 → main.py 读取当前用户 ApiSetting
       → secrets.py 解密 API Key
       → ai_service.py 生成兼容请求
       → 用户配置的 /chat/completions
```

- `app/__init__.py`：应用工厂，创建 Flask 应用并装配数据库、登录和 CSRF。
- `app/models.py`：持久化模型与关系，是数据结构的唯一来源。
- `app/auth.py`：注册、登录、退出，只负责身份相关流程。
- `app/admin.py`：邀请、用户角色、账户状态、会话撤销和审计查询。
- `app/main.py`：任务、实验、样本、论文、统计、AI 和设置等业务路由。
- `app/security.py`：密码规则、重置令牌、登录锁定、审计记录与权限辅助。
- `app/mailer.py`：邀请和密码重置邮件，开发环境可显示一次性链接。
- `app/commands.py`：创建和提升系统管理员的 Flask CLI 命令。
- `app/ai_service.py`：URL 规范化、鉴权、模型读取、请求与错误处理。
- `app/secrets.py`：使用独立凭据密钥加密和解密 API Key。
- `migrations/`：Alembic 数据库结构版本；生产启动时自动升级。
- `app/templates/`：Jinja 页面；`app/static/`：共享样式与轻量交互。
- `tests/`：使用内存 SQLite 验证路由、权限和 API 契约。

## 实验导出格式

实验详情页通过“导出格式”下拉框选择输出内容：

- Markdown：UTF-8 文本报告，适合继续编辑和版本管理
- Word（DOCX）：排版后的实验报告，适合打印、汇报和交接
- Excel（XLSX）：分别用实验信息、样本、计划参数、步骤、记录、记录参数和附件清单工作表保存结构化数据
- JSON：包含完整实验结构和附件元数据，适合迁移、备份或后续程序处理
- ZIP 完整归档：包含 Markdown 报告、JSON 数据、附件清单和原始附件文件

报告按以下顺序组织：

1. 实验名称、编号、状态、负责人和计划日期。
2. 批次、重复类型、实验分组、关联样本与计划参数。
3. 实验目的及按步骤顺序排列的执行信息。
4. 按日期正序排列的结构化参数、实验条件、过程、结果和结论备注。
5. 附件分类、版本和 SHA-256 校验值。

ZIP 归档额外包含 `experiment.json`、`file-manifest.csv` 和全部原始附件，适合提交、交接和离线归档；Markdown 可以在 VS Code、Typora 和常见笔记软件中继续编辑。Word、Excel 和 JSON 只保存附件元数据，只有 ZIP 会包含原始附件文件。

## 实验结果与数据文件

实验记录详情页支持选择多个文件或整个文件夹。系统保留原始文件夹相对路径，并按“账号 / 实验 / 记录日期 / 记录”存储，再按图片、数据、文档、压缩包和其他类型展示。PNG、JPEG、WebP 和 GIF 可在页面预览，其他格式只提供下载，不会作为网页静态文件执行。

本地模式默认不限制单个文件或单次请求大小，文件按原始可读名称保存，实验记录页可直接在 Windows 资源管理器中打开对应目录。需要限制公网流量时，可给 `MAX_ATTACHMENT_MB` 和 `MAX_UPLOAD_REQUEST_MB` 设置正整数；`0` 表示应用层不限制。部署时应将 `instance/uploads/` 与数据库一同备份。

每个登录页面右下角都有 AI 悬浮助手。它支持持久聊天、任意格式附件、聊天记录 Markdown 导出，以及基于当前实验或实验记录生成结构化修改提案。提案会先展示修改前后差异，只有用户确认后才写入数据库。官方 OpenAI API 可使用内置网页检索并返回 URL 引用；其他 OpenAI-compatible API 保持普通聊天兼容，不会伪造联网引用。文本、CSV、JSON、Markdown 和 DOCX 会提取有限长度的文字节选作为模型上下文，其他格式会保留文件名、类型和大小并存入本地目录。

在实验详情页展开“批量管理”后，可勾选任意步骤、计划参数、样本关联或历史记录统一处理。AI 助手接受“整理当前实验全部内容”“把选中的历史实验总结成下一次计划”等自然语言指令；涉及页面写入时，它只生成可审阅的修改提案。确认前不会改动数据库，提案生成后若页面内容又被人工修改，旧提案会失效，避免覆盖新数据。

## 步骤模板、记录模板、AI 历史与 PowerPoint

实验详情页的“实验步骤”区域可以把当前步骤单独保存为步骤模板。模板保存步骤标题、说明和相对日期，不携带实验目的、计划参数、样本或历史结果；可在步骤模板详情页查看、编辑，并以“追加”或“替换”方式调用到实验中。实验列表顶部也可从步骤模板创建一个带步骤的新实验。

已保存的实验记录详情页可以把实验条件、实验过程、结论备注和结构化参数保存为记录模板，不保存日期、实验人员、成功/失败结论或附件。记录模板可单独查看和编辑，调用时只预填目标实验的“新增实验记录”表单，用户核对后再保存。

打开右下角 AI 助手后，展开“选择实验历史”，可以自由勾选一个或多个实验。AI 只会加载所选实验的记录、结构化参数和附件说明；内部引用使用 `[R编号]` 并链接回具体实验或记录。页面修改仍需先查看差异并确认保存。输入框按 Enter 发送、Shift+Enter 换行；请求运行时可以用 × 收起悬浮窗，浏览器会继续等待结果，完成后通过右下角提醒和标签页标题通知。外观按钮与 AI 按钮分开放置。

### 私人知识库与助手提示词

1. 打开右下角 AI 助手，展开“知识库与助手设置”。
2. 填写名称、用途和可选的知识库使用说明，点击“创建知识库”。
3. 在知识库条目中上传资料，或直接添加一段文本。文件保存在本机 `instance/uploads/knowledge/`，数据库只记录归属和元数据；不同账号不能查看或调用彼此的知识库。
4. 在“本次对话使用的知识库”中勾选需要的一个或多个知识库。AI 会把可提取的内容加入当前对话，并用 `[K编号]` 标出来源；无法解析正文的格式仍会保留文件名、类型和大小供管理。
5. 在“科研助手提示词”中填写研究领域、输出结构、术语或工作偏好并保存。点击“重置默认”会删除当前账号的自定义内容，立即恢复系统默认提示词。

知识库文件和提示词都属于本地用户数据，备份时应与 `instance/research.db` 一并保护，不要提交到公开仓库。自定义提示词不能关闭引用要求、人工核验、差异确认或用户数据隔离。

### AI 窗口与修改确认

- 助手默认使用“历史聊天 + 当前对话”双栏布局；窄窗口和手机会把历史聊天变成可收起的侧边抽屉。历史聊天支持搜索、新建、切换、重命名和整组删除。
- 拖动标题栏可以移动助手，拖动边缘可以调整大小；顶部按钮支持左/右停靠、最大化和独立窗口。窗口位置与大小保存在当前浏览器中。
- AI 回复可以复制、引用、删除或重新生成；最后一轮用户提问可以编辑并重新生成对应回复。为避免后续上下文与旧内容冲突，更早的提问不会被直接改写。
- 已经应用到页面且尚未撤销的 AI 提案不能被删除或重新生成。运行中的请求会显示耗时并提供停止按钮；停止会立即结束浏览器等待，但外部 API 已经开始的请求可能仍会在服务端完成清理。
- AI 生成页面修改时，可逐项勾选需要应用的差异。保存后可在对应提案上撤销；如果页面后来被人工修改，系统会拒绝撤销，避免覆盖较新的内容。
- 删除实验记录或附件文件等涉及物理文件的操作不可保证完整恢复，因此这类提案会明确标记为不可撤销。

常用快捷键：`Ctrl+N` 新建聊天，`Ctrl+K` 聚焦输入框，`Ctrl+Shift+L` 显示或收起历史聊天，`Alt+↑/↓` 切换相邻会话，`Esc` 关闭窄屏历史抽屉。macOS 可使用 `Command` 代替 `Ctrl`。

侧栏“周报 PPT”可选择日期范围和实验，生成标准 `.pptx` 文件。文字、形状和实验结果图片可在 Microsoft PowerPoint 中继续编辑。这一方式不绑定某个 Office/ChatGPT 插件；未来接入 Office 插件时，可以继续复用同一份数据范围和 PPTX 输出层。

PPT 生成需要 Node.js 和 `@oai/artifact-tool` 演示文稿运行时。在当前 Codex 本地环境中会自动发现；迁移到其他电脑时可配置：

```dotenv
PRESENTATION_NODE_PATH=C:\\path\\to\\node.exe
ARTIFACT_TOOL_MODULE=C:\\path\\to\\artifact_tool.mjs
```

如果运行时缺失，网页会显示明确错误，不会修改实验数据。

## 测试

```powershell
pytest -q
```

测试覆盖登录、邀请注册、密码重置与锁定、管理员权限、会话撤销、任务 CRUD、步骤模板、记录模板、实验步骤与记录、批量管理、AI 复合页面提案与冲突保护、跨账户隔离、AI 历史范围、PPT 数据范围、只读角色、AI URL 安全和多格式导出。

## 项目结构

```text
research_assistant/
├─ app/
│  ├─ __init__.py       # 应用工厂、扩展初始化
│  ├─ models.py         # SQLAlchemy 数据模型
│  ├─ auth.py           # 注册、登录、重置密码
│  ├─ admin.py          # 管理员后台
│  ├─ security.py       # 账户安全与审计
│  ├─ mailer.py         # SMTP 邮件
│  ├─ commands.py       # 管理员 CLI 命令
│  ├─ main.py           # 业务路由
│  ├─ ai_service.py     # AI 接口与本地降级
│  ├─ presentation_service.py # PowerPoint 数据交接与生成进程
│  ├─ secrets.py        # API Key 加密与解密
│  ├─ templates/        # Jinja 页面
│  └─ static/           # CSS 与 JavaScript
├─ tests/               # pytest 测试
├─ migrations/          # Alembic 数据库迁移
├─ scripts/build_weekly_presentation.mjs # 可编辑实验周报 PPTX
├─ scripts/backup.sh    # PostgreSQL 备份脚本
├─ .vscode/             # F5 调试配置
├─ Dockerfile
├─ docker-compose.yml
├─ Caddyfile            # HTTPS 反向代理
├─ DEPLOYMENT.md        # 公网部署手册
├─ requirements.txt
└─ run.py
```

## 当前边界

项目同时支持两种运行方式：本地模式使用 SQLite，适合个人学习和科研记录；公网生产模式使用 PostgreSQL、Redis、Gunicorn、Caddy、邀请注册、管理员后台、审计日志和自动备份脚本。完整操作见 [DEPLOYMENT.md](DEPLOYMENT.md)。

当前业务数据仍按个人账户隔离，尚未实现实验室成员共享同一个项目，也未实现医院统一身份认证。涉及患者数据或真实临床资料前，必须完成服务器地区、服务商协议、医院制度、伦理和数据脱敏评估。
