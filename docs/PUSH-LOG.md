# 更新与 GitHub 推送日志

这份清单用于提交本轮 API 预设、AI 科研助手、实验执行模型、旧数据迁移和统一导出更新。当前工作区包含较多改动，必须按组检查，不能直接使用 `git add .`。

## 1. 确认仓库与环境

```powershell
cd "C:\Users\32406\Documents\New project\research_assistant"
.\.venv\Scripts\python.exe --version
git branch --show-current
git remote -v
```

当前预期分支为 `main`，远程仓库为：

`https://github.com/weideai/research-assistant.git`

## 2. 推送前验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q app migrations tests scripts packaging desktop_launcher.py linux_launcher.py version_info.py
node --check app\static\js\app.js
node --check scripts\build_weekly_presentation.mjs
.\.venv\Scripts\python.exe -m flask --app run.py db heads
git diff --check
```

本次最终测试基线：`149 passed, 9 warnings in 136.95s`。

迁移链预期输出：

```text
d1f3a5b7c902 (head)
```

Windows 下 pytest 退出时可能出现临时目录 `WinError 5` 清理提示；只有测试汇总通过且进程退出码为 `0` 才能继续提交。

## 3. 检查敏感信息与本地数据

```powershell
git status --short
git diff --stat
git diff -- .env.example README.md app\secrets.py app\main.py
```

提交前确认不包含：

- `.env`、真实 API Key、Token、SMTP 密码或生产密钥
- `instance/`、SQLite 数据库、迁移备份和迁移报告
- 用户上传的实验附件、知识库文件、聊天附件和自定义背景
- 本地导出的 `.ralab`、Word、Excel、PPT 或包含真实实验数据的 ZIP
- 个人截图、宣传图和临时文件

API Key 字段名、示例占位符和加密代码可以提交，真实密钥值不能提交。可用下面的命令辅助检查暂存内容，但匹配结果仍需人工逐条判断：

```powershell
git diff --cached | Select-String -Pattern 'sk-|api[_-]?key|token|secret|password' -CaseSensitive:$false
```

## 4. 按功能分组暂存

先暂存 API、AI 和领域逻辑：

```powershell
git add app\ai_service.py app\main.py app\models.py app\export_service.py
git add app\workspace.py app\project_package.py app\migration_service.py
```

再暂存页面、样式和交互：

```powershell
git add app\static\css\app.css app\static\css\assistant.css app\static\js\app.js
git add app\templates\base.html app\templates\api_settings.html app\templates\dashboard.html
git add app\templates\projects.html app\templates\project_detail.html app\templates\experiments.html
git add app\templates\experiment_detail.html app\templates\batch_detail.html app\templates\record_detail.html
git add app\templates\template_center.html app\templates\template_detail.html app\templates\record_template_detail.html
git add app\templates\samples.html app\templates\step_edit.html
git add app\templates\ai.html app\templates\assistant_popup.html
```

暂存数据库迁移与测试：

```powershell
git add migrations\versions\a4d8f6c2e701_research_workspace_v2.py
git add migrations\versions\e6b9c1d4f208_repair_legacy_record_executions.py
git add migrations\versions\7c3d9a1e5f42_persist_api_model_capabilities.py
git add migrations\versions\c9a4e7d2b610_enforce_execution_record_hierarchy.py
git add migrations\versions\d2f8a1c7b604_add_ai_execution_scope.py
git add migrations\versions\d1f3a5b7c902_execution_step_instances.py
git add tests\test_ai_service.py tests\test_api_presets_skills.py tests\test_assistant.py
git add tests\test_app.py tests\test_research_workflow.py tests\test_workspace_v2.py
git add tests\test_experiment_exports.py tests\test_legacy_record_repair.py tests\test_project_package_integrity.py
git add tests\test_template_center.py tests\test_bulk_management.py tests\test_attachments.py
git add tests\test_updates_and_migrations.py
git add tests\test_execution_steps.py tests\test_execution_step_migration.py tests\test_execution_step_exports.py
git add tests\test_dashboard_execution_context.py
```

最后暂存文档与明确属于本轮的配置：

```powershell
git add CONTEXT.md docs\adr\0001-separate-plans-executions-and-records.md
git add docs\UX-IA-V2.md docs\UPDATE-LOG.md docs\PUSH-LOG.md README.md .env.example
git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
```

工作流、安装包脚本和 Release 二进制只有在确认属于本次版本并重新构建校验后再单独暂存；不要因为它们已经出现在 `git status` 中就直接提交。

## 5. 升级迁移检查

桌面版首次启动会在升级前备份 SQLite 数据库并生成迁移报告。手工运行 Web 版或开发环境迁移前，也应先备份数据库：

```powershell
.\.venv\Scripts\python.exe -m flask --app run.py backup-local
.\.venv\Scripts\python.exe -m flask --app run.py db current
.\.venv\Scripts\python.exe -m flask --app run.py db upgrade
.\.venv\Scripts\python.exe -m flask --app run.py db current
```

本轮数据迁移会把活动的异常旧记录归入 `HISTORY-LEGACY` 历史执行。其 `downgrade()` 不会故意恢复错误归属，因此不要把降级当作数据回滚；需要恢复时使用升级前数据库备份。

## 6. 创建提交

```powershell
git commit -m "feat: streamline AI presets and experiment execution workflow"
git log -1 --oneline --decorate
```

推荐提交说明：

```text
收口 API 预设和模型能力展示，将系统入口归入个人菜单；支持 AI 创建和修改科研项目、新建实验执行并明确实验计划归属；统一实验计划、实验执行和过程记录层级，修复旧记录归属，升级 JSON、Markdown、Word、Excel 和 ZIP 导出的一致性与软删除过滤。
```

## 7. 推送与发布检查

```powershell
git push origin main
git status --short
git log -1 --oneline --decorate
```

推送后在 GitHub Actions 页面确认测试与安装包构建通过。若需要触发应用内版本更新提醒，还必须：

1. 提升应用版本号。
2. 创建高于当前版本的 GitHub Release。
3. 上传重新构建的 Windows、Linux 安装包及对应 SHA-256 清单。
4. 在另一台无本地数据的机器上验证首次安装、迁移和更新提示。

仅推送 `main` 分支不会自动让已安装客户端收到新版本。
