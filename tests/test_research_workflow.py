import io
import sqlite3
import zipfile

from app import create_app, db
from app.models import (
    Experiment, ExperimentAttachment, ExperimentBatch, ExperimentParameter, ExperimentSample,
    ExperimentTemplate, ExperimentTemplateParameter, RecordParameter,
    RecordTemplate, RecordTemplateParameter, Sample, User,
)


def _start_execution(client, app, experiment_id, batch_code="BATCH-01"):
    response = client.post(f"/experiments/{experiment_id}/batches", data={
        "batch_code": batch_code,
    })
    assert response.status_code == 302
    with app.app_context():
        return ExperimentBatch.query.filter_by(
            experiment_id=experiment_id, batch_code=batch_code,
        ).one().id


def test_step_template_only_reuses_experiment_steps(client, auth, app):
    auth.register()
    client.post("/samples", data={"sample_code": "S-001", "sample_type": "细胞", "status": "可用"})
    client.post("/experiments", data={
        "title": "WB 模板来源", "code": "EXP-001",
        "owner": "研究员", "status": "进行中", "start_date": "2026-07-21",
    })
    with app.app_context():
        experiment = Experiment.query.one()
        sample = Sample.query.one()
        experiment_id, sample_id = experiment.id, sample.id
        assert experiment.batches == []

    response = client.post(f"/experiments/{experiment_id}/batches", data={
        "batch_code": "B-01", "repeat_kind": "生物学重复",
        "repeat_number": "2", "group_name": "处理组", "start_date": "2026-07-21",
    })
    assert response.status_code == 302

    client.post(f"/experiments/{experiment_id}/steps", data={
        "title": "加药", "description": "处理 24h", "planned_date": "2026-07-22",
    })
    client.post(f"/experiments/{experiment_id}/parameters", data={
        "plan_parameter_name": ["药物浓度", "处理时间"],
        "plan_parameter_value": ["5", "24"],
        "plan_parameter_unit": ["μM", "h"],
        "plan_parameter_notes": ["目标值", "固定"],
    })
    client.post(f"/experiments/{experiment_id}/samples", data={
        "sample_id": sample_id, "role": "处理组", "amount_used": "1 管", "notes": "Day 1",
    })
    client.post(f"/experiments/{experiment_id}/record-template", data={
        "record_conditions_template": "浓度：\n时间：",
        "record_content_template": "操作：\n观察：",
        "record_remark_template": "下次注意：",
    })
    client.post(f"/experiments/{experiment_id}/save-template", data={"name": "标准 WB", "description": "24h 处理"})

    with app.app_context():
        item = db.session.get(Experiment, experiment_id)
        batch = ExperimentBatch.query.filter_by(experiment_id=experiment_id).one()
        assert batch.batch_code == "B-01"
        assert batch.repeat_kind == "生物学重复"
        assert batch.repeat_number == 2
        assert batch.group_name == "处理组"
        assert ExperimentParameter.query.count() == 2
        assert ExperimentSample.query.one().sample.sample_code == "S-001"
        template = ExperimentTemplate.query.one()
        assert template.steps[0].planned_offset_days == 1
        assert ExperimentTemplateParameter.query.count() == 0
        assert template.parameters == []
        assert template.sample_requirements_json == "[]"
        assert template.record_content_template == ""
        template_id = template.id

    detail = client.get(f"/templates/{template_id}")
    assert detail.status_code == 200
    assert "步骤模板".encode() in detail.data
    assert "加药".encode() in detail.data
    assert "样本角色要求".encode() not in detail.data
    assert "默认实验过程".encode() not in detail.data

    client.post("/experiments/from-template", data={
        "template_id": template_id, "title": "WB 重复实验", "start_date": "2026-08-01",
        "repeat_kind": "技术重复", "repeat_number": "3",
    })
    with app.app_context():
        copied = Experiment.query.filter_by(title="WB 重复实验").one()
        assert copied.steps[0].title == "加药"
        assert copied.steps[0].planned_date.isoformat() == "2026-08-02"
        assert copied.plan_parameters == []
        assert copied.record_content_template == ""
        assert copied.sample_requirements_json == "[]"


def test_record_template_saves_views_and_prefills_new_record(client, auth, app):
    auth.register()
    client.post("/experiments", data={"title": "记录模板来源", "code": "REC-TPL-01"})
    with app.app_context():
        experiment_id = Experiment.query.one().id
    batch_id = _start_execution(client, app, experiment_id)

    client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id,
        "record_date": "2026-07-21", "operator": "研究员", "result": "成功",
        "conditions": "药物浓度 5 μM", "content": "孵育 24 小时后完成检测",
        "remark": "下次降低细胞密度",
        "record_parameter_name": ["药物浓度", "处理时间"],
        "record_parameter_value": ["5", "24"],
        "record_parameter_unit": ["μM", "h"],
        "record_parameter_notes": ["终浓度", "固定"],
    })
    with app.app_context():
        record = Experiment.query.one().records[0]
        record_id = record.id

    response = client.post(f"/records/{record_id}/save-template", data={
        "name": "WB 记录模板", "description": "适用于 24 小时处理",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "调用记录模板".encode() in response.data

    with app.app_context():
        template = RecordTemplate.query.one()
        template_id = template.id
        assert template.conditions == "药物浓度 5 μM"
        assert template.content == "孵育 24 小时后完成检测"
        assert template.remark == "下次降低细胞密度"
        assert RecordTemplateParameter.query.count() == 2
        assert template.parameters[0].name == "药物浓度"

    detail = client.get(f"/record-templates/{template_id}")
    assert detail.status_code == 200
    assert "WB 记录模板".encode() in detail.data
    assert "药物浓度 5 μM".encode() in detail.data
    assert "药物浓度".encode() in detail.data

    use_response = client.get(f"/batches/{batch_id}?record_template_id={template_id}")
    assert use_response.status_code == 200
    assert "已填入记录模板".encode() in use_response.data
    assert 'value="5"'.encode() in use_response.data
    assert "孵育 24 小时后完成检测".encode() in use_response.data
    assert f'name="batch_id" value="{batch_id}"'.encode() in use_response.data


def test_weekly_presentation_download_uses_selected_experiments(client, auth, app, monkeypatch):
    auth.register()
    client.post("/experiments", data={"title": "周报实验", "code": "WEEK-01"})
    with app.app_context():
        experiment_id = Experiment.query.one().id
    batch_id = _start_execution(client, app, experiment_id)
    client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id,
        "record_date": "2026-07-21", "content": "完成检测", "result": "成功",
    })
    captured = {}

    def fake_build(payload):
        captured["payload"] = payload
        return b"fake-pptx"

    monkeypatch.setattr("app.presentation_service.build_weekly_presentation", fake_build)
    response = client.post("/reports/presentation", data={
        "title": "第 30 周实验周报", "start_date": "2026-07-20", "end_date": "2026-07-26",
        "experiment_ids": [str(experiment_id)], "include_images": "1",
    })
    assert response.status_code == 200
    assert response.data == b"fake-pptx"
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert captured["payload"]["metrics"]["record_count"] == 1
    assert captured["payload"]["experiments"][0]["title"] == "周报实验"


def test_record_parameters_attachment_metadata_and_archive(client, auth, app):
    auth.register()
    client.post("/experiments", data={"title": "归档实验", "code": "ARCH-01"})
    with app.app_context():
        experiment_id = Experiment.query.one().id
    batch_id = _start_execution(client, app, experiment_id)
    response = client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id,
        "record_date": "2026-07-21", "operator": "研究员", "content": "完成检测。",
        "record_parameter_name": ["浓度"], "record_parameter_value": ["5"],
        "record_parameter_unit": ["μM"], "record_parameter_notes": ["终浓度"],
        "attachment_category": "原始数据",
        "files": (io.BytesIO(b"sample,value\nA,1\n"), "raw/result.csv"),
    }, content_type="multipart/form-data", follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        attachment = ExperimentAttachment.query.one()
        attachment_id = attachment.id
        assert len(attachment.sha256) == 64
        assert attachment.version_number == 1
        assert RecordParameter.query.one().name == "浓度"

    client.post(f"/attachments/{attachment_id}/metadata", data={
        "category": "分析结果", "tags": "Figure 1, CSV", "description": "归一化结果",
    })
    verified = client.post(f"/attachments/{attachment_id}/verify", follow_redirects=True)
    assert "文件完整性校验通过".encode() in verified.data

    archive_response = client.get(f"/experiments/{experiment_id}/archive.zip")
    assert archive_response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive_response.data)) as archive:
        names = archive.namelist()
        assert "report.md" in names
        assert "file-manifest.csv" in names
        assert any(name.endswith("raw/result.csv") for name in names)
        report = archive.read("report.md").decode("utf-8-sig")
        assert "浓度：5 μM" in report
        assert "SHA-256" in report


def test_legacy_attachment_gets_hash_baseline(client, auth, app):
    auth.register()
    client.post("/experiments", data={"title": "旧附件实验"})
    with app.app_context():
        experiment_id = Experiment.query.one().id
    batch_id = _start_execution(client, app, experiment_id)
    client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id,
        "content": "旧记录", "files": (io.BytesIO(b"legacy"), "legacy.bin"),
    }, content_type="multipart/form-data")
    with app.app_context():
        attachment = ExperimentAttachment.query.one()
        attachment.sha256 = ""
        attachment_id = attachment.id
        db.session.commit()
    response = client.post(f"/attachments/{attachment_id}/verify", follow_redirects=True)
    assert "建立 SHA-256 校验基线".encode() in response.data
    with app.app_context():
        assert len(db.session.get(ExperimentAttachment, attachment_id).sha256) == 64


def test_local_backup_and_restore_commands(tmp_path):
    database_path = tmp_path / "research.db"
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
        "SECRET_KEY": "test-key",
        "CREDENTIAL_ENCRYPTION_KEY": "credential-key",
        "RATELIMIT_ENABLED": False,
        "ATTACHMENT_UPLOAD_DIR": str(tmp_path / "experiment-files"),
        "AI_UPLOAD_DIR": str(tmp_path / "assistant-files"),
        "APPEARANCE_UPLOAD_DIR": str(tmp_path / "backgrounds"),
        "BACKUP_DIR": str(tmp_path / "backups"),
    })
    with app.app_context():
        db.create_all()
        user = User(name="备份用户", email="backup@example.com", role="researcher")
        user.set_password("Password1234")
        db.session.add(user)
        db.session.commit()

    runner = app.test_cli_runner()
    backup_result = runner.invoke(args=["backup-local"])
    assert backup_result.exit_code == 0
    backup_path = next((tmp_path / "backups").glob("*.zip"))
    with sqlite3.connect(database_path) as connection:
        connection.execute("DELETE FROM user")
        connection.commit()
    restore_result = runner.invoke(args=["restore-local", "--archive", str(backup_path), "--yes"])
    assert restore_result.exit_code == 0
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM user").fetchone()[0] == 1
