# R/LAB DESIGN SYSTEM

**01 · STYLE GUIDE**

> ## Data-Dense Swiss
> ### 数据密集型瑞士风格
>
> 以网格系统、理性排版、无衬线字体、客观的信息层级和高效的视觉传达为核心特征。
> **为快速比对与扫读优化，不为视觉炫技优化。**

**KEYWORDS** — Grid System · Typography First · Clarity · Functionality · Objectivity · Minimalism

**产品** R/LAB Research Assistant · 单人科研工作台
**载体** 桌面固定画布的 Flask + Jinja2 多页应用，唯一 Swiss 研究主题
**版本** v1.1 · 2026-08-02

---

> ⚠️ **本文是新增页面的唯一参照。**
> 任何新页面、新组件在写第一行代码前必须先对照本文。现有页面按 `docs/OPTIMIZATION-PLAN.md` 的分期路线分批对齐，不要求一次改完。
> 配套文档：`docs/IA-MAP.md`（页面与按键结构图）· `docs/OPTIMIZATION-PLAN.md`（功能优化建议）· `docs/UX-IA-V3.md`（信息架构）

---

## 02 · COLOR PALETTE

### 信号色 PRIMARY

| 色卡 | Token | 值 | 用途 |
|---|---|---|---|
| ██ | `--blue` | `#d71920` | 主按钮、链接、聚焦环、eyebrow、活动指示 |
| ██ | `--blue-ink` | `#a51218` | 浅红底上的文字，实测 7.03:1 |
| ░░ | `--blue-soft` | `#fff0f1` | 信息底色、选中态 |

> `--blue` 是为兼容现有组件保留的语义令牌名；默认 `research` 主题中它映射为 Swiss Style 信号红。状态成功、警告与危险仍使用各自语义令牌。

### 强调色 ACCENT

| 色卡 | Token | 值 | 用途 |
|---|---|---|---|
| ██ | `--brand-accent` | `#d71920` | 品牌方块、侧栏活动指示条 |

> 品牌红上的文字统一使用 `--on-accent #fff`，实测对比度 **5.19:1**。信号红只承担品牌、主操作和活动指示，不作为大面积页面底色。

### 中性色 NEUTRAL

| 色卡 | Token | 值 | 用途 |
|---|---|---|---|
| ░░ | `--bg` | `#f2f2ef` | 页面底色 |
| ░░ | `--surface` | `#ffffff` | 面板、卡片、输入框 |
| ░░ | `--surface-soft` | `#f7f7f4` | 表头、次级填充 |
| ▒▒ | `--line` | `#d8d8d3` | 所有 1px 描边 |
| ▓▓ | `--muted` | **`#5f5f5b`** | 次要文字、说明文案 |
| ██ | `--ink` | `#111111` | 正文与标题 |
| ░░ | `--sidebar` | `#f7f7f4` | 浅色侧栏底色 |
| ██ | `--sidebar-ink` | `#111111` | 侧栏主文字 |

> 默认主题的 `--muted` 在 `--bg` 上实测 **5.72:1**、在白色面板上 **6.41:1**。侧栏文字独立使用 `--sidebar-ink`，避免浅色侧栏继续继承白字。

### 语义色 SEMANTIC —— 双档制

每个语义色分**填充档**与**文字档**。填充档三色在白底上均不足 4.5:1，**绝不能直接作正文颜色**。

| 语义 | 填充档（背景 / 描边 / 圆点） | 白底对比度 | 文字档 | 浅底 |
|---|---|---|---|---|
| 成功 | `--green` `#008a62` | 4.36:1 ❌ | `--green-ink` `#006b4b` | `#e3f7ef` |
| 危险 | `--red` `#e5484d` | 3.91:1 ❌ | `--red-ink` `#b4232a` | `#ffeaec` |
| 警告 | `--yellow` `#c77c02` | 3.31:1 ❌ | `--yellow-ink` `#8b5903` | `#fff3d6` |
| 信息 / 主操作 | `--blue` `#d71920` | 5.19:1 ✅ | `--blue-ink` `#a51218` | `#fff0f1` |

```css
/* ✅ 正确 */
.badge-success { background: var(--green-soft); border-color: #bce8d7; color: var(--green-ink); }
.status-dot    { background: var(--green); }

/* ❌ 错误 —— 填充档色不能作文字 */
.text-success  { color: var(--green); }
```

代码里 `.result-成功`、`.priority-高` 已经自发用了 `-ink` 值，本规范把这个做法固化为制度。

### 固定界面约束

软件只保留一套黑白灰 + 信号红的 Swiss 桌面界面，不提供皮肤、暗色模式或自定义背景。

> **所有组件只能引用 `var(--token)`，禁止硬编码 hex。**
> 调色板集中在 `tokens.css`；`app.css` 与 `assistant.css` 中保持 **0 个裸色值**。

---

## 03 · TYPOGRAPHY

```css
--font-sans: "Inter", "Microsoft YaHei UI", "Noto Sans SC", system-ui, sans-serif;
--font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Consolas, monospace;
```

**`--font-mono` 强制用于**：实验编号 `EXP-2026-001` · 批次编号 · 结构化参数值 · SHA-256 · 文件路径 · 时间戳。

### 字号阶梯 SCALE

| Token | 值 | 用途 |
|---|---|---|
| `--fs-display` | 32px | 大数字指标 |
| `--fs-h1` | `clamp(26px, 3vw, 34px)` | 页面标题 |
| `--fs-h2` | 20px | 面板标题 |
| `--fs-h3` | 16px | 区块标题 |
| `--fs-body` | **14px** | 正文（基准） |
| `--fs-sm` | 13px | 次要正文、表格辅助信息 |
| `--fs-caption` | 12px | 标签、说明、`small` |
| `--fs-micro` | 11px | **仅限** eyebrow / 徽章 / 表头，且必须大写拉丁或数字 |

> **删除 9px 与 10px 两档。** 品牌署名、侧栏本地状态和附件元数据等中文辅助文字全部保持在 11–12px。

### 字重 WEIGHT

`400` 正文 · `600` 强调 · `700` 小标题·按钮 · `800` eyebrow·表头 · `900` 品牌

### 行高 LEADING

标题 `1.25` · 正文 `1.55` · 密集表格 `1.4`

### 字距与数字

- eyebrow 与表头：`letter-spacing: .08em; text-transform: uppercase`
- 其余：`letter-spacing: 0`
- **全站数字启用 `font-variant-numeric: tabular-nums`** —— 指标、表格、参数、日期。现状缺失，数据类应用必须补，否则列对不齐。

---

## 04 · SPACING · 4pt 基准

```css
--space-1:  4px;   --space-2:  8px;   --space-3: 12px;   --space-4: 16px;
--space-5: 20px;   --space-6: 24px;   --space-8: 32px;   --space-10: 40px;
--space-12: 48px;  --space-16: 64px;
```

| 场景 | 值 |
|---|---|
| 面板内边距 | `20 22`（头部同为 `20 22`，见下方实测） |
| 面板之间 | `16` |
| 页面上 / 下 | `32` / `64` |
| 页面左右 | `clamp(24px, 4vw, 56px)` |
| 表单字段之间 | `12` |
| 表单组之间 | `20` |
| 表格单元格 | `12 16` |
| 图标与文字 | `8` |

> **头部横向内边距实测修正。** 本表原写「面板内边距 `20`，头部 `20 24`」，两个数都不对。
> 实测直接位于 `.panel` 内并自设横向内边距的区块 —— `.task-list` `.record-form`
> `.timeline` `.inline-add` `.step-add-form` `.template-row` `.revision-list` ——
> **主流值是 22px**（`.trace-add-form` 为 20px，是既有的孤例）。头部同为 22px，与内容对齐。
>
> 规范里的 `20 / 20 24` 两个值会分别让标题左移 2px、右移 2px。
> 校验见 `tests/test_design_tokens.py::test_panel_head_aligns_with_the_panel_body_family`，
> 它断言头部等于内容区的主流值，而不是等于某个写死的数字。
>
> **部分归档（UI-3）。** 实测原有 1236 个间距值，其中 ≥8px 且不在栅格上的有 530 处。
> 与 HEAD 逐条比对（按选择器+属性+出现序号配对，非按文档位置）：
> **150 处已改**，这些值到最近档位的距离唯一，方向没有歧义（如 `9→8` `13→12` `15→16` `11→12`）。
>
> 当前仍在栅格外的 ≥8px 值共 **250 处**，全部是 4pt 中点：
> `10px`×71 · `14px`×49 · `18px`×84 · `22px`×46。这是刻意保留，理由见下。
>
> **只处理 ≥8px**；1–3px 是描边与光学微偏移，4–7px 是紧凑控件内部间距，
> 强行取整会挤坏本设计赖以生存的密集行。8px 以下的 287 处保持原值。
>
> **中点为什么不动。** 中点到两侧档位距离相等，「就近取整」给不出答案。
> 曾试图用「一律向下」反推，实测不成立 —— 拿上表逐条校验：
>
> | 角色 | 代码原值 | 上表规定 | 「向下」会给出 | |
> |---|---|---|---|---|
> | 面板之间 | 18 | 16 | 16 | ✅ |
> | 表格单元格 | 13 | 12 | 12 | ✅ |
> | 表单字段之间 | 12 | 12 | 12 | ✅ |
> | 面板头部 | 22 | 24 | 20 | ❌ |
> | 表单组之间 | 15 | 20 | 16 | ❌ |
>
> 最后一行是决定性的：**15 根本不是中点**，任何最近邻规则都给 16，而上表要 20。
> 说明上表不是某个取整函数的采样，而是**8 条各自独立的设计决定**，
> 从中反推通用规则这个做法本身是错的。因此中点方向无据可依，不动。
>
> **正确做法是按角色定值，不是按数值取整。** 上表 8 行就是 8 个答案；
> 未列入的值先判断它属于哪个角色，再继承该角色的值 —— 这是位置问题，不是算术问题。
> 归不进任何角色的散值保持原样。代价是 4/8/10/12/14/16/18/20/22/24 共存，这是已知债。
>
> 校验见 `tests/test_design_tokens.py::test_spacing_roles_match_the_spec_table`，
> 它断言上表的角色值，不再断言栅格本身 —— 原来那条「≥8px 必须在栅格上」的测试是**通过的**，
> 但它守的是被上表证伪的规则，让一次无据的批量改动看起来像已被验证。已删除。

---

## 05 · RADIUS

```css
--radius-sm:    6px;   /* input · button · icon-btn · chip 内部 */
--radius-md:    8px;   /* panel · card · metric */
--radius-lg:   12px;   /* dialog · popover · AI dock */
--radius-full: 999px;  /* badge · chip · pill */

/* 主题面向的两个别名 —— 主题只覆盖这两个，不逐组件重写 border-radius */
--radius-panel:   var(--radius-md);   /* panel · metric · experiment-card */
--radius-control: var(--radius-sm);   /* btn · input · textarea · select */
```

圆形元素（avatar · status-dot · step-marker）继续用 `50%`，不占档位。

> **已归档（UI-3）。** 原稿写「5/6/7/8 四种混用」，实测是 **11 种**：
> `2 · 3 · 4 · 5 · 6 · 7 · 8 · 10 · 12 · 16 · 999`（另有 `50%` 与 `0`）。
> 现已全部归入上面三档 + `999px`，主文件里 **0 处硬编码圆角**。
>
> 其中两处位移最大：`5→6`（22 处，输入框与小磁贴）、`7→8`（17 处，弹层与卡片）。
> AI dock 的 `10→12` 有 1 处；旧响应布局中的另一处声明已随该布局删除。
>
> 固定界面使用 `--radius-panel: 2px` 与 `--radius-control: 2px`；不设置主题例外，
> 组件也不允许单独写像素圆角。
>
> 静态校验见 `tests/test_design_tokens.py`：`test_no_literal_pixel_radius_outside_the_token_layer`
> 守住 0 硬编码，`test_retired_theme_stylesheet_is_not_restored` 防止旧皮肤层回流。

---

## 06 · BORDER & SHADOW

```css
--border:   1px solid var(--line);
--shadow-1: 0 1px  2px rgba(20, 30, 36, .06);   /* 小型浮层 */
--shadow-2: 0 8px 24px rgba( 9, 18, 24, .10);   /* popover · dropdown */
--shadow-3: 0 14px 36px rgba( 9, 18, 24, .24);  /* dialog · AI dock */
```

只允许这三档，**禁止多层叠加阴影**。

---

## 07 · UI COMPONENTS

### BUTTONS

高 `40` · 内边距 `8 15` · 圆角 `6` · 字重 `700` · 图标 `18px` · 图标与文字间距 `8`

| 级别 | 规格 |
|---|---|
| `primary` | `--blue` 底 / 当前主题高对比前景色 · hover `--blue-hover` |
| `secondary` | `--surface` 底 / `--line` 边 · hover 边框加深 |
| `ghost` | 透明 · hover `--surface-soft` |
| `danger` | `--red-soft` 底 / `--red-ink` 字 / `--red` 边 |

**图标按钮**：视觉 `36×36`，**命中区 `44×44`** —— 用 `::after` 扩展，不影响布局：

```css
.icon-btn { position: relative; width: 36px; height: 36px; }
.icon-btn::after { content: ""; position: absolute; inset: -4px; }
```

> `.icon-btn` 通过视觉尺寸与伪元素扩展共同保证 44×44 命中区。

### INPUT FIELD · SELECT

高 `40` · 内边距 `9 11` · 圆角取 `--radius-control` · 边框 `1px --line-strong`
聚焦：`border-color: var(--blue); box-shadow: var(--focus-ring)`

### PANEL

`--surface` + `1px --line` + 圆角取 `--radius-panel`。默认 `research` 主题使用 `2px` 且无常驻阴影；其他主题可通过令牌调整圆角与层级。
面板头 `20 24`，底部 `1px --line` 分隔。

### METRIC 指标卡

总览使用连续四列栅格、`112px` 最小高、细分隔线与 `3px` 信号红强调；数字使用 `tabular-nums`。
**每项必须可点击下钻**到对应筛选列表。

### BADGE

圆角 `full` · `11px / 800` · 内边距 `3 8`
**必须带文字**，不可仅靠颜色传达状态。

### TABLE

行高 `48` · 单元格 `12 16` · 表头 `--surface-soft` + `11px / 800` 大写 · hover `--surface-hover`
数字列右对齐 + `tabular-nums`。

### EMPTY STATE

图标 `32px` + 一句说明 + 一个主操作 · **高度 ≤ 140px**（现状 220px）。

### DIALOG

圆角 `12` · `--shadow-3` · 遮罩 `rgba(9,18,24,.45)`。

---

## 08 · ICONOGRAPHY

**Lucide 0.468** · `stroke-width: 1.8` · 尺寸四档 `14` / `18` / `22` / `32`

- **禁止 emoji 作 UI 图标**
- 纯图标控件必须同时有 `title` 与 `aria-label`
- 优先补可见文字标签 —— 图标 + 文字 > 纯图标 + tooltip

---

## 09 · MOTION

- 时长：`120ms`（微交互）/ `180ms`（浮层）
- 缓动：`cubic-bezier(.2, 0, 0, 1)`
- **只允许 `opacity` 与 `transform`**
- `@media (prefers-reduced-motion: reduce)` 下全部降至 `0.01ms`
- **卡片 hover 不做 `scale`** —— 会挤动相邻布局。只改边框色与阴影

---

## 10 · ACCESSIBILITY 底线

| 项 | 要求 |
|---|---|
| 正文对比度 | ≥ 4.5:1（大字 ≥18px/700 时 ≥ 3:1） |
| 焦点环 | 全局可见 `var(--focus-ring)`，随主题主色变化；禁止 `outline: none` 无替代 |
| 触控目标 | ≥ 44×44 |
| 状态传达 | 不可仅靠颜色 —— 徽章带文字，状态点旁必须有文本 |
| 表单错误 | 紧邻出错字段，不只在顶部 flash |
| 危险操作 | 与常规操作不同权重；永久删除保持二次输入确认 |

---

## 11 · LAYOUT PROPORTION 布局比例规则

> 对应「不要有些部分占比过大」，写成可逐条检查的条款。

1. **内容区 : 辅助区 ≥ 2:1** —— 侧边辅助栏不得超过内容区宽度的 1/3
2. **低频创建不占版面** —— 创建 / 导入表单一律走抽屉或对话框。只有单行、高频的快速添加（如加任务）可常驻页顶
3. **首屏必须出现真正的内容** —— 不能是「页头 + 创建表单 + 指标卡」三件套占满第一屏
4. **单一区块高度 ≤ 视口的 40%**
5. **空状态高度 ≤ 140px** —— 空状态不该比有内容时更抢眼
6. **文字截断用 `line-clamp`，禁止固定 `height` + `overflow: hidden`** —— 后者短文本留白、长文本硬切
7. **条件区域不留空位** —— 图片区、附件区在无内容时应折叠，由文字区占满宽度，而非显示占位框
8. **数字即入口** —— 指标卡、计数标签应可点击下钻，否则降低其视觉权重

**现状违规实例**（详见 `docs/OPTIMIZATION-PLAN.md` §E）：

| 页面 | 违规 | 条款 |
|---|---|---|
| `projects.html` | 「新建项目」表单 sticky 常驻，吃掉内容区 31% | 2 |
| `experiments.html` | 创建区在页顶且默认展开六字段，列表被挤出首屏 | 2 · 3 |
| `template_center.html` | 两个创建表单排在模板库之前 | 2 · 3 |
| `experiment_report_index.html` | 图片区固定占 42%，无图时全是空白占位框 | 7 |
| `.experiment-card > p` | `height: 44px; overflow: hidden` 硬裁剪 | 6 |
| `.empty` | `min-height: 220px` | 5 |
| `.metric` | 已改为连续栅格并全部可点击下钻 | 8 · 已修复 |

---

## 12 · 禁止清单 NEVER

1. **禁止中文业务值作 CSS 类名** —— `.priority-高` `.status-进行中` `.result-成功` `.state-暂停` `.sample-可用` 改为 `data-state="high|in-progress|success"` + 属性选择器。改文案会静默破坏样式，不报错
2. **禁止 < 11px 字号**
3. **禁止把 `--brand-accent` 用作大面积页面底色或无文字的状态表达**
4. **禁止硬编码 hex** —— 组件样式统一使用 token；仅主题预览色块豁免
5. **禁止 emoji 作 UI 图标**
6. **禁止非交互元素伪装成输入框** —— 顶栏 `.topbar-search` 现为 `<a>` 却长得像搜索框且带 `⌘K` 角标
7. **禁止单页堆叠 4 个以上区块** —— 超过必须分标签页，参照 `record_detail.html` 的四标签页做法
8. **禁止在浏览页常驻低频创建表单**

---

## 13 · WHEN TO USE

**适用** 企业级科研工具 · 数据密集看板 · 专业记录系统 · 需长期一致性的多页面应用
**不适用** 营销落地页 · 消费级 App · 需要情绪化视觉的场景

---

## 14 · NOTES

瑞士风格强调信息传达的清晰与视觉的客观性，适用于需要建立信任、传达严谨、强调效率与专业性的产品与工具。**减少装饰，尊重内容本身。**

对本产品而言这尤其重要：科研记录的价值在于**可追溯与可复现**，任何为视觉效果牺牲可读性、可扫描性的决定，都是在损害产品的核心价值。
