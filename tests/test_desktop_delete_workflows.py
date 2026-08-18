from app import db
import json

from app.models import User
from app.services.desktop_workspace import DesktopApplicationService
import app.services.desktop_modules as desktop_modules


def desktop_service(app):
    with app.app_context():
        db.session.add(User(
            name="删除流程测试", email="delete-workflows@example.invalid",
            password_hash="local", role="system_admin",
        ))
        db.session.commit()
    return DesktopApplicationService(app)


def test_literature_can_move_to_trash_and_restore(app):
    service = desktop_service(app)
    item = service.save_literature({"title": "待删除文献", "authors": "测试作者"})

    service.trash_move({"entity_type": "literature", "id": item["id"]})
    assert service.list_literature() == []
    assert any(row["entity_type"] == "literature" and row["id"] == item["id"] for row in service.trash_list())

    service.trash_restore({"entity_type": "literature", "id": item["id"]})
    assert service.list_literature()[0]["id"] == item["id"]


def test_recycle_bin_can_permanently_delete_an_item(app):
    service = desktop_service(app)
    item = service.save_literature({"title": "永久删除文献", "authors": "测试作者"})

    service.trash_move({"entity_type": "literature", "id": item["id"]})
    assert service.trash_purge({"entity_type": "literature", "id": item["id"]}) == {"purged": True}
    assert not any(row["id"] == item["id"] for row in service.trash_list())


def test_zotero_sync_restores_matching_literature_from_recycle_bin(app, monkeypatch):
    service = desktop_service(app)

    class Response:
        def read(self):
            return json.dumps([{
                "key": "ZOT-RESTORE-1", "version": 7,
                "data": {"key": "ZOT-RESTORE-1", "title": "Zotero 恢复文献", "creators": []},
            }]).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(desktop_modules.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    first = service.zotero_sync()
    item = service.list_literature()[0]
    service.trash_move({"entity_type": "literature", "id": item["id"]})

    second = service.zotero_sync()

    assert first["added"] == 1
    assert second["restored"] == 1
    assert service.list_literature()[0]["id"] == item["id"]


def test_only_manual_calendar_events_can_be_removed(app):
    service = desktop_service(app)
    project = service.create_project({"title": "日历删除测试"})
    record = service.create_record({
        "project_id": project["id"], "title": "自动实验日期", "experiment_date": "2026-08-12",
    })
    task = service.save_task({
        "project_id": project["id"], "title": "自动任务截止日", "deadline": "2026-08-13",
    })
    event = service.create_calendar_event({
        "project_id": project["id"], "title": "手动提醒", "starts_at": "2026-08-14T09:00:00",
    })

    service.trash_move({"entity_type": "calendar_event", "id": event["id"]})
    events = service.list_calendar({"start": "2026-08-01", "end": "2026-08-31"})
    source_keys = {(row["source_type"], row["source_id"]) for row in events}
    assert ("event", event["id"]) not in source_keys
    assert ("record", record["id"]) in source_keys
    assert ("task", task["id"]) in source_keys
    assert any(row["entity_type"] == "calendar_event" and row["id"] == event["id"] for row in service.trash_list())

    service.trash_restore({"entity_type": "calendar_event", "id": event["id"]})
    assert ("event", event["id"]) in {
        (row["source_type"], row["source_id"])
        for row in service.list_calendar({"start": "2026-08-01", "end": "2026-08-31"})
    }
