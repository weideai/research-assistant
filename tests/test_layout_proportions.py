"""Guard the list-page proportions called out in design.md section 11."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
APP_CSS = ROOT / "app" / "static" / "css" / "app.css"


def _template(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_project_creation_is_a_dialog_not_a_sticky_sidebar():
    html = _template("projects.html")
    assert 'id="project-create-dialog"' in html
    assert "data-workspace-dialog" in html
    assert "project-create-panel" not in html


def test_experiment_list_precedes_low_frequency_creation_ui():
    html = _template("experiments.html")
    assert 'id="create-experiment"' in html and "data-workspace-dialog" in html
    assert "workspace-intro" not in html


def test_template_creation_and_import_are_dialogs():
    html = _template("template_center.html")
    assert 'id="template-create-dialog"' in html
    assert 'id="template-import-dialog"' in html
    assert html.count("data-workspace-dialog") >= 2


def test_report_cards_leave_export_to_the_report_reader():
    html = _template("experiment_report_index.html")
    assert "record_export" not in html
    assert "report-thumb-empty" not in html
    assert "{% if images %}" in html
    assert "打开报告" in html


def test_report_toolbar_keeps_the_result_count_on_one_line():
    css = APP_CSS.read_text(encoding="utf-8")
    search_rule = re.search(r"\.report-feed-search\s*\{([^}]*)\}", css)
    count_rule = re.search(r"\.report-feed-toolbar\s*>\s*\.count-label\s*\{([^}]*)\}", css)

    assert search_rule and "min-width: 0" in search_rule.group(1)
    assert count_rule and "white-space: nowrap" in count_rule.group(1)


def test_retired_layout_rules_are_not_left_in_the_stylesheet():
    css = APP_CSS.read_text(encoding="utf-8")
    retired = (
        ".workspace-layout", ".project-create-panel", ".workspace-intro",
        ".report-feed-grid", ".report-feed-assets", ".report-feed-thumbs",
        ".report-thumb-empty", ".report-folder-link",
    )
    assert not [selector for selector in retired if selector in css]
