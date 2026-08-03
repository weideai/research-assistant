import io
from datetime import date
from pathlib import Path

from app import db
from app.ai_service import AIConfig
from app.models import (
    AIMessage, BatchSample, BatchStep, Experiment, ExperimentAttachment, ExperimentBatch, ExperimentParameter, ExperimentRecord,
    ExperimentSample, ExperimentStep, RecordParameter, Sample, User, WeeklyReport,
    WeeklyReportUpdate,
)


def _experiment(client, app, title="批量管理实验"):
    client.post("/experiments", data={"title": title, "status": "进行中", "owner": "研究员"})
    with app.app_context():
        return Experiment.query.filter_by(title=title).one().id


def _batch(client, app, experiment_id):
    client.post(f"/experiments/{experiment_id}/batches", data={
        "batch_code": f"BULK-{experiment_id}",
    })
    with app.app_context():
        return ExperimentBatch.query.filter_by(experiment_id=experiment_id).one().id


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
        "operator_mode": "replace", "operator": "统一执行人",
        "date_mode": "shift", "shift_days": "2", "description_mode": "append",
        "description": "批量复核",
    })
    assert response.status_code == 302
    with app.app_context():
        steps = ExperimentStep.query.filter_by(experiment_id=experiment_id).order_by(ExperimentStep.position).all()
        assert all(not hasattr(value, "is_done") for value in steps)
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
    batch_id = _batch(client, app, experiment_id)
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
        client.post(f"/batches/{batch_id}/records", data={
            "batch_id": batch_id,
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
    assert client.post(f"/batches/{batch_id}/records/bulk", data={
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
    batch_id = _batch(client, app, experiment_id)
    client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id, "content": "含附件记录",
    })
    with app.app_context():
        record_id = ExperimentRecord.query.one().id
    client.post(f"/records/{record_id}/attachments", data={
        "files": (io.BytesIO(b"private-data"), "raw.bin"),
    }, content_type="multipart/form-data")
    with app.app_context():
        attachment = ExperimentAttachment.query.one()
        stored_path = Path(app.config["ATTACHMENT_UPLOAD_DIR"]) / attachment.stored_path
        assert stored_path.is_file()
    assert client.post(f"/batches/{batch_id}/records/bulk", data={
        "record_ids": [str(record_id)], "action": "delete",
    }).status_code == 302
    assert stored_path.exists()
    with app.app_context():
        record = ExperimentRecord.query.one()
        attachment = ExperimentAttachment.query.one()
        assert record.is_deleted is True
        assert attachment.is_deleted is True


def test_weekly_update_bulk_scope_filters_and_rejects_cross_report_ids(client, auth, app):
    auth.register()
    with app.app_context():
        user_id = User.query.one().id
        first_report = WeeklyReport(
            user_id=user_id, title="批量周报 A", original_name="a.pptx",
            report_date=date(2026, 7, 31),
        )
        second_report = WeeklyReport(
            user_id=user_id, title="批量周报 B", original_name="b.pptx",
            report_date=date(2026, 8, 1),
        )
        db.session.add_all((first_report, second_report))
        db.session.flush()
        matching = WeeklyReportUpdate(
            report_id=first_report.id, user_id=user_id, entry_date=date(2026, 7, 20),
            kind="反馈", status="待处理", content="筛选目标 A",
        )
        wrong_status = WeeklyReportUpdate(
            report_id=first_report.id, user_id=user_id, entry_date=date(2026, 7, 21),
            kind="反馈", status="已完成", content="筛选目标 B",
        )
        wrong_content = WeeklyReportUpdate(
            report_id=first_report.id, user_id=user_id, entry_date=date(2026, 7, 22),
            kind="反馈", status="待处理", content="不应修改",
        )
        foreign = WeeklyReportUpdate(
            report_id=second_report.id, user_id=user_id, entry_date=date(2026, 7, 23),
            kind="反馈", status="待处理", content="筛选目标 C",
        )
        db.session.add_all((matching, wrong_status, wrong_content, foreign))
        db.session.commit()
        first_report_id = first_report.id
        matching_id, wrong_status_id, wrong_content_id, foreign_id = (
            matching.id, wrong_status.id, wrong_content.id, foreign.id,
        )

    response = client.post(f"/reports/weekly/{first_report_id}/updates/bulk", data={
        "selection_scope": "all", "update_q": "筛选目标",
        "return_update_kind": "反馈", "return_update_status": "待处理",
        "action": "update", "bulk_update_kind": "修改日常",
        "bulk_update_status": "已完成", "date_mode": "shift", "shift_days": "2",
        "content_mode": "append", "content": "批量复核",
    })
    assert response.status_code == 302
    with app.app_context():
        matching = db.session.get(WeeklyReportUpdate, matching_id)
        assert (matching.kind, matching.status, matching.entry_date) == (
            "修改日常", "已完成", date(2026, 7, 22),
        )
        assert matching.content.endswith("批量复核")
        assert db.session.get(WeeklyReportUpdate, wrong_status_id).content == "筛选目标 B"
        assert db.session.get(WeeklyReportUpdate, wrong_content_id).status == "待处理"
        assert db.session.get(WeeklyReportUpdate, foreign_id).content == "筛选目标 C"

    assert client.post(f"/reports/weekly/{first_report_id}/updates/bulk", data={
        "update_ids": [str(wrong_status_id), str(foreign_id)], "action": "delete",
        "return_update_kind": "全部", "return_update_status": "全部",
    }).status_code == 404
    with app.app_context():
        assert db.session.get(WeeklyReportUpdate, wrong_status_id) is not None
        assert db.session.get(WeeklyReportUpdate, foreign_id) is not None

    assert client.post(f"/reports/weekly/{first_report_id}/updates/bulk", data={
        "update_ids": str(wrong_status_id), "action": "delete",
        "return_update_kind": "全部", "return_update_status": "全部",
    }).status_code == 302
    with app.app_context():
        assert db.session.get(WeeklyReportUpdate, wrong_status_id) is None
        assert db.session.get(WeeklyReportUpdate, foreign_id) is not None


def test_sample_trace_bulk_management_keeps_plan_and_actual_usage_separate(client, auth, app):
    auth.register()
    with app.app_context():
        user_id = User.query.one().id
        first_sample = Sample(user_id=user_id, sample_code="TRACE-A", status="可用")
        second_sample = Sample(user_id=user_id, sample_code="TRACE-B", status="可用")
        first_experiment = Experiment(user_id=user_id, title="筛选目标计划")
        second_experiment = Experiment(user_id=user_id, title="另一个计划")
        db.session.add_all((first_sample, second_sample, first_experiment, second_experiment))
        db.session.flush()
        first_batch = ExperimentBatch(experiment_id=first_experiment.id, batch_code="TRACE-RUN-A")
        second_batch = ExperimentBatch(experiment_id=second_experiment.id, batch_code="TRACE-RUN-B")
        db.session.add_all((first_batch, second_batch))
        db.session.flush()
        plan_usage = ExperimentSample(
            experiment_id=first_experiment.id, sample_id=first_sample.id,
            role="计划处理组", amount_used="1 管", notes="原计划",
        )
        foreign_plan_usage = ExperimentSample(
            experiment_id=second_experiment.id, sample_id=second_sample.id,
            role="其他计划", amount_used="1 管",
        )
        actual_usage = BatchSample(
            batch_id=first_batch.id, sample_id=first_sample.id,
            role="实际处理组", amount_used="0.5 管", notes="原记录",
        )
        foreign_actual_usage = BatchSample(
            batch_id=second_batch.id, sample_id=second_sample.id,
            role="其他实际使用", amount_used="1 管",
        )
        db.session.add_all((plan_usage, foreign_plan_usage, actual_usage, foreign_actual_usage))
        db.session.commit()
        sample_id = first_sample.id
        plan_usage_id, foreign_plan_id = plan_usage.id, foreign_plan_usage.id
        actual_usage_id, foreign_actual_id = actual_usage.id, foreign_actual_usage.id

    assert client.post(f"/samples/{sample_id}/plan-usages/bulk", data={
        "selection_scope": "all", "plan_usage_q": "筛选目标",
        "action": "update", "role_mode": "replace", "role": "统一计划用途",
        "amount_mode": "keep", "notes_mode": "append", "notes": "批量复核",
    }).status_code == 302
    with app.app_context():
        usage = db.session.get(ExperimentSample, plan_usage_id)
        assert usage.role == "统一计划用途"
        assert usage.notes.endswith("批量复核")
        assert db.session.get(BatchSample, actual_usage_id).role == "实际处理组"

    assert client.post(f"/samples/{sample_id}/plan-usages/bulk", data={
        "usage_ids": str(foreign_plan_id), "action": "delete",
    }).status_code == 404
    assert client.post(f"/samples/{sample_id}/batch-usages/bulk", data={
        "usage_ids": [str(actual_usage_id), str(foreign_actual_id)], "action": "delete",
    }).status_code == 404
    assert client.post(f"/samples/{sample_id}/batch-usages/bulk", data={
        "usage_ids": str(actual_usage_id), "action": "delete",
    }).status_code == 302
    with app.app_context():
        assert db.session.get(BatchSample, actual_usage_id) is None
        assert db.session.get(BatchSample, foreign_actual_id) is not None

def test_experiment_and_batch_pages_expose_scoped_bulk_management_controls(client, auth, app):
    auth.register()
    experiment_id = _experiment(client, app)
    client.post(f"/experiments/{experiment_id}/steps", data={"title": "方案阶段"})
    batch_id = _batch(client, app, experiment_id)
    client.post(f"/batches/{batch_id}/steps", data={"title": "本批次加样"})
    response = client.get(f"/experiments/{experiment_id}")
    assert response.status_code == 200
    for form_id in ("step-bulk-form", "sample-bulk-form", "parameter-bulk-form"):
        assert f'id="{form_id}"'.encode() in response.data
    assert "批量管理方案阶段".encode() in response.data
    batch_response = client.get(f"/batches/{batch_id}")
    assert batch_response.status_code == 200
    assert b'id="batch-step-bulk-form"' in batch_response.data
    assert "本批次实验步骤".encode() in batch_response.data
    assert b'id="batch-record-bulk-form"' in batch_response.data
    assert "过程记录时间线".encode() in batch_response.data


def test_ai_manages_plan_resources_without_crossing_into_execution_records(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = _experiment(client, app)
    batch_id = _batch(client, app, experiment_id)
    client.post(f"/experiments/{experiment_id}/steps", data={"title": "旧步骤", "description": "旧说明"})
    client.post(f"/experiments/{experiment_id}/parameters", data={
        "plan_parameter_name": "浓度", "plan_parameter_value": "5", "plan_parameter_unit": "uM",
    })
    client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id, "content": "旧记录", "result": "待确认",
    })
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
            "changes": {"objective": "AI 整理后的目的"},
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
    assert message["proposal"]["step_operations"][0]["changes"] == {"description": "新说明"}
    assert len(message["proposal"]["diff"]) >= 4
    assert client.post(f"/assistant/proposals/{message['id']}/apply").status_code == 200
    with app.app_context():
        experiment = db.session.get(Experiment, experiment_id)
        assert experiment.objective == "AI 整理后的目的"
        assert len(experiment.steps) == 2
        assert not hasattr(db.session.get(ExperimentStep, step_id), "is_done")
        assert db.session.get(ExperimentParameter, parameter_id).unit == "μM"
        assert db.session.get(ExperimentRecord, record_id).result == "待确认"
        assert ExperimentRecord.query.filter_by(content="新增复核记录", batch_id=batch_id).count() == 0
        assert db.session.get(AIMessage, message["id"]).applied_at is not None


def test_ai_manages_execution_step_status_without_mutating_plan(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = _experiment(client, app, "AI 执行步骤")
    client.post(f"/experiments/{experiment_id}/steps", data={
        "title": "计划加药", "description": "计划定义",
    })
    batch_id = _batch(client, app, experiment_id)
    client.post(f"/batches/{batch_id}/steps", data={
        "title": "本批次加药", "description": "实际执行定义",
    })
    with app.app_context():
        plan_step = ExperimentStep.query.filter_by(experiment_id=experiment_id).one()
        batch_step = BatchStep.query.filter_by(batch_id=batch_id).one()
        plan_step_id, batch_step_id = plan_step.id, batch_step.id

    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="manager-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "已生成执行步骤更新提案。",
        "proposal": {
            "action": "manage_batch", "changes": {},
            "step_operations": [{
                "operation": "update", "id": batch_step_id,
                "changes": {"is_done": True, "completed_date": "2026-07-24"},
            }],
        },
        "references": [], "web_requested": False, "web_used": False,
    })
    response = client.post("/assistant/chat", data={
        "message": "把本次加药步骤标记完成",
        "page_type": "batch", "page_id": str(batch_id),
    })
    assert response.status_code == 200
    message = response.get_json()["assistant_message"]
    assert message["proposal"]["action"] == "manage_batch"
    assert client.post(f"/assistant/proposals/{message['id']}/apply").status_code == 200
    with app.app_context():
        plan_step = db.session.get(ExperimentStep, plan_step_id)
        execution_step = db.session.get(BatchStep, batch_step_id)
        assert not hasattr(plan_step, "is_done")
        assert plan_step.title == "计划加药"
        assert execution_step.title == "本批次加药"
        assert execution_step.is_done is True
        assert execution_step.completed_date.isoformat() == "2026-07-24"


def test_ai_record_management_updates_parameters_and_attachment_metadata(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = _experiment(client, app)
    batch_id = _batch(client, app, experiment_id)
    client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id, "content": "原始过程",
        "record_parameter_name": "曝光", "record_parameter_value": "10",
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


def test_ai_delete_requires_second_confirmation_and_moves_record_to_recycle_bin(client, auth, app, monkeypatch):
    auth.register()
    experiment_id = _experiment(client, app)
    batch_id = _batch(client, app, experiment_id)
    client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id, "content": "待删除记录",
    })
    with app.app_context():
        record_id = ExperimentRecord.query.one().id
    monkeypatch.setattr("app.main.current_ai_config", lambda: AIConfig(
        api_url="https://api.example.test/v1", api_key="test", model="manager-model", enabled=True,
    ))
    monkeypatch.setattr("app.main.chat_with_assistant", lambda *_args, **_kwargs: {
        "reply": "已生成删除提案。", "proposal": {
            "action": "manage_batch", "changes": {},
            "record_operations": [{"operation": "delete", "id": record_id, "changes": {}}],
        }, "references": [], "web_requested": False, "web_used": False,
    })
    response = client.post("/assistant/chat", data={
        "message": "删除这条记录", "page_type": "batch", "page_id": str(batch_id),
    })
    message_id = response.get_json()["assistant_message"]["id"]
    blocked = client.post(f"/assistant/proposals/{message_id}/apply")
    assert blocked.status_code == 409
    assert blocked.get_json()["requires_destructive_confirmation"] is True
    with app.app_context():
        assert db.session.get(ExperimentRecord, record_id).is_deleted is False

    applied = client.post(f"/assistant/proposals/{message_id}/apply", data={
        "destructive_confirmation": "确认删除",
    })
    assert applied.status_code == 200
    with app.app_context():
        assert db.session.get(ExperimentRecord, record_id).is_deleted is True
