import json
from uuid import uuid4

from app import ai_service
from app.desktop.bridge import DesktopBridge
from app.desktop.native import NativeCapabilities
from app.services.desktop_workspace import DesktopApplicationService


def call(bridge, command, *, version=None, **payload):
    return bridge.invoke({
        "request_id": str(uuid4()), "command": command, "payload": payload, "expected_row_version": version,
    })


def test_assistant_carries_a_plan_from_chat_into_the_saved_record(app, monkeypatch):
    bridge = DesktopBridge(DesktopApplicationService(app), object(), {})
    project = call(bridge, "project.create", title="色卡演示")["data"]
    assert call(bridge, "settings.save", section="api", url="https://api.example.test/v1",
                model="mock-chat", api_key="synthetic", enabled=True)["ok"]
    plan = {"design": "对照蓝色与绿色色卡。", "objective": "核对颜色标签。"}
    draft = {"kind": "lab_record", "title": "色卡核对", "project_title": project["title"], "plan": plan}
    sent = []

    def chat(messages, system_prompt, config):
        sent.append(messages)
        if len(sent) == 2:
            historical = json.loads(messages[-2]["content"])["proposal"]["create_draft"]
            assert historical["plan"] == plan
        proposal = json.dumps({"create_draft": {
            **draft,
            "plan": {**plan, "actual_result": "不可写入"},
            "actual_result": "不可写入",
        }}, ensure_ascii=False)
        return ai_service._assistant_result('{"reply"："已整理计划，请核对。"，"proposal":' + proposal + "}")

    monkeypatch.setattr(ai_service, "chat_with_assistant", chat)
    first = call(bridge, "ai.propose", target_type="general", prompt="整理成色卡演示的实验草稿")
    assert first["ok"]
    conversation_id = first["data"]["conversation_id"]
    assert first["data"]["reply"] == "已整理计划，请核对。"
    assert first["data"]["create_draft"] == {**draft, "project_id": None}
    assert call(bridge, "record.list")["data"] == []
    followup = call(bridge, "ai.propose", target_type="general", conversation_id=conversation_id, prompt="继续填写")
    assert followup["ok"]
    saved_draft = call(bridge, "ai.conversation.get", id=conversation_id)["data"]["messages"][-1]["create_draft"]
    assert saved_draft["plan"] == plan

    created = call(bridge, "record.create", project_id=project["id"], title=saved_draft["title"],
                   **saved_draft["plan"], actual_result="不可写入")
    assert created["ok"]
    record = call(bridge, "record.get", id=created["data"]["id"])["data"]
    assert {field: record[field] for field in plan} == plan
    assert record["status"] == "draft" and record["experiment_date"] is None and record["actual_result"] == ""


def test_protocol_import_and_management_reuse_workspace_notes(app, tmp_path):
    native = NativeCapabilities(tmp_path)
    bridge = DesktopBridge(DesktopApplicationService(app), native, {})
    project = call(bridge, "project.create", title="色卡演示")["data"]
    sample = tmp_path / "色卡检查.md"
    sample.write_text("# 色卡检查\n\n记录颜色标签。", encoding="utf-8-sig")
    rejected = call(bridge, "note.protocol.read", path=str(sample))
    assert not rejected["ok"] and rejected["error"]["code"] == "invalid_native_request"
    native._remember([str(sample)])

    imported = call(bridge, "note.protocol.read", path=str(sample))
    assert imported["data"] == {"title": "色卡检查", "body": "# 色卡检查\n\n记录颜色标签。"}
    assert call(bridge, "note.list", kind="experiment_guide")["data"] == []
    assert call(bridge, "note.save", title="普通笔记", kind="general")["ok"]
    saved = call(bridge, "note.save", kind="experiment_guide", project_id=project["id"], **imported["data"])["data"]
    edited = call(bridge, "note.save", id=saved["id"], version=saved["row_version"], kind="experiment_guide",
                  project_id=project["id"], title=saved["title"], body="复核标签及示例颜色")["data"]
    results = call(bridge, "note.list", kind="experiment_guide", project_id=project["id"], search="复核标签")["data"]
    assert [item["id"] for item in results] == [edited["id"]]
    assert call(bridge, "note.get", id=edited["id"])["data"]["body"] == "复核标签及示例颜色"
    assert call(bridge, "note.bulk", ids=[edited["id"]], action="project", value=None)["ok"]
    assert call(bridge, "note.list", kind="experiment_guide", project_id=project["id"])["data"] == []
    assert call(bridge, "note.list", kind="experiment_guide", project_id="unclassified")["data"][0]["id"] == edited["id"]
    assert call(bridge, "note.bulk", ids=[edited["id"]], action="trash")["ok"]
    assert call(bridge, "note.list", kind="experiment_guide")["data"] == []
