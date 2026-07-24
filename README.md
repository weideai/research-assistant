# R/LAB Research Assistant

项目作者：面壁者 · [GitHub 仓库](https://github.com/weideai/research-assistant)

一个面向医学研究生和实验室工作的科研助手，可在 Windows 本地运行，也可用 Docker 部署到公网。V2 以“科研项目 → 实验计划 → 实验执行 → 过程记录”为主线，把任务、样本、文件证据、论文返修、汇报和 AI 辅助放进同一个可追溯工作台。

本次页面信息架构更新见 [更新日志](docs/UPDATE-LOG.md)，在 VS Code 中提交并推送到 GitHub 的步骤见 [更新与推送日志](docs/PUSH-LOG.md)。

仓库内已生成可分发安装文件：Windows 使用 `release/ResearchAssistant-Windows-Setup.exe`，Linux 使用 `release/ResearchAssistant-Linux-Installer.run`。安装说明和 SHA-256 校验值位于 `release/README.md`。

## 已实现功能

- 用户注册、登录、数据按账户隔离
- 科研项目总览，可在项目下统一管理任务、实验计划、实验执行、过程记录与文件证据
- 每次实验执行记录实际参数和实际使用样本，明确区分计划条件与真实执行条件
- 计划步骤只定义方案；每次实验执行拥有独立步骤快照、完成状态、实际执行人和完成日期，多次重复互不覆盖
- 过程记录支持草稿、定稿和修订；定稿后修改必须填写原因，并保留修改前后版本
- 任务增删改查、完成状态、优先级、分类与截止日期筛选
- 实验计划、含执行人/说明/完成日期的步骤管理，以及可查看和编辑的结构化过程记录
- 实验步骤、计划参数、关联样本和过程记录支持勾选、全选、批量修改与批量删除
- 步骤模板和记录模板彼此独立，可分别在对应页面创建、查看、编辑和调用
- 样本与实验双向追溯，记录样本用途、使用量和备注
- 实验计划参数与单次记录参数，可按“名称 / 数值 / 单位 / 说明”结构化保存
- 单个实验可自由选择导出 Markdown、Word、Excel、JSON，或包含报告、结构化数据、清单和原始文件的 ZIP 完整归档
- 每条过程记录可批量导入图片、任意格式文件或整个文件夹，并按实验和日期分类管理
- 文件可选择复制到应用托管目录，或只登记外部大文件/文件夹路径；外部原始文件永远不会被应用删除
- 附件支持 SHA-256 完整性校验、标签、说明和同路径版本号
- 科研、科技、极简和可爱四套主题，可独立切换日间/夜间模式并上传个人背景
- 样本编号、来源、数量、精确存放位置、状态、搜索与 CSV 导出
- 论文状态、投稿/返修日期、Reviewer 意见与回复草稿
- 任务完成率、实验状态、本月实验结果统计
- 通过账号菜单管理多个 API 预设，填写 URL 与 Key 后可拉取模型并选择当前模型
- AI 对话可自由勾选一个或多个历史实验，并仅基于所选记录、参数和附件说明进行比较、总结与引用
- 每个账号可创建多个私人知识库，上传任意格式文件或添加文本资料；对话时可自由勾选知识库，并通过 `[K编号]` 查看引用来源
- 科研助手提示词可按账号自定义并随时重置为默认值；固定的安全规则、人工核验和确认后写入机制不能被自定义提示词覆盖
- AI 可创建和修改科研项目、创建实验执行，管理当前实验计划的步骤/参数/样本、当前执行的实际参数/过程记录，以及记录参数和附件元数据；所有写入先展示差异并确认，页面已变化时拒绝覆盖
- AI 输入框支持 Enter 发送、Shift+Enter 换行；悬浮助手可拖动、缩放、左右停靠或最大化，关闭悬浮窗后当前请求继续运行，完成时显示页内提醒
- AI 对话采用双栏工作区，可新建、搜索、切换、重命名和删除历史聊天；回复支持复制、引用、删除与重新生成，最后一轮用户提问可编辑后重发
- 修改提案可逐项勾选确认，已应用且页面未再次变化的提案可以撤销
- 可按日期和实验生成可编辑的 Office PowerPoint 周报，自动排版进展、参数证据、结果图片和人工核验清单
- 内置证据优先周报、实验复盘和论文进展三套 PPT Skill；用户也可创建不执行脚本的声明式 Skill，导出前先预览证据范围
- 项目可导出为 `.ralab` 包，包含清单、结构化数据、模式版本和 SHA-256；托管附件随包复制，外部文件只保存链接元数据，API Key 不会导出
- 支持多个加密 API 预设，可从兼容接口拉取模型，并用图标区分视觉、推理、联网搜索和工具能力的声明、推测与未知状态
- AI 外发前展示 API 主机、模型、实验/知识库/文件范围和敏感词提醒；写入需确认差异，删除需再次输入确认文字
- AI 生成内容保存模型、提示词、上下文、生成时间和来源聊天，可定位回原始对话
- API Key 加密保存；未启用账号 API 预设时助手保持未连接，不会读取环境变量中的其他连接
- 响应式桌面/移动端界面、CSRF 防护和关键流程测试
- 邀请制注册、密码重置、登录锁定、会话撤销和审计日志
- 管理员后台、角色权限、PostgreSQL 迁移和 Docker/Caddy 公网部署
- 每 24 小时检查一次 GitHub Releases；只显示新版提醒，绝不静默下载或安装
- 删除内容进入回收站，支持恢复；永久删除托管副本需二次确认，外部原始文件不会被删除

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

生成的安装程序位于 `dist\windows\ResearchAssistant-Setup.exe`。双击后选择“快速安装”，程序会创建桌面和开始菜单快捷方式。如果从当前项目的 `dist\windows` 目录直接安装，并且安装数据目录还是空的，安装程序会自动复制当前 `instance` 中的账户、过程记录、附件和密钥；重复安装或升级不会覆盖已经存在的安装版数据。

启动后会自动打开网页，并在 Windows 右下角显示 R/LAB 托盘图标。托盘菜单可重新打开网页、打开数据目录或退出本地服务。Windows“已安装的应用”中可以卸载程序；卸载默认保留科研数据，避免误删过程记录。

## Linux 安装包

Linux 不使用 Windows `.exe` 格式。项目生成以下两种 Linux x86-64 产物：

- `research-assistant_2.0.0_amd64.deb`：适用于 Ubuntu、Debian、Linux Mint 等 Debian 系发行版。
- `research-assistant_2.0.0_linux_amd64.tar.gz`：包含独立可执行文件，适用于其他常见 x86-64 Linux 发行版。
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
sudo apt install ./dist/linux/research-assistant_2.0.0_amd64.deb
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

仓库中的 `.github/workflows/build-desktop-installers.yml` 会在 GitHub Actions 中同时生成 Windows 安装包和 Linux `.deb`/压缩包。手动运行工作流只生成可下载的 Actions 产物；推送 `v*` 标签时才会创建 GitHub Release，并附加 Windows 安装包、Linux 三种安装产物和 `SHA256SUMS.txt`。

## V2 数据与迁移

核心层级如下：

```text
科研项目 ResearchProject
  └─ 实验计划 Experiment
       └─ 实验执行 ExperimentBatch
            ├─ 实际参数 BatchParameter
            ├─ 实际样本 BatchSample
            └─ 过程记录 ExperimentRecord
                 ├─ 修订历史 RecordRevision
                 └─ 文件 ExperimentAttachment
```

桌面版启动时会检查数据库版本。确实需要升级时，程序先将 SQLite 数据库备份到本地数据目录的 `migration-backups/`，再执行迁移，并在 `migration-reports/` 写入包含旧版本、新版本、备份路径和结果的 JSON 报告。迁移不会移动或删除附件；失败时启动日志会给出可恢复的数据库备份位置。

## V2 页面信息架构

页面按科研工作的实际顺序组织，而不是按数据库表平铺：

```text
工作台 → 科研项目 → 实验计划 → 实验执行 → 过程记录 → 文件与导出
```

- “实验计划”页面只负责查找实验计划和开始创建；创建方式明确分为“空白创建”和“从步骤模板创建”。
- “模板中心”是独立入口，步骤模板与记录模板分栏显示；每个模板在列表中直接预览，可空白创建、编辑、复制、调用或删除。
- 实验计划详情按“概览 / 实验方案 / 实验执行”切换；过程记录只在所属实验执行中创建和管理。
- 记录详情按“阅读 / 文件与数据 / 编辑 / 模板与修订”切换，默认先阅读，不把编辑表单和附件管理叠在首屏。

完整的页面职责、用户流程和交互约束见 [`docs/UX-IA-V2.md`](docs/UX-IA-V2.md)。

`.ralab` 是项目交换包，不是整机备份。它适合在两台 Research Assistant 之间迁移某个科研项目；完整备份仍应使用下方的本地备份命令。外部链接指向的原始大文件不会被塞入 `.ralab` 包，导入后需要在目标电脑重新确认路径。

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

手工更新代码后，先备份，再检查并升级数据库结构：

```powershell
.\.venv\Scripts\python.exe -m flask --app run.py db current
.\.venv\Scripts\python.exe -m flask --app run.py db upgrade
.\.venv\Scripts\python.exe -m flask --app run.py db current
```

## 配置 AI（可选）

登录后点击侧栏底部的个人头像并打开“API 预设”，可以为当前账户创建和保存多个预设。页面不再提供单连接兼容表单，每个连接都作为独立预设管理。每个预设可填写：

- API 根地址，例如 `https://api.openai.com/v1`
- 完整 Chat Completions 地址，例如 `http://127.0.0.1:1234/v1/chat/completions`
- API Key；无需鉴权的本地服务可以留空
- 当前模型；可以通过“拉取模型”读取接口目录后选择，也可以手动填写模型 ID

模型旁的视觉、推理、联网搜索和工具图标会区分接口明确声明、按模型名称保守推测、明确不支持和未知。拉取模型后，当前模型的能力与判定来源会随预设保存，刷新页面不会退回名称猜测。标准 `/models` 接口通常只返回模型 ID，因此灰色“未知”是正常状态，并不等于不支持。联网搜索还受 API 服务商和应用接入方式限制，不会只凭模型名称对兼容服务显示为可用。

切换预设时敏感数据发送提醒会自动恢复开启。实验内容发给外部 API 前，助手会列出目标主机、模型、所选实验、知识库和附件文本范围；确认后才发送。此检查只描述应用准备发送的上下文，仍应避免输入可识别患者身份的信息。

网页中的 API 预设是助手唯一的连接来源；未启用默认预设时，助手会提示先配置，不会静默读取环境变量中的另一套连接。API Key 使用独立的 `CREDENTIAL_ENCRYPTION_KEY` 加密，页面不会回显明文。本地开发未提供该变量时，程序会使用 `instance/credential_key`；修改或删除密钥后，需要重新输入已保存的 API Key。备份本地数据库时也应同时备份这个文件。生产环境必须显式配置 `CREDENTIAL_ENCRYPTION_KEY`，且不能与 `SECRET_KEY` 相同。

复制 `.env.example` 为 `.env` 时，只需为账号会话和预设密钥加密准备两段彼此不同的随机值：

```dotenv
SECRET_KEY=请替换为随机长字符串
CREDENTIAL_ENCRYPTION_KEY=请替换为另一段随机长字符串
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
AI 悬浮助手 → main.py 读取当前用户激活的 ApiPreset（没有时保持未连接）
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

实验计划详情页通过“导出格式”下拉框选择输出内容：

- Markdown：UTF-8 文本报告，适合继续编辑和版本管理
- Word（DOCX）：排版后的实验报告，适合打印、汇报和交接
- Excel（XLSX）：分别用实验信息、样本、计划参数、步骤、实验执行、过程记录、记录参数和附件清单工作表保存结构化数据
- JSON：使用 schema v3 同时保存计划步骤、按实验执行分组的执行步骤与过程记录索引，适合迁移、备份或后续程序处理
- ZIP 完整归档：包含 Markdown 报告、JSON 数据、附件清单和原始附件文件

报告按以下顺序组织：

1. 实验计划名称、编号、状态、负责人和计划日期。
2. 各次实验执行的编号、重复类型、实验分组、实际参数和实际样本。
3. 实验目的、计划步骤，以及每次实验执行各自的步骤状态。
4. 在所属实验执行下，按日期正序排列过程记录的结构化参数、条件、操作、结果和结论备注。
5. 附件分类、版本和 SHA-256 校验值。

ZIP 归档额外包含 `experiment.json`、`file-manifest.csv` 和全部托管附件，文件按“执行编号 / 记录日期 / 记录 / 分类”组织，适合提交、交接和离线归档；外部大文件只写入清单，不会被复制。Markdown 可以在 VS Code、Typora 和常见笔记软件中继续编辑。Word、Excel 和 JSON 只保存附件元数据，只有 ZIP 会包含托管的原始附件文件。

所有格式都过滤已经移入回收站的过程记录和附件。数据库升级前若仍存在缺少实验执行归属的旧记录，普通实验导出会把它们放入 `HISTORY-UNASSIGNED` 兼容分组并明确提示；完整 `.ralab` 项目包会停止导出，避免静默漏掉数据。

## 实验结果与数据文件

过程记录详情页支持选择多个文件或整个文件夹。系统保留原始文件夹相对路径，并按“账号 / 实验计划 / 过程记录日期 / 过程记录”存储，再按图片、数据、文档、压缩包和其他类型展示。PNG、JPEG、WebP 和 GIF 可在页面预览，其他格式只提供下载，不会作为网页静态文件执行。

本地模式默认不限制单个文件或单次请求大小，文件按原始可读名称保存，过程记录页可直接在 Windows 资源管理器中打开对应目录。需要限制公网流量时，可给 `MAX_ATTACHMENT_MB` 和 `MAX_UPLOAD_REQUEST_MB` 设置正整数；`0` 表示应用层不限制。部署时应将 `instance/uploads/` 与数据库一同备份。

每个登录页面右下角都有唯一的 AI 悬浮助手入口。它支持持久聊天、任意格式附件、聊天记录 Markdown 导出，以及创建科研项目、管理实验计划、实验执行和过程记录的结构化修改提案。提案会先展示修改前后差异，只有用户确认后才写入数据库。官方 OpenAI API 可使用内置网页检索并返回 URL 引用；其他 OpenAI-compatible API 保持普通聊天兼容，不会伪造联网引用。文本、CSV、JSON、Markdown 和 DOCX 会提取有限长度的文字节选作为模型上下文，其他格式会保留文件名、类型和大小并存入本地目录。

在实验计划页可批量处理步骤、计划参数和样本要求；在实验执行页可批量处理本次过程记录。AI 助手接受“创建一个科研项目”“修改当前项目”“新建一次实验执行”“整理当前实验执行”“把选中的历史执行总结成下一次计划”等自然语言指令；新建实验计划时可在差异确认区明确选择所属科研项目。涉及页面写入时，它只生成可审阅的修改提案。确认前不会改动数据库，提案生成后若页面内容又被人工修改，旧提案会失效，避免覆盖新数据。

## 步骤模板、记录模板、AI 历史与 PowerPoint

实验计划详情页的“实验步骤”区域可以把当前步骤单独保存为步骤模板。模板保存步骤标题、说明和相对日期，不携带实验目的、计划参数、样本或历史结果；可在步骤模板详情页查看、编辑，并以“追加”或“替换”方式调用到实验计划中。实验计划列表顶部也可从步骤模板创建一个带步骤的新计划。

已保存的过程记录详情页可以把实验条件、实验过程、结论备注和结构化参数保存为记录模板，不保存日期、实验人员、成功/失败结论或附件。记录模板可单独查看和编辑，调用时先选择一次实验执行，再预填“添加过程记录”表单，用户核对后保存。

打开右下角 AI 助手后，展开“选择实验历史”，可以先选择实验计划，再精确选择其中的一次或多次实验执行。AI 只会加载所选范围内的执行参数、过程记录和附件说明；内部引用使用 `[R编号]` 并链接回具体实验执行或过程记录。页面修改仍需先查看差异并确认保存。输入框按 Enter 发送、Shift+Enter 换行；请求运行时可以用 × 收起悬浮窗，浏览器会继续等待结果，完成后通过右下角提醒和标签页标题通知。外观按钮与 AI 按钮分开放置。

### 私人知识库与助手提示词

1. 打开右下角 AI 助手，展开“知识库与助手设置”。
2. 填写名称、用途和可选的知识库使用说明，点击“创建知识库”。
3. 在知识库条目中上传资料，或直接添加一段文本。文件保存在本机 `instance/uploads/knowledge/`，数据库只记录归属和元数据；不同账号不能查看或调用彼此的知识库。
4. 在“本次对话使用的知识库”中勾选需要的一个或多个知识库。AI 会把可提取的内容加入当前对话，并用 `[K编号]` 标出来源；无法解析正文的格式仍会保留文件名、类型和大小供管理。
5. 在“科研助手提示词”中填写研究领域、输出结构、术语或工作偏好并保存。点击“重置默认”会删除当前账号的自定义内容，立即恢复系统默认提示词。

知识库文件和提示词都属于本地用户数据，备份时应与 `instance/research.db` 一并保护，不要提交到公开仓库。自定义提示词不能关闭引用要求、人工核验、差异确认或用户数据隔离。

### AI 窗口与修改确认

- 助手默认使用“历史聊天 + 当前对话”双栏布局；窄窗口和手机会把历史聊天变成可收起的侧边抽屉。历史聊天支持搜索、新建、切换、重命名和整组删除。
- 拖动标题栏可以移动助手，拖动边缘可以调整大小；顶部按钮支持左/右停靠和最大化。窗口位置与大小保存在当前浏览器中。
- AI 回复可以复制、引用、删除或重新生成；最后一轮用户提问可以编辑并重新生成对应回复。为避免后续上下文与旧内容冲突，更早的提问不会被直接改写。
- 已经应用到页面且尚未撤销的 AI 提案不能被删除或重新生成。运行中的请求会显示耗时并提供停止按钮；停止会立即结束浏览器等待，但外部 API 已经开始的请求可能仍会在服务端完成清理。
- AI 生成页面修改时，可逐项勾选需要应用的差异。保存后可在对应提案上撤销；如果页面后来被人工修改，系统会拒绝撤销，避免覆盖较新的内容。
- 删除过程记录或附件文件等涉及物理文件的操作不可保证完整恢复，因此这类提案会明确标记为不可撤销。

常用快捷键：`Ctrl+N` 新建聊天，`Ctrl+K` 聚焦输入框，`Ctrl+Shift+L` 显示或收起历史聊天，`Alt+↑/↓` 切换相邻会话，`Esc` 关闭窄屏历史抽屉。macOS 可使用 `Command` 代替 `Ctrl`。

侧栏“汇报”可选择日期范围和实验计划，生成标准 `.pptx` 文件。文字、形状和实验结果图片可在 Microsoft PowerPoint 中继续编辑。这一方式不绑定某个 Office/ChatGPT 插件；未来接入 Office 插件时，可以继续复用同一份数据范围和 PPTX 输出层。

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
│  ├─ ai_service.py     # API URL 规范化、模型发现与兼容请求
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
