"""Keep the detail-page tab systems wired end to end.

Every failure mode here is silent. A tab whose panel is missing renders an empty
pane; a panel whose tab is missing is unreachable but still in the DOM; a CSS
rule for a key that exists in neither looks like a working feature in the
stylesheet while doing nothing. None of these throw, and none are visible in a
diff — a stray `[data-active-tab="records"]` pair sat in app.css unnoticed
precisely because the stylesheet read as if the tab existed.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
APP_CSS = ROOT / "app" / "static" / "css" / "app.css"
APP_JS = ROOT / "app" / "static" / "js" / "app.js"

# (template, tab attr, panel attr, css active-state attr, js hook)
TAB_SYSTEMS = [
    ("experiment_detail.html", "data-experiment-tab", "data-experiment-panel",
     "data-active-tab", "experimentWorkspace"),
    ("batch_detail.html", "data-batch-tab", "data-batch-panel",
     "data-active-batch-tab", "batchWorkspace"),
    ("record_detail.html", "data-record-tab", "data-record-panel",
     "data-active-record-tab", "recordWorkspace"),
]


def _keys(text, attr):
    return sorted(set(re.findall(rf'{attr}="([a-z-]+)"', text)))


def _system(template):
    return (TEMPLATES / template).read_text(encoding="utf-8")


@pytest.mark.parametrize("template,tab_attr,panel_attr,_css,_js", TAB_SYSTEMS)
def test_every_tab_has_a_panel(template, tab_attr, panel_attr, _css, _js):
    html = _system(template)
    tabs, panels = _keys(html, tab_attr), _keys(html, panel_attr)
    assert tabs, f"{template} 没有解析到标签，属性名可能已改"
    orphans = [key for key in tabs if key not in panels]
    assert not orphans, f"{template} 中以下标签没有对应面板，点开是空白：{orphans}"


@pytest.mark.parametrize("template,tab_attr,panel_attr,_css,_js", TAB_SYSTEMS)
def test_every_panel_has_a_tab(template, tab_attr, panel_attr, _css, _js):
    html = _system(template)
    tabs, panels = _keys(html, tab_attr), _keys(html, panel_attr)
    unreachable = [key for key in panels if key not in tabs]
    assert not unreachable, (
        f"{template} 中以下面板没有对应标签，内容进不去：{unreachable}"
    )


@pytest.mark.parametrize("template,tab_attr,_panel,css_attr,_js", TAB_SYSTEMS)
def test_no_css_rule_targets_a_tab_that_does_not_exist(template, tab_attr, _panel, css_attr, _js):
    """Speculative CSS makes an unbuilt feature look finished."""
    html, css = _system(template), APP_CSS.read_text(encoding="utf-8")
    tabs = _keys(html, tab_attr)
    styled = sorted(set(re.findall(rf'{css_attr}="([a-z-]+)"', css)))
    orphans = [key for key in styled if key not in tabs]
    assert not orphans, (
        f"app.css 里 {css_attr} 有以下取值，但 {template} 没有对应标签："
        f"{orphans}。样式表看起来像功能已实现，实际是死规则。"
    )


@pytest.mark.parametrize("_t,_tab,_panel,_css,js_hook", TAB_SYSTEMS)
def test_the_javascript_controller_is_present(_t, _tab, _panel, _css, js_hook):
    """Without the controller no tab ever activates and every panel renders stacked."""
    js = APP_JS.read_text(encoding="utf-8")
    assert js_hook in js, (
        f"app.js 里找不到 {js_hook}，标签控制器缺失时所有面板会同时堆叠渲染，且不报错"
    )


@pytest.mark.parametrize("template,tab_attr,panel_attr,_css,_js", TAB_SYSTEMS)
def test_tabs_and_panels_expose_accessible_roles(template, tab_attr, panel_attr, _css, _js):
    html = _system(template)
    assert re.search(r'<nav\b[^>]*role="tablist"', html), (
        f"{template} 的页签导航缺少 role=tablist"
    )
    tab_tags = re.findall(rf'<a\b[^>]*{tab_attr}="[a-z-]+"[^>]*>', html)
    panel_tags = re.findall(
        rf'<(?:section|details|div)\b[^>]*{panel_attr}="[a-z-]+"[^>]*>', html
    )
    assert tab_tags and all('role="tab"' in tag for tag in tab_tags)
    assert all('aria-selected=' in tag and 'aria-controls=' in tag for tag in tab_tags)
    assert panel_tags and all('role="tabpanel"' in tag for tag in panel_tags)
    assert all('aria-labelledby=' in tag for tag in panel_tags)

    ids = set(re.findall(r'\bid="([a-z0-9-]+)"', html))
    controlled = [
        item
        for tag in tab_tags
        for item in re.search(r'aria-controls="([^"]+)"', tag).group(1).split()
    ]
    assert all(item in ids for item in controlled), (
        f"{template} 的 aria-controls 指向不存在的面板："
        f"{sorted(set(controlled) - ids)}"
    )


def test_tab_controllers_support_roving_keyboard_focus():
    js = APP_JS.read_text(encoding="utf-8")
    assert "wireTabKeyboard" in js
    for key in ("ArrowLeft", "ArrowRight", "Home", "End"):
        assert f'event.key === "{key}"' in js
    assert 'setAttribute("aria-selected"' in js


def test_tabs_ready_is_set_by_script_not_hardcoded():
    """`.tabs-ready` gates every hide rule.

    It must come from JS: hardcoding it in the template would hide panels for
    anyone whose script failed to load, with no way to reach them.
    """
    assert 'classList.add("tabs-ready")' in APP_JS.read_text(encoding="utf-8"), (
        "app.js 应当由脚本添加 .tabs-ready"
    )
    for template, *_ in TAB_SYSTEMS:
        assert "tabs-ready" not in _system(template), (
            f"{template} 不应硬编码 tabs-ready —— 脚本失败时面板会被隐藏且无法访问"
        )
