# R/LAB Research Assistant

一个面向医学研究生和实验室工作的科研助手，可在 Windows 本地运行，也可用 Docker 部署到公网。它不是简单的 Todo List，而是把任务、实验计划、实验记录、样本库存、论文返修和 AI 笔记整理放进同一个工作台。

## 已实现功能

- 用户注册、登录、数据按账户隔离
- 任务增删改查、完成状态、优先级、分类与截止日期筛选
- 实验计划、步骤进度、状态管理和结构化实验记录
- 样本编号、来源、数量、精确存放位置、状态、搜索与 CSV 导出
- 论文状态、投稿/返修日期、Reviewer 意见与回复草稿
- 任务完成率、实验状态、本月实验结果统计
- 可在网页中自由配置 API URL、API Key 和模型，支持读取模型列表
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

数据库会在首次运行时自动创建于 `instance/research.db`。备份这个文件即可备份全部数据。

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

## 测试

```powershell
pytest -q
```

测试覆盖登录、邀请注册、密码重置与锁定、管理员权限、会话撤销、任务 CRUD、实验步骤与记录、跨账户隔离、只读角色、AI URL 安全和 CSV 导出。

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
│  ├─ secrets.py        # API Key 加密与解密
│  ├─ templates/        # Jinja 页面
│  └─ static/           # CSS 与 JavaScript
├─ tests/               # pytest 测试
├─ migrations/          # Alembic 数据库迁移
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
