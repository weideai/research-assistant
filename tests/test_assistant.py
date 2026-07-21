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


def test_assistant_uses_internal_records_and_saves_generation_audit(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = create_experiment(client, app)
    client.post(f"/experiments/{experiment_id}/records", data={
        "record_date": "2026-07-21", "operator": "研究员", "conditions": "5 μM，24 h",
        "content": "细胞活力下降。", "result": "待确认", "remark": "需要增加重复。",
        "record_parameter_name": ["药物浓度"], "record_parameter_value": ["5"],
        "record_parameter_unit": ["μM"], "record_parameter_notes": ["终浓度"],
    })
    captured = {}

    def fake_chat(_messages, system_prompt, _config, **_kwargs):
        captured["prompt"] = system_prompt
        return {
            "reply": "历史记录显示 5 μM 条件下活力下降 [R2]，剂量和统计结论需人工核验。",
            "proposal": None, "references": [], "web_requested": False, "web_used": False,
        }

    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="audit-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", fake_chat)

    response = client.post("/assistant/chat", data={
        "message": "比较历史记录的剂量和统计结果",
        "page_type": "experiment", "page_id": str(experiment_id),
    })
    assert response.status_code == 200
    message = response.get_json()["assistant_message"]
    assert message["model_name"] == "audit-model"
    assert message["requires_human_review"] is True
    assert message["references"][0]["citation"] == "R2"
    assert message["references"][0]["url"].startswith("/records/")
    assert "5 μM" in captured["prompt"]

    prompt_response = client.get(f"/assistant/messages/{message['id']}/prompt.txt")
    assert prompt_response.status_code == 200
    assert "用户可访问的科研数据与内部引用".encode() in prompt_response.data
    with app.app_context():
        saved = db.session.get(AIMessage, message["id"])
        assert saved.model_name == "audit-model"
        assert saved.prompt_snapshot
        assert saved.context_snapshot_json


def test_experiment_detail_exposes_collapsible_tools_and_template_entry(client, auth, app):
    auth.register()
    experiment_id = create_experiment(client, app)
    response = client.get(f"/experiments/{experiment_id}")
    assert response.status_code == 200
    assert b'data-disclosure-key="experiment-' in response.data
    assert b'id="step-templates"' in response.data
    assert "保存步骤模板".encode() in response.data
    assert "新增实验记录".encode() in response.data


def test_assistant_supports_enter_send_and_background_completion_notice(client, auth):
    auth.register()
    response = client.get("/")
    assert response.status_code == 200
    assert b'id="ai-completion-toast"' in response.data

    script = client.get("/static/js/app.js")
    assert script.status_code == 200
    assert b'event.key === "Enter"' in script.data
    assert b'!event.shiftKey' in script.data
    assert b'aiRequestRunning' in script.data
    assert b'showAiNotice' in script.data


def test_assistant_limits_research_context_to_selected_experiments(client, auth, app, monkeypatch):
    auth.register()
    first_id = create_experiment(client, app)
    client.post("/experiments", data={"title": "Selected history", "code": "AI-002"})
    with app.app_context():
        second_id = Experiment.query.filter_by(title="Selected history").one().id
    client.post(f"/experiments/{first_id}/records", data={"content": "FIRST PRIVATE RESULT", "result": "成功"})
    client.post(f"/experiments/{second_id}/records", data={"content": "SECOND SELECTED RESULT", "result": "成功"})
    captured = {}

    def fake_chat(_messages, system_prompt, _config, **_kwargs):
        captured["prompt"] = system_prompt
        return {"reply": "已总结所选实验 [R2]。", "proposal": None, "references": [], "web_requested": False, "web_used": False}

    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="scope-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", fake_chat)
    response = client.post("/assistant/chat", data={
        "message": "总结所选实验历史", "experiment_scope_present": "1",
        "experiment_ids": [str(second_id)],
    })
    assert response.status_code == 200
    assert "SECOND SELECTED RESULT" in captured["prompt"]
    assert "FIRST PRIVATE RESULT" not in captured["prompt"]
    state = client.get(f"/assistant/state?conversation_id={response.get_json()['conversation_id']}").get_json()
    assert state["conversation"]["selected_experiment_ids"] == [second_id]
