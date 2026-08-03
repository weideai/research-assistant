"""Keep the primary navigation compact without making retained routes unreachable."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
STATIC = ROOT / "app" / "static"


def _template(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _primary_nav():
    html = _template("base.html")
    return html.split('<nav class="nav-list"', 1)[1].split("</nav>", 1)[0]


def test_primary_navigation_has_exactly_eight_destinations():
    nav = _primary_nav()
    assert len(re.findall(r"<a\s", nav)) == 8
    for label in ("总览", "实验计划", "任务", "报告与文件", "周报", "模板中心", "物品管理", "回收站"):
        assert f"<span>{label}</span>" in nav


def test_absorbed_routes_are_not_duplicated_in_primary_navigation():
    nav = _primary_nav()
    assert "<span>实验台</span>" not in nav
    assert "<span>实验报告</span>" not in nav
    assert "<span>文件中心</span>" not in nav
    assert "<span>API 设置</span>" not in nav


def test_project_switcher_is_not_duplicated_on_the_experiment_list():
    projects = _template("projects.html")
    experiments = _template("experiments.html")
    assert 'class="section-tabs"' in projects
    assert "workspace.projects" in projects and "main.experiments" in projects
    assert 'aria-label="实验台视图"' not in experiments
    assert "按课题组织" not in experiments


def test_evidence_views_have_two_way_tabs():
    reports = _template("experiment_report_index.html")
    files = _template("file_center.html")
    for html in (reports, files):
        assert 'class="section-tabs"' in html
        assert "main.experiment_report_index" in html and "main.file_center" in html


def test_local_workspace_keeps_system_routes_reachable_without_account_menu():
    html = _template("base.html")
    local_state = html.split('<div class="local-workspace-state">', 1)[1].split("</div>", 1)[0]

    assert '<nav aria-label="账号与系统设置">' not in html
    assert "main.api_settings" in local_state
    assert "workspace.recycle_bin" in _primary_nav()
    for removed_route in ("auth.change_password", "auth.logout", "admin.dashboard"):
        assert removed_route not in html


def test_desktop_shell_has_no_mobile_navigation_or_floating_ai_entry():
    html = _template("base.html")
    javascript = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
    styles = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (STATIC / "css").glob("*.css")
    )

    assert 'content="width=1180"' in html
    for retired_hook in ('class="mobile-bar"', 'id="menu-toggle"', 'id="ai-fab"'):
        assert retired_hook not in html
    for retired_hook in ("menu-toggle", "ai-fab", ".mobile-bar"):
        assert retired_hook not in javascript
        assert retired_hook not in styles


def test_activity_rail_is_removed_and_resource_explorer_is_collapsible():
    html = _template("base.html")
    javascript = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
    styles = (STATIC / "css" / "ide.css").read_text(encoding="utf-8")

    assert "activity-rail" not in html
    assert "activity-rail" not in styles
    assert 'id="workspace-sidebar"' in html
    assert html.count("data-sidebar-toggle") == 2
    assert 'aria-controls="workspace-sidebar"' in html
    assert "rlab-workspace-sidebar-collapsed" in javascript
    assert "sidebar-collapsed" in javascript and "sidebar-collapsed" in styles
