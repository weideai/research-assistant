from app import db
from app.models import LiteratureItem, User
from app.services.desktop_workspace import DesktopApplicationService


def _service(app):
    with app.app_context():
        user = User(
            name="Pagination test", email="pagination@example.invalid",
            password_hash="local", role="system_admin",
        )
        db.session.add(user)
        db.session.commit()
    return DesktopApplicationService(app)


def test_literature_list_supports_opt_in_server_pagination_filter_and_sort(app):
    service = _service(app)
    # Resolve/create the local workspace before inserting scoped rows.
    service.list_literature({})
    with app.app_context():
        workspace_id = LiteratureItem.query.with_entities(LiteratureItem.workspace_id).first()
        if workspace_id is None:
            from app.models import Workspace
            workspace_id = Workspace.query.one().id
        else:
            workspace_id = workspace_id[0]
        for index, (title, source) in enumerate((("Zulu", "manual"), ("Alpha", "manual"), ("Hidden", "zotero"))):
            db.session.add(LiteratureItem(
                workspace_id=workspace_id, title=title, source=source,
                source_key=f"test:{index}",
                read_status="unread", authors_json="[]", keywords_json="[]",
            ))
        db.session.commit()

    result = service.list_literature({
        "pagination": True, "page": 1, "page_size": 1,
        "source": "manual", "sort": "title_asc",
    })

    assert result["pagination"] == {"page": 1, "page_size": 1, "pages": 2, "total": 2}
    assert [item["title"] for item in result["items"]] == ["Alpha"]


def test_legacy_list_contract_remains_a_plain_list(app):
    service = _service(app)
    assert isinstance(service.list_tasks({}), list)
    assert isinstance(service.list_notes({}), list)
    assert isinstance(service.list_weekly({}), list)
    assert isinstance(service.list_library_items({}), list)
    assert isinstance(service.list_records({}), list)


def test_record_server_pagination_applies_search_status_and_date_filters(app):
    service = _service(app)
    project = service.create_project({"title": "Pagination records"})
    alpha = service.create_record({
        "project_id": project["id"], "title": "Alpha protocol", "status": "completed",
        "experiment_date": "2026-08-10",
    })
    beta = service.create_record({
        "project_id": project["id"], "title": "Beta protocol", "status": "in_progress",
        "experiment_date": "2026-08-12",
    })
    service.update_record({"id": alpha["id"], "status": "completed"}, alpha["row_version"])
    service.update_record({"id": beta["id"], "status": "in_progress"}, beta["row_version"])

    result = service.list_records({
        "pagination": True, "page": 1, "page_size": 20,
        "search": "Beta", "status": "in_progress",
        "date_start": "2026-08-11", "date_end": "2026-08-13",
    })

    assert result["pagination"]["total"] == 1
    assert [item["title"] for item in result["items"]] == ["Beta protocol"]
