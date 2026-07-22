import io
from datetime import date
from pathlib import Path

from app import db
from app.ai_service import AIConfig
from app.models import (
    AIMessage, Experiment, ExperimentAttachment, ExperimentParameter, ExperimentRecord,
    ExperimentSample, ExperimentStep, RecordParameter, Sample,
)


def _experiment(client, app, title="批量管理实验"):
    client.post("/experiments", data={"title": title, "status": "进行中", "owner": "研究员"})
    with app.app_context():
        return Experiment.query.filter_by(title=title).one().id


def test_step_bulk_update_delete_and_scope_protection(client, auth, app):
    auth.register()
    experiment_id = _experiment(client, app)
    for index in range(2):
        client.post(f"/experiments/{experiment_id}/steps", data={
            "title": f"步骤 {index + 1}", "operator": "原执行人",
            "planned_date": f"2026-07-{22 + index}", "description": "原说明",
        })
    other_id = _experiment(client, app, "另一个实验")
    client.post(f"/experiments/{other_id}/steps", data={"title": "其他步骤"})
    with app.app_context():
        selected_ids = [value.id for value in ExperimentStep.query.filter_by(experiment_id=experiment_id).all()]
        other_step_id = ExperimentStep.query.filter_by(experiment_id=other_id).one().id

    response = client.post(f"/experiments/{experiment_id}/steps/bulk", data={
        "step_ids": [str(value) for value in selected_ids], "action": "update",
        "status_mode": "complete", "operator_mode": "replace", "operator": "统一执行人",
        "date_mode": "shift", "shift_days": "2", "description_mode": "append",
        "description": "批量复核",
    })
    assert response.status_code == 302
    with app.app_context():
        steps = ExperimentStep.query.filter_by(experiment_id=experiment_id).order_by(ExperimentStep.position).all()
        assert all(value.is_done and value.completed_date == date.today() for value in steps)
        assert {value.operator for value in steps} == {"统一执行人"}
        assert [value.planned_date.isoformat() for value in steps] == ["2026-07-24", "2026-07-25"]
        assert all(value.description.endswith("批量复核") for value in steps)

    assert client.post(f"/experiments/{experiment_id}/steps/bulk", data={
        "step_ids": [str(other_step_id)], "action": "delete",
    }).status_code == 404
    assert client.post(f"/experiments/{experiment_id}/steps/bulk", data={
        "step_ids": [str(selected_ids[0])], "action": "delete",
    }).status_code == 302
    with app.app_context():
        remaining = ExperimentStep.query.filter_by(experiment_id=experiment_id).one()
        assert remaining.position == 1


def test_parameter_sample_and_record_bulk_management(client, auth, app):
    auth.register()
    experiment_id = _experiment(client, app)
    client.post(f"/experiments/{experiment_id}/parameters", data={
        "plan_parameter_name": ["浓度", "时间"], "plan_parameter_value": ["5", "24"],
        "plan_parameter_unit": ["uM", "h"], "plan_parameter_notes": ["原值", "原值"],
    })
    client.post("/samples", data={"sample_code": "S-BULK", "sample_type": "细胞"})
    with app.app_context():
        sample_id = Sample.query.one().id
        parameter_ids = [value.id for value in ExperimentParameter.query.all()]
    client.post(f"/experiments/{experiment_id}/samples", data={
        "sample_id": str(sample_id), "role": "处理组", "amount_used": "1 管", "notes": "原备注",
    })
    for day in (21, 22):
        client.post(f"/experiments/{experiment_id}/records", data={
            "record_date": f"2026-07-{day}", "operator": "原人员", "content": f"记录 {day}",
            "result": "待确认", "remark": "原结论",
        })
    with app.app_context():
        usage_id = ExperimentSample.query.one().id
        record_ids = [value.id for value in ExperimentRecord.query.all()]

    assert client.post(f"/experiments/{experiment_id}/parameters/bulk", data={
        "parameter_ids": [str(value) for value in parameter_ids], "action": "update",
        "unit_mode": "replace", "unit": "统一单位", "notes_mode": "append", "notes": "已校准",
    }).status_code == 302
    assert client.post(f"/experiments/{experiment_id}/samples/bulk", data={
        "sample_usage_ids": [str(usage_id)], "action": "update",
        "role_mode": "replace", "role": "对照组", "amount_mode": "replace", "amount_used": "2 管",
        "notes_mode": "append", "notes": "复核后",
    }).status_code == 302
    assert client.post(f"/experiments/{experiment_id}/records/bulk", data={
        "record_ids": [str(value) for value in record_ids], "action": "update", "result": "成功",
        "operator_mode": "replace", "operator": "统一人员", "shift_days": "1",
        "remark_mode": "append", "remark": "已批量复核",
    }).status_code == 302
    with app.app_context():
        assert {value.unit for value in ExperimentParameter.query.all()} == {"统一单位"}
        usage = ExperimentSample.query.one()
        assert (usage.role, usage.amount_used) == ("对照组", "2 管")
        records = ExperimentRecord.query.order_by(ExperimentRecord.record_date).all()
        assert [value.record_date.isoformat() for value in records] == ["2026-07-22", "2026-07-23"]
        assert {value.result for value in records} == {"成功"}
        assert {value.operator for value in records} == {"统一人员"}


def test_record_bulk_delete_removes_local_attachments(client, auth, app):
    auth.register()
    experiment_id = _experiment(client, app)
    client.post(f"/experiments/{experiment_id}/records", data={"content": "含附件记录"})
    with app.app_context():
        record_id = ExperimentRecord.query.one().id
    client.post(f"/records/{record_id}/attachments", data={
        "files": (io.BytesIO(b"private-data"), "raw.bin"),
    }, content_type="multipart/form-data")
    with app.app_context():
        attachment = ExperimentAttachment.query.one()
        stored_path = Path(app.config["ATTACHMENT_UPLOAD_DIR"]) / attachment.stored_path
        assert stored_path.is_file()
    assert client.post(f"/experiments/{experiment_id}/records/bulk", data={
        "record_ids": [str(record_id)], "action": "delete",
    }).status_code == 302
    assert not stored_path.exists()
    with app.app_context():
        assert ExperimentRecord.query.count() == 0
        assert ExperimentAttachment.query.count() == 0


def test_experiment_page_exposes_bulk_management_controls(client, auth, app):
    auth.register()
    experiment_id = _experiment(client, app)
    response = client.get(f"/experiments/{experiment_id}")
    assert response.status_code == 200
    for form_id in ("step-bulk-form", "sample-bulk-form", "parameter-bulk-form", "record-bulk-form"):
        assert f'id="{form_id}"'.encode() in response.data
    assert "批量管理步骤".encode() in response.data


def test_ai_can_manage_experiment_resources_in_one_confirmed_proposal(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = _experiment(client, app)
    client.post(f"/experiments/{experiment_id}/steps", data={"title": "旧步骤", "description": "旧说明"})
    client.post(f"/experiments/{experiment_id}/parameters", data={
        "plan_parameter_name": "浓度", "plan_parameter_value": "5", "plan_parameter_unit": "uM",
    })
    client.post(f"/experiments/{experiment_id}/records", data={"content": "旧记录", "result": "待确认"})
    with app.app_context():
        step_id = ExperimentStep.query.one().id
        parameter_id = ExperimentParameter.query.one().id
        record_id = ExperimentRecord.query.one().id

    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="manager-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "已生成页面管理提案。",
        "proposal": {
            "action": "manage_experiment",
            "changes": {"objective": "AI 整理后的目的", "batch_code": "B-2026"},
            "step_operations": [
                {"operation": "update", "id": step_id, "changes": {"description": "新说明", "is_done": True}},
                {"operation": "create", "changes": {"title": "新增复核步骤", "operator": "研究员"}},
            ],
            "parameter_operations": [
                {"operation": "update", "id": parameter_id, "changes": {"unit": "μM", "notes": "终浓度"}},
            ],
            "record_operations": [
                {"operation": "update", "id": record_id, "changes": {"result": "成功", "remark": "AI 整理，人工确认"}},
                {"operation": "create", "changes": {"content": "新增复核记录", "result": "待确认"}},
            ],
        },
        "references": [], "web_requested": False, "web_used": False,
    })
    response = client.post("/assistant/chat", data={
        "message": "整理当前实验全部内容", "page_type": "experiment", "page_id": str(experiment_id),
    })
    assert response.status_code == 200
    message = response.get_json()["assistant_message"]
    assert message["proposal"]["action"] == "manage_experiment"
    assert len(message["proposal"]["diff"]) >= 6
    assert client.post(f"/assistant/proposals/{message['id']}/apply").status_code == 200
    with app.app_context():
        experiment = db.session.get(Experiment, experiment_id)
        assert experiment.objective == "AI 整理后的目的"
        assert experiment.batch_code == "B-2026"
        assert len(experiment.steps) == 2
        assert db.session.get(ExperimentStep, step_id).is_done is True
        assert db.session.get(ExperimentParameter, parameter_id).unit == "μM"
        assert db.session.get(ExperimentRecord, record_id).result == "成功"
        assert ExperimentRecord.query.filter_by(content="新增复核记录").one()
        assert db.session.get(AIMessage, message["id"]).applied_at is not None


def test_ai_record_management_updates_parameters_and_attachment_metadata(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = _experiment(client, app)
    client.post(f"/experiments/{experiment_id}/records", data={
        "content": "原始过程", "record_parameter_name": "曝光", "record_parameter_value": "10",
    })
    with app.app_context():
        record_id = ExperimentRecord.query.one().id
        parameter_id = RecordParameter.query.one().id
    client.post(f"/records/{record_id}/attachments", data={
        "files": (io.BytesIO(b"result"), "result.csv"),
    }, content_type="multipart/form-data")
    with app.app_context():
        attachment_id = ExperimentAttachment.query.one().id

    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="manager-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "已整理记录。", "proposal": {
            "action": "manage_record", "changes": {"remark": "需要人工复核"},
            "parameter_operations": [
                {"operation": "update", "id": parameter_id, "changes": {"unit": "s", "notes": "未饱和"}},
                {"operation": "create", "changes": {"name": "重复次数", "value": "3"}},
            ],
            "attachment_operations": [
                {"operation": "update", "id": attachment_id, "changes": {
                    "category": "统计结果", "folder": "Figure 1", "tags": "主图", "description": "用于周报",
                }},
            ],
        }, "references": [], "web_requested": False, "web_used": False,
    })
    response = client.post("/assistant/chat", data={
        "message": "整理当前记录参数和附件", "page_type": "record", "page_id": str(record_id),
    })
    message_id = response.get_json()["assistant_message"]["id"]
    assert client.post(f"/assistant/proposals/{message_id}/apply").status_code == 200
    with app.app_context():
        record = db.session.get(ExperimentRecord, record_id)
        attachment = db.session.get(ExperimentAttachment, attachment_id)
        assert record.remark == "需要人工复核"
        assert len(record.parameters) == 2
        assert db.session.get(RecordParameter, parameter_id).unit == "s"
        assert attachment.category == "统计结果"
        assert attachment.relative_path == "Figure 1/result.csv"
        assert attachment.tags == "主图"


def test_ai_management_rejects_stale_resource_changes(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = _experiment(client, app)
    client.post(f"/experiments/{experiment_id}/steps", data={"title": "待修改步骤", "description": "版本一"})
    with app.app_context():
        step_id = ExperimentStep.query.one().id
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="manager-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "已生成提案。", "proposal": {
            "action": "manage_experiment", "changes": {},
            "step_operations": [{"operation": "update", "id": step_id, "changes": {"description": "AI 版本"}}],
        }, "references": [], "web_requested": False, "web_used": False,
    })
    response = client.post("/assistant/chat", data={
        "message": "修改步骤", "page_type": "experiment", "page_id": str(experiment_id),
    })
    message_id = response.get_json()["assistant_message"]["id"]
    with app.app_context():
        db.session.get(ExperimentStep, step_id).description = "人工版本二"
        db.session.commit()
    applied = client.post(f"/assistant/proposals/{message_id}/apply")
    assert applied.status_code == 409
    with app.app_context():
        assert db.session.get(ExperimentStep, step_id).description == "人工版本二"
