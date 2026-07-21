import io

from app import db
from app.ai_service import AIConfig
from app.models import AIChatAttachment, AIConversation, AIMessage, Experiment, ExperimentStep


def create_experiment(client, app):
    client.post("/experiments", data={
        "title": "AI planning test", "code": "AI-001", "objective": "Original objective",
        "owner": "Researcher", "status": "进行中",
    })
    with app.app_context():
        return Experiment.query.one().id


def test_floating_assistant_proposes_diff_and_applies_experiment_changes(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = create_experiment(client, app)
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="test-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "I prepared a revision.",
        "proposal": {
            "action": "update_experiment",
            "changes": {"objective": "Revised objective", "status": "进行中"},
            "steps": [{"title": "Collect samples", "description": "Keep on ice", "operator": "Researcher"}],
        },
        "references": [{"title": "Protocol source", "url": "https://example.test/protocol"}],
        "web_requested": False,
        "web_used": False,
    })

    response = client.post("/assistant/chat", data={
        "message": "Revise this experiment and add a step.",
        "page_type": "experiment", "page_id": str(experiment_id),
    }, content_type="multipart/form-data")
    assert response.status_code == 200
    payload = response.get_json()
    proposal = payload["assistant_message"]["proposal"]
    assert proposal["action"] == "update_experiment"
    assert any(item["field"] == "实验目的" for item in proposal["diff"])
    message_id = payload["assistant_message"]["id"]

    applied = client.post(f"/assistant/proposals/{message_id}/apply")
    assert applied.status_code == 200
    with app.app_context():
        experiment = db.session.get(Experiment, experiment_id)
        assert experiment.objective == "Revised objective"
        assert ExperimentStep.query.filter_by(experiment_id=experiment_id, title="Collect samples").one()
        assert db.session.get(AIMessage, message_id).applied_at is not None

    exported = client.get(f"/assistant/conversations/{payload['conversation_id']}/export.md")
    assert exported.status_code == 200
    assert b"Protocol source" in exported.data


def test_assistant_accepts_arbitrary_files_and_keeps_conversations_private(client, auth, app, monkeypatch):
    auth.register(email="assistant-owner@example.com")
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="test-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "File received.", "proposal": None, "references": [],
        "web_requested": False, "web_used": False,
    })
    response = client.post("/assistant/chat", data={
        "message": "Read this file",
        "files": (io.BytesIO(b"sample,value\nA,42\n"), "result.unusual-format"),
    }, content_type="multipart/form-data")
    assert response.status_code == 200
    conversation_id = response.get_json()["conversation_id"]
    with app.app_context():
        attachment = AIChatAttachment.query.one()
        assert attachment.original_name == "result.unusual-format"
        assert attachment.size_bytes > 0
        assert AIConversation.query.one().messages

    auth.logout()
    auth.register(email="assistant-other@example.com")
    assert client.get(f"/assistant/state?conversation_id={conversation_id}").status_code == 404
    assert client.get(f"/assistant/conversations/{conversation_id}/export.md").status_code == 404


def test_assistant_can_create_a_complete_experiment_plan(client, auth, app, monkeypatch):
    auth.register()
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="test-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "Plan ready.",
        "proposal": {
            "action": "create_experiment",
            "changes": {"title": "Dose response", "objective": "Measure viability", "status": "未开始"},
            "steps": [
                {"title": "Seed cells", "planned_date": "2026-07-22"},
                {"title": "Add compound", "planned_date": "2026-07-23"},
            ],
        },
        "references": [], "web_requested": False, "web_used": False,
    })
    response = client.post("/assistant/chat", data={"message": "Create a dose response experiment"})
    message_id = response.get_json()["assistant_message"]["id"]
    applied = client.post(f"/assistant/proposals/{message_id}/apply")
    assert applied.status_code == 200
    with app.app_context():
        experiment = Experiment.query.filter_by(title="Dose response").one()
        assert experiment.objective == "Measure viability"
        assert len(experiment.steps) == 2
