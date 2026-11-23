import json
from uuid import uuid4

from app import ai_service
from app.desktop.bridge import DesktopBridge
from app.services.desktop_workspace import DesktopApplicationService


def assistant(app, monkeypatch, reply):
    bridge = DesktopBridge(DesktopApplicationService(app), object(), {})
    sent = []

    def invoke(command, **payload):
        return bridge.invoke({"request_id": str(uuid4()), "command": command, "payload": payload})

    def chat(messages, system_prompt, config):
        sent.append(messages)
        return ai_service._assistant_result(json.dumps(reply))

    monkeypatch.setattr(ai_service, "chat_with_assistant", chat)
    assert invoke("settings.save", section="api", url="https://api.example.test/v1",
                  model="mock-chat", api_key="synthetic", enabled=True)["ok"]
    return invoke, sent


def test_general_chat_needs_no_project_and_excludes_workspace_snapshot(app, monkeypatch):
    invoke, sent = assistant(app, monkeypatch, {"reply": "你好", "proposal": {"title": "忽略"}})
    first = invoke("ai.propose", target_type="general", prompt="你好", source_snapshot={"hidden": "ignore"})
    assert first["ok"]
    chat = first["data"]
    assert chat["id"] is None and chat["proposal"] == {}
    assert sent[0] == [{"role": "user", "content": "你好"}]
    again = invoke("ai.propose", target_type="general", conversation_id=chat["conversation_id"], prompt="继续")
    assert again["ok"] and [message["role"] for message in sent[1]] == ["user", "assistant", "user"]

    project = invoke("project.create", title="项目甲")["data"]
    denied = invoke("ai.propose", target_type="project", target_id=project["id"],
                    conversation_id=chat["conversation_id"], prompt="跨范围")
    assert not denied["ok"] and len(sent) == 2


def test_create_drafts_reopen_without_writing_or_changing_existing_project(app, monkeypatch):
    reply = {"reply": "请核对草稿", "proposal": {"create_draft": {"kind": "project", "title": "新研究"}}}
    invoke, _ = assistant(app, monkeypatch, reply)
    result = invoke("ai.propose", target_type="general", prompt="新建新研究项目")["data"]
    assert result["create_draft"] == {"kind": "project", "title": "新研究"}
    assert invoke("project.list")["data"] == []

    project = invoke("project.create", title=result["create_draft"]["title"])["data"]
    reply["proposal"] = {
        "title": "这个字段不可应用",
        "create_draft": {"kind": "lab_record", "title": "第一次记录", "project_id": 999, "actual_result": "忽略"},
    }
    result = invoke("ai.propose", target_type="project", target_id=project["id"], prompt="新建第一次记录")["data"]
    draft = {"kind": "lab_record", "title": "第一次记录", "project_id": project["id"]}
    assert result["create_draft"] == draft and result["proposal"] == {} and result["id"] is None
    messages = invoke("ai.conversation.get", id=result["conversation_id"])["data"]["messages"]
    assert messages[-1]["create_draft"] == draft
    assert invoke("record.list")["data"] == []
    assert invoke("project.list")["data"][0]["title"] == "新研究"
    assert invoke("record.create", project_id=draft["project_id"], title=draft["title"])["ok"]
