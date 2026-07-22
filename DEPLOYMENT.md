# R/LAB 公网部署手册

本文档面向第一次部署服务器的用户。推荐环境是 Ubuntu 24.04、Docker Compose、PostgreSQL、Redis、Gunicorn 和 Caddy。

## 0. 已经完成与需要你完成的部分

项目中已经完成：

- PostgreSQL 配置和 Alembic 数据库迁移
- 邀请制注册、强密码、密码重置和登录失败锁定
- 管理员后台、角色、账户停用、会话撤销和审计日志
- API Key 独立加密密钥和 API URL 内网访问防护
- Docker、Gunicorn、Redis、Caddy 和自动 HTTPS 配置
- 健康检查、数据库与用户背景备份脚本和生产环境模板

你需要准备：

1. 一台有公网 IPv4 的 Linux 云服务器，建议至少 2 核 CPU、2 GB 内存、30 GB 磁盘。
2. 一个域名，例如 `research.example.com`。
3. 可选的 SMTP 邮件账户，用于发送邀请和密码重置邮件。
4. 允许连接的 AI API 域名列表。

医学或患者数据部署前，需要确认服务器地区、服务商协议、医院制度和课题组要求。

## 1. 购买并登录服务器

服务器系统选择 Ubuntu 24.04 LTS。购买后会得到公网 IP，例如 `203.0.113.10`。

在 Windows PowerShell 登录：

```powershell
ssh root@203.0.113.10
```

首次连接会询问是否信任主机，核对 IP 后输入 `yes`。

建议创建普通部署用户：

```bash
adduser deploy
usermod -aG sudo deploy
```

退出后改用：

```powershell
ssh deploy@203.0.113.10
```

## 2. 配置域名 DNS

在域名服务商控制台添加：

```text
类型：A
主机记录：research
记录值：你的服务器公网 IP
TTL：600
```

例如最终域名：

```text
research.example.com
```

等待解析后，在本机检查：

```powershell
nslookup research.example.com
```

返回的 IP 必须是服务器公网 IP。

## 3. 安装 Docker

在服务器运行：

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2 ufw
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

退出 SSH 后重新登录，使 Docker 用户组生效。然后检查：

```bash
docker --version
docker compose version
```

## 4. 配置防火墙

只开放 SSH、HTTP 和 HTTPS：

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

不要开放 PostgreSQL 的 `5432` 或 Redis 的 `6379` 端口。

## 5. 上传项目

推荐将项目放在：

```bash
sudo mkdir -p /opt/research-assistant
sudo chown "$USER":"$USER" /opt/research-assistant
```

如果使用私有 Git 仓库：

```bash
git clone 你的私有仓库地址 /opt/research-assistant
cd /opt/research-assistant
```

如果暂时不用 Git，可在 Windows 项目目录创建压缩包：

```powershell
cd "C:\path\to\research_assistant"
tar --exclude=.venv --exclude=instance --exclude=.pytest_cache --exclude=.env -czf ..\research-assistant.tar.gz .
scp ..\research-assistant.tar.gz deploy@203.0.113.10:/tmp/
```

在服务器解压：

```bash
cd /opt/research-assistant
tar -xzf /tmp/research-assistant.tar.gz
```

## 6. 创建生产环境配置

在服务器项目目录运行：

```bash
cd /opt/research-assistant
cp .env.production.example .env.production
chmod 600 .env.production
```

生成三个不同的随机值：

```bash
openssl rand -hex 48
openssl rand -hex 48
openssl rand -hex 32
```

分别用于：

```text
SECRET_KEY
CREDENTIAL_ENCRYPTION_KEY
POSTGRES_PASSWORD
```

编辑配置：

```bash
nano .env.production
```

必须修改：

```dotenv
DOMAIN=research.example.com
PUBLIC_BASE_URL=https://research.example.com
TRUSTED_HOSTS=research.example.com
SECRET_KEY=第一个随机值
CREDENTIAL_ENCRYPTION_KEY=第二个随机值
POSTGRES_PASSWORD=第三个随机值
```

`SECRET_KEY` 用于登录会话，`CREDENTIAL_ENCRYPTION_KEY` 用于加密 API Key。两者不能相同，也不能在应用运行后随意更换。

## 7. 配置邮件

密码重置需要 SMTP。向邮件服务商获取以下信息：

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=research@example.com
SMTP_PASSWORD=邮件服务提供的应用密码
SMTP_USE_TLS=true
MAIL_FROM=research@example.com
```

不要填写邮箱网页登录密码，应使用服务商提供的 SMTP 应用密码。

没有 SMTP 时，管理员仍可在后台复制邀请链接，但用户无法自行完成“忘记密码”流程。

## 8. 配置 AI 出站白名单

生产环境默认禁止访问本机和内网地址。填写允许使用的 API 域名：

```dotenv
AI_ALLOWED_HOSTS=api.openai.com
ALLOW_PRIVATE_API_URLS=false
AI_SETTINGS_ADMIN_ONLY=true
```

多个域名用英文逗号分隔：

```dotenv
AI_ALLOWED_HOSTS=api.openai.com,api.example.com
```

不要把 `ALLOW_PRIVATE_API_URLS` 改成 `true`，除非服务器位于受控内网且你明确理解 SSRF 风险。

实验文件上传限制可在 `.env.production` 调整：

```dotenv
MAX_UPLOAD_REQUEST_MB=0
MAX_ATTACHMENT_MB=0
ALLOW_OPEN_LOCAL_FOLDERS=false
```

任意格式文件都保存在非静态上传目录并强制下载；只有经过文件头识别的栅格图片允许页面预览。

## 9. 构建并启动

所有 Compose 命令都要带生产环境文件：

```bash
docker compose --env-file .env.production build
docker compose --env-file .env.production up -d
```

检查状态：

```bash
docker compose --env-file .env.production ps
docker compose --env-file .env.production logs --tail=100 web
docker compose --env-file .env.production logs --tail=100 caddy
```

`web`、`db`、`redis` 应显示 healthy。Caddy 会在 DNS 正确、80/443 端口开放后自动申请 HTTPS 证书。

## 10. 创建第一个管理员

执行交互式命令：

```bash
docker compose --env-file .env.production exec web flask create-admin
```

依次输入管理员邮箱、姓名和强密码。密码至少 12 位，并包含大小写字母和数字。

然后打开：

```text
https://research.example.com
```

## 11. 邀请其他用户

1. 使用管理员账户登录。
2. 打开侧栏“系统管理”。
3. 输入成员邮箱并选择角色。
4. 点击“创建邀请”。
5. SMTP 正常时系统自动发送；否则复制一次性邀请链接并通过安全渠道发送。

角色说明：

```text
system_admin  系统管理员
lab_admin     预留的实验室管理员角色，当前不具备全站管理权限
researcher    普通研究员
viewer        只读成员
```

当前版本的数据仍按个人账户隔离；角色主要控制系统管理权限。跨成员共享实验数据需要后续增加实验室工作区模型。

## 12. 配置每日备份

先手动测试：

```bash
cd /opt/research-assistant
chmod +x scripts/backup.sh
./scripts/backup.sh
ls -lh backups
```

设置每天凌晨 3 点备份：

```bash
crontab -e
```

加入：

```cron
0 3 * * * cd /opt/research-assistant && ./scripts/backup.sh >> /var/log/research-backup.log 2>&1
```

脚本会同时生成 PostgreSQL 数据库备份和用户背景文件备份，并保留最近 30 天。还应定期将两类备份同步到另一台服务器或加密对象存储。

恢复前先停止 Web 服务：

```bash
docker compose --env-file .env.production stop web
gunzip -c backups/research-YYYYMMDD-HHMMSS.sql.gz | docker compose --env-file .env.production exec -T db psql -U research -d research
docker compose --env-file .env.production start web
docker compose --env-file .env.production exec -T web tar -xzf - -C /app/instance < backups/research-uploads-YYYYMMDD-HHMMSS.tar.gz
docker compose --env-file .env.production restart web
```

正式恢复前应先在测试数据库演练。

## 13. 更新版本

上传或拉取新代码后：

```bash
cd /opt/research-assistant
docker compose --env-file .env.production build web
docker compose --env-file .env.production up -d
docker compose --env-file .env.production logs --tail=100 web
```

容器启动时会自动执行 `flask db upgrade`。

## 14. 上线检查清单

- `https://` 正常，浏览器没有证书警告
- `http://` 自动跳转 HTTPS
- `/healthz` 返回 `{"status":"ok"}`
- 未受邀请访问 `/register` 显示“注册需要邀请”
- 普通研究员访问 `/admin` 返回 403
- 连续错误登录会触发临时锁定
- 密码重置邮件能够收到
- 修改密码后旧设备会话失效
- API URL 无法填写 `127.0.0.1` 或内网地址
- PostgreSQL 和 Redis 端口没有对公网开放
- 每日备份实际生成，并完成过恢复演练
- 日志中没有 API Key、密码或患者身份信息

## 15. 常用排障命令

```bash
docker compose --env-file .env.production ps
docker compose --env-file .env.production logs -f web
docker compose --env-file .env.production logs -f caddy
docker compose --env-file .env.production restart web
docker compose --env-file .env.production exec web flask db current
docker compose --env-file .env.production exec db pg_isready -U research -d research
```

不要通过删除数据库卷解决迁移问题。`docker compose down -v` 会删除数据库，应避免执行。
