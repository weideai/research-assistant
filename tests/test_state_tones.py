"""Keep stored Chinese status values out of the stylesheet.

`.state-进行中` couples CSS to business wording: rename a status and the badge
silently loses its colour, with nothing failing. The `state_tone` filter is the
only bridge between the two, so these tests guard both ends — that no selector
or template rebuilds the old coupling, and that every value the app can store
has a tone.
"""

import re
from pathlib import Path

import pytest

from app.main import DEFAULT_STATE_TONE, STATE_TONE_BY_VALUE, STATE_TONES

ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = ROOT / "app" / "static" / "css"
TEMPLATE_DIR = ROOT / "app" / "templates"
HAS_CHINESE = re.compile(r"[一-龥]")

# Values that only exist as literal <option> text, with no importable constant.
TEMPLATE_ONLY_VALUES = ("高", "中", "低", "可用", "使用中", "耗尽", "异常", "成功", "失败", "待确认")


def _importable_status_values():
    from app import main, workspace

    names = (
        "WEEKLY_REPORT_STATUSES", "WEEKLY_REPORT_UPDATE_STATUSES", "PROJECT_AI_STATUSES",
        "BATCH_AI_STATUSES", "FINALIZED_RECORD_STATUSES",
    )
    values = set()
    for module in (main, workspace):
        for name in names + ("PROJECT_STATUSES", "BATCH_STATUSES"):
            for value in getattr(module, name, ()) or ():
                if HAS_CHINESE.search(value):
                    values.add(value)
    return values


@pytest.mark.parametrize("value", sorted(_importable_status_values() | set(TEMPLATE_ONLY_VALUES)))
def test_every_storable_status_has_a_tone(value):
    """An unmapped value renders grey and only warns, so it hides in plain sight."""
    assert value in STATE_TONE_BY_VALUE, (
        f"状态值 {value!r} 没有在 STATE_TONES 里登记配色档位，会静默按 "
        f"{DEFAULT_STATE_TONE} 渲染。新增状态时必须同步这张表。"
    )


def test_no_chinese_in_css_selectors():
    """A Chinese class name means the coupling came back."""
    offenders = []
    for path in sorted(CSS_DIR.glob("*.css")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # Only the selector side matters; Chinese prose in comments is fine.
            selector = line.split("{")[0]
            if line.lstrip().startswith(("/*", "*")):
                continue
            if HAS_CHINESE.search(selector) and "." in selector:
                offenders.append(f"{path.name}:{line_number}")
    assert not offenders, (
        "以下 CSS 选择器里出现中文业务值，应改为 [data-state=...]：" + ", ".join(offenders)
    )


def test_no_template_interpolates_a_status_into_a_class_name():
    """`class="badge state-{{ x }}"` is the exact pattern this replaced."""
    pattern = re.compile(
        r'class="[^"]*(?:priority|state|result|sample|status|lifecycle)-(?:\{\{|[一-龥])'
    )
    offenders = []
    for path in sorted(TEMPLATE_DIR.rglob("*.html")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.name}:{line_number}")
    assert not offenders, (
        "以下模板仍把状态值拼进 class，应改为 data-state=\"{{ value | state_tone }}\"："
        + ", ".join(offenders)
    )


def test_tone_values_are_disjoint():
    """One value in two tones makes the rendered colour depend on dict order."""
    seen, duplicates = set(), []
    for values in STATE_TONES.values():
        for value in values:
            if value in seen:
                duplicates.append(value)
            seen.add(value)
    assert not duplicates, "以下状态值在多个档位里重复出现：" + ", ".join(duplicates)


def test_every_tone_has_a_css_rule():
    """A tone with no rule renders unstyled, which reads as 'no status'."""
    css = (CSS_DIR / "app.css").read_text(encoding="utf-8")
    missing = [tone for tone in STATE_TONES if f'[data-state="{tone}"]' not in css]
    assert not missing, "以下档位在 app.css 里没有对应规则：" + ", ".join(missing)


@pytest.mark.parametrize("value,expected", [
    ("进行中", "info"), ("失败", "danger"), ("高", "danger"), ("中", "warning"),
    ("成功", "success"), ("低", "neutral"), ("  成功  ", "success"),
    ("", DEFAULT_STATE_TONE), (None, DEFAULT_STATE_TONE), ("没有这个状态", DEFAULT_STATE_TONE),
])
def test_state_tone_filter_maps_values(app, value, expected):
    with app.app_context():
        assert app.jinja_env.filters["state_tone"](value) == expected
