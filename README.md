# R/LAB Research Assistant

一个面向医学研究生和实验室工作的科研助手，可在 Windows 本地运行，也可用 Docker 部署到公网。它不是简单的 Todo List，而是把任务、实验计划、实验记录、样本库存、论文返修和 AI 笔记整理放进同一个工作台。

## 已实现功能

- 用户注册、登录、数据按账户隔离
- 任务增删改查、完成状态、优先级、分类与截止日期筛选
- 实验计划、含执行人/说明/完成日期的步骤管理，以及可查看和编辑的结构化实验记录
- 步骤模板和记录模板彼此独立，可分别在对应页面创建、查看、编辑和调用
- 样本与实验双向追溯，记录样本用途、使用量和备注
- 实验计划参数与单次记录参数，可按“名称 / 数值 / 单位 / 说明”结构化保存
- 单个实验可导出 Markdown 报告或包含报告、清单和原始文件的 ZIP 完整归档
- 每条实验记录可批量导入图片、任意格式文件或整个文件夹，并按实验和日期分类管理
- 附件支持 SHA-256 完整性校验、标签、说明和同路径版本号
- 科研、科技、极简和可爱四套主题，可独立切换日间/夜间模式并上传个人背景
- 样本编号、来源、数量、精确存放位置、状态、搜索与 CSV 导出
- 论文状态、投稿/返修日期、Reviewer 意见与回复草稿
- 任务完成率、实验状态、本月实验结果统计
- 可在网页中自由配置 API URL、API Key 和模型，支持读取模型列表
- AI 对话可自由勾选一个或多个历史实验，并仅基于所选记录、参数和附件说明进行比较、总结与引用
- AI 输入框支持 Enter 发送、Shift+Enter 换行；关闭悬浮窗后当前请求继续运行，完成时显示页内提醒
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
5. 浏览器打开 <http://127.0.0.1:5000>，先创建本地账户。

数据库会在首次运行时自动创建于 `instance/research.db`。

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

实验详情页可下载 UTF-8 Markdown 报告，也可下载 ZIP 完整归档。报告按以下顺序组织：

1. 实验名称、编号、状态、负责人和计划日期。
2. 批次、重复类型、实验分组、关联样本与计划参数。
3. 实验目的及按步骤顺序排列的执行信息。
4. 按日期正序排列的结构化参数、实验条件、过程、结果和结论备注。
5. 附件分类、版本和 SHA-256 校验值。

ZIP 归档额外包含 `file-manifest.csv` 和全部原始附件，适合提交、交接和离线归档；Markdown 可以在 VS Code、Typora 和常见笔记软件中继续编辑。

## 实验结果与数据文件

实验记录详情页支持选择多个文件或整个文件夹。系统保留原始文件夹相对路径，并按“账号 / 实验 / 记录日期 / 记录”存储，再按图片、数据、文档、压缩包和其他类型展示。PNG、JPEG、WebP 和 GIF 可在页面预览，其他格式只提供下载，不会作为网页静态文件执行。

本地模式默认不限制单个文件或单次请求大小，文件按原始可读名称保存，实验记录页可直接在 Windows 资源管理器中打开对应目录。需要限制公网流量时，可给 `MAX_ATTACHMENT_MB` 和 `MAX_UPLOAD_REQUEST_MB` 设置正整数；`0` 表示应用层不限制。部署时应将 `instance/uploads/` 与数据库一同备份。

每个登录页面右下角都有 AI 悬浮助手。它支持持久聊天、任意格式附件、聊天记录 Markdown 导出，以及基于当前实验或实验记录生成结构化修改提案。提案会先展示修改前后差异，只有用户确认后才写入数据库。官方 OpenAI API 可使用内置网页检索并返回 URL 引用；其他 OpenAI-compatible API 保持普通聊天兼容，不会伪造联网引用。文本、CSV、JSON、Markdown 和 DOCX 会提取有限长度的文字节选作为模型上下文，其他格式会保留文件名、类型和大小并存入本地目录。

## 步骤模板、记录模板、AI 历史与 PowerPoint

实验详情页的“实验步骤”区域可以把当前步骤单独保存为步骤模板。模板保存步骤标题、说明和相对日期，不携带实验目的、计划参数、样本或历史结果；可在步骤模板详情页查看、编辑，并以“追加”或“替换”方式调用到实验中。实验列表顶部也可从步骤模板创建一个带步骤的新实验。

已保存的实验记录详情页可以把实验条件、实验过程、结论备注和结构化参数保存为记录模板，不保存日期、实验人员、成功/失败结论或附件。记录模板可单独查看和编辑，调用时只预填目标实验的“新增实验记录”表单，用户核对后再保存。

打开右下角 AI 助手后，展开“选择实验历史”，可以自由勾选一个或多个实验。AI 只会加载所选实验的记录、结构化参数和附件说明；内部引用使用 `[R编号]` 并链接回具体实验或记录。页面修改仍需先查看差异并确认保存。输入框按 Enter 发送、Shift+Enter 换行；请求运行时可以用 × 收起悬浮窗，浏览器会继续等待结果，完成后通过右下角提醒和标签页标题通知。外观按钮与 AI 按钮分开放置。

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

测试覆盖登录、邀请注册、密码重置与锁定、管理员权限、会话撤销、任务 CRUD、步骤模板、记录模板、实验步骤与记录、跨账户隔离、AI 历史范围、PPT 数据范围、只读角色、AI URL 安全和 CSV 导出。

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
