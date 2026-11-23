# R/LAB 桌面前端设计与功能评审

**范围** `app/desktop_ui/`（正式桌面前端）、`app/desktop/bridge.py`、`app/services/desktop_workspace.py`
**基线** `desktop.css` 81,350 bytes / 667 行 · `index.html` 52,862 bytes / 154 行
**参照** `design.md` v1.2 · `PROJECT_ARCHITECTURE.md` · `CONTEXT.md`

> 本文是一次性诊断与改造路线，属于开发过程记录，已按 `PROJECT_ARCHITECTURE.md` §8.6 加入 `.gitignore`，不进发布提交。
> **可长期生效的规则一律回写 `design.md`**（声明的唯一参照），本文不承担规范职责。

---

## 1 · 根因

问题不是散落的样式瑕疵，而是一条结构性断裂：

> **设计系统与测试守的是 Flask 兼容层，产品实际跑的是 `app/desktop_ui/`。**

三条证据：

**(a) 规范描述的载体不是产品。** `design.md:14` 写「载体：桌面固定画布的 Flask + Jinja2 多页应用」，而 `PROJECT_ARCHITECTURE.md:7` 明确产品是 `pywebview + WebView2` 桌面应用，Flask 只是兼容层（`:21`「Web 入口属于兼容层，不能成为桌面功能的第二套实现」）。`design.md:21` 引用的三份配套文档 `docs/OPTIMIZATION-PLAN.md`、`docs/IA-MAP.md`、`docs/UX-IA-V3.md` 已在工作区删除，引用悬空。

**(b) 没有一个 UI 测试读 `app/desktop_ui/`。**

| 测试文件 | 实际守的路径 |
|---|---|
| `tests/test_design_tokens.py:15` | `CSS_DIR = app/static/css`（tokens/skins/app/ide/themes） |
| `tests/test_layout_proportions.py` | `APP_CSS = app/static/css/app.css` + `app/templates/*.html` |
| `tests/test_state_tones.py` | `CSS_DIR = app/static/css`（glob `*.css`）+ `templates/**.html` |
| `tests/test_navigation_structure.py` | `base.html` `projects.html` `experiments.html` … |
| `tests/test_appearance.py` | `themes.css` |

于是 `pytest -q` 全绿的同时，产品实际前端可以任意漂移 —— 下面每一条偏离都是在测试全绿的情况下累积的。

**(c) `tokens.css` 被加载但完全没有被引用。** `index.html:6-7` 只加载 `../static/css/tokens.css` 与 `desktop.css`（`skins.css`/`app.css`/`ide.css` 不在桌面产品里）。而 `desktop.css:1-26` 的 `:root` 自建了一套平行词汇：

```css
--canvas / --canvas-strong / --surface-soft / --surface-tint / --surface-blue
--line / --line-strong / --ink / --muted
--accent / --accent-strong / --accent-soft
--shadow: 0 10px 28px rgba(46, 44, 72, .08);   /* 只有一档 */
```

对 `tokens.css` 令牌的引用实测计数：`--fs-body` 0 · `--space-4` 0 · `--shadow-1` 0 · `--radius-panel` 0 · `--radius-control` 0 · `--bg` 0 · `--blue` 0 · `--green` 0。

**`tokens.css` 对桌面产品是死代码。**

---

## 2 · 实测偏离

全部位于 `app/desktop_ui/desktop.css`，计数为脚本实测。

### 2.1 字号 —— 最严重

`design.md` §03 定 8 档、下限 11px，§12.2「禁止 < 11px 字号」，§03 附注「**删除 9px 与 10px 两档**」。

实测 13 档，且分布是倒置的：

| 字号 | 次数 | | 字号 | 次数 |
|---|---|---|---|---|
| **9px** | **46** | | 14px（正文基准） | 5 |
| **10px** | **43** | | 18px | 5 |
| 11px | 34 | | 17px ⚠️离格 | 2 |
| 12px | 20 | | 16px | 1 |
| 13px | 8 | | 21px ⚠️离格 | 1 |
| **8px** | **5** | | 24px | 1 |
| | | | 25px ⚠️离格 | 1 |

- **94 处低于 11px 下限**（9px×46 + 10px×43 + 8px×5）。
- 规范基准 14px 只有 **5 处**，最常见的两档是被规范明令删除的 9px 和 10px。
- 17/21/25px 三个值不在阶梯上。

对一个中文科研记录工具，9px 正文违背 `design.md:381` 自己写的判据：「任何为视觉效果牺牲可读性、可扫描性的决定，都是在损害产品的核心价值」。

### 2.2 数字对齐

`design.md` §03「**全站数字启用 `font-variant-numeric: tabular-nums`** —— 指标、表格、参数、日期。现状缺失，数据类应用必须补，否则列对不齐」。

实测 `tabular-nums` **0 处**。这是一个表格密集的科研工具，参数列、日期列、编号列全部无法竖向对齐。

### 2.3 硬编码颜色

`design.md` §12.4「禁止硬编码 hex」。实测 **74 处**（`#fff`×8、`#111`×2、`#d71920`×2、`#0f1f2e`×2 等）。

### 2.4 圆角

`design.md` §05 定 3 档 + pill，并称「主文件里 **0 处硬编码圆角**」—— 那句话描述的是 `app/static/css`，不是产品。

实测 7 个像素值：`6px`×26 · `5px`×13 · `4px`×8 · `7px`×7 · `8px`×3 · `2px`×2 · `1px`×1（另有 `50%`×7）。`tokens.css:54-55` 已提供 `--radius-panel` / `--radius-control` 别名，`desktop.css` 一次都没用。

### 2.5 阴影

`design.md` §06 定 3 档且「只允许这三档」：面板 `--shadow-1`、浮层 `--shadow-2`、对话框 `--shadow-3`。

实测只有一档 `--shadow`（`desktop.css:1-26`）。结果面板、下拉、8 个 `<dialog>` 共享同一层级，**浮层失去了层次线索** —— 用户看不出哪个元素浮在上面。

### 2.6 命中区

`design.md` §07 + §10「触控目标 ≥ 44×44」，并给出现成写法（`.icon-btn` 36×36 + `::after { inset: -4px }`）。

实测 `.icon-button { width: 34px; height: 34px }`，`.icon-button::after` **0 处匹配**。34×34 命中区。

### 2.7 控件与主操作色

- `.button { min-height: 36px }` —— 规范 §07 定 40px（`tokens.css:68` 已有 `--control-height: 40px`）。
- `.button.primary { background: var(--ink) }`（近黑）+ `:hover { background: var(--accent-strong) }`（紫）。**主操作按钮 hover 时换色系**，规范 §07 要求 `--blue` 底 + `--blue-hover`。

### 2.8 布局比例

| 违规 | 条款 | 实测 |
|---|---|---|
| 空状态 220px | §11.5 ≤140px | `.empty-row td { height: 220px }`、`.data-list { min-height: 300px }` |
| 固定高度硬裁剪 | §11.6 必须用 `line-clamp` | `td { height: 42px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }`、`.data-list td { height: 54px }` |
| 首页无指标卡 | §07 METRIC + §11.8「数字即入口」 | `.dashboard-grid` 无指标卡，而服务层 `dashboard()` 已返回 `counts` |

§11.5 的 220px 空状态正是 `design.md:352` 表格里点名的那处违规 —— 规范记录了它，但因为记录在 Flask 层的语境里，产品这边从未修。

### 2.9 字体族

三套并存：
1. `desktop.css:1-26` 正文 `"思源宋体", "Source Han Serif SC", ..., serif`
2. `.brand strong { font: 800 16px/1 "Segoe UI", sans-serif }` / `.brand-mark { font: 900 14px/1 "Segoe UI", sans-serif }`
3. Lucide 图标字形

`tokens.css:17` 声明的 `--font-sans`（Inter / Microsoft YaHei UI / Noto Sans SC）未被使用。

**衬线正文本身是可辩护的**（注释理由：跨 WebView2 机器保持中文字形度量稳定，配 `font-synthesis: none` 避免伪粗体），但衬线 + 9px + 无 `tabular-nums` 三者叠加，表格区可读性与可扫描性同时受损。

### 2.10 外观（skin）分裂

- `skins.css` 只定义 `ide-light` / `ide-dark` / `swiss`，**没有 `soft-lab`**。
- 而 `soft-lab` 是发布默认：`index.html:2` `data-skin="soft-lab"`、`desktop.js:298` `localStorage.getItem("rlab-desktop-skin")||"soft-lab"`、`desktop_system.js:32` 设置界面。
- `desktop.css:29/36/46` 另有一份 `ide-light`/`ide-dark`/`swiss` 重复定义，`:74/75/101` 还有 swiss 组件覆盖。

**结果：外观定义分散在两个文件、两套令牌词汇，且发布默认外观在规范里不存在。** `design.md:87` 声明「三套受控外观」，产品发四套。

### 2.11 状态色不完整

`.status` 只映射 `.completed` 与 `.awaiting_analysis`，其余状态全部落到强调色 —— 不同状态视觉上无法区分。另外类名用中文业务值，违反 `design.md` §12.1（改文案会静默破坏样式且不报错）。

---

## 3 · 功能与后端缺陷

### 3.1 保存冲突无法恢复 —— 会丢用户输入

`app/desktop_ui/desktop_research.js`：

```js
async function saveRecord(){ ... catch(error){ setSaveState("error",error.message); toast(error.message); } }
function markDirty(){ ... state.dirty=true; ... state.saveTimer=setTimeout(saveRecord,900); }
```

失败后 `state.dirty` 仍为 `true`，`row_version` 不刷新。于是 `row_version_conflict` 下**每次击键都用同一个过期版本重发，永远失败**：持续「保存失败」、toast 刷屏、无重载/合并入口，而已输入内容只存在于 DOM 里。

`app/services/errors.py` 定义了 `ConflictError` → code `row_version_conflict`，服务层 `update_record`（`desktop_workspace.py:414-459`）的冲突检测是正确的（`row_version` 比对 + 带条件 UPDATE + `rowcount` 复核）。**但 `app/desktop_ui/*.js` 里 `row_version_conflict` 0 次匹配 —— 这个错误码前端从未处理。**

后端做对了，前端没接。

### 3.2 离开未保存记录用原生 confirm 且丢弃修改

`desktop.js:192`：

```js
if(state.dirty&&switchingRecord){if(!confirm("当前实验记录尚未保存，仍要离开吗？"))return;clearTimeout(state.saveTimer);state.dirty=false;}
```

问题两层：用原生 `confirm()`（而 `desktop.js:250` 已有 `R.confirmAction()` + `<dialog id="confirm-dialog">`，`desktop_planning.js`/`desktop_resources.js`/`desktop_system.js` 都在用）；且确认后**直接丢弃修改**，没有「保存后离开」。

### 3.3 批量导出阻塞 Bridge 线程

`bridge.py:206-256` `_export_records`：同步循环最多 200 条，逐条 `get_record` + `export_record`（docx/pdf 生成），**无任务号、无进度、无取消**。

**同一文件 `bridge.py:129-192` 已经是标准答案**：`zotero.sync.start/.status/.cancel` = 后台线程 + `threading.Event` 取消 + `progress(value, stage)` 回调 + 只保留最近 20 个已完成任务的注册表。照抄即可。

另两处：
- `record.export.batch` 与 `record.export_batch` 注册到同一处理器（`bridge.py:57-58`），命令面还经 `build_app_info` 对外发布。
- 文件名去重跑两遍且方案不同：先按 `used_names` 得到 `candidate_name`，再 `while target.exists()` 用 `f"{stem}-{counter}"` 重算 —— **丢掉批内后缀**，可能重复测试同一路径。

### 3.4 `record_count` 触发全表长文本加载

```python
# desktop_workspace.py:111
"record_count": len(project.lab_records),
# desktop_workspace.py:189
items = ResearchProject.query.options(selectinload(ResearchProject.lab_records))...
# desktop_workspace.py:198
return [self._project_dto(item) for item in items.order_by(...).all()]
```

`selectinload` + 无分页 `.all()` + `len()` = **为了取一个长度，把每条实验记录的全部长文本列都加载进内存**。`RECORD_FIELDS` 含 objective/background/design/analysis/conclusion 等大字段。项目和记录一多，首屏就开始拖。

`app/services/desktop_modules.py:158` 已有 `_page_result` 分页助手可复用。

### 3.5 `counts.projects` 永远 ≤ 5

```python
# desktop_workspace.py:163-165
projects = (...).limit(5).all()
# desktop_workspace.py:180
"counts": {"projects": len(projects), "records": sum(counts.values()), **counts},
```

`len()` 取的是 `.limit(5)` 之后的列表 —— **计数上限 5**。目前是潜伏 bug：前端从未消费 `counts.projects`（grep 只在 demo fixture 里命中）。而这恰好也是 §2.8 那条缺失：规范要求四张可下钻指标卡，服务层已备好数据，前端没做，于是错误的计数也没暴露。第 3 期做指标卡前必须先修。

### 3.6 `invoke()` 无超时、无并发控制

`desktop.js` 的 Bridge 包装：无超时、无 in-flight 去重、无全局忙态、无取消。Bridge 慢时用户重复点击会叠加请求。

### 3.7 记录双栏布局在运行时从未生效

`index.html` 写了 `.record-workspace` 双栏主从（列表 + `#record-inline-detail`），`desktop.css:163-174` 为它写了栅格、粘顶头部、`max-height: calc(100vh - 255px)`、1100px 断点。

但 `desktop_research.js:10` 在启动时 `recordEditSurface.append(recordInlineDetail)` 把详情面板搬进独立编辑页，`desktop.css:635` 再用 `grid-template-columns: 1fr` 覆盖成单栏。

**这是刻意的**，`desktop.css:632-634` 注释写明：「Records are a directory page followed by a dedicated editor page. The editor keeps the existing form, but no longer competes with the list for half of the viewport.」

所以 `:163-174` 是被故意覆盖的死代码。改造决定见 §4 第 3 期 —— 恢复双栏，但右栏改只读预览，编辑仍走全宽页，同时满足原顾虑。

---

## 4 · 分期路线

| 期 | 内容 | 为什么这个顺序 |
|---|---|---|
| **0** | 校准 `design.md`；新增 `tests/test_desktop_ui_design.py` 守 `app/desktop_ui/`（带基线豁免清单） | 不先立护栏，后面每期都会重新漂移 |
| **1** | 排版与字体：`--font-serif`/`--font-sans` 分工、表格数据区无衬线 + `tabular-nums`、按角色抬字号消除 94 处 <11px | 视觉影响最大且可独立验证 |
| **2** | 令牌回归：私有令牌改为指向 `tokens.css`、三档阴影、圆角归档、40px 控件 + 44×44 命中区、primary 改 `--blue`、补 `soft-lab` 并去重、状态色补全 | 依赖第 0 期的规范定稿 |
| **3** | 布局与 IA：恢复双栏主从（右栏只读预览）、四张可下钻指标卡、空状态 ≤140px、`line-clamp` | 行高变化需与第 1 期一起目视验证 |
| **4** | 功能与后端：冲突恢复、离开守卫、导出异步化、N+1、`counts.projects`、`invoke()` 超时 | 与样式解耦，可并行 |

第 4 期内部优先级：**3.1 保存冲突最先做** —— 它是唯一会真实丢用户输入的缺陷。

---

## 5 · 不在本次范围

**`app/services/desktop_modules.py` 拆分**（233,180 bytes / 4,335 行）。单文件混合了：

- Zotero HTTP 客户端（`_fetch_zotero_top_items`、`_fetch_zotero_items`、`ZoteroSyncCancelled`）
- docx 写出（`:597` `_write_record_docx`、`:1009` 表格模板版，内嵌 `set_font`/`shade_cell`/`table_borders`/`put_cell`，硬编码 `name="思源宋体"`、`size=9.2/8.8/8.1/8.2`）
- pdf 写出（`:844`、`:1248`）、markdown 写出（`:538`、`:1399`）
- 一个覆盖 literature/library/note/task/calendar/weekly/ai/search/trash/settings 的巨型 `DesktopModuleServiceMixin`（`:1437`）

值得拆（基础设施与业务逻辑混层，违反 `PROJECT_ARCHITECTURE.md` §4 的分层意图），但与本次审美/功能目标正交，改动面足以单独成期。

另记：`search()`（`:4002`）内联惰性重建 `SearchDocument` 后报 `mode="like"` + `diagnostic="FTS5 trigram 不可用，当前使用 LIKE 降级搜索"` —— 需确认 FTS5 降级是环境所致还是索引未建。

**导出字体硬编码**（`size=9.2/8.8/8.1` 等）属于 docx 输出版式，与屏幕字号下限是两件事，本次不动。
