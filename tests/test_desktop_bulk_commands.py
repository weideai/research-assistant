from app import db
from app.models import Note, Task, User, WeeklyReport
from app.services.desktop_workspace import DesktopApplicationService


def _service(app):
    with app.app_context():
        db.session.add(User(
            name="Bulk test", email="bulk@example.invalid",
            password_hash="local", role="system_admin",
        ))
        db.session.commit()
    return DesktopApplicationService(app)


def test_desktop_bulk_commands_update_in_one_call_and_return_item_results(app):
    service = _service(app)
    project = service.create_project({"title": "Bulk project"})
    task_a = service.save_task({"title": "Task A", "project_id": project["id"]})
    task_b = service.save_task({"title": "Task B", "project_id": project["id"]})
    note = service.save_note({"title": "Note", "body": "Body", "project_id": project["id"]})
    weekly = service.save_weekly({"week": "2026-08-10", "title": "Weekly"})

    task_result = service.task_bulk({"ids": [task_a["id"], task_b["id"]], "action": "status", "value": "done"})
    note_result = service.note_bulk({"ids": [note["id"]], "action": "trash"})
    weekly_result = service.weekly_bulk({"ids": [weekly["id"]], "action": "status", "value": "reviewed"})

    assert task_result["updated"] == 2
    assert {row["status"] for row in task_result["results"]} == {"updated"}
    assert note_result["results"] == [{"id": note["id"], "status": "updated"}]
    assert weekly_result["results"] == [{"id": weekly["id"], "status": "updated"}]
    with app.app_context():
        assert {row.status for row in Task.query.all()} == {"done"}
        assert db.session.get(Note, note["id"]).is_deleted is True
        assert db.session.get(WeeklyReport, weekly["id"]).status == "reviewed"
