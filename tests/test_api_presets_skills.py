import json

from app import db
from app.models import ApiPreset, Experiment, ExperimentBatch, PresentationSkill


def _start_execution(client, app, experiment_id, batch_code="BATCH-01"):
    response = client.post(f"/experiments/{experiment_id}/batches", data={
        "batch_code": batch_code,
    })
    assert response.status_code == 302
    with app.app_context():
        return ExperimentBatch.query.filter_by(
            experiment_id=experiment_id, batch_code=batch_code,
        ).one().id


def test_api_presets_encrypt_keys_switch_and_restore_warning(client, auth, app):
    auth.register()
    response = client.post("/settings/api", data={
        "action": "preset_save", "preset_name": "主力文本模型",
        "preset_api_url": "https://api.example.test/v1", "preset_api_key": "secret-one",
        "text_model": "text-model",
        "preset_enabled": "1", "sensitive_warning_enabled": "1",
    })
    assert response.status_code == 302
    client.post("/settings/api", data={
        "action": "preset_save", "preset_name": "本地备用",
        "preset_api_url": "http://127.0.0.1:11434/v1", "text_model": "local-model",
        "preset_enabled": "1",
    })
    with app.app_context():
        presets = ApiPreset.query.order_by(ApiPreset.id).all()
        assert len(presets) == 2
        assert "secret-one" not in presets[0].encrypted_api_key
        first_id, second_id = presets[0].id, presets[1].id
        assert presets[0].is_default is True

    client.post("/settings/api", data={"action": "preset_activate", "preset_id": second_id})
    with app.app_context():
        assert db.session.get(ApiPreset, first_id).is_default is False
        second = db.session.get(ApiPreset, second_id)
        assert second.is_default is True
        assert second.sensitive_warning_enabled is True

    client.post("/settings/api", data={
        "action": "preset_save", "preset_id": second_id, "preset_name": "本地备用",
        "preset_api_url": "http://127.0.0.1:11434/v1", "text_model": "local-model",
        "preset_enabled": "1",
    })
    preview = client.post("/assistant/context-preview", data={"message": "普通总结"}).get_json()
    assert preview["provider"]["model"] == "local-model"
    assert preview["requires_confirmation"] is False

    page = client.get("/settings/api")
    assert "单连接兼容配置".encode() not in page.data
    assert "视觉模型".encode() not in page.data
    assert "嵌入模型".encode() not in page.data
    assert "图像模型".encode() not in page.data
    assert b'name="vision_model"' not in page.data
    assert b'name="embedding_model"' not in page.data
    assert b'name="image_model"' not in page.data
    assert "拉取模型".encode() in page.data


def test_discovered_model_capabilities_persist_after_saving_preset(client, auth, app, monkeypatch):
    auth.register()
    api_url = "http://127.0.0.1:1234/v1"
    discovered_model = {
        "id": "gpt-5-lab",
        "owned_by": "local-lab",
        "capabilities": {
            "vision": {"supported": False, "status": "declared"},
            "reasoning": {"supported": True, "status": "declared"},
            "web_search": {"supported": True, "status": "declared"},
            "tools": {"supported": False, "status": "declared"},
        },
    }
    monkeypatch.setattr("app.main.discover_models", lambda _config: [discovered_model])

    discovery = client.post("/settings/api/models", json={"api_url": api_url})
    assert discovery.status_code == 200
    selected = discovery.get_json()["models"][0]
    snapshot = {
        "model_id": selected["id"],
        "api_url": api_url,
        "capabilities": selected["capabilities"],
    }
    saved = client.post("/settings/api", data={
        "action": "preset_save",
        "preset_name": "能力证据预设",
        "preset_api_url": api_url,
        "text_model": selected["id"],
        "model_capabilities_json": json.dumps(snapshot),
        "preset_enabled": "1",
    })
    assert saved.status_code == 302

    with app.app_context():
        persisted = json.loads(ApiPreset.query.one().model_capabilities_json)
        assert persisted == snapshot

    refreshed = client.get("/settings/api")
    assert refreshed.status_code == 200
    assert "视觉输入：不支持（接口声明）".encode() in refreshed.data
    assert "推理：支持（接口声明）".encode() in refreshed.data
    assert "联网搜索：支持（接口声明）".encode() in refreshed.data
    assert "工具调用：不支持（接口声明）".encode() in refreshed.data
    assert "视觉输入：支持（名称推测）".encode() not in refreshed.data
    assert client.get("/assistant/state").get_json()["api"]["web_capable"] is True


def test_disabled_default_preset_is_not_presented_as_current(client, auth, app):
    auth.register()
    client.post("/settings/api", data={
        "action": "preset_save", "preset_name": "暂时停用",
        "preset_api_url": "https://api.example.test/v1", "text_model": "text-model",
        "preset_enabled": "1",
    })
    with app.app_context():
        preset_id = ApiPreset.query.one().id
    client.post("/settings/api", data={
        "action": "preset_save", "preset_id": preset_id, "preset_name": "暂时停用",
        "preset_api_url": "https://api.example.test/v1", "text_model": "text-model",
    })

    page = client.get("/settings/api")
    assert "尚未选择预设".encode() in page.data
    assert "已停用".encode() in page.data
    assert "当前使用".encode() not in page.data
    assert client.get("/assistant/state").get_json()["api"]["enabled"] is False


def test_custom_presentation_skill_can_preview_evidence(client, auth, app):
    auth.register()
    client.post("/experiments", data={"title": "Skill 实验", "code": "SK-01"})
    with app.app_context():
        experiment_id = Experiment.query.one().id
    batch_id = _start_execution(client, app, experiment_id)
    client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id,
        "record_date": "2026-07-23", "content": "目标蛋白表达下降", "result": "成功",
    })
    saved = client.post("/reports/presentation/skills", data={
        "name": "课题组组会", "description": "证据优先组会",
        "theme": "review", "instructions": "先展示证据，再区分事实和推断。",
        "slides": "研究问题\n实验进展\n结果证据\n限制\n下一步计划",
    })
    assert saved.status_code == 302
    with app.app_context():
        skill = PresentationSkill.query.one()
        skill_id = skill.id
        assert "结果证据" in skill.slide_schema_json

    response = client.post("/reports/presentation", data={
        "action": "preview", "title": "组会汇报",
        "start_date": "2026-07-20", "end_date": "2026-07-26",
        "experiment_ids": [str(experiment_id)], "presentation_skill": f"user:{skill_id}",
        "include_images": "1",
    })
    assert response.status_code == 200
    assert "导出前预览".encode() in response.data
    assert "课题组组会".encode() in response.data
    assert "目标蛋白表达下降".encode() in response.data
    assert "内置已审核".encode() in response.data
