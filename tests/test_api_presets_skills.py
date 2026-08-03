import json

from app import db
from app.models import ApiPreset, Experiment, ExperimentBatch, PresentationSkill, User


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


def test_api_presets_support_filtered_bulk_edit_and_pagination(client, auth, app):
    auth.register()
    with app.app_context():
        user_id = User.query.one().id
        for index in range(9):
            db.session.add(ApiPreset(
                user_id=user_id, name=f"分页预设 {index + 1:02d}",
                api_url=f"https://api-{index + 1}.example.test/v1",
                text_model=f"model-{index + 1}",
                is_enabled=True, sensitive_warning_enabled=True,
            ))
        db.session.add(ApiPreset(
            user_id=user_id, name="保留预设", api_url="https://keep.example.test/v1",
            text_model="keep-model", is_enabled=True, sensitive_warning_enabled=True,
        ))
        db.session.commit()
        first_id = ApiPreset.query.filter_by(name="分页预设 01").one().id
        last_id = ApiPreset.query.filter_by(name="分页预设 09").one().id

    body = client.get("/settings/api?page=2&per_page=8").get_data(as_text=True)
    assert f'name="preset_ids" value="{first_id}"' in body
    assert f'name="preset_ids" value="{last_id}"' not in body
    assert "第 2 / 2 页" in body

    assert client.post("/settings/api/bulk", data={
        "selection_scope": "all", "q": "分页预设 0", "action": "update",
        "bulk_enabled": "disabled", "bulk_warning": "disabled",
    }).status_code == 302
    with app.app_context():
        for preset in ApiPreset.query.all():
            if preset.name.startswith("分页预设"):
                assert preset.is_enabled is False
                assert preset.sensitive_warning_enabled is False
            elif preset.name == "保留预设":
                assert preset.is_enabled is True
                assert preset.sensitive_warning_enabled is True


def test_presentation_skill_editor_is_reachable_from_the_weekly_report_page(client, auth, app):
    """Every skill route needs a UI entry point, or the feature is unusable."""
    auth.register()
    page = client.get("/reports/presentation")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "/reports/presentation/skills" in body, "缺少创建 Skill 的表单入口"
    assert "创建自己的 PPT Skill" in body
    assert 'name="slides"' in body and 'name="instructions"' in body

    saved = client.post("/reports/presentation/skills", data={
        "name": "可达性检查", "description": "验证入口",
        "theme": "evidence", "instructions": "说明。",
        "slides": "封面\n结论",
    })
    assert saved.status_code == 302
    with app.app_context():
        skill_id = PresentationSkill.query.one().id

    listing = client.get("/reports/presentation").get_data(as_text=True)
    assert "可达性检查" in listing
    assert f"/reports/presentation/skills/{skill_id}/delete" in listing, "缺少删除入口"

    removed = client.post(f"/reports/presentation/skills/{skill_id}/delete")
    assert removed.status_code == 302
    assert "可达性检查" not in client.get("/reports/presentation").get_data(as_text=True)


def test_custom_presentation_skills_support_filtered_bulk_edit_and_pagination(client, auth, app):
    auth.register()
    for index in range(9):
        client.post("/reports/presentation/skills", data={
            "name": f"分页 Skill {index + 1:02d}",
            "description": "筛选目标" if index < 2 else "其他用途",
            "theme": "evidence", "instructions": "原叙事说明",
            "slides": "封面\n结论",
        })
    with app.app_context():
        matching_ids = {
            item.id for item in PresentationSkill.query.filter(
                PresentationSkill.description == "筛选目标"
            ).all()
        }
        first_skill_id = PresentationSkill.query.filter_by(name="分页 Skill 01").one().id
        last_skill_id = PresentationSkill.query.filter_by(name="分页 Skill 09").one().id

    body = client.get(
        "/reports/presentation?skill_page=2&skill_per_page=8#custom-skills"
    ).get_data(as_text=True)
    assert f'name="skill_ids" value="{first_skill_id}"' in body
    assert f'name="skill_ids" value="{last_skill_id}"' not in body
    assert "第 2 / 2 页" in body
    assert "选择当前筛选全部 9 个" in body

    response = client.post("/reports/presentation/skills/bulk", data={
        "selection_scope": "all", "skill_q": "筛选目标", "action": "update",
        "bulk_enabled": "disabled", "bulk_theme": "review",
        "description_mode": "append", "description": "批量复核",
        "instruction_mode": "keep",
    })
    assert response.status_code == 302
    with app.app_context():
        for skill in PresentationSkill.query.all():
            if skill.id in matching_ids:
                assert skill.is_enabled is False
                assert skill.theme == "review"
                assert skill.description.endswith("批量复核")
            else:
                assert skill.is_enabled is True
                assert skill.theme == "evidence"


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
