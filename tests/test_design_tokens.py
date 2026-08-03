"""Guard the design tokens that `design.md` pins down.

These are cheap static checks on the stylesheets. They exist because the failures
they catch are invisible in review: a muted colour that misses AA by 0.2, or a 9px
label that nobody can read, both look perfectly fine in a diff.
"""

import collections
import re
from pathlib import Path

import pytest


CSS_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "css"
TOKENS_CSS = CSS_DIR / "tokens.css"
SKINS_CSS = CSS_DIR / "skins.css"
APP_CSS = CSS_DIR / "app.css"
IDE_CSS = CSS_DIR / "ide.css"
THEMES_CSS = CSS_DIR / "themes.css"

MIN_CONTRAST = 4.5
MIN_FONT_SIZE_PX = 11
SEMANTICS = ("blue", "red", "green", "yellow", "info")


def _relative_luminance(value):
    digits = value.lstrip("#")
    if len(digits) == 3:
        digits = "".join(char * 2 for char in digits)
    channels = (int(digits[index:index + 2], 16) / 255 for index in (0, 2, 4))
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground, background):
    first, second = _relative_luminance(foreground), _relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def _strip_comments(text):
    """Comments between rules otherwise get captured as part of the next selector."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _iter_rule_blocks(text):
    """Yield (selector, body) for each brace block, tolerating nested at-rules."""
    text = _strip_comments(text)
    index = 0
    while True:
        opening = text.find("{", index)
        if opening == -1:
            return
        boundary = max(text.rfind("}", 0, opening), text.rfind("{", 0, opening)) + 1
        depth, cursor = 1, opening + 1
        while cursor < len(text) and depth:
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
            cursor += 1
        yield " ".join(text[boundary:opening].split()), text[opening + 1:cursor - 1]
        index = cursor


def _resolved_theme_palettes():
    """Return the default palette and every supported skin resolved over it."""
    blocks = list(_iter_rule_blocks(TOKENS_CSS.read_text(encoding="utf-8")))
    blocks += list(_iter_rule_blocks(SKINS_CSS.read_text(encoding="utf-8")))

    def declarations(body):
        return dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})", body))

    base = {}
    for selector, body in blocks:
        if selector == ":root":
            base.update(declarations(body))

    palettes = [(":root", dict(base))]
    for selector, body in blocks:
        overrides = declarations(body)
        if selector.startswith("html[") and overrides:
            resolved = dict(base)
            resolved.update(overrides)
            palettes.append((selector, resolved))
    return palettes


def _theme_palettes():
    """(selector, muted, bg, surface) for every supported palette."""
    out = []
    for selector, tokens in _resolved_theme_palettes():
        if all(key in tokens for key in ("--muted", "--bg", "--surface")):
            out.append((selector, tokens["--muted"], tokens["--bg"], tokens["--surface"]))
    return out


def _sidebar_palettes():
    """(selector, sidebar ink, sidebar muted, sidebar background)."""
    out = []
    for selector, tokens in _resolved_theme_palettes():
        keys = ("--sidebar-ink", "--sidebar-muted", "--sidebar")
        if all(key in tokens for key in keys):
            out.append((selector, *(tokens[key] for key in keys)))
    return out


def _ink_pairs():
    """(selector, semantic, ink, soft) for every semantic colour."""
    pairs = []
    for selector, tokens in _resolved_theme_palettes():
        for name in SEMANTICS:
            ink, soft = tokens.get(f"--{name}-ink"), tokens.get(f"--{name}-soft")
            if ink and soft:
                pairs.append((selector, name, ink, soft))
    return pairs


def test_supported_palettes_are_declared():
    palettes = _theme_palettes()
    assert [palette[0] for palette in palettes] == [
        ":root",
        'html[data-skin="ide-light"]',
        'html[data-skin="ide-dark"]',
        'html[data-skin="swiss"]',
    ]


@pytest.mark.parametrize("selector,ink,muted,background", _sidebar_palettes())
def test_sidebar_text_meets_wcag_aa(selector, ink, muted, background):
    """A light sidebar must not inherit white text from the former dark shell."""
    for role, foreground in (("--sidebar-ink", ink), ("--sidebar-muted", muted)):
        achieved = contrast_ratio(foreground, background)
        assert achieved >= MIN_CONTRAST, (
            f"{selector}: {role} {foreground} 在 --sidebar {background} 上只有 "
            f"{achieved:.2f}:1，未达 {MIN_CONTRAST}:1"
        )


@pytest.mark.parametrize("selector,name,ink,soft", _ink_pairs())
def test_semantic_ink_grade_is_readable_on_its_own_soft_background(selector, name, ink, soft):
    """The -ink grade exists precisely so text never uses the fill grade."""
    achieved = contrast_ratio(ink, soft)
    assert achieved >= MIN_CONTRAST, (
        f"{selector}: --{name}-ink {ink} 在 --{name}-soft {soft} 上只有 {achieved:.2f}:1，"
        f"未达 {MIN_CONTRAST}:1"
    )


def test_supported_palettes_define_both_grades_for_every_semantic_colour():
    """A missing -ink token silently falls back to the unreadable fill grade."""
    gaps = []
    for selector, tokens in _resolved_theme_palettes():
        for name in SEMANTICS:
            for suffix in ("", "-ink", "-soft"):
                key = f"--{name}{suffix}"
                if key not in tokens:
                    gaps.append(f"{selector} 缺 {key}")
    assert not gaps, "语义色档位不完整：" + "; ".join(gaps)


LITERAL_HEX_ALLOWED_MARKERS = ('.skin-dot[data-dot=',)


def test_no_literal_hex_outside_the_token_layer():
    """Component colours must stay sourced from the shared token layer."""
    offenders = []
    for path in (APP_CSS, IDE_CSS, THEMES_CSS, CSS_DIR / "assistant.css"):
        if not path.exists():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("/*", "*")):
                continue
            if any(marker in line for marker in LITERAL_HEX_ALLOWED_MARKERS):
                continue
            for match in re.finditer(r"#[0-9a-fA-F]{3,8}\b", line):
                offenders.append(f"{path.name}:{line_number} {match.group(0)}")
    assert not offenders, (
        f"发现 {len(offenders)} 处硬编码颜色，应改为 var(--token)："
        + ", ".join(offenders[:15]) + (" ..." if len(offenders) > 15 else "")
    )


def test_token_layer_defines_no_malformed_colour():
    """A stray character in a hex value fails silently — the theme just looks wrong."""
    malformed = []
    for path in (TOKENS_CSS, SKINS_CSS):
        for match in re.finditer(r"(--[a-z0-9-]+):\s*(#[^;\s]*)", path.read_text(encoding="utf-8")):
            digits = match.group(2)[1:]
            if len(digits) not in (3, 6, 8) or not re.fullmatch(r"[0-9a-fA-F]+", digits):
                malformed.append(f"{path.name} {match.group(1)}: {match.group(2)}")
    assert not malformed, "主题令牌存在非法颜色值：" + ", ".join(malformed)


LITERAL_RADIUS_ALLOWED_MARKERS = ()
RADIUS_MIN_STEP_PX = 2
# design.md 05 pins exactly these three steps plus the pill.
RADIUS_SCALE_STEPS = ("--radius-sm", "--radius-md", "--radius-lg")
RADIUS_ALIASES = ("--radius-panel", "--radius-control")


def _resolved_radius_scales():
    """(selector, {token: px}), with var() aliases followed to a number."""
    blocks = list(_iter_rule_blocks(TOKENS_CSS.read_text(encoding="utf-8")))
    blocks += list(_iter_rule_blocks(SKINS_CSS.read_text(encoding="utf-8")))

    def declarations(body):
        return dict(re.findall(r"(--radius-[a-z0-9-]+):\s*([^;]+?)\s*(?:;|$)", body))

    base = {}
    for selector, body in blocks:
        if selector == ":root":
            base.update(declarations(body))

    def resolve(tokens, raw, hops=4):
        """Follow a radius alias to its pixel value."""
        for _ in range(hops):
            reference = re.fullmatch(r"var\((--radius-[a-z0-9-]+)\)", raw.strip())
            if not reference:
                break
            raw = tokens.get(reference.group(1), base.get(reference.group(1), ""))
        pixels = re.fullmatch(r"(\d+)px", raw.strip())
        return int(pixels.group(1)) if pixels else None

    scales = []
    themed_blocks = [b for b in blocks if b[0].startswith("html[") and declarations(b[1])]
    for selector, body in [(":root", "")] + themed_blocks:
        tokens = dict(base)
        tokens.update(declarations(body))
        scales.append((selector, {name: resolve(tokens, raw) for name, raw in tokens.items()}))
    return scales


def test_radius_scale_steps_stay_visually_distinguishable():
    """The 11-value sprawl this replaced had 1px gaps — invisible, so not a decision."""
    scale = dict(_resolved_radius_scales()[0][1])
    steps = [(name, scale.get(name)) for name in RADIUS_SCALE_STEPS]
    missing = [name for name, px in steps if px is None]
    assert not missing, "tokens.css 缺少圆角档位：" + ", ".join(missing)
    tight = [
        f"{steps[i][0]}({steps[i][1]}px) 与 {steps[i + 1][0]}({steps[i + 1][1]}px)"
        for i in range(len(steps) - 1)
        if steps[i + 1][1] - steps[i][1] < RADIUS_MIN_STEP_PX
    ]
    assert not tight, (
        f"以下相邻圆角档位相差不足 {RADIUS_MIN_STEP_PX}px，肉眼无法分辨：" + "; ".join(tight)
    )


def test_supported_palettes_define_both_radius_aliases():
    gaps = []
    for selector, scale in _resolved_radius_scales():
        for alias in RADIUS_ALIASES:
            if scale.get(alias) is None:
                gaps.append(f"{selector} 缺 {alias}")
    assert not gaps, "圆角别名不完整：" + "; ".join(gaps)


def test_no_literal_pixel_radius_outside_the_token_layer():
    """A literal radius ignores the theme, so minimal/tech stop looking square."""
    offenders = []
    for path in (APP_CSS, IDE_CSS, THEMES_CSS, CSS_DIR / "assistant.css"):
        if not path.exists():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("/*", "*")):
                continue
            if any(marker in line for marker in LITERAL_RADIUS_ALLOWED_MARKERS):
                continue
            for match in re.finditer(r"border-radius:[^;}]*?(\d+px)", line):
                offenders.append(f"{path.name}:{line_number} {match.group(1)}")
    assert not offenders, (
        f"发现 {len(offenders)} 处硬编码圆角，应改为 var(--radius-*)："
        + ", ".join(offenders[:15]) + (" ..." if len(offenders) > 15 else "")
    )


# design.md 04's role table, transcribed. These are eight independent decisions,
# not samples of a rounding function — a previous version of this file asserted a
# derived "midpoints round down" rule instead, which passed while enforcing
# something the table disproves: 表单组之间 is 15px in code and 20 in the spec,
# and 15 is not a midpoint, so no nearest-neighbour rule produces 20.
SPACING_ROLES = (
    ("面板之间", ".dashboard-grid", "gap", 16),
    ("表格单元格", "th, td", "padding", 12),
    ("表单字段之间", ".form-grid", "gap", 12),
    ("表单组之间", ".stack-form", "gap", 20),
    ("页面顶部", ".main-shell", "padding", 32),
    ("图标与文字", ".btn", "gap", 8),
)


def _declared_length(selector, prop, css):
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    if not match:
        return None
    value = re.search(prop + r":\s*(\d+)px", match.group(1))
    return int(value.group(1)) if value else None


@pytest.mark.parametrize("role,selector,prop,expected", SPACING_ROLES)
def test_spacing_roles_match_the_spec_table(role, selector, prop, expected):
    """Assert the spec's own values, not a rule inferred from them."""
    actual = _declared_length(selector, prop, APP_CSS.read_text(encoding="utf-8"))
    assert actual is not None, f"未解析到 {selector} 的 {prop}"
    assert actual == expected, (
        f"design.md 04 规定「{role}」为 {expected}px，{selector} 实际 {actual}px"
    )


def test_page_shell_uses_the_pinned_inline_and_bottom_spacing():
    css = APP_CSS.read_text(encoding="utf-8")
    # Only top-level rules participate at desktop width. Requiring every one is
    # intentional: app.css has a later visual-refresh layer, and checking only
    # the first declaration previously let that layer silently override the spec.
    desktop_rules = re.findall(r"(?m)^\.main-shell\s*\{([^}]*)\}", css)
    assert desktop_rules, "未解析到桌面端 .main-shell"
    incorrect = [
        body for body in desktop_rules
        if not re.search(r"padding:\s*32px\s+var\(--page-inline\)\s+64px", body)
    ]
    assert not incorrect, "页面应使用 32px 顶部、--page-inline 左右、64px 底部间距"


def test_focus_styles_follow_the_active_theme_colour():
    """A hard-coded blue focus halo survives a palette switch and looks broken."""
    css = APP_CSS.read_text(encoding="utf-8")
    assert "rgba(33, 102, 243" not in css
    assert re.search(
        r":where\(a, button, input, textarea, select, summary\):focus-visible\s*"
        r"\{[^}]*box-shadow:\s*var\(--focus-ring\)",
        css,
    ), "可聚焦控件应统一使用主题感知的 --focus-ring"


def test_experiment_snapshot_keeps_a_spacious_desktop_hierarchy():
    css = APP_CSS.read_text(encoding="utf-8")
    expected = (
        r"\.experiment-snapshot-content\s*\{[^}]*padding:\s*28px",
        r"\.experiment-snapshot-metrics\s*>\s*div\s*\{[^}]*min-height:\s*96px",
        r"\.experiment-plan-strip\s*\{[^}]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)",
        r"\.experiment-plan-strip\s*>\s*li\s*\{[^}]*min-height:\s*116px",
        r"\.snapshot-record-row,\s*\.snapshot-file-row\s*\{[^}]*padding:\s*14px\s+0",
    )
    missing = [pattern for pattern in expected if not re.search(pattern, css)]
    assert not missing, "实验工作台重新变得拥挤，缺少宽松布局约束：" + "; ".join(missing)


# Blocks that sit directly inside a .panel and set their own inline padding.
#
# This list is hand-curated and that is a known limitation: which blocks are
# direct children of a .panel is a fact about the markup, and scanning the
# templates for it only reaches each panel's *first* child, so it cannot produce
# the full set. Add to this list when a new panel-level block appears.
#
# They are not unanimous — .trace-add-form is 20px where the rest are 22px, and
# that predates this file. So the head is checked against the family's dominant
# value rather than against every member, and the outlier is recorded here rather
# than silently tolerated.
PANEL_BODY_SELECTORS = (
    ".task-list", ".record-form", ".timeline", ".inline-add",
    ".step-add-form", ".trace-add-form", ".template-row", ".revision-list",
)


def _inline_padding(selector, css):
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    if not match:
        return None
    shorthand = re.search(r"padding:\s*(\d+)px\s+(\d+)px", match.group(1))
    return int(shorthand.group(2)) if shorthand else None


def test_panel_head_aligns_with_the_panel_body_family():
    """An offset between head and rows is visible but trivial to introduce.

    design.md 04 specified `20 24` for the head against `20` for the body, which
    would misalign every panel title. Both numbers were wrong: the family is 22px.
    """
    css = APP_CSS.read_text(encoding="utf-8")
    head = _inline_padding(".panel-head", css)
    assert head is not None, "未解析到 .panel-head 的横向内边距"

    measured = {sel: _inline_padding(sel, css) for sel in PANEL_BODY_SELECTORS}
    present = [px for px in measured.values() if px is not None]
    assert present, "未解析到任何面板内容区的横向内边距，选择器可能已改名"

    dominant = collections.Counter(present).most_common(1)[0][0]
    assert head == dominant, (
        f".panel-head 横向内边距为 {head}px，但面板内容区主流值是 {dominant}px，"
        f"标题会与它标注的每一行错位。实测：{measured}"
    )


def test_retired_theme_stylesheet_is_not_restored():
    assert not THEMES_CSS.exists()


@pytest.mark.parametrize("selector,muted,bg,surface", _theme_palettes())
def test_muted_text_meets_wcag_aa(selector, muted, bg, surface):
    """--muted carries nearly all secondary copy, so it must clear AA everywhere."""
    on_bg = contrast_ratio(muted, bg)
    on_surface = contrast_ratio(muted, surface)
    assert on_bg >= MIN_CONTRAST, (
        f"{selector}: --muted {muted} 在 --bg {bg} 上只有 {on_bg:.2f}:1，未达 {MIN_CONTRAST}:1"
    )
    assert on_surface >= MIN_CONTRAST, (
        f"{selector}: --muted {muted} 在 --surface {surface} 上只有 {on_surface:.2f}:1，"
        f"未达 {MIN_CONTRAST}:1"
    )


def _declared_font_sizes():
    hits = []
    for path in (APP_CSS, IDE_CSS, THEMES_CSS, CSS_DIR / "assistant.css"):
        if not path.exists():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in re.finditer(r"font-size:\s*(\d+(?:\.\d+)?)px", line):
                hits.append((path.name, line_number, float(match.group(1))))
    return hits


def test_no_font_size_below_the_readable_minimum():
    """Chinese glyphs are unreadable below 11px; design.md deletes the 9px/10px steps."""
    too_small = [hit for hit in _declared_font_sizes() if hit[2] < MIN_FONT_SIZE_PX]
    assert not too_small, (
        f"发现 {len(too_small)} 处小于 {MIN_FONT_SIZE_PX}px 的字号："
        + ", ".join(f"{name}:{line} ({size:g}px)" for name, line, size in too_small[:12])
        + (" ..." if len(too_small) > 12 else "")
    )


MIN_ICON_BUTTON_PX = 36
HIT_AREA_INSET_PX = 2


def _icon_button_sizes():
    """Every rule that sets an explicit .icon-btn width."""
    pattern = re.compile(r"([^{};]*\.icon-btn(?:[^{};]*)?)\{([^}]*)\}")
    sizes = []
    for path in (APP_CSS, CSS_DIR / "assistant.css"):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            width = re.search(r"\bwidth:\s*(\d+)px", match.group(2))
            if width:
                selector = " ".join(match.group(1).split())[-52:]
                sizes.append((path.name, selector, int(width.group(1))))
    return sizes


def test_icon_buttons_are_large_enough_to_reach_a_44px_hit_area():
    """34x34 plus a 2px inset still misses 44x44; the visual box must be >= 36px."""
    sizes = _icon_button_sizes()
    assert sizes, "未找到任何 .icon-btn 尺寸声明，选择器可能已改名"
    undersized = [entry for entry in sizes if entry[2] < MIN_ICON_BUTTON_PX]
    assert not undersized, (
        f"以下 .icon-btn 视觉尺寸小于 {MIN_ICON_BUTTON_PX}px，"
        f"加上 {HIT_AREA_INSET_PX}px 扩展也达不到 44x44："
        + ", ".join(f"{name} [{sel}] {px}px" for name, sel, px in undersized)
    )


def test_icon_button_hit_area_is_extended_without_affecting_layout():
    text = APP_CSS.read_text(encoding="utf-8")
    assert re.search(r"\.icon-btn\s*\{[^}]*position:\s*relative", text), (
        ".icon-btn 需要 position: relative 才能承载 ::after 命中区"
    )
    assert re.search(r"\.icon-btn::after\s*\{[^}]*inset:\s*-\d+px", text), (
        ".icon-btn 需要 ::after + 负 inset 扩展命中区"
    )


def test_icon_button_rows_do_not_overlap_their_neighbours_hit_areas():
    """A 2px inset on both sides needs a >= 4px gap, or targets steal each other's clicks."""
    minimum_gap = HIT_AREA_INSET_PX * 2
    containers = ("row-actions", "record-actions", "file-center-row-actions", "ai-dock-actions")
    offenders = []
    for path in (APP_CSS, CSS_DIR / "assistant.css"):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for container in containers:
            for match in re.finditer(rf"\.{container}\s*\{{([^}}]*)\}}", text):
                gap = re.search(r"\bgap:\s*(\d+)px", match.group(1))
                if gap and int(gap.group(1)) < minimum_gap:
                    offenders.append(f"{path.name} .{container} gap:{gap.group(1)}px")
    assert not offenders, (
        f"以下容器的 gap 小于 {minimum_gap}px，相邻按钮命中区会重叠：" + ", ".join(offenders)
    )
