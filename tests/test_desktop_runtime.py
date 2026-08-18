from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_production_desktop_entry_has_no_http_server_or_browser_startup():
    sources = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "desktop_main.py",
            "desktop_launcher.py",
            "app/desktop/runtime.py",
            "app/desktop/bridge.py",
        )
    )

    for forbidden in ("app.run(", "make_server", "serve_forever", "webbrowser.open(", "socket.listen("):
        assert forbidden not in sources
    assert "http_server=False" in sources
    assert '#bridge=pywebview' in sources
    assert "desktop_main.py" in (ROOT / "scripts/build_windows_installer.ps1").read_text(encoding="utf-8")


def test_desktop_ui_is_local_and_has_no_remote_dependency():
    html = (ROOT / "app/desktop_ui/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/desktop_ui/desktop.js").read_text(encoding="utf-8")

    assert "https://" not in html
    assert "http://" not in html
    assert "connect-src 'none'" in html
    assert "window.pywebview.api.invoke" in script
    assert "bridgeRequired" in script
    assert 'window.location.hash === "#bridge=pywebview"' in script
    assert "if(!bridgeRequired)setTimeout(boot" in script
    assert (ROOT / "app/static/vendor/lucide.min.js").is_file()


def test_dialog_cancel_bypasses_required_field_validation():
    script = (ROOT / "app/desktop_ui/desktop.js").read_text(encoding="utf-8")

    assert 'dialog button[value="cancel"]' in script
    assert 'event.preventDefault();cancel.closest("dialog")?.close("cancel")' in script
    assert 'dialog.addEventListener("close",()=>trigger?.focus?.(),{once:true})' in script


def test_desktop_tabs_and_search_support_keyboard_navigation():
    html = (ROOT / "app/desktop_ui/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/desktop_ui/desktop.js").read_text(encoding="utf-8")
    system_script = (ROOT / "app/desktop_ui/desktop_system.js").read_text(encoding="utf-8")

    assert 'id="project-tabs" role="tablist"' in html
    assert 'class="settings-nav panel" role="tablist"' in html
    assert 'event.target.closest?.(\'[role="tab"]\')' in script
    assert 'event.key==="ArrowLeft"||event.key==="ArrowRight"' in script
    assert 'event.key==="ArrowDown"||event.key==="ArrowUp"' in system_script


def test_assistant_close_stays_hidden_in_wide_layout_and_history_has_new_chat():
    html = (ROOT / "app/desktop_ui/index.html").read_text(encoding="utf-8")
    css = (ROOT / "app/desktop_ui/desktop.css").read_text(encoding="utf-8")
    script = (ROOT / "app/desktop_ui/desktop.js").read_text(encoding="utf-8")
    system_script = (ROOT / "app/desktop_ui/desktop_system.js").read_text(encoding="utf-8")

    assert ".assistant-window[hidden] { display: none; }" in css
    assert ".assistant-window.assistant-wide:not(.minimized):not([hidden]) { display: grid;" in css
    assert ".assistant-window:not(.minimized) { display: grid;" not in css
    assert 'id="assistant-close"' in html
    assert '$("#assistant-close").addEventListener("click",closeAssistant)' in script
    assert "width: 390px" in css
    assert "min-width: 320px" in css
    assert "min-width: 600px" not in css
    assert "minWidth=320" in script
    assert 'classList.toggle("assistant-wide",assistantWindow.offsetWidth>=720)' in script
    assert 'id="assistant-new-chat-side"' in html
    assert 'id="ai-history-manage"' in html
    assert 'class="assistant-window history-collapsed"' in html
    assert 'class="assistant-prompt-history collapsed"' in html
    assert 'id="ai-history-toggle"' in html
    assert 'setAiHistoryCollapsed(true)' in system_script
    assert 'history-collapsed' in css
    assert 'for(const button of [$("#assistant-new-chat"),$("#assistant-new-chat-side")])' in system_script
    assert 'Number(item.id)===Number(currentConversationId)?"active":""' in system_script


def test_desktop_resource_workspaces_and_project_ai_controls_are_complete():
    html = (ROOT / "app/desktop_ui/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/desktop_ui/desktop.js").read_text(encoding="utf-8")
    system_script = (ROOT / "app/desktop_ui/desktop_system.js").read_text(encoding="utf-8")
    resource_script = (ROOT / "app/desktop_ui/desktop_resources.js").read_text(encoding="utf-8")
    planning_script = (ROOT / "app/desktop_ui/desktop_planning.js").read_text(encoding="utf-8")

    assert 'class="resource-workspace literature-workspace"' in html
    assert 'class="resource-workspace weekly-library-layout"' in html
    assert 'id="ai-project"' in html
    assert 'id="ai-preview"' not in html
    assert 'id="ai-target-type"' not in html
    assert html.count("data-assistant-resize=") == 8
    assert "setPointerCapture" in script
    assert "assistantNormalRect" in script
    for control in (
        "assistant-new-chat", "ai-web-access", "ai-revert",
        "ai-history-rename", "ai-history-delete", "trash-select-page", "trash-pagination",
    ):
        assert f'id="{control}"' in html
    assert 'invoke("ai.conversations"' in system_script
    assert "data-ai-message-copy" in system_script
    assert "data-ai-message-regenerate" in system_script
    assert 'id="ai-copy"' not in html
    assert 'id="ai-regenerate"' not in html
    assert ">开始</span><input id=\"ai-history-start\"" in html
    assert ">结束</span><input id=\"ai-history-end\"" in html
    assert 'class="resource-table literature-table"' in resource_script
    assert 'data-literature-trash' in resource_script
    assert 'data-literature-bulk="trash"' in html
    assert 'data-trash-calendar-event' in planning_script
    assert 'entity_type:"calendar_event"' in planning_script
    assert 'state.currentCalendarEvent?.source_type==="event"' in planning_script
    assert "data-open-calendar-source" in planning_script
    assert "查看内容" in planning_script
    assert 'if(params.id){taskScope="all"' in planning_script
    assert 'R.register("weekly-library",{load:async params=>' in planning_script
    assert 'R.register("literature",{load:async params=>' in resource_script
    assert 'R.register("files",{load:async params=>' in resource_script
    assert 'invoke("trash.purge"' in system_script
    assert 'calendar-clear-date' in planning_script
    assert 'class="resource-table weekly-table"' in planning_script
    assert "data-picker-select-page" in (ROOT / "app/desktop_ui/desktop_research.js").read_text(encoding="utf-8")
    assert 'id="ai-select-records"' in html
    assert "data-ai-record-select-page" in system_script
    assert 'invoke("weekly.annotate"' in planning_script
    assert "literature-workspace:not(.detail-expanded)" in (ROOT / "app/desktop_ui/desktop.css").read_text(encoding="utf-8")
    desktop_css = (ROOT / "app/desktop_ui/desktop.css").read_text(encoding="utf-8")
    weekly_layout_rule = desktop_css.split(".weekly-library-layout", 1)[1].split("}", 1)[0]
    assert "grid-template-columns" not in weekly_layout_rule
    assert ".weekly-library-layout .detail-header" in desktop_css
    assert "grid-template-rows: auto auto auto minmax(220px,1fr) auto auto" in desktop_css


def test_project_directory_and_home_schedule_expose_pagination_and_actions():
    html = (ROOT / "app/desktop_ui/index.html").read_text(encoding="utf-8")
    research_script = (ROOT / "app/desktop_ui/desktop_research.js").read_text(encoding="utf-8")
    desktop_script = (ROOT / "app/desktop_ui/desktop.js").read_text(encoding="utf-8")

    for control in ("project-bulk-bar", "project-select-page", "project-pagination"):
        assert f'id="{control}"' in html
    assert 'data-project-bulk="trash"' in html
    assert 'data-project-bulk="status"' in html
    assert 'project.bulk' in desktop_script
    assert 'data-home-calendar-day' in research_script
    assert 'invoke("calendar.list"' in research_script
    assert 'navigate("calendar",{date:homeDay.dataset.homeCalendarDay})' in research_script
    assert "data-home-focus-view" in research_script
    assert "captureNavigationState" in desktop_script
    assert "restoreNavigationState" in desktop_script


def test_experiment_records_use_dedicated_editor_page():
    html = (ROOT / "app/desktop_ui/index.html").read_text(encoding="utf-8")
    research_script = (ROOT / "app/desktop_ui/desktop_research.js").read_text(encoding="utf-8")
    desktop_script = (ROOT / "app/desktop_ui/desktop.js").read_text(encoding="utf-8")
    css = (ROOT / "app/desktop_ui/desktop.css").read_text(encoding="utf-8")

    # The list stays in the records view while the existing editor surface is
    # moved into the dedicated record-edit panel at runtime.
    assert 'class="record-workspace"' in html
    assert 'id="record-inline-detail"' in html
    assert html.count('id="record-form"') == 1
    assert 'data-view-panel="records"' in html
    assert 'data-view-panel="record-edit"' in html
    assert 'id="record-edit-surface"' in html
    assert "const detail=$(\"#record-inline-detail\")" in research_script
    assert 'navigate("record-edit",{id:Number(record.dataset.openRecord)})' in research_script
    assert 'const panelView=view;' in desktop_script
    assert ".record-workspace" in css


def test_literature_relations_weekly_sources_and_zotero_jobs_are_navigable():
    resources = (ROOT / "app/desktop_ui/desktop_resources.js").read_text(encoding="utf-8")
    planning = (ROOT / "app/desktop_ui/desktop_planning.js").read_text(encoding="utf-8")
    bridge = (ROOT / "app/desktop/bridge.py").read_text(encoding="utf-8")

    for marker in (
        "data-open-related-project", "data-open-related-record", "data-open-related-note",
        "data-open-related-file", "data-unlink-literature", 'invoke("literature.bulk"',
    ):
        assert marker in resources
    assert "data-open-weekly-source" in planning
    assert 'R.go("record-edit"' in planning
    for command in ("zotero.sync.start", "zotero.sync.status", "zotero.sync.cancel"):
        assert command in bridge
        assert command in resources
    assert "zotero.collections.list" in resources
    assert "zotero.collections.map" in resources
    assert 'invoke("library.open"' in resources
    assert "本地附件无法直接打开，已转到 Zotero" in resources
    assert "data-open-weekly-history-source" in planning
    assert "currentWeeklyDetail.entries" in planning
    assert "pagination:true,page:literaturePage" in resources
    assert "pagination:true,page:notePage" in resources
    assert "pagination:true,page:filePage" in resources
    research = (ROOT / "app/desktop_ui/desktop_research.js").read_text(encoding="utf-8")
    assert "pagination:true,page:recordsPage" in research
    assert "weeklyLibraryPaged" in planning
    assert "pagination:true,page:weeklyPage" in planning
    assert 'taskMode==="list"' in planning and "pagination:true,page:taskPage" in planning
    css = (ROOT / "app/desktop_ui/desktop.css").read_text(encoding="utf-8")
    assert "body { font-size: 13px; }" in css
    assert ".calendar-date { border: 0; background: transparent" in css
    desktop = (ROOT / "app/desktop_ui/desktop.js").read_text(encoding="utf-8")
    assert 'setAttribute("aria-live","assertive")' in desktop
    assert '["zotero-state","note-save-state","save-state"]' in desktop
    assert "restoreNavigationControls" in desktop
