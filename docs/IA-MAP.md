# R/LAB 全量界面结构图（页面 · 按键 · 去向）

> 逆向自 `app/main.py`、`app/workspace.py` 与 `app/templates/*.html`。
> 当前口径：本地单用户、8 项侧栏导航、5 个全局浮层、仅桌面端。
> 本文只描述**现状**，改进建议见第 6 节，视觉规范见根目录 `design.md`。

---

## 1. 全局外壳（`base.html`，所有本地工作页面共用）

```text
┌─ 侧栏 sidebar (236px, 固定) ──────────────────────────────┐
│ R/LAB 品牌 ──────────────────────────► /  (总览)          │
│                                                           │
│ 【工作区】                                                │
│  ├ 总览      layout-dashboard ──────► /                   │
│  ├ 实验台    panels-top-left ───────► /projects           │
│  └ 任务      check-square-2 ────────► /tasks              │
│ 【资料】                                                  │
│  ├ 报告与文件 library-big ──────────► /experiment-reports │
│  └ 周报      calendar-days ─────────► /reports/presentation│
│ 【复用】                                                  │
│  ├ 模板中心  copy ──────────────────► /templates          │
│  └ 物品管理  archive ───────────────► /samples            │
│ 【系统】                                                  │
│  └ 回收站    trash-2 ───────────────► /recycle-bin        │
│                                                           │
│ 本地工作区状态 ─────────────────────► /settings/api       │
│ 项目署名 ────────────────────────────► GitHub (新窗口)    │
└───────────────────────────────────────────────────────────┘

┌─ 顶栏 workspace-topbar ───────────────────────────────────┐
│ 面包屑：科研助手 › {当前页名}（endpoint 硬编码映射）      │
│ 搜索入口「搜索实验、报告和文件 Ctrl K」► /experiment-reports※1│
│ 「实验分析专家 / 打开 AI 助手」──► 展开 AI Dock           │
└───────────────────────────────────────────────────────────┘

浮层（5 个）
 ① 外观设置    右上角调色板按钮 → <dialog>
 ② AI Dock     右下角 FAB「AI」/ 顶栏按钮 → 侧滑面板
③ 发送前检查  AI 发送时 → <dialog> 确认外发内容
④ 更新提醒    GET /updates/check → 顶部 banner
⑤ Flash 提示  服务端 flash → 右上角堆叠
```

※1 **它不是输入框，是一个跳转链接**，见 6.3。

桌面画布按 1180px 设计。应用不提供移动导航、手机断点或移动端 AI 入口。

### 1.1 外观设置浮层

| 控件 | 行为 |
|---|---|
| 界面风格 ×4 单选 | `research` / `tech` / `minimal` / `cute` → `html[data-theme]` |
| 夜间模式开关 | → `html[data-mode="dark"]` |
| 背景图片上传 | PNG/JPEG/WebP ≤5MB → `--workspace-background-image` |
| 恢复默认 / 清除背景 / 保存外观 | `POST /settings/appearance` |

### 1.2 AI Dock 浮层（功能最密集的单一界面）

```text
头部  ├ 展开历史会话 (Ctrl+Shift+L)   ├ 新建对话 (Ctrl+N)
      ├ API 设置 ──► /settings/api    ├ 制作 PPT ──► /reports/presentation
      ├ 导出聊天 ──► /assistant/conversations/<id>/export.md
      └ 最大化 / 关闭
左栏  历史会话列表（最近 100）+ 会话搜索 + 新建
主区  ├ 上下文条：当前页面范围提示
      ├ <details> 知识库与助手设置
      │    ├ 知识库多选 + 刷新 ──► POST /assistant/knowledge-bases
      │    ├ 新建知识库表单
      │    └ 自定义提示词（保存 / 重置默认）
      ├ <details> 选择实验计划与执行
      │    └ 仅当前范围 / 全选 / 清空
      ├ 消息流（可编辑、可重新生成 message）
      ├ 快速开始 ×6：新建项目 / 生成下次计划 / 整理当前页 /
      │              比较历史 / 生成周报 / 检索记录
      └ 输入区：附件上传 · 联网开关 · 停止 · 发送
写入  AI 提案 ──► POST /assistant/proposals/<id>/apply   （先显示 diff）
      撤销     ──► POST /assistant/proposals/<id>/revert
```

---

## 2. 主链路页面（业务核心）

### 2.1 总览 `GET /` → `dashboard.html`

```text
页头  「早上好，{name}」 + 主按钮
        └ 无项目 → 创建第一个科研项目 ──► /projects
          有项目 → 新建实验计划       ──► /experiments

引导带（仅当 record_count == 0 时出现）
  01 科研项目 ──► /projects
  02 实验计划 ──► /experiments
  03 实验执行 ──► /batches/<最近> 或 /experiments/<id>#batches
  04 过程记录 ──► /batches/<最近>#new-record
  「浏览模板」──► /templates

指标 ×4（纯展示，不可点）
  今日待办 · 进行中计划 · 可用样本 · 任务完成率

面板
  近期任务    ├ ☑ 勾选 ──► POST /tasks/<id>/toggle（原地刷新）
              └ 查看全部 ──► /tasks
  实验计划进度 每行 ──► /experiments/<id>
  最近过程记录 表格：实验计划──►/experiments/<id>
                    实验执行──►/batches/<id>
                    摘要────►/records/<id>

空态兜底  「载入示例工作流」──► POST /seed-demo
```

### 2.2 实验台 `GET|POST /projects` → `projects.html`

| 控件 | 去向 |
|---|---|
| 回收站 | `/recycle-bin` |
| `<details>` 导入完整项目包（.ralab） | `POST /projects/import`（校验 SHA-256 清单） |
| 项目卡片（编号/状态/目标/计划·执行·记录·定稿 计数） | `/projects/<id>` |
| 右侧「新建项目」表单：名称·编号·目标·状态·起止日期 | `POST /projects` |

### 2.3 项目详情 `GET|POST /projects/<id>` → `project_detail.html`

```text
页头  面包屑 ──► /projects
      导出完整项目 ──► GET /projects/<id>/package  (.ralab 下载)
      新建实验计划 ──► /experiments?project_id=<id>#create-experiment

指标条  实验计划数 · 实验执行数 · 项目任务数 · 当前状态

主区  实验计划与执行（每行）
        ├ 计划标题 ──► /experiments/<id>
        ├ 执行小卡 ──► /batches/<id>
        └ [+] 图标 ──► POST /experiments/<id>/batches   ※纯图标，34×34
      项目任务  └ 管理全部任务 ──► /tasks

侧栏  项目信息表单（名称/编号/状态/起止/目标/备注）──► POST /projects/<id>
      移入回收站 ──► POST /projects/<id>/delete   (data-confirm)
```

### 2.4 实验计划列表 `GET|POST /experiments` → `experiments.html`

| 区块 | 控件 → 去向 |
|---|---|
| 页头 | 模板中心 → `/templates?kind=steps`；新建实验计划 → `#create-experiment` |
| 创建区 A「空白创建」 | 名称·项目·编号·负责人·状态·起止 → `POST /experiments` →「创建并进入计划」 |
| 创建区 B「使用模板创建」 | 选步骤模板 → `POST /experiments/from-template`；查看全部模板 → `/templates` |
| 状态筛选 chip | 全部 / 未开始 / 进行中 / 完成 / 暂停 → `/experiments?status=` |
| 实验卡片 | 标题、进度条、负责人、日期 → `/experiments/<id>` |

### 2.5 实验计划详情 `GET|POST /experiments/<id>` → `experiment_detail.html`（**251 行，最重的页面**）

```text
页头  ← 返回项目 ──► /projects/<pid>      ← 返回实验计划 ──► /experiments
      实验报告 ──► /experiments/<id>/reports
      导出 <select> + 按钮 ──► /experiments/<id>/export        (PDF/Word)
                          ──► /experiments/<id>/export.md      (Markdown)
                          ──► /experiments/<id>/archive.zip    (完整包)
      新建/查看实验执行 ──► #batches

Tab 区（页内锚点，非真 tab）
 ├ 概览      目标与基本信息表单 ──► POST /experiments/<id>「保存信息」
 │           移入回收站         ──► POST /experiments/<id>/delete
 ├ 实验方案
 │   步骤     添加步骤 ──► POST /experiments/<id>/steps
 │            编辑     ──► /steps/<sid>/edit  （独立页面）
 │            删除     ──► POST /steps/<sid>/delete
 │            批量保存/批量删除 ──► POST /experiments/<id>/steps/bulk
 │            保存步骤模板 ──► POST /experiments/<id>/save-template
 │            调用模板   ──► POST /experiments/<id>/apply-step-template
 │            查看模板   ──► /templates/<tid>
 │   参数     添加/删除/批量 ──► POST /experiments/<id>/parameters[/bulk]
 │                            ──► POST /experiment-parameters/<pid>/delete
 │   样本     关联/解除/批量 ──► POST /experiments/<id>/samples[/bulk]
 │                            ──► POST /experiment-samples/<sid>/delete
 │   记录模板 绑定 ──► POST /experiments/<id>/record-template
 └ 实验执行  执行列表 ──► /batches/<bid>
             新建执行 ──► POST /experiments/<id>/batches
             最近记录 ──► /records/<rid>
             附件缩略 ──► /attachments/<aid>/download
             进入实验文件中心 ──► /experiments/<id>/files
```

### 2.6 实验执行详情 `GET|POST /batches/<id>` → `batch_detail.html`（**165 行**）

```text
面包屑  项目 ──► /projects/<pid>   计划 ──► /experiments/<eid>

执行步骤（本次快照，独立完成状态）
  标记完成 / 未完成 ──► POST /batch-steps/<sid>/toggle
  编辑             ──► POST /batch-steps/<sid>/edit
  保存本次步骤      ──► POST /batches/<id>/steps/bulk

新增过程记录 #new-record
  记录模板：查看 ──► /record-templates/<tid>
            填入表单（前端预填，不落库）
            无模板 → 前往模板中心创建 ──► /templates?kind=records
  提交 ──► POST /batches/<id>/records

实际参数    添加/移除行 → 保存到当前执行 ──► POST /batches/<id>/parameters
实际样本    添加/关联 ──► POST /batches/<id>/samples
            查看样本 ──► /samples/<sid>/edit
过程记录列表 查看并编辑 ──► /records/<rid>
            批量保存/批量移入回收站 ──► POST /batches/<id>/records/bulk
执行信息    保存执行 ──► POST /batches/<id>
```

### 2.7 过程记录详情 `GET|POST /records/<id>` → `record_detail.html`（**四标签页，全站最好的分区范例**）

```text
面包屑  项目 › 计划 › 执行            报告视图 ──► /experiments/<eid>/reports?record_id=
定稿    POST /records/<id>/finalize   （锁定原文，后续只能走「修订」）

Tab ① 阅读    只读渲染已记录内容
Tab ② 编辑    正文/条件/结果/备注 → POST /records/<id>「保存修改」
              结构化参数：添加行/移除行/保存参数/删除参数
              调整执行归属 ──► POST /records/<id>/move-batch
Tab ③ 文件与数据
              上传托管文件      ──► POST /records/<id>/attachments
              添加外部数据链接  ──► POST /records/<id>/attachments/external
              在资源管理器打开  ──► POST /records/<id>/open-folder
              导入所选内容      ──► POST /attachments/<aid>/open-external
              下载 / 预览       ──► /attachments/<aid>/download | /preview
              校验文件完整性    ──► POST /attachments/<aid>/verify  (SHA-256)
              批量保存 / 一键删除 ──► POST /records/<id>/attachments/bulk
              删除文件          ──► POST /attachments/<aid>/delete
Tab ④ 模板与修订
              保存记录模板 ──► POST /records/<id>/save-template
              模板列表     ──► /record-templates/<tid>
              修订历史（只读时间线）
删除记录  POST /records/<id>/delete
```

---

## 3. 资料库页面

### 3.1 实验报告（全局） `GET /experiment-reports` → `experiment_report_index.html`

卡片流。搜索框（实验/执行编号/结果/记录内容）；每卡：结果徽章、目的、过程摘要、结果备注、**最多 2 张缩略图** →`/attachments/<id>/preview`、"查看所有原始数据与附件"→`/experiments/<eid>/files?record_id=`、导出 PDF/Word →`/records/<rid>/export?format=`、打开完整报告 →`/experiments/<eid>/reports?record_id=`。

### 3.2 实验报告（项目内） `GET /experiments/<id>/reports` → `experiment_reports.html`

左侧记录列表（可查询/清除筛选）+ 右侧报告阅读器 + 上一份/下一份翻页；附件缩略 →`/attachments/<id>/preview`；「打开所属文件夹」→`/experiments/<id>/files`；「返回记录编辑页」→`/records/<rid>`；导出 PDF/Word。

### 3.3 文件中心 `GET /file-center` → `file_center.html`

搜索（文件名/路径/实验/标签）+ 分类下拉 + 每页数量；表格支持全选跨页；批量下载（ZIP）`POST /file-center/download`、批量删除、保存批量修改；单行：预览 / 下载 / 打开所属记录 →`/records/<rid>`、进入实验文件夹 →`/experiments/<eid>/files`；分页。

### 3.4 实验文件中心（单实验） `GET /experiments/<id>/files` → `experiment_files.html`

同上，作用域收窄到单个实验；额外有「导出完整资料包」→`/experiments/<id>/export`。

### 3.5 周报 `GET|POST /reports/presentation` → **`weekly_reports.html`**

```text
上传周报  POST /reports/weekly/upload        (PPT/PDF/ODP/KEY，本地归档)
筛选周报  按日期/项目
周报列表  选中 ──► /reports/presentation?report_id=
          下载文件   ──► /reports/weekly/<id>/download
          打开文件夹 ──► /reports/weekly/<id>/folder
          保存信息   ──► POST /reports/weekly/<id>
          删除       ──► POST /reports/weekly/<id>/delete
反馈时间线 记录一条更新 ──► POST /reports/weekly/<id>/updates
           标记完成/待处理 ──► POST /reports/weekly-updates/<uid>/toggle
折叠工具「生成 PPT」
  选实验（全选/清空）→ 预览证据与结构 → 生成并下载 PPTX
  Skill 管理：保存 Skill ──► POST /reports/presentation/skills
              删除       ──► POST /reports/presentation/skills/<id>/delete
```

### 3.6 模板中心 `GET /templates` → `template_center.html`

两个 tab：**步骤模板** / **记录模板**（`?kind=steps|records`）。

| 步骤模板 | 记录模板 |
|---|---|
| 新建空白（名称+说明）→ 创建并编辑 | 同左 |
| 从参考网页/文本生成本地模板（AI 提取）`POST /templates/import` | — |
| 应用到实验 + 追加/替换 → `POST /templates/<id>/apply` | 目标实验执行 → `GET /record-templates/<id>/use` |
| 查看与编辑 →`/templates/<id>` · 复制 · 删除 | 查看与编辑 →`/record-templates/<id>` · 复制 · 删除 |

子页 `/templates/<id>`：复制模板 / 保存步骤模板 / 添加步骤 / 保存步骤 / 删除步骤 / 启用此模板。
子页 `/record-templates/<id>`：复制 / 保存 / 参数增删 / 在新增记录中调用 / 删除。

### 3.7 物品管理 `GET|POST /samples` → `samples.html`

样本入库表单；搜索/清除；表格行操作：编辑 →`/samples/<id>/edit`、删除 →`POST /samples/<id>/delete`；导出 CSV →`/export/samples.csv`。
子页 `/samples/<id>/edit`：保存修改；反查「实验使用」→`/batches/<bid>`、「计划用途」→`/experiments/<eid>`。

### 3.8 任务 `GET|POST /tasks` → `tasks.html`

快速添加表单（标题/项目/分类/优先级/截止/备注）；筛选 chip（状态 ×3 + 分类 ×5）；表格：勾选切换、编辑 →`/tasks/<id>/edit`、删除；导出 CSV。

---

## 4. 系统页面

| 页面 | 路由 | 主要控件 |
|---|---|---|
| API 设置 | `/settings/api` | 显示/隐藏密钥 · 拉取模型 `POST /settings/api/models` · 保存 · 预设列表（设为当前/删除）· 保存预设 · 账号安全跳转 |
| 回收站 | `/recycle-bin` | 类型导航（项目/计划/执行/记录/附件/任务/周报/步骤模板/记录模板/Skill）· 搜索 · 分页 · 恢复 `POST .../restore` · 永久删除（需输入「永久删除」二次确认）`POST .../purge` |
| 系统管理 | `/admin` | 创建邀请 `POST /admin/invitations` · 修改角色/停用/撤销全部会话 `POST /admin/users/<id>/update` |
| 账号安全 | `/account/security` | 修改密码并撤销其他会话 |
| 健康检查 | `/healthz` | — |
| 更新检查 | `/updates/check` | 前端轮询，只提醒不下载 |

## 5. 未登录页面

`/login` · `/register`（凭邀请）· `/forgot-password` · `/reset-password/<token>` → 均由 `auth.html` / 各自模板渲染，共用 `auth-body` 样式。错误页 `404.html` / `error.html` → 返回首页。

---

## 6. 现状问题（逆向过程中发现，均可复现）

### 6.1 导航层级与业务层级不一致
侧栏「工作区」把 **总览 / 实验台 / 任务 / 实验计划 / 实验报告 / 文件中心** 六项平铺。但按 `CONTEXT.md` 的业务模型，`实验台(项目) ⊃ 实验计划 ⊃ 实验执行 ⊃ 过程记录` 是一条父子链，把「实验计划」提到与「实验台」同级，用户无法从导航看出两者关系；「实验报告」和「文件中心」又是同一批数据的两个视图。**11 项一级导航超过了短期记忆的舒适上限。**

### 6.2 同一功能多入口、无权威入口
- 新建实验执行：`project_detail` 的 `+` 图标 / `experiment_detail` 的按钮 / `dashboard` 引导卡 —— 三处样式与文案都不同。
- 应用步骤模板：`template_center` 的「应用模板」/ `experiment_detail` 的「调用」/ `experiments` 的「使用模板创建」。
- API 设置：侧栏 + 账号菜单 + AI Dock 头部，三个入口。

### 6.3 顶栏"搜索框"不是搜索框，且全站没有全局搜索
`base.html` 的 `.topbar-search` 带 `<kbd>Ctrl K</kbd>`，视觉完全是搜索输入框，实际是 `<a href="/experiment-reports">`。

Ctrl+K **确实有绑定**（`app/static/js/app.js:1766-1774`），但它只做一件事：聚焦**当前页面的本地搜索框**（`.report-feed-search input` / `.file-center-search input` / `.report-search-form input` / `.weekly-index-filter input`）。在总览、实验台、实验计划、任务、模板中心、物品管理、回收站以及所有详情页上没有本地搜索框，于是回退到 `.topbar-search.click()` —— 直接把你跳到实验报告页。

真实缺陷是**没有全局搜索**。现有搜索是四个互不相通的局部搜索：文件中心 · 实验报告 · 回收站 · 周报。搜不到：项目 · 实验计划 · 实验执行 · 物品 · 模板 · 参数值。控件外观承诺了它不具备的能力。

### 6.4 死代码
`app/templates/presentation_report.html`（38 行）没有任何 `render_template` 引用 —— `/reports/presentation` 实际渲染的是 `weekly_reports.html`。路由名与页面语义也已脱节。

### 6.5 触控目标与纯图标按钮
`.icon-btn` 为 34×34px，低于 WCAG 2.5.5 建议的 44×44。`project_detail` 的「新建实验执行」、`samples` 的编辑/删除只有图标（虽有 `title`/`aria-label`，但无可见文字标签）。

### 6.6 字号低于可读下限
`app.css` 中存在 `font-size: 9px`（`.project-credit small`）、`10px`（`.brand small` `.user-meta small` `.attachment-meta small` `.account-menu-popover small`）。中文在 10px 以下几乎不可辨认。

### 6.7 正文对比度不足
`--muted: #697581` 在 `--bg: #f2f4f6` 上约 **4.07:1**，未达 AA 4.5:1。而 `.muted` 被大量用于页面说明文字、表格次要信息、`small` 标签。

### 6.8 中文数据值被当作 CSS 类名
`.priority-高`、`.status-进行中`、`.result-成功`、`.state-暂停`、`.sample-可用` —— 样式直接耦合业务文案，任何文案调整都会静默破坏样式。

### 6.9 详情页缺少真正的分区
`experiment_detail.html`（251 行）在一屏内堆叠了 概览/方案/步骤/参数/样本/执行/记录/附件/模板/删除 十个区块，仅靠锚点跳转。对照 `record_detail.html` 已经用了四标签页，效果明显更好 —— 这个模式没有推广。

### 6.10 设计令牌分散
`:root` 在 `app.css` 顶部，主题覆盖在 `themes.css`，`--surface-soft` 等又只在 `themes.css` 的 `html` 上定义。且 `app.css` 采用单行超长压缩写法，实际维护成本很高。

---

## 7. 建议的导航精简（11 项 → 7 项，零功能丢失）

```text
现状（11 项）                     建议（7 项 / 3 组）
─────────────────────            ──────────────────────────────────────
工作区                            工作
 ├ 总览                            ├ 总览          （不变）
 ├ 实验台          ──┐             ├ 实验台        项目 › 计划 › 执行 › 记录
 ├ 任务             │             │                 四层收进同一条链路，
 ├ 实验计划        ──┘             │                 计划列表成为实验台内 tab
 ├ 实验报告        ──┐             └ 任务          （不变）
 └ 文件中心        ──┤
资料库              │             资料
 ├ 周报             └──────────►   ├ 报告与文件    报告卡片流 / 文件表格
 ├ 模板中心                        │                两个 tab，同一页面
 └ 物品管理                        └ 周报          （不变）
系统
 ├ API 设置                       复用
 └ 回收站                          ├ 模板中心      （不变）
                                   └ 物品管理      （不变）

                                  系统项收进账号菜单（已有入口）：
                                   API 设置 · 回收站 · 账号安全 · 系统管理
```

**功能去向对照（确认无丢失）：**

| 现有入口 | 新位置 | 说明 |
|---|---|---|
| 实验计划（列表页） | 实验台 → 「全部计划」tab | 路由 `/experiments` 保留，导航不再单列 |
| 实验报告 | 资料 → 报告与文件 → 「报告」tab | 路由 `/experiment-reports` 保留 |
| 文件中心 | 资料 → 报告与文件 → 「文件」tab | 路由 `/file-center` 保留 |
| API 设置 | 账号菜单（已有）+ AI Dock（已有） | 侧栏一级项移除，两处入口足够 |
| 回收站 | 账号菜单 + 实验台页头（已有） | 侧栏一级项移除 |

## 8. 建议的主界面（总览）重排

现状总览已有的四指标 + 三面板结构合理，缺的是**「继续上次工作」**这一最高频动作。建议顺序：

```text
1  继续工作      最近一次实验执行 → 一键「添加过程记录」
                 （当前需要 3 次点击：总览→实验计划→执行→记录）
2  今日焦点      今日待办 · 逾期任务 · 今天该记录的执行
3  指标条 ×4     今日待办 · 进行中计划 · 可用样本 · 完成率（保持）
4  进行中计划    （保持）
5  最近过程记录  （保持）
6  引导带        仅零记录时出现（保持现有逻辑）
```

---

*视觉规范（主色/辅色/强调色/字体/间距/圆角）见根目录 `design.md`。*
