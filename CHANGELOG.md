---
schema_version: 1
document_status: approved
owner: release-owner
last_verified_commit: null
---

# Change Log

## Unreleased

No user-visible release is declared by REV-001. Bridge v1 and architecture governance are internal compatibility work pending independent and Windows release validation.

### Added (TASK-002)

- Integrate approved research workspace UI into desktop app (TASK-002): rebuilt sidebar per approved preview (brand + workspace-switcher \LOCAL WORKSPACE\ + WORKSPACE/RESOURCES/SYSTEM grouping + sidebar-footer) and added dashboard-metrics 4-card overview bound to \dashboard.get\ counts \{projects, records, open_tasks, files}\.
- Fix \pp/services/desktop_workspace.py:dashboard()\ to use bounded COUNT queries (\ResearchProject/Task status!=done/LibraryItem\) instead of truncating via recent-project limit; return stable \counts\ alongside \workspace/projects/recent_records\.
- Update \	ests/test_desktop_service.py\ contract coverage: add \	est_dashboard_returns_complete_workspace_counts\ (7 projects / 1 open task / 1 file) and align \LibraryItem\ fixture to \workspace_id\ schema.

