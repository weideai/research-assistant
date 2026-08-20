# R/LAB 部署说明（桌面版）

R/LAB 当前为本地桌面应用（`pywebview + WebView2`，`desktop_main.py`），不再提供官方公网 Web 部署。历史 Web 部署手册、Docker/Caddy/PostgreSQL/Redis/Gunicorn 相关入口与兼容页面已归档至 `app/legacy_web/`，仅作回滚参考。

## 桌面运行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe desktop_main.py
```

- 正式入口：`desktop_main.py`（`app.desktop.runtime.main()`，不启动 HTTP 监听）
- 兼容入口 `desktop_launcher.py` 仅为旧快捷方式保留
- 公网部署相关文件（`run.py` / `Dockerfile` / `docker-compose.yml` / `Caddyfile` / `docker-entrypoint.sh`）已于 TASK-003 归档移除；`requirements-prod.txt` 现仅为 `-r requirements.txt` 透传

如需恢复历史 Web 能力，请从 Git 历史或 `app/legacy_web/` 恢复归档文件，并自行评估安全与运维成本。本仓库不再提供官方公网部署与线上运维手册。
