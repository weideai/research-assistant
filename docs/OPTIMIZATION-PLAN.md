# R/LAB 软件优化建议书

> 产出日期：2026-08-01
> 配套文档：`design.md`（视觉规范）· `docs/IA-MAP.md`（页面与按键结构图）· `docs/UX-IA-V3.md`（信息架构）
> **本文只提建议，不含已执行的改动。**

## 定位收敛

软件收敛成**纯管理型工具**，只管明白三件事：

```
实验记录  ·  物品  ·  周报
```

其余交出去：日常事务 → 飞书 · 文献 → Zotero（只借鉴其「本地文件库 + 元数据 + 一秒检索」的交互思路，不做集成）。

已确认的四个决策：

| 议题 | 决策 |
|---|---|
| Zotero | 只借鉴交互模式，不集成。本软件不做文献模块 |
| 统计 | 指之前已删除的功能，已完成。总览现有 4 个指标卡不动 |
| 任务模块 | 保留现状（飞书承接日常，但软件内 `/tasks` 不删） |
| 云盘 | 显式化现有「外部数据链接」机制，不写任何云盘 SDK |

---

## A. 已经实现的（不必再做）

| 方向 | 现状证据 |
|---|---|
| 样品改成物品管理 | 侧栏已显示「物品管理」（`app/templates/base.html`）。**但路由仍是 `/samples`、模型仍是 `Sample`** —— 只改了 UI 文案，代码层没改，见 D2 |
| 论文去掉 | 全库无文献模块 —— 已移除 |
| 统计去掉 | 已移除 |
| 上传周报、管理周报 | `WeeklyReport`（`app/models.py:265`）完整：上传、报告日期、覆盖周期、状态、摘要、归档目录、SHA-256、文件大小 |
| 老板和其他人的意见整理到备注 | `WeeklyReportUpdate`（`app/models.py:296`）已是按 `entry_date` 排序的反馈时间线，支持「标记完成 / 待处理」 |
| 助手加 API 链接快捷 | AI Dock 头部 `#ai-api-settings` → `/settings/api`。侧栏、账号菜单还各有一个，**共 3 个入口**（见 D5） |
| 导出实验记录 | `/records/<id>/export?format=pdf\|docx` · `/experiments/<id>/export` · `export.md` · `archive.zip` |
| 附件模块放所有原始结果 | `ExperimentAttachment` + 记录详情「文件与数据」tab + 文件中心 + 单实验文件中心，四层齐备 |
| 网盘作为本地管理内容 | 「外部数据链接」已存路径 + SHA-256 + 清单，**不复制原文件**；有「校验完整性」「在资源管理器打开」 |

---

## B. 被数据结构挡住的（必须改模型）

### B1 物品数量是字符串 —— 「样品管理最大的问题」的根因

```python
Sample.quantity               = db.Column(db.String(60))   # models.py:590
ExperimentSample.amount_used  = db.Column(db.String(80))   # models.py:608
BatchSample.amount_used       = db.Column(db.String(80))   # models.py:620
```

`"5 g"` / `"约5克"` / `"5g"` / `"五克"` 都能存进去。后果：

- 算不出「产的样本多少 g」—— 无法求和
- 消耗不扣库存 —— `BatchSample.amount_used` 写了多少，`Sample.quantity` 纹丝不动
- 总览的「可用样本 N 个」只是数了行数，不反映实际余量
- 无法排序、无法预警「快用完了」

**建议**

```
quantity_value    DECIMAL(12,4)
quantity_unit     ENUM(g, mg, µg, kg, mL, µL, L, 管, 只, 板, 瓶, 支)
initial_quantity  DECIMAL(12,4)     # 入库量，用于算消耗比例
```

新增 `ItemLedger`（物品流水）：

```
item_id · 类型(入库/消耗/报废/盘点/转移) · 数量 · 单位 · batch_id · 操作日期 · 备注
```

**库存 = 流水求和**，而不是手工维护的一个数 —— 任何一次实验消耗都自动可追溯。

### B2 物品无分类体系 —— 「模块化」的落点

```python
Sample.sample_type = db.Column(db.String(80), default="")   # 自由文本
```

**建议**：`category` 枚举 + 每类专属字段（子表或 JSON 列）

| 分类 | 专属字段 |
|---|---|
| 引物 | 序列、方向 F/R、Tm、长度、纯化方式、合成公司 |
| 动物 / 小鼠 | 品系、性别、周龄、耳号、笼位、伦理批号 |
| 药物 / 试剂 | CAS 号、浓度、溶剂、储存温度、开封日期、有效期 |
| 抗体 | 宿主、克隆号、推荐稀释比、应用（WB / IHC / IF） |
| 细胞株 | 代次、支原体检测日期、培养基 |
| 质粒 | 抗性、载体骨架、测序验证状态 |
| 组织 / 样本 | 来源个体、取材日期、保存方式、冻存位置 |

**公共字段**：编号 · 名称 · 分类 · 数量+单位 · 位置 · 状态 · 有效期 · 供应商 · 批号 · 备注

列表页按分类分 tab，每个 tab 的表格列随分类变化 —— 引物显示序列和 Tm，小鼠显示品系和耳号。

### B3 实验记录缺 4 个字段

| 现有 | 缺失 |
|---|---|
| `conditions`（条件）· `content`（正文）· `result`（成功/失败/待确认）· `remark`（备注） | **材料与设备** · **方法** · **意外情况说明** · **结果分析** |

**连带影响（重要）**：`Experiment` 只有三个模板槽 —— `record_conditions_template` / `record_content_template` / `record_remark_template`（`models.py:330-332`）；`RecordTemplate` 也只有 conditions / content / remark 三段。

> **加字段必须同步扩展模板结构**，否则模板填不满新表单，「用模板新建记录」会留下一半空白。

**建议**一次性把记录字段定为七段，模板结构与之一一对应：

```
① 目的        ② 材料与设备    ③ 方法 / 步骤    ④ 过程记录（正文）
⑤ 结果分析    ⑥ 意外情况说明  ⑦ 备注
```

---

## C. 逐条建议

### C1 「查看要像记录模板的样子，看到什么就导出什么 PDF」

现状 `experiment_reports.html` 已是阅读器（左记录列表 + 右阅读器 + 上/下翻页 + 导出 PDF/Word），但它的排版顺序和「记录模板」的字段顺序**不是同一套定义** —— 分别写死在模板文件和 `export_service.py`（1422 行）里。

> **建议：一处定义，三处渲染。**
> 让记录模板成为字段顺序与标题的唯一来源，**编辑表单、阅读视图、PDF 导出共用同一份字段定义**。
> 这样「查看 = 模板的样子」「导出 = 看到的样子」自动成立，不需要三处手工对齐。

### C2 「编辑完，生成结果，什么一下都能找到」

记录定稿（`finalize`）后自动生成一张**记录卡** —— 结论 + 关键参数 + 2 张核心图 + 附件数 + 本次消耗的物品 —— 并进入全局检索索引。

> 配合真正的全局搜索（D1）这条才成立。**目前没有全局搜索，这是最大的阻碍。**

### C3 「留下编辑时间 / 展示上一次的修改时间」

数据全都有（`TimestampMixin.updated_at`），纯粹是没显示。当前只有 `experiment_report_index.html` 显示了 `record.updated_at`。

**统一显示位置**：记录详情页头 · 执行详情页头 · 实验详情页头 · 附件行 · 物品行 · 周报行 · 文件中心表格列

**格式**：7 天内显示相对时间（「3 小时前编辑」），超过 7 天显示绝对日期（「最后编辑 2026-07-18」）

### C4 云盘显式化

- 设置里新增「**原始数据根目录**」，指向已同步的 OneDrive / 坚果云 / 百度网盘本地文件夹
- 外部链接改存**相对根目录的路径** —— 换电脑、换盘符不失效（现在存绝对路径，换机就全断）
- 界面显示三态：**在线**（文件存在且 SHA-256 匹配）/ **未同步**（云端有本地无）/ **已丢失**（路径无效）
- 不写任何云盘 SDK，跨网盘通用

### C5 看板模式

一个视图组件，两处入口：

| 看板 | 列 | 卡 |
|---|---|---|
| 实验台看板 | 实验计划状态（未开始 / 进行中 / 完成 / 暂停） | 实验计划 |
| 执行看板 | 执行状态 | 实验执行，卡上显示「已 N 天未记录」 |

拖拽改状态直接复用现有 `POST /experiments/<id>` 与 `POST /batches/<id>`，**不需要新路由**。列表视图与看板视图共用同一套筛选条件，右上角切换。

### C6 「把物品、实验记录、周报管明白」—— 三者打通

```
物品  ──（某次执行消耗，自动扣库存 + 写流水）──►  实验记录
                                                      │
                                                      │（本周产出）
                                                      ▼
                                                    周报
```

- 物品详情页已有「反查使用」，补上**消耗流水**（哪次执行、用了多少、还剩多少）
- 周报页补「**本周涉及的实验执行与记录**」自动汇总 —— 现在只有手动勾选实验生成 PPT，写周报时还得自己回忆这周做了什么

---

## D. 结构性问题

### D1 没有全局搜索 —— 第一优先级

顶栏那个带 `⌘K` 角标、长得完全像搜索输入框的控件，实际是 `<a href="/experiment-reports">`（`app/templates/base.html`）。

Ctrl+K 确实有绑定（`app/static/js/app.js:1766`），但它只是**聚焦当前页面的本地搜索框**；在总览、实验台、实验计划、任务、模板中心、物品管理、回收站以及所有详情页上没有本地搜索框，于是直接把你跳走。

现有搜索是**四个互不相通的局部搜索**：文件中心 · 实验报告 · 回收站 · 周报。
**搜不到**：项目 · 实验计划 · 实验执行 · 物品 · 模板 · 参数值。

> **建议**：一个真正的全局搜索，跨 项目 / 计划 / 执行 / 记录 / 附件 / 物品 / 周报 / 模板 八类，按类型分组显示结果。这是「什么一下都能找到」的唯一实现路径。

### D2 命名分裂成三层

| 业务语言（CONTEXT.md） | 代码 | URL | UI |
|---|---|---|---|
| 实验执行 | `ExperimentBatch` | `/batches/<id>` | 实验执行 |
| 过程记录 | `ExperimentRecord` | `/records/<id>` | 过程记录 |
| 物品 | `Sample` | `/samples` | 物品管理 |
| 周报 | `WeeklyReport` | `/reports/presentation` | 周报 |

`CONTEXT.md` 明确写了「代码中的 `ExperimentBatch` 是这一概念的兼容名称」—— 说明这是已知的历史债，但还没还。改一处必漏一处。

### D3 导航 11 项平铺，父子关系被拍平

实验台(项目) ⊃ 实验计划 ⊃ 实验执行 ⊃ 过程记录 是一条链，导航却把「实验台」和「实验计划」并列；「实验报告」和「文件中心」是同一批数据的两个视图，也并列。

**建议 11 → 8**（保留任务模块）：

```
工作   总览 · 实验台（含「全部计划」tab） · 任务
资料   报告与文件（两 tab 合并） · 周报
复用   模板中心 · 物品管理
系统   → 收进账号菜单（API 设置 · 回收站 · 账号安全 · 系统管理，四处入口均已存在）
```

**所有路由保留，只改导航呈现，零功能丢失。** 功能去向对照见 `docs/IA-MAP.md` §7。

### D4 `experiment_detail.html` 单页堆了 10 个区块

251 行模板里塞了：概览 / 方案 / 步骤 / 参数 / 样本 / 记录模板 / 实验执行 / 最近记录 / 附件 / 删除，只靠锚点跳转。`batch_detail.html`（165 行）同样。

对照 `record_detail.html` 已经用了**四标签页**（阅读 / 编辑 / 文件与数据 / 模板与修订），效果明显更好 —— 这个模式没有推广。

### D5 同一功能多入口，且没有权威入口

| 功能 | 入口数 | 分布 |
|---|---|---|
| 新建实验执行 | 3 | 项目详情的纯 `+` 图标按钮 / 实验详情的文字按钮 / 总览引导卡 —— 样式与文案各不相同 |
| 应用方案模板 | 3 | 模板中心「应用模板」/ 实验详情「调用」/ 实验列表「使用模板创建」 |
| API 设置 | 3 | 侧栏 / 账号菜单 / AI Dock 头部 |

### D6 死代码

`app/templates/presentation_report.html`（38 行）没有任何 `render_template` 引用 —— `/reports/presentation` 实际渲染的是 `weekly_reports.html`。

### D7 无障碍硬伤（实测数据）

- `--muted` 在 `--bg` 上仅 **4.27:1**，未达 WCAG AA 的 4.5:1。`.muted` 承载了几乎全部页面说明文字。
  实测有 **两个**主题未达标：`default` (#697581, 4.27:1) 与 `cute` (#687983, 4.23:1)；其余 6 个主题（含 4 个暗色）已达标
- 存在 **93 处** 9px/10px 字号（`app.css` 62 处、`assistant.css` 31 处）—— 中文在 10px 以下不可辨认
- `.icon-btn` 为 **34×34px**，低于 WCAG 2.5.5 建议的 44×44。另有 5 处更小的覆盖（AI dock 30–32px、文件中心 32px）

### D8 中文业务值被当作 CSS 类名

`.priority-高` `.status-进行中` `.result-成功` `.state-暂停` `.sample-可用` —— 样式直接耦合业务文案，任何文案调整都会**静默**破坏样式，不报错。

### D9 设计令牌与皮肤层（已完成）

裸色值已归零，调色板集中到 `app/static/css/tokens.css`。质量较低的多皮肤、暗色模式与自定义背景已整体退役，`themes.css` 已删除，应用固定为黑白灰 + 信号红界面。

### D10 `main.py` 6133 行单文件，含 110+ 路由

物品管理、周报、AI 助手、模板、文件、导出全在一个文件里。要做到「功能明确」，先按模块拆蓝图 —— `workspace.py` 已经拆出去一部分，是个好开头。

---

## E. 界面比例与信息密度 —— 「不要有些部分占比过大」

### E1 低频创建表单常驻，挤压高频浏览区（系统性问题）

| 页面 | 现状 | 问题 |
|---|---|---|
| `projects.html` | `.workspace-layout { minmax(0,1fr) 330px }` + `.project-create-panel { position: sticky }` | 1440px 视口下「新建项目」表单**粘性常驻**，吃掉内容区约 **31%**。而建项目是极低频操作 |
| `experiments.html` | `.workspace-intro` 创建区在页面**最顶部**，`<details class="creation-choice" open>` 默认展开六字段表单 | 实验计划列表被挤出首屏 —— 打开「实验计划」页看不到实验计划 |
| `template_center.html` | 「新建空白模板」+「从参考模板生成」**两个创建表单**都排在模板库之前 | 同上 |

> **建议**：统一改为「页头主按钮 + 抽屉/对话框」。首屏只放内容，创建走浮层。
> `tasks.html` 顶部的快速添加表单**保留** —— 加任务是高频、单行、成本低，是正确的例外。

### E2 固定高度硬裁剪

- `.experiment-card > p { height: 44px; overflow: hidden }` —— 短描述留白、长描述被生硬切断
- `.experiment-card { min-height: 270px }` × 3 列 —— 一屏最多看 6 个实验计划
- `.empty { min-height: 220px }` —— 空状态比很多有内容的面板还高

> **建议**：文字截断改 `-webkit-line-clamp: 2`（按行截断，自适应）；卡片高度自适应，去掉 `min-height`；空状态降到 140px。

### E3 实验报告卡片承载过多 —— 「实验报告等功能要简单」

`experiment_report_index.html` 一张卡塞了 **5 个区域 + 3 个按钮**：

```
头部（日期 / 执行号 / 标题 / 项目 / 人员 / 结果徽章）
三段文字（目的 / 过程记录 / 结果备注）
2 张缩略图  +  文件夹链接
底部（修改时间 + 导出 PDF + 导出 Word + 打开完整报告）
```

且 `.report-feed-grid { minmax(0,1fr) minmax(250px,.72fr) }` —— 图片区固定占约 **42%**，**没有图片时这 42% 全部是 `.report-thumb-empty` 空白占位框**。

> **建议**：卡片降到四件事 —— 标题 + 结果徽章 + 一段结论 + 缩略图（有才显示）+ 一个主操作「打开报告」。
> 导出 PDF/Word 移到报告详情页（`experiment_reports.html` 已经有了，卡片上是重复）。
> 无图时文字区占满宽度，不留空位。

### E4 首屏 153px 给了 4 个不可点击的数字

`.metric { min-height: 135px }` × 4 + 18px margin。指标卡既不可点击也不可下钻，纯展示。

> **建议**：高度降到 96px；让每张卡可点击跳转到对应列表（今日待办 → `/tasks?status=待办`，进行中计划 → `/experiments?status=进行中`），把静态数字变成入口。

---

## G. 导出与报告格式（Word / PDF）

现有导出能力：**JSON · Markdown · DOCX · PDF · XLSX · ZIP 资料包**，六种格式，实现全部在 `app/export_service.py`（1422 行）。

### G1 三套报告模板，只有 PDF 生效 —— Word 完全忽略 ⚠️

```python
# app/main.py:3951   Word —— 没传 template
_binary_export_response(build_docx_export(item, _attachment_path), item, "docx", ...)

# app/main.py:3957   PDF —— 传了
_binary_export_response(build_pdf_export(item, _attachment_path, report_template), item, "pdf", ...)
```

`build_docx_export(item, attachment_path_resolver=None)` 的签名里**根本没有 `template_key` 参数**（`export_service.py:666`）。用户在界面上选了「实验记录本」再导 Word，拿到的还是「科研档案」的样子。

记录级同样：`build_record_docx_export(record, _attachment_path)`（`main.py:3976`）不接模板，而 `build_record_pdf_export(record, template_key, _attachment_path)`（`main.py:3983`）接。

> **这是明确的功能缺陷，不是设计取舍。** 界面提供了选择，Word 分支静默丢弃。

### G2 模板只换配色，不换结构

```python
REPORT_TEMPLATES = {
    "research": {"label": "科研档案", "kicker": "RESEARCH RECORD",
                 "accent": "2166F3", "text_accent": "174EA6",
                 "soft": "EDF3FF", "include_hash": True},
    "notebook": {...},   # 实验记录本
    "compact":  {...},   # 简洁结果报告
}
```

六个变量**全是外观**。章节顺序（`01 实验概览` / `02 实验目的` / …）、字段选择、表格列全部硬编码在 `build_docx_export`（145 行）与 `build_pdf_export`（340 行）里。

想删掉某一章、调换顺序、加一个字段 —— **只能改 Python 源码**。

### G3 同一份报告有 4 套独立实现

| 函数 | 行数 | 作用域 |
|---|---|---|
| `build_docx_export` | 145 | 实验级 Word |
| `build_record_docx_export` | 65 | 记录级 Word |
| `build_pdf_export` | 340 | 实验级 PDF |
| `build_record_pdf_export` | 195 | 记录级 PDF |
| `_markdown_from_payload` | 146 | Markdown |
| `build_xlsx_export` | 75 | Excel |

每套各自维护一遍章节顺序与字段列表。**加一个字段要改 6 处。**

> B3 提的「记录 7 段字段」一旦落地，这 6 处全部返工 —— 所以 G 与 B3 应当合并规划，见 §I。

### G4 PDF 中文字体靠碰运气 —— 真实部署风险 ⚠️

```python
def _pdf_font_name():
    candidates = [
        os.getenv("RESEARCH_ASSISTANT_PDF_FONT", ""),
        r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\Deng.ttf", r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
        r"/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        r"/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    ...
    return "Helvetica"        # ← 全部找不到时的兜底
```

**Helvetica 没有中文字形。** 走到这个分支，导出的 PDF 中文会全部变成空白或方块 —— 而且**不报错**，用户拿到一份看起来正常、打开全空的 PDF。

Docker 镜像和 Linux 安装包如果没显式安装 Noto CJK，用户第一次导 PDF 就是这个结果。

> **建议**：字体文件随包分发（Noto Sans SC Regular 约 5–8 MB），或在应用启动自检时检测并**明确报错**，而不是静默降级到一个不可用的字体。

### G5 缺 HTML 导出

现有六种格式里没有 HTML。HTML 可以直接贴进邮件、OneNote、飞书文档，是汇报场景最省事的格式，且实现成本低于 PDF。

---

## H. 能不能上传模板让 AI 换格式？

**可行 —— 但必须先把三个层次分开，它们的可行性完全不同。**

| 层次 | 要换的东西 | Word | PDF |
|---|---|---|---|
| **外观层** | 字体、字号、页边距、页眉页脚、标题样式、表格样式 | ✅ **成本极低** | ❌ 只能参数化 |
| **结构层** | 章节顺序、章节标题、每章含哪些字段、表格列 | ✅ | ✅ |
| **像素级复刻** | 完全复刻一份现有 PDF 的排版 | — | ❌ **不建议做** |

### H1 外观层 —— Word 上传模板，几乎零成本

`python-docx` **已经是依赖**（`requirements.txt: python-docx==1.2.0`）。它支持以一份现有 `.docx` 作为基底：

```python
document = Document(user_template_path)   # 继承样式表、页边距、页眉页脚
# 清空正文，再照常 add_heading / add_paragraph / add_table
```

用户上传自己课题组的报告模板 —— 哪怕只是一份空白的、设好了 `Heading 1/2/3`、`Normal`、`Table Grid` 样式和页眉页脚页边距的 `.docx` —— 导出就自动继承它的外观。

> **不需要 AI，不需要新依赖，改动量很小。** 这是投入产出比最高的一项。

**限制**：只继承**样式定义**，不继承内容布局；用户模板里已有的正文需要清空。

**PDF 不能这么做** —— reportlab 是从零绘制，没有「继承一份 PDF」的概念。PDF 的外观只能靠 `REPORT_TEMPLATES` 这类参数化配置扩展（增加字体、页边距、页眉页脚、logo 等字段）。

### H2 结构层 —— 这才是 AI 该做的事

把「报告结构」从 Python 代码里抽出来，变成一份可存储、可编辑、**可由 AI 生成**的结构描述：

```json
{
  "name": "课题组标准实验报告",
  "sections": [
    {"key": "overview",    "title": "01 实验概览",     "layout": "kv",
     "fields": ["code", "status", "owner", "start_date", "end_date"]},
    {"key": "objective",   "title": "02 实验目的",     "source": "experiment.objective"},
    {"key": "materials",   "title": "03 材料与设备",   "source": "record.materials"},
    {"key": "method",      "title": "04 方法与步骤",   "source": "record.method"},
    {"key": "records",     "title": "05 过程记录",     "layout": "table",
     "columns": ["record_date", "operator", "content", "result"]},
    {"key": "analysis",    "title": "06 结果分析",     "source": "record.analysis"},
    {"key": "incidents",   "title": "07 意外情况说明", "source": "record.incidents"},
    {"key": "attachments", "title": "08 附件清单",     "layout": "table", "previews": 2}
  ],
  "appearance": {
    "accent": "2166F3", "include_hash": true,
    "docx_base": "uploads/report-templates/<user>/lab-standard.docx"
  }
}
```

**Word 渲染器和 PDF 渲染器都读这同一份描述** —— 这正是 §C1「一处定义，多处渲染」的延伸：

```
                      ┌──►  编辑表单
                      ├──►  阅读视图
  报告结构描述  ──────┼──►  Word 渲染器
   （唯一事实来源）    ├──►  PDF  渲染器
                      ├──►  Markdown 渲染器
                      └──►  HTML 渲染器
```

一次定义解决 G2（结构不可改）、G3（6 处重复）和 C1（查看 ≠ 导出）三个问题。

**AI 的角色**：用户上传一份现有实验报告（师兄的、期刊要求的、课题组模板）→ AI 读它 → 推断章节结构 → 生成上面这份 JSON → **展示 diff 让用户确认** → 保存为一个报告模板。

这完全复用现有的 AI 提案机制（`assistant_apply_proposal` `main.py:5444` / `assistant_revert_proposal` `main.py:5768`），**不需要新的安全模型** —— AI 只生成结构描述，不生成可执行内容、不直接产出文件。

### H3 AI 读模板需要补的解析能力

现状 `_extract_text_excerpt`（`app/main.py:1692`）：

| 格式 | 现状实现 | 够不够 |
|---|---|---|
| 纯文本 / `.md` | 直接 `decode` | ✅ 够 |
| `.docx` | `zipfile` 抠 `word/document.xml` + 正则去标签 | ❌ **只拿到文字**，标题层级、表格、样式全丢 |
| `.pdf` | 列在 `DOCUMENT_EXTENSIONS` 里但**没有实现分支**，返回空字符串 | ❌ 无 |
| 图片 | 无 | 需 vision 模型（`ai_service.py:111` 已有能力检测） |

**建议**：

- **`.docx`** 改用已有的 `python-docx` 读 `paragraph.style.name` —— 直接拿到 `Heading 1/2/3` 层级与表格结构。**这是最准的输入，且零新依赖**，应作为唯一推荐的上传格式
- **`.pdf`** 需要新依赖（`pypdf` 提文本层，或 `pdfplumber` 连表格一起提）。**建议先不做** —— PDF 是导出格式，不是输入格式；让用户上传 Word 即可
- **图片** 走 vision 模型作为兜底（拍一张师兄报告的照片）。优先级最低

### H4 边界与风险

- AI 推断的结构**必须经用户确认才能保存**，不能自动生效 —— 沿用现有 diff 确认机制
- 用户上传的 `.docx` 作渲染基底时，须校验是合法 zip、限制体积、**剥离宏与外部引用**
- 报告模板应可导出 / 导入，方便课题组内共享 —— `.ralab` 项目包已有类似机制可复用
- **不做像素级 PDF 复刻**：投入产出比极差，且永远做不像

### H5 落地顺序（这一块内部的顺序很关键）

```
① 修 Word 忽略模板的缺陷（G1）           —— 独立，可立刻做
② 修 PDF 中文字体兜底（G4）              —— 独立，可立刻做
③ 抽出「报告结构描述」+ 统一渲染器（G2/G3/C1）—— 必须在 B3 加字段之前或同时
④ Word 上传模板作基底（H1）              —— 依赖 ③
⑤ AI 读 .docx 推断结构（H2/H3）          —— 依赖 ③④
⑥ HTML 导出（G5）                        —— 依赖 ③，顺手就有
```

> **③ 是枢纽。** 不先做它，B3 的 7 段字段会让 6 个渲染函数各返工一遍；做了它，加字段只改一处描述。

---

## I. 全项目优化总路线

### 阶段划分

| 阶段 | 主题 | 内容 | 动数据库 |
|---|---|---|---|
| **P0** | 止血 | 全局搜索（D1）· 补最后编辑时间（C3）· 无障碍三项（D7）· 删死代码（D6）· 界面比例四项（E1–E4）· **Word 忽略模板（G1）**· **PDF 字体兜底（G4）** | 否 |
| **P1** | 渲染统一 | **抽出「报告结构描述」，统一 Word/PDF/Markdown/HTML/阅读视图五处渲染（G2 · G3 · C1）**· HTML 导出（G5） | 否 |
| **P2** | 数据结构 | 物品数量数字化+单位（B1）· 物品分类+专属字段（B2）· 记录 7 段字段（B3）· `ItemLedger` 流水表 | **是，一次迁移做完** |
| **P3** | 体验 | 看板模式（C5）· 详情页分标签页（D4）· 导航 11→8（D3）· 物品-记录-周报闭环（C6）· **Word 上传模板作基底（H1）** | 否 |
| **P4** | AI 增强 | **AI 读 `.docx` 推断报告结构（H2 · H3）**· 记录卡自动生成（C2）· 云盘根目录显式化（C4） | 少量 |
| **P5** | 工程债 | 命名统一（D2）· 类名解耦（D8）· 令牌收敛（D9）· `main.py` 拆蓝图（D10）· 多入口收敛（D5） | 部分（重命名迁移） |

### 关键依赖

```
P1（报告结构描述）
   │
   ├──► P2（记录 7 段字段）      不先做 P1，加字段要改 6 个渲染函数
   ├──► P3（Word 上传模板）      基底样式需要挂在结构描述上
   └──► P4（AI 推断结构）        AI 的输出目标就是这份描述
```

**两条硬约束：**

1. **P1 必须在 P2 之前** —— 否则 B3 的 7 段字段会让 6 个渲染函数各返工一遍
2. **P2 必须一次做完** —— 物品字段、记录字段、流水表分三次改会产生三次迁移和三轮模板返工

### 每阶段的验收标准

| 阶段 | 验收 |
|---|---|
| P0 | 任意页面按 ⌘K 能搜到项目/计划/执行/记录/物品/周报/模板；导 Word 时三套模板外观确实不同；无字体的干净容器里导 PDF 会明确报错而非输出空白 |
| P1 | 改一处结构描述，Word / PDF / Markdown / HTML / 阅读视图五处同步变化 |
| P2 | 物品消耗自动扣库存并写流水；「本月产出样本 X g」可直接算出 |
| P3 | 上传一份课题组 `.docx` 模板，导出的 Word 继承其字体、页边距、页眉页脚 |
| P4 | 上传师兄的实验报告 `.docx`，AI 给出结构提案 → 用户确认 → 成为可选报告模板 |
| P5 | 全库无中文 CSS 类名；`app.css` 无裸 hex；`main.py` < 1500 行 |
