import io
import json
from datetime import date, datetime

from app import db
from app.ai_service import AIConfig
from app.models import (
    AIAssistantPreference, AIChatAttachment, AIConversation, AIKnowledgeBase,
    AIKnowledgeDocument, AIMessage, BatchParameter, Experiment, ExperimentAttachment,
    ExperimentBatch, ExperimentRecord, ExperimentStep, RecordParameter, RecordRevision,
    ResearchProject,
)


def create_experiment(client, app):
    client.post("/experiments", data={
        "title": "AI planning test", "code": "AI-001", "objective": "Original objective",
        "owner": "Researcher", "status": "进行中",
    })
    with app.app_context():
        return Experiment.query.one().id


def create_batch(client, app, experiment_id):
    client.post(f"/experiments/{experiment_id}/batches", data={
        "batch_code": f"AI-BATCH-{experiment_id}",
    })
    with app.app_context():
        return ExperimentBatch.query.filter_by(experiment_id=experiment_id).one().id


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
    assert any(item["field"] == "实验计划目的" for item in proposal["diff"])
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


def test_assistant_creates_project_only_after_confirmation_and_can_revert(client, auth, app, monkeypatch):
    auth.register()
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="project-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "项目草案已准备好，请确认后创建。",
        "proposal": {
            "action": "create_project",
            "changes": {
                "title": "骨肉瘤耐药机制研究", "code": "OS-RES-01",
                "objective": "验证候选耐药机制", "status": "规划中",
                "start_date": "2026-07-24", "end_date": "2026-12-31",
                "notes": "先完成体外验证。",
            },
        },
        "references": [], "web_requested": False, "web_used": False,
    })

    response = client.post("/assistant/chat", data={"message": "创建一个耐药机制科研项目"})
    assert response.status_code == 200
    payload = response.get_json()
    proposal = payload["assistant_message"]["proposal"]
    assert proposal["action"] == "create_project"
    assert any(row["field"] == "项目名称" for row in proposal["diff"])
    with app.app_context():
        assert ResearchProject.query.count() == 0

    applied = client.post(f"/assistant/proposals/{payload['assistant_message']['id']}/apply")
    assert applied.status_code == 200
    with app.app_context():
        project = ResearchProject.query.filter_by(code="OS-RES-01").one()
        project_id = project.id
        assert project.title == "骨肉瘤耐药机制研究"
        assert project.status == "规划中"
        assert project.start_date.isoformat() == "2026-07-24"
    assert applied.get_json()["redirect_url"].endswith(f"/projects/{project_id}")

    reverted = client.post(f"/assistant/proposals/{payload['assistant_message']['id']}/revert")
    assert reverted.status_code == 200
    with app.app_context():
        assert db.session.get(ResearchProject, project_id) is None


def test_assistant_manages_current_project_after_confirmation_and_can_revert(client, auth, app, monkeypatch):
    auth.register()
    client.post("/projects", data={
        "title": "原始科研项目", "code": "PROJECT-01", "status": "规划中",
        "objective": "原始目标",
    })
    with app.app_context():
        project_id = ResearchProject.query.filter_by(code="PROJECT-01").one().id
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="project-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "项目更新草案已生成。",
        "proposal": {
            "action": "manage_project",
            "changes": {"objective": "验证新的研究假设", "status": "进行中"},
        },
        "references": [], "web_requested": False, "web_used": False,
    })

    proposed = client.post("/assistant/chat", data={
        "message": "更新当前科研项目", "page_type": "project", "page_id": project_id,
    }).get_json()
    message_id = proposed["assistant_message"]["id"]
    assert proposed["assistant_message"]["proposal"]["action"] == "manage_project"
    with app.app_context():
        assert db.session.get(ResearchProject, project_id).objective == "原始目标"

    applied = client.post(f"/assistant/proposals/{message_id}/apply")
    assert applied.status_code == 200, applied.get_json()
    with app.app_context():
        project = db.session.get(ResearchProject, project_id)
        assert project.objective == "验证新的研究假设"
        assert project.status == "进行中"

    reverted = client.post(f"/assistant/proposals/{message_id}/revert")
    assert reverted.status_code == 200, reverted.get_json()
    with app.app_context():
        project = db.session.get(ResearchProject, project_id)
        assert project.objective == "原始目标"
        assert project.status == "规划中"


def test_assistant_creates_execution_for_current_plan_and_can_revert(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = create_experiment(client, app)
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="execution-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "实验执行草案已生成。",
        "proposal": {
            "action": "create_execution",
            "changes": {
                "batch_code": "RUN-AI-01", "status": "进行中",
                "start_date": "2026-07-24", "operator": "研究员",
            },
        },
        "references": [], "web_requested": False, "web_used": False,
    })

    proposed = client.post("/assistant/chat", data={
        "message": "开始一次新的实验执行", "page_type": "experiment", "page_id": experiment_id,
    }).get_json()
    proposal = proposed["assistant_message"]["proposal"]
    assert proposal["action"] == "create_execution"
    assert proposal["create_resource"] is True
    assert proposal["diff"][0]["id"] == "execution:create"
    message_id = proposed["assistant_message"]["id"]
    with app.app_context():
        assert ExperimentBatch.query.filter_by(experiment_id=experiment_id).count() == 0

    applied = client.post(f"/assistant/proposals/{message_id}/apply")
    assert applied.status_code == 200, applied.get_json()
    with app.app_context():
        execution = ExperimentBatch.query.filter_by(experiment_id=experiment_id).one()
        execution_id = execution.id
        assert execution.batch_code == "RUN-AI-01"
        assert execution.status == "进行中"
        assert execution.start_date == date(2026, 7, 24)
    assert applied.get_json()["redirect_url"].endswith(f"/batches/{execution_id}")

    reverted = client.post(f"/assistant/proposals/{message_id}/revert")
    assert reverted.status_code == 200, reverted.get_json()
    with app.app_context():
        assert db.session.get(ExperimentBatch, execution_id) is None


def test_assistant_requires_project_choice_when_multiple_projects_exist(client, auth, app, monkeypatch):
    auth.register()
    with app.app_context():
        user_id = ResearchProject.query.first().user_id if ResearchProject.query.first() else 1
        first = ResearchProject(user_id=user_id, title="项目一", status="规划中")
        second = ResearchProject(user_id=user_id, title="项目二", status="规划中")
        db.session.add_all((first, second))
        db.session.commit()
        second_id = second.id
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="plan-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "实验计划草案已生成。",
        "proposal": {
            "action": "create_experiment",
            "changes": {"title": "需要明确归属的实验计划"},
        },
        "references": [], "web_requested": False, "web_used": False,
    })

    proposed = client.post("/assistant/chat", data={"message": "创建实验计划"}).get_json()
    message_id = proposed["assistant_message"]["id"]
    blocked = client.post(f"/assistant/proposals/{message_id}/apply")
    assert blocked.status_code == 400
    assert "选择实验计划的所属项目" in blocked.get_json()["error"]

    applied = client.post(f"/assistant/proposals/{message_id}/apply", data={"project_id": second_id})
    assert applied.status_code == 200, applied.get_json()
    with app.app_context():
        experiment = Experiment.query.filter_by(title="需要明确归属的实验计划").one()
        assert experiment.project_id == second_id


def test_assistant_rejects_invalid_project_fields(client, auth, app, monkeypatch):
    auth.register()
    proposals = iter((
        {
            "action": "create_project",
            "changes": {"title": "非法状态项目", "status": "随便做做"},
        },
        {
            "action": "create_project",
            "changes": {
                "title": "日期倒置项目", "status": "规划中",
                "start_date": "2026-08-02", "end_date": "2026-08-01",
            },
        },
    ))
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="project-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "请核对项目提案。", "proposal": next(proposals), "references": [],
        "web_requested": False, "web_used": False,
    })

    first = client.post("/assistant/chat", data={"message": "创建第一个项目"}).get_json()
    invalid_status = client.post(f"/assistant/proposals/{first['assistant_message']['id']}/apply")
    assert invalid_status.status_code == 400
    assert invalid_status.get_json()["error"] == "项目状态不合法。"

    second = client.post("/assistant/chat", data={"message": "创建第二个项目"}).get_json()
    invalid_dates = client.post(f"/assistant/proposals/{second['assistant_message']['id']}/apply")
    assert invalid_dates.status_code == 400
    assert invalid_dates.get_json()["error"] == "项目预计结束日期不能早于开始日期。"
    with app.app_context():
        assert ResearchProject.query.count() == 0


def test_project_proposal_is_private_to_conversation_owner(client, auth, app, monkeypatch):
    auth.register(email="project-owner@example.com")
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="project-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "项目提案已生成。",
        "proposal": {"action": "create_project", "changes": {"title": "私有科研项目"}},
        "references": [], "web_requested": False, "web_used": False,
    })
    response = client.post("/assistant/chat", data={"message": "创建私有项目"}).get_json()
    message_id = response["assistant_message"]["id"]

    auth.logout()
    auth.register(email="project-other@example.com")
    assert client.post(f"/assistant/proposals/{message_id}/apply").status_code == 404
    with app.app_context():
        assert ResearchProject.query.count() == 0

    auth.logout()
    auth.login(email="project-owner@example.com")
    assert client.post(f"/assistant/proposals/{message_id}/apply").status_code == 200
    with app.app_context():
        assert ResearchProject.query.filter_by(title="私有科研项目").one()


def test_project_context_receives_new_experiment_and_blocks_unsafe_project_revert(client, auth, app, monkeypatch):
    auth.register()
    client.post("/projects", data={"title": "当前项目", "code": "CURRENT-PROJECT"})
    with app.app_context():
        current_project_id = ResearchProject.query.filter_by(code="CURRENT-PROJECT").one().id
    page = client.get(f"/projects/{current_project_id}")
    assert b'data-assistant-page-type="project"' in page.data
    assert f'data-assistant-page-id="{current_project_id}"'.encode() in page.data

    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="project-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "实验计划已准备好。",
        "proposal": {
            "action": "create_experiment",
            "changes": {"title": "当前项目下的实验", "status": "未开始"},
        },
        "references": [], "web_requested": False, "web_used": False,
    })
    planned = client.post("/assistant/chat", data={
        "message": "在当前项目创建实验", "page_type": "project", "page_id": current_project_id,
    }).get_json()
    assert planned["assistant_message"]["proposal"]["project_id"] == current_project_id
    assert client.post(f"/assistant/proposals/{planned['assistant_message']['id']}/apply").status_code == 200
    with app.app_context():
        assert Experiment.query.filter_by(title="当前项目下的实验").one().project_id == current_project_id

    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "新项目提案已准备好。",
        "proposal": {"action": "create_project", "changes": {"title": "待扩展项目"}},
        "references": [], "web_requested": False, "web_used": False,
    })
    created = client.post("/assistant/chat", data={"message": "再创建一个科研项目"}).get_json()
    message_id = created["assistant_message"]["id"]
    assert client.post(f"/assistant/proposals/{message_id}/apply").status_code == 200
    with app.app_context():
        created_project_id = ResearchProject.query.filter_by(title="待扩展项目").one().id
    client.post("/experiments", data={
        "project_id": created_project_id, "title": "后续新增实验",
    })

    blocked = client.post(f"/assistant/proposals/{message_id}/revert")
    assert blocked.status_code == 409
    assert "停止撤销" in blocked.get_json()["error"]
    with app.app_context():
        assert db.session.get(ResearchProject, created_project_id) is not None
        assert Experiment.query.filter_by(project_id=created_project_id, title="后续新增实验").one()


def test_assistant_uses_internal_records_and_saves_generation_audit(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = create_experiment(client, app)
    batch_id = create_batch(client, app, experiment_id)
    client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id,
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


def test_experiment_and_batch_details_expose_planning_and_record_tools(client, auth, app):
    auth.register()
    experiment_id = create_experiment(client, app)
    batch_id = create_batch(client, app, experiment_id)
    response = client.get(f"/experiments/{experiment_id}")
    assert response.status_code == 200
    assert b'data-disclosure-key="experiment-' in response.data
    assert b'id="step-templates"' in response.data
    assert "保存步骤模板".encode() in response.data
    batch_response = client.get(f"/batches/{batch_id}")
    assert batch_response.status_code == 200
    assert "添加过程记录".encode() in batch_response.data
    assert b'id="batch-record-bulk-form"' in batch_response.data


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
    assert b'confirmAiOutgoingContext' in script.data
    assert b'destructive_confirmation' in script.data


def test_assistant_context_preview_lists_outgoing_research_scope(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = create_experiment(client, app)
    batch_id = create_batch(client, app, experiment_id)
    client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id, "content": "PRIVATE RESULT",
    })
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://gateway.example.test/v1", api_key="test", model="preview-model", enabled=True,
    ))
    response = client.post("/assistant/context-preview", data={
        "message": "总结所选实验记录", "page_type": "experiment", "page_id": experiment_id,
        "experiment_scope_present": "1", "experiment_ids": [str(experiment_id)],
        "file_names": ["result.csv"], "file_sizes": ["120"], "web_access": "1",
    })
    assert response.status_code == 200
    preview = response.get_json()
    assert preview["provider"] == {"host": "gateway.example.test", "model": "preview-model", "source": "explicit"}
    assert preview["research"]["experiment_count"] == 1
    assert preview["research"]["record_count"] == 1
    assert preview["files"] == [{"name": "result.csv", "size_bytes": 120}]
    assert preview["web_access"] is True
    assert preview["requires_confirmation"] is True


def test_existing_conversation_uses_current_page_context_for_preview_and_generation(client, auth, app, monkeypatch):
    auth.register()
    client.post("/projects", data={"title": "旧页面项目", "code": "OLD-PAGE"})
    client.post("/projects", data={"title": "当前页面项目", "code": "CURRENT-PAGE"})
    with app.app_context():
        old_project_id = ResearchProject.query.filter_by(code="OLD-PAGE").one().id
        current_project_id = ResearchProject.query.filter_by(code="CURRENT-PAGE").one().id

    prompts = []

    def fake_chat(_messages, system_prompt, _config, **_kwargs):
        prompts.append(system_prompt)
        return {
            "reply": "已按当前页面处理。", "proposal": None, "references": [],
            "web_requested": False, "web_used": False,
        }

    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="context-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", fake_chat)
    first = client.post("/assistant/chat", data={
        "message": "第一轮", "page_type": "project", "page_id": old_project_id,
    }).get_json()
    conversation_id = first["conversation_id"]

    preview = client.post("/assistant/context-preview", data={
        "conversation_id": conversation_id, "message": "继续",
        "page_type": "project", "page_id": current_project_id,
    })
    assert preview.status_code == 200
    assert preview.get_json()["page"] == {
        "type": "project", "id": current_project_id, "field_count": 7,
    }

    generated = client.post("/assistant/chat", data={
        "conversation_id": conversation_id, "message": "继续",
        "page_type": "project", "page_id": current_project_id,
    })
    assert generated.status_code == 200
    assert "当前页面项目" in prompts[-1]
    assert "旧页面项目" not in prompts[-1]
    with app.app_context():
        conversation = db.session.get(AIConversation, conversation_id)
        assert (conversation.page_type, conversation.page_id) == ("project", current_project_id)
        assistant_message = AIMessage.query.filter_by(
            conversation_id=conversation_id, role="assistant",
        ).order_by(AIMessage.id.desc()).first()
        page_snapshot = json.loads(assistant_message.context_snapshot_json)["page"]
        assert page_snapshot["page_type"] == "project"
        assert page_snapshot["page_id"] == current_project_id


def test_assistant_rejects_page_context_owned_by_another_user(client, auth, app, monkeypatch):
    auth.register(email="page-owner@example.com")
    client.post("/projects", data={"title": "私有页面", "code": "PRIVATE-PAGE"})
    with app.app_context():
        foreign_project_id = ResearchProject.query.filter_by(code="PRIVATE-PAGE").one().id
    auth.logout()
    auth.register(email="page-other@example.com")
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="context-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "ok", "proposal": None, "references": [],
        "web_requested": False, "web_used": False,
    })
    conversation_id = client.post("/assistant/chat", data={"message": "建立会话"}).get_json()["conversation_id"]
    page_data = {
        "conversation_id": conversation_id, "message": "读取私有页面",
        "page_type": "project", "page_id": foreign_project_id,
    }

    assert client.post("/assistant/context-preview", data=page_data).status_code == 404
    assert client.post("/assistant/chat", data=page_data).status_code == 404
    with app.app_context():
        conversation = db.session.get(AIConversation, conversation_id)
        assert (conversation.page_type, conversation.page_id) == ("", None)
        assert len(conversation.messages) == 2


def test_assistant_state_exposes_projects_and_project_ids_for_default_scope(client, auth, app):
    auth.register()
    client.post("/projects", data={"title": "项目甲", "code": "PROJECT-A"})
    client.post("/projects", data={"title": "项目乙", "code": "PROJECT-B"})
    with app.app_context():
        project_a = ResearchProject.query.filter_by(code="PROJECT-A").one()
        project_b = ResearchProject.query.filter_by(code="PROJECT-B").one()
        project_a_id, project_b_id = project_a.id, project_b.id
    client.post("/experiments", data={
        "title": "项目甲实验 1", "code": "A-01", "project_id": project_a_id,
    })
    client.post("/experiments", data={
        "title": "项目甲实验 2", "code": "A-02", "project_id": project_a_id,
    })
    client.post("/experiments", data={
        "title": "项目乙实验", "code": "B-01", "project_id": project_b_id,
    })

    state = client.get("/assistant/state").get_json()
    projects = {item["id"]: item for item in state["projects"]}
    assert projects[project_a_id] == {"id": project_a_id, "title": "项目甲", "code": "PROJECT-A"}
    assert projects[project_b_id] == {"id": project_b_id, "title": "项目乙", "code": "PROJECT-B"}
    experiments = {item["code"]: item for item in state["experiments"]}
    assert experiments["A-01"]["project_id"] == project_a_id
    assert experiments["A-02"]["project_id"] == project_a_id
    assert experiments["B-01"]["project_id"] == project_b_id

    script = client.get("/static/js/app.js").data
    assert b"state.page_scope || {}" in script
    assert b"experiment.project_id" in script
    assert b"aiProjectOptions = state.projects || []" in script
    assert b"state.batches" in script


def test_assistant_state_exposes_execution_metadata_and_current_page_scope(client, auth, app):
    auth.register()
    experiment_id = create_experiment(client, app)
    first_batch_id = create_batch(client, app, experiment_id)
    client.post(f"/experiments/{experiment_id}/batches", data={
        "batch_code": "RUN-02", "repeat_kind": "生物学重复", "repeat_number": "2",
        "group_name": "处理组", "start_date": "2026-07-24",
    })
    with app.app_context():
        second = ExperimentBatch.query.filter_by(experiment_id=experiment_id, batch_code="RUN-02").one()
        second_batch_id = second.id
        project_id = db.session.get(Experiment, experiment_id).project_id
        db.session.add(BatchParameter(
            batch_id=second.id, position=1, name="药物浓度", value="5", unit="μM",
        ))
        db.session.commit()

    state = client.get(
        f"/assistant/state?page_type=batch&page_id={second_batch_id}"
    ).get_json()
    assert state["page_scope"] == {
        "project_id": project_id,
        "experiment_id": experiment_id,
        "batch_id": second_batch_id,
    }
    batches = {item["id"]: item for item in state["batches"]}
    assert {first_batch_id, second_batch_id}.issubset(batches)
    assert batches[second_batch_id]["code"] == "RUN-02"
    assert batches[second_batch_id]["repeat_kind"] == "生物学重复"

    client.post(f"/batches/{second_batch_id}/records", data={
        "batch_id": second_batch_id, "content": "执行二观察记录",
    })
    with app.app_context():
        record_id = ExperimentRecord.query.filter_by(batch_id=second_batch_id).one().id
    record_state = client.get(
        f"/assistant/state?page_type=record&page_id={record_id}"
    ).get_json()
    assert record_state["page_scope"]["experiment_id"] == experiment_id
    assert record_state["page_scope"]["batch_id"] == second_batch_id


def test_assistant_execution_scope_separates_repeats_and_cites_execution_parameters(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = create_experiment(client, app)
    first_batch_id = create_batch(client, app, experiment_id)
    client.post(f"/experiments/{experiment_id}/batches", data={
        "batch_code": "RUN-02", "repeat_kind": "生物学重复", "repeat_number": "2",
        "group_name": "处理组", "start_date": "2026-07-24",
    })
    with app.app_context():
        second = ExperimentBatch.query.filter_by(experiment_id=experiment_id, batch_code="RUN-02").one()
        second_batch_id = second.id
        db.session.add(BatchParameter(
            batch_id=second.id, position=1, name="药物浓度", value="5", unit="μM",
            notes="终浓度",
        ))
        db.session.commit()
    client.post(f"/batches/{first_batch_id}/records", data={
        "batch_id": first_batch_id, "content": "RUN ONE PRIVATE RESULT", "result": "成功",
    })
    client.post(f"/batches/{second_batch_id}/records", data={
        "batch_id": second_batch_id, "content": "RUN TWO SELECTED RESULT", "result": "成功",
    })
    captured = {}

    def fake_chat(_messages, system_prompt, _config, **_kwargs):
        captured["prompt"] = system_prompt
        return {
            "reply": "已按 RUN-02 汇总实际参数和过程记录 [R2] [R3]。",
            "proposal": None, "references": [], "web_requested": False, "web_used": False,
        }

    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="scope-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", fake_chat)
    response = client.post("/assistant/chat", data={
        "message": "只总结所选实验执行",
        "experiment_scope_present": "1", "batch_scope_present": "1",
        "batch_ids": [str(second_batch_id)],
    })
    assert response.status_code == 200
    assert "RUN TWO SELECTED RESULT" in captured["prompt"]
    assert "RUN ONE PRIVATE RESULT" not in captured["prompt"]
    assert '"batch_id": ' + str(second_batch_id) in captured["prompt"]
    assert '"code": "RUN-02"' in captured["prompt"]
    assert '"name": "药物浓度"' in captured["prompt"]

    payload = response.get_json()
    references = payload["assistant_message"]["references"]
    execution_reference = next(item for item in references if item["type"] == "experiment_execution")
    record_reference = next(item for item in references if item["type"] == "experiment_record")
    assert execution_reference["batch_id"] == second_batch_id
    assert execution_reference["execution_code"] == "RUN-02"
    assert execution_reference["actual_parameters"][0]["value"] == "5"
    assert record_reference["batch_id"] == second_batch_id
    assert record_reference["execution_code"] == "RUN-02"
    assert record_reference["execution_actual_parameters"][0]["name"] == "药物浓度"

    state = client.get(
        f"/assistant/state?conversation_id={payload['conversation_id']}"
    ).get_json()["conversation"]
    assert state["selected_experiment_ids"] == []
    assert state["selected_batch_ids"] == [second_batch_id]


def test_assistant_limits_research_context_to_selected_experiments(client, auth, app, monkeypatch):
    auth.register()
    first_id = create_experiment(client, app)
    client.post("/experiments", data={"title": "Selected history", "code": "AI-002"})
    with app.app_context():
        second_id = Experiment.query.filter_by(title="Selected history").one().id
    first_batch_id = create_batch(client, app, first_id)
    second_batch_id = create_batch(client, app, second_id)
    client.post(f"/batches/{first_batch_id}/records", data={
        "batch_id": first_batch_id, "content": "FIRST PRIVATE RESULT", "result": "成功",
    })
    client.post(f"/batches/{second_batch_id}/records", data={
        "batch_id": second_batch_id, "content": "SECOND SELECTED RESULT", "result": "成功",
    })
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


def test_user_can_build_private_knowledge_base_and_reset_prompt(client, auth, app, monkeypatch):
    auth.register(email="knowledge-owner@example.com")
    created = client.post("/assistant/knowledge-bases", data={
        "name": "细胞培养 SOP", "description": "实验室内部流程",
        "custom_instructions": "优先提醒无菌操作。",
    })
    assert created.status_code == 200
    base_id = created.get_json()["id"]
    added = client.post(f"/assistant/knowledge-bases/{base_id}/documents", data={
        "title": "换液规范", "text_content": "细胞融合度达到 70% 后按 SOP 换液。",
    })
    assert added.status_code == 200
    saved_prompt = client.post("/assistant/preferences", data={
        "custom_prompt": "回答时先给出操作清单，再列出风险点。",
    })
    assert saved_prompt.status_code == 200

    captured = {}

    def fake_chat(_messages, system_prompt, _config, **_kwargs):
        captured["prompt"] = system_prompt
        return {
            "reply": "知识库要求在 70% 融合度后换液 [K1]。",
            "proposal": None, "references": [], "web_requested": False, "web_used": False,
        }

    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="knowledge-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", fake_chat)
    chat = client.post("/assistant/chat", data={
        "message": "根据知识库说明换液时间", "knowledge_scope_present": "1",
        "knowledge_base_ids": [str(base_id)],
    })
    assert chat.status_code == 200
    assert "细胞融合度达到 70%" in captured["prompt"]
    assert "先给出操作清单" in captured["prompt"]
    assert "必须由用户查看修改前后差异并确认" in captured["prompt"]
    assert chat.get_json()["assistant_message"]["references"][0]["citation"] == "K1"

    state = client.get(f"/assistant/state?conversation_id={chat.get_json()['conversation_id']}").get_json()
    assert state["conversation"]["selected_knowledge_base_ids"] == [base_id]
    assert state["knowledge_bases"][0]["documents"][0]["readable"] is True

    reset = client.post("/assistant/preferences", data={"action": "reset"})
    assert reset.status_code == 200
    assert reset.get_json()["using_default"] is True
    with app.app_context():
        assert AIAssistantPreference.query.one().custom_prompt == ""
        document_id = AIKnowledgeDocument.query.one().id

    auth.logout()
    auth.register(email="knowledge-other@example.com")
    assert client.get(f"/assistant/knowledge-documents/{document_id}/download").status_code == 404
    assert client.post(f"/assistant/knowledge-bases/{base_id}", data={"action": "delete"}).status_code == 404


def test_assistant_applies_selected_diff_only_and_can_revert(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = create_experiment(client, app)
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="test-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "Prepared two field changes.",
        "proposal": {
            "action": "manage_experiment",
            "changes": {"objective": "Selected objective", "owner": "AI owner"},
        },
        "references": [], "web_requested": False, "web_used": False,
    })
    response = client.post("/assistant/chat", data={
        "message": "Update objective and owner", "page_type": "experiment", "page_id": experiment_id,
    })
    message_id = response.get_json()["assistant_message"]["id"]
    applied = client.post(f"/assistant/proposals/{message_id}/apply", data={
        "selection_present": "1", "selected_change_ids": ["field:objective"],
    })
    assert applied.status_code == 200
    assert applied.get_json()["can_revert"] is True
    with app.app_context():
        experiment = db.session.get(Experiment, experiment_id)
        assert experiment.objective == "Selected objective"
        assert experiment.owner == "Researcher"

    reverted = client.post(f"/assistant/proposals/{message_id}/revert")
    assert reverted.status_code == 200
    with app.app_context():
        experiment = db.session.get(Experiment, experiment_id)
        assert experiment.objective == "Original objective"
        assert experiment.owner == "Researcher"
        assert db.session.get(AIMessage, message_id).reverted_at is not None


def test_assistant_ui_exposes_window_knowledge_and_message_controls(client, auth):
    auth.register()
    response = client.get("/")
    assert response.status_code == 200
    for control_id in (
        "ai-dock-left", "ai-dock-right", "ai-maximize",
        "ai-knowledge-create-form", "ai-prompt-form", "ai-prompt-reset", "ai-stop",
    ):
        assert f'id="{control_id}"'.encode() in response.data
    assert b'id="ai-popout"' not in response.data
    assert client.get("/assistant/popup").status_code == 404
    script = client.get("/static/js/app.js").data
    assert b"ResizeObserver" in script
    assert b"selected_change_ids" in script
    assert b"syncExperimentScopeControls" in script
    assert b"parent.indeterminate" in script
    assert b'batch_scope_present' in script
    assert b"navigator.clipboard.writeText" in script


def test_assistant_conversations_can_be_listed_renamed_and_deleted_privately(client, auth, app):
    auth.register(email="conversation-owner@example.com")
    first = client.post("/assistant/conversations", data={}).get_json()
    second = client.post("/assistant/conversations", data={}).get_json()

    renamed = client.post(f"/assistant/conversations/{first['id']}", data={
        "action": "rename", "title": "细胞实验复盘",
    })
    assert renamed.status_code == 200
    state = client.get(f"/assistant/state?conversation_id={first['id']}").get_json()
    assert state["conversation"]["title"] == "细胞实验复盘"
    assert {item["id"] for item in state["conversations"]} == {first["id"], second["id"]}

    auth.logout()
    auth.register(email="conversation-other@example.com")
    assert client.post(f"/assistant/conversations/{first['id']}", data={"action": "delete"}).status_code == 404

    auth.logout()
    auth.login(email="conversation-owner@example.com")
    deleted = client.post(f"/assistant/conversations/{first['id']}", data={"action": "delete"})
    assert deleted.status_code == 200
    assert deleted.get_json()["next_conversation_id"] == second["id"]
    with app.app_context():
        assert db.session.get(AIConversation, first["id"]) is None


def test_assistant_can_edit_final_prompt_and_regenerate_final_reply(client, auth, app, monkeypatch):
    auth.register()
    replies = iter(("first reply", "edited reply", "regenerated reply"))
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="history-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": next(replies), "proposal": None, "references": [],
        "web_requested": False, "web_used": False,
    })

    chat = client.post("/assistant/chat", data={"message": "original prompt"}).get_json()
    conversation_id = chat["conversation_id"]
    state = client.get(f"/assistant/state?conversation_id={conversation_id}").get_json()["conversation"]
    user_message, assistant_message = state["messages"]
    assert user_message["can_edit"] is True
    assert assistant_message["can_regenerate"] is True

    edited = client.post(f"/assistant/messages/{user_message['id']}", data={
        "action": "edit", "content": "edited prompt",
    })
    assert edited.status_code == 200
    assert edited.get_json()["assistant_message"]["content"] == "edited reply"
    state = client.get(f"/assistant/state?conversation_id={conversation_id}").get_json()["conversation"]
    assert [item["content"] for item in state["messages"]] == ["edited prompt", "edited reply"]

    final_reply_id = state["messages"][-1]["id"]
    regenerated = client.post(f"/assistant/messages/{final_reply_id}/regenerate")
    assert regenerated.status_code == 200
    assert regenerated.get_json()["assistant_message"]["content"] == "regenerated reply"
    with app.app_context():
        assert AIMessage.query.filter_by(conversation_id=conversation_id).count() == 2


def test_assistant_rejects_editing_older_turn_and_active_applied_reply(client, auth, app, monkeypatch):
    auth.register()
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="guard-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "reply", "proposal": None, "references": [],
        "web_requested": False, "web_used": False,
    })
    first = client.post("/assistant/chat", data={"message": "first"}).get_json()
    conversation_id = first["conversation_id"]
    client.post("/assistant/chat", data={"conversation_id": conversation_id, "message": "second"})
    state = client.get(f"/assistant/state?conversation_id={conversation_id}").get_json()["conversation"]
    assert state["messages"][0]["can_edit"] is False
    assert client.post(f"/assistant/messages/{state['messages'][0]['id']}", data={
        "action": "edit", "content": "changed first",
    }).status_code == 409

    final_reply_id = state["messages"][-1]["id"]
    with app.app_context():
        message = db.session.get(AIMessage, final_reply_id)
        message.applied_at = message.created_at
        db.session.commit()
    assert client.post(f"/assistant/messages/{final_reply_id}/regenerate").status_code == 409
    assert client.post(f"/assistant/messages/{final_reply_id}", data={"action": "delete"}).status_code == 409


def test_assistant_ui_exposes_chat_history_and_cherry_style_shortcuts(client, auth):
    auth.register()
    page = client.get("/").data
    for control_id in (
        "ai-sidebar-toggle", "ai-new-chat", "ai-new-chat-side",
        "ai-conversation-search", "ai-conversation-list",
    ):
        assert f'id="{control_id}"'.encode() in page
    script = client.get("/static/js/app.js").data
    assert b"ai-edit-message" in script
    assert b"ai-delete-message" in script
    assert b"ai-regenerate-message" in script
    assert b"ai-proposal-project" in script
    assert b'data.set("project_id", projectSelect.value)' in script
    assert b'event.key.toLowerCase() === "n"' in script
    assert b'event.key.toLowerCase() === "k"' in script
    assert b'event.key.toLowerCase() === "l"' in script


def test_project_credit_exposes_author_and_repository(client, auth):
    auth.register()
    page = client.get("/").data
    assert "作者：面壁者".encode() in page
    assert b'https://github.com/weideai/research-assistant' in page
    assert 'aria-label="打开项目 GitHub 仓库"'.encode() in page


def test_assistant_manages_batch_records_after_confirmation_and_reverts_fully(
        client, auth, app, monkeypatch):
    auth.register()
    experiment_id = create_experiment(client, app)
    batch_id = create_batch(client, app, experiment_id)
    finalized_at = datetime(2026, 7, 23, 9, 30)
    with app.app_context():
        batch = db.session.get(ExperimentBatch, batch_id)
        batch.status = "进行中"
        batch.start_date = date(2026, 7, 20)
        parameter = BatchParameter(
            batch_id=batch_id, position=1, name="温度", value="37", unit="°C",
        )
        record = ExperimentRecord(
            experiment_id=experiment_id, batch_id=batch_id,
            record_date=date(2026, 7, 21), content="原始观察", result="待确认",
            lifecycle_status="已定稿", finalized_at=finalized_at,
        )
        db.session.add_all((parameter, record))
        db.session.flush()
        db.session.add_all((
            RecordParameter(record_id=record.id, position=1, name="浓度", value="5", unit="μM"),
            RecordRevision(
                record_id=record.id, user_id=1, reason="人工定稿",
                before_json="{}", after_json='{"content":"原始观察"}',
            ),
        ))
        db.session.commit()
        parameter_id = parameter.id
        record_id = record.id

    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="batch-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "执行批次修改已准备好，请核对差异。",
        "proposal": {
            "action": "manage_batch",
            "changes": {
                "status": "已完成", "end_date": "2026-07-24",
                "summary": "本次执行完成", "requires_repeat": "true",
            },
            "parameter_operations": [
                {"operation": "update", "id": parameter_id, "changes": {"value": "36.5"}},
                {"operation": "create", "changes": {"name": "孵育时间", "value": "24", "unit": "h"}},
            ],
            "record_operations": [
                {
                    "operation": "update", "id": record_id,
                    "changes": {"content": "AI 整理后的观察", "result": "成功"},
                },
                {
                    "operation": "create",
                    "changes": {
                        "record_date": "2026-07-24", "content": "新增复核记录", "result": "待确认",
                    },
                },
            ],
        },
        "references": [], "web_requested": False, "web_used": False,
    })

    proposed = client.post("/assistant/chat", data={
        "message": "整理本次执行并补一条记录", "page_type": "batch", "page_id": batch_id,
    })
    assert proposed.status_code == 200
    message_id = proposed.get_json()["assistant_message"]["id"]
    with app.app_context():
        assert db.session.get(ExperimentBatch, batch_id).status == "进行中"
        assert db.session.get(ExperimentRecord, record_id).content == "原始观察"

    applied = client.post(f"/assistant/proposals/{message_id}/apply")
    assert applied.status_code == 200, applied.get_json()
    assert applied.get_json()["can_revert"] is True
    with app.app_context():
        batch = db.session.get(ExperimentBatch, batch_id)
        record = db.session.get(ExperimentRecord, record_id)
        created_record = ExperimentRecord.query.filter_by(
            batch_id=batch_id, content="新增复核记录",
        ).one()
        assert batch.status == "已完成"
        assert batch.end_date == date(2026, 7, 24)
        assert batch.requires_repeat is True
        assert {value.name: value.value for value in batch.actual_parameters} == {
            "温度": "36.5", "孵育时间": "24",
        }
        assert record.content == "AI 整理后的观察"
        assert record.lifecycle_status == "修订"
        assert record.source_ai_message_id == message_id
        assert RecordRevision.query.filter_by(
            record_id=record_id, source_ai_message_id=message_id,
        ).one()
        assert created_record.batch_id == batch_id

    reverted = client.post(f"/assistant/proposals/{message_id}/revert")
    assert reverted.status_code == 200, reverted.get_json()
    with app.app_context():
        batch = db.session.get(ExperimentBatch, batch_id)
        record = db.session.get(ExperimentRecord, record_id)
        assert batch.status == "进行中"
        assert batch.end_date is None
        assert batch.summary == ""
        assert batch.requires_repeat is False
        assert [(value.name, value.value) for value in batch.actual_parameters] == [("温度", "37")]
        assert record.content == "原始观察"
        assert record.result == "待确认"
        assert record.lifecycle_status == "已定稿"
        assert record.finalized_at == finalized_at
        assert record.source_ai_message_id is None
        assert [(value.name, value.value) for value in record.parameters] == [("浓度", "5")]
        assert RecordRevision.query.filter_by(record_id=record_id).count() == 1
        assert ExperimentRecord.query.filter_by(batch_id=batch_id, content="新增复核记录").first() is None


def test_assistant_rejects_invalid_batch_values_and_effective_date_order(
        client, auth, app, monkeypatch):
    auth.register()
    experiment_id = create_experiment(client, app)
    batch_id = create_batch(client, app, experiment_id)
    with app.app_context():
        batch = db.session.get(ExperimentBatch, batch_id)
        batch.status = "进行中"
        batch.start_date = date(2026, 7, 24)
        record = ExperimentRecord(
            experiment_id=experiment_id, batch_id=batch_id,
            record_date=date(2026, 7, 24), content="已定稿记录",
            lifecycle_status="已定稿",
        )
        db.session.add(record)
        db.session.commit()
        record_id = record.id

    proposals = iter((
        {"action": "manage_batch", "changes": {"status": ""}},
        {"action": "manage_batch", "changes": {"requires_repeat": "perhaps"}},
        {"action": "manage_batch", "changes": {"end_date": "2026-07-23"}},
        {
            "action": "manage_batch", "changes": {},
            "record_operations": [{
                "operation": "create", "changes": {"record_date": "", "content": "无效日期记录"},
            }],
        },
        {
            "action": "manage_batch", "changes": {},
            "record_operations": [{
                "operation": "create", "changes": {"record_date": "2026-07-23", "content": "越界记录"},
            }],
        },
        {
            "action": "manage_batch", "changes": {},
            "record_operations": [{
                "operation": "update", "id": record_id, "changes": {"record_date": "2026-07-23"},
            }],
        },
        {
            "action": "manage_batch", "changes": {},
            "record_operations": [{"operation": "delete", "id": record_id, "changes": {}}],
        },
    ))
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="batch-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "请核对。", "proposal": next(proposals), "references": [],
        "web_requested": False, "web_used": False,
    })

    expected_errors = (
        "实验执行状态不合法。",
        "完成状态必须是 true 或 false。",
        "实际结束日期不能早于实际开始日期。",
        "记录日期格式不合法。",
        "记录日期不能早于实验执行开始日期 2026-07-24。请先调整执行日期。",
        "记录日期不能早于实验执行开始日期 2026-07-24。请先调整执行日期。",
        "已定稿过程记录不能通过 AI 删除，请保留原记录并通过修订说明更正。",
    )
    for index, expected_error in enumerate(expected_errors):
        response = client.post("/assistant/chat", data={
            "message": f"生成无效提案 {index}", "page_type": "batch", "page_id": batch_id,
        })
        message_id = response.get_json()["assistant_message"]["id"]
        applied = client.post(f"/assistant/proposals/{message_id}/apply")
        if applied.status_code == 409 and applied.get_json().get("requires_destructive_confirmation"):
            applied = client.post(f"/assistant/proposals/{message_id}/apply", data={
                "destructive_confirmation": "确认删除",
            })
        assert applied.status_code == 400, (index, applied.get_json())
        assert applied.get_json()["error"] == expected_error

    with app.app_context():
        record = db.session.get(ExperimentRecord, record_id)
        assert ExperimentRecord.query.filter_by(batch_id=batch_id).count() == 1
        assert record.record_date == date(2026, 7, 24)
        assert record.is_deleted is False
        assert db.session.get(ExperimentBatch, batch_id).end_date is None


def test_assistant_batch_record_delete_requires_confirmation_and_disables_undo(
        client, auth, app, monkeypatch):
    auth.register()
    experiment_id = create_experiment(client, app)
    batch_id = create_batch(client, app, experiment_id)
    with app.app_context():
        batch = db.session.get(ExperimentBatch, batch_id)
        batch.status = "进行中"
        record = ExperimentRecord(
            experiment_id=experiment_id, batch_id=batch_id,
            record_date=date(2026, 7, 24), content="待删除记录",
        )
        db.session.add(record)
        db.session.flush()
        attachment = ExperimentAttachment(
            experiment_id=experiment_id, record_id=record.id, original_name="result.csv",
            relative_path="result.csv", stored_path=f"test/{record.id}/result.csv",
            size_bytes=10, category="原始数据",
        )
        db.session.add(attachment)
        db.session.commit()
        record_id, attachment_id = record.id, attachment.id

    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="batch-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "删除提案待确认。",
        "proposal": {
            "action": "manage_batch", "changes": {},
            "record_operations": [{"operation": "delete", "id": record_id, "changes": {}}],
        },
        "references": [], "web_requested": False, "web_used": False,
    })
    proposed = client.post("/assistant/chat", data={
        "message": "删除这条记录", "page_type": "batch", "page_id": batch_id,
    }).get_json()
    message_id = proposed["assistant_message"]["id"]

    first_apply = client.post(f"/assistant/proposals/{message_id}/apply")
    assert first_apply.status_code == 409
    assert first_apply.get_json()["requires_destructive_confirmation"] is True
    applied = client.post(f"/assistant/proposals/{message_id}/apply", data={
        "destructive_confirmation": "确认删除",
    })
    assert applied.status_code == 200
    assert applied.get_json()["can_revert"] is False
    with app.app_context():
        assert db.session.get(ExperimentRecord, record_id).is_deleted is True
        assert db.session.get(ExperimentAttachment, attachment_id).is_deleted is True
    assert client.post(f"/assistant/proposals/{message_id}/revert").status_code == 409


def test_assistant_batch_undo_stops_after_new_record_children_are_added(
        client, auth, app, monkeypatch):
    auth.register()
    experiment_id = create_experiment(client, app)
    batch_id = create_batch(client, app, experiment_id)
    with app.app_context():
        batch = db.session.get(ExperimentBatch, batch_id)
        batch.status = "进行中"
        record = ExperimentRecord(
            experiment_id=experiment_id, batch_id=batch_id,
            record_date=date(2026, 7, 24), content="撤销保护记录",
        )
        db.session.add(record)
        db.session.commit()
        record_id = record.id

    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="batch-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "摘要修改待确认。",
        "proposal": {"action": "manage_batch", "changes": {"summary": "AI 摘要"}},
        "references": [], "web_requested": False, "web_used": False,
    })
    proposed = client.post("/assistant/chat", data={
        "message": "补充执行摘要", "page_type": "batch", "page_id": batch_id,
    }).get_json()
    message_id = proposed["assistant_message"]["id"]
    assert client.post(f"/assistant/proposals/{message_id}/apply").status_code == 200

    with app.app_context():
        db.session.add_all((
            RecordParameter(record_id=record_id, position=1, name="后续参数", value="1"),
            RecordRevision(
                record_id=record_id, user_id=1, reason="后续人工修订",
                before_json="{}", after_json="{}",
            ),
            ExperimentAttachment(
                experiment_id=experiment_id, record_id=record_id, original_name="later.txt",
                relative_path="later.txt", stored_path=f"test/{record_id}/later.txt",
                size_bytes=5, category="实验文档",
            ),
        ))
        db.session.commit()

    blocked = client.post(f"/assistant/proposals/{message_id}/revert")
    assert blocked.status_code == 409
    assert "停止撤销" in blocked.get_json()["error"]
    with app.app_context():
        assert db.session.get(ExperimentBatch, batch_id).summary == "AI 摘要"
