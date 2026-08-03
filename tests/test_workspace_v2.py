import io
import json
import zipfile
from datetime import date
from pathlib import Path

from app import db
from app.models import (
    Experiment, ExperimentAttachment, ExperimentBatch, ExperimentRecord,
    RecordRevision, RecordTemplate, ResearchProject,
)


def _workspace_experiment(client, app):
    client.post("/projects", data={
        "title": "骨肉瘤耐药机制", "code": "OS-01", "objective": "验证耐药机制",
    })
    with app.app_context():
        project_id = ResearchProject.query.filter_by(code="OS-01").order_by(ResearchProject.id.desc()).first().id
    client.post("/experiments", data={
        "project_id": project_id, "title": "WB 验证", "code": "EXP-01",
        "owner": "研究员", "status": "进行中",
    })
    with app.app_context():
        experiment = Experiment.query.filter_by(code="EXP-01").order_by(Experiment.id.desc()).first()
        experiment_id = experiment.id
    client.post(f"/experiments/{experiment_id}/batches", data={"batch_code": "BATCH-01"})
    with app.app_context():
        batch = ExperimentBatch.query.filter_by(experiment_id=experiment_id).first()
        return project_id, experiment_id, batch.id


def _deleted_managed_attachments(client, app, names=("one.bin", "two.bin")):
    _project_id, experiment_id, batch_id = _workspace_experiment(client, app)
    client.post(f"/experiments/{experiment_id}/records", data={
        "batch_id": batch_id, "content": "待批量清理的附件记录",
    })
    with app.app_context():
        record_id = ExperimentRecord.query.filter_by(experiment_id=experiment_id).one().id
    for name in names:
        client.post(f"/records/{record_id}/attachments", data={
            "files": (io.BytesIO(name.encode()), name),
        }, content_type="multipart/form-data")
    with app.app_context():
        attachments = ExperimentAttachment.query.filter_by(record_id=record_id).order_by(
            ExperimentAttachment.id
        ).all()
        attachment_ids = [item.id for item in attachments]
        stored_paths = [
            Path(app.config["ATTACHMENT_UPLOAD_DIR"]) / item.stored_path
            for item in attachments
        ]
    for attachment_id in attachment_ids:
        client.post(f"/attachments/{attachment_id}/delete")
    return attachment_ids, stored_paths


def test_project_workspace_creates_plan_then_explicit_execution(client, auth, app):
    auth.register()
    project_id, experiment_id, batch_id = _workspace_experiment(client, app)

    assert client.get("/projects").status_code == 301
    assert client.get(f"/projects/{project_id}").status_code == 301
    assert client.get(f"/batches/{batch_id}").status_code == 200
    with app.app_context():
        experiment = db.session.get(Experiment, experiment_id)
        assert experiment.project_id == project_id
        assert experiment.batches[0].batch_code == "BATCH-01"


def test_first_record_starts_execution_and_enforces_execution_date_range(client, auth, app):
    auth.register()
    _project_id, experiment_id, batch_id = _workspace_experiment(client, app)

    response = client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id,
        "record_date": "2026-07-20",
        "content": "首条回填记录",
    })
    assert response.status_code == 302
    with app.app_context():
        batch = db.session.get(ExperimentBatch, batch_id)
        record = ExperimentRecord.query.filter_by(content="首条回填记录").one()
        record_id = record.id
        assert batch.status == "进行中"
        assert batch.start_date == date(2026, 7, 20)
        batch.end_date = date(2026, 7, 22)
        db.session.commit()

    for start_date, end_date, expected_message in (
        ("2026-07-21", "2026-07-22", "开始日期不能晚于已有过程记录"),
        ("2026-07-20", "2026-07-19", "结束日期不能早于开始日期"),
        ("", "2026-07-22", "实验批次开始日期不能为空"),
    ):
        response = client.post(f"/batches/{batch_id}", data={
            "batch_code": "BATCH-01", "repeat_kind": "独立实验", "repeat_number": "1",
            "status": "进行中", "start_date": start_date, "end_date": end_date,
        }, follow_redirects=True)
        assert expected_message.encode() in response.data

    with app.app_context():
        batch = db.session.get(ExperimentBatch, batch_id)
        assert batch.start_date == date(2026, 7, 20)
        assert batch.end_date == date(2026, 7, 22)

    for invalid_date, expected_message in (
        ("not-a-date", "有效的过程记录日期"),
        ("2026-07-19", "不能早于实验批次开始日期"),
        ("2026-07-23", "不能晚于实验批次结束日期"),
    ):
        response = client.post(f"/batches/{batch_id}/records", data={
            "batch_id": batch_id,
            "record_date": invalid_date,
            "content": f"不应保存 {invalid_date}",
        }, follow_redirects=True)
        assert expected_message.encode() in response.data

    response = client.post(f"/records/{record_id}", data={
        "record_date": "2026-07-23",
        "content": "不应移动到结束日期之后",
        "result": "待确认",
    }, follow_redirects=True)
    assert "不能晚于实验批次结束日期".encode() in response.data

    client.post(f"/batches/{batch_id}/records/bulk", data={
        "record_ids": [str(record_id)],
        "action": "update",
        "result": "__keep__",
        "operator_mode": "keep",
        "remark_mode": "keep",
        "shift_days": "3",
    })
    with app.app_context():
        assert ExperimentRecord.query.count() == 1
        record = db.session.get(ExperimentRecord, record_id)
        assert record.record_date == date(2026, 7, 20)
        assert record.content == "首条回填记录"


def test_finalized_record_cannot_move_bulk_change_or_delete(client, auth, app):
    auth.register()
    _project_id, experiment_id, batch_id = _workspace_experiment(client, app)
    client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id,
        "content": "定稿后保持不可变",
        "operator": "原记录人",
    })
    client.post(f"/experiments/{experiment_id}/batches", data={"batch_code": "BATCH-02"})
    with app.app_context():
        record_id = ExperimentRecord.query.filter_by(content="定稿后保持不可变").one().id
        other_batch_id = ExperimentBatch.query.filter_by(
            experiment_id=experiment_id, batch_code="BATCH-02",
        ).one().id
    client.post(f"/records/{record_id}/finalize")

    response = client.post(f"/records/{record_id}/move-batch", data={
        "batch_id": other_batch_id,
    }, follow_redirects=True)
    assert "不能更换实验批次".encode() in response.data

    response = client.post(f"/batches/{batch_id}/records/bulk", data={
        "record_ids": [str(record_id)],
        "action": "update",
        "result": "成功",
        "operator_mode": "replace",
        "operator": "批量覆盖人",
        "remark_mode": "keep",
        "shift_days": "0",
    }, follow_redirects=True)
    assert "不能批量修改或删除".encode() in response.data

    client.post(f"/batches/{batch_id}/records/bulk", data={
        "record_ids": [str(record_id)],
        "action": "delete",
    })
    response = client.post(f"/records/{record_id}/delete", follow_redirects=True)
    assert "不能直接删除".encode() in response.data

    with app.app_context():
        record = db.session.get(ExperimentRecord, record_id)
        assert record.batch_id == batch_id
        assert record.lifecycle_status == "已定稿"
        assert record.operator == "原记录人"
        assert record.result == "待确认"
        assert record.is_deleted is False
        assert RecordRevision.query.count() == 0


def test_new_plan_waits_for_user_to_start_a_batch(client, auth, app):
    auth.register()
    client.post("/projects", data={"title": "先计划后执行", "code": "PLAN-FIRST"})
    with app.app_context():
        project_id = ResearchProject.query.filter_by(code="PLAN-FIRST").one().id

    response = client.post("/experiments", data={
        "project_id": project_id,
        "title": "尚未开始执行的计划",
    })
    assert response.status_code == 302
    with app.app_context():
        experiment = Experiment.query.filter_by(title="尚未开始执行的计划").one()
        experiment_id = experiment.id
        assert experiment.batches == []

    detail = client.get(f"/experiments/{experiment_id}")
    assert "新建实验批次".encode() in detail.data
    created = client.post(f"/experiments/{experiment_id}/batches", data={
        "batch_code": "BATCH-01",
    })
    assert created.status_code == 302
    with app.app_context():
        assert ExperimentBatch.query.filter_by(experiment_id=experiment_id).count() == 1


def test_execution_workspace_owns_record_creation_and_navigation(client, auth, app):
    auth.register()
    _project_id, experiment_id, batch_id = _workspace_experiment(client, app)

    experiment_page = client.get(f"/experiments/{experiment_id}").get_data(as_text=True)
    assert 'data-experiment-tab="overview"' in experiment_page
    assert 'data-experiment-tab="protocol"' in experiment_page
    assert 'data-experiment-tab="batches"' in experiment_page
    assert 'data-experiment-tab="records"' not in experiment_page
    assert "新增实验记录" not in experiment_page

    batch_page = client.get(f"/batches/{batch_id}").get_data(as_text=True)
    assert f'action="/batches/{batch_id}/records"' in batch_page
    assert f'name="batch_id" value="{batch_id}"' in batch_page
    assert "添加过程记录" in batch_page
    assert "过程记录时间线" in batch_page

    response = client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id,
        "content": "完成上样并开始电泳",
        "conditions": "120 V",
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/batches/{batch_id}#batch-records")

    with app.app_context():
        record = ExperimentRecord.query.filter_by(experiment_id=experiment_id).one()
        record_id = record.id
        assert record.batch_id == batch_id

    record_page = client.get(f"/records/{record_id}").get_data(as_text=True)
    assert f'href="/batches/{batch_id}#batch-records"' in record_page
    assert "过程记录" in record_page

    experiment_page = client.get(f"/experiments/{experiment_id}").get_data(as_text=True)
    assert "跨批次过程记录索引" in experiment_page
    assert "完成上样并开始电泳" in experiment_page


def test_execution_record_create_keeps_validation_and_file_redirects(client, auth, app):
    auth.register()
    _project_id, experiment_id, batch_id = _workspace_experiment(client, app)

    invalid = client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id,
        "content": "",
    })
    assert invalid.status_code == 302
    assert invalid.headers["Location"].endswith(f"/batches/{batch_id}#new-record")

    created = client.post(f"/batches/{batch_id}/records", data={
        "batch_id": batch_id,
        "content": "完成成像并上传原始结果",
        "files": (io.BytesIO(b"image-result"), "result.tif"),
    }, content_type="multipart/form-data")
    assert created.status_code == 302
    with app.app_context():
        record = ExperimentRecord.query.filter_by(
            experiment_id=experiment_id, content="完成成像并上传原始结果",
        ).one()
        record_id = record.id
        assert ExperimentAttachment.query.filter_by(record_id=record.id).one().original_name == "result.tif"
    assert created.headers["Location"].endswith(f"/records/{record_id}#record-files")


def test_execution_names_counts_and_dashboard_links_follow_research_hierarchy(client, auth, app):
    auth.register()
    client.post("/projects", data={"title": "层级导航项目", "code": "NAV-01"})
    with app.app_context():
        project_id = ResearchProject.query.filter_by(code="NAV-01").one().id
    client.post("/experiments", data={
        "project_id": project_id, "title": "层级导航计划", "code": "NAV-EXP-01",
    })
    with app.app_context():
        experiment_id = Experiment.query.filter_by(code="NAV-EXP-01").one().id

    client.post(f"/experiments/{experiment_id}/batches", data={})
    with app.app_context():
        execution = ExperimentBatch.query.filter_by(experiment_id=experiment_id, is_deleted=False).one()
        execution_id = execution.id
        assert execution.batch_code == "RUN-01"
        db.session.add(ExperimentBatch(
            experiment_id=experiment_id, batch_code="RUN-REMOVED", is_deleted=True,
        ))
        db.session.commit()

    plan_page = client.get(f"/experiments/{experiment_id}").get_data(as_text=True)
    assert "返回实验计划" in plan_page
    assert "批次编号，如 RUN-02" in plan_page
    assert "BATCH-" not in plan_page

    # Project page now redirects to experiments with project filter
    project_redirect = client.get(f"/projects/{project_id}")
    assert project_redirect.status_code == 301

    dashboard = client.get("/").get_data(as_text=True)
    assert f'href="/batches/{execution_id}"' in dashboard
    assert f'href="/batches/{execution_id}#new-record"' in dashboard
    assert "新建实验计划" in dashboard

    plan_index = client.get("/experiments").get_data(as_text=True)
    assert "<h1>实验计划</h1>" in plan_index
    assert "打开实验计划" in plan_index


def test_batch_record_create_requires_matching_explicit_batch(client, auth, app):
    auth.register()
    _project_id, experiment_id, batch_id = _workspace_experiment(client, app)
    client.post(f"/experiments/{experiment_id}/batches", data={"batch_code": "BATCH-02"})
    with app.app_context():
        other_batch_id = ExperimentBatch.query.filter_by(
            experiment_id=experiment_id, batch_code="BATCH-02"
        ).one().id

    assert client.post(f"/batches/{batch_id}/records", data={
        "content": "缺少显式归属",
    }).status_code == 400
    assert client.post(f"/batches/{batch_id}/records", data={
        "batch_id": other_batch_id,
        "content": "归属与页面不匹配",
    }).status_code == 400
    with app.app_context():
        assert ExperimentRecord.query.count() == 0


def test_batch_record_template_and_bulk_tools_stay_in_current_execution(client, auth, app):
    auth.register()
    _project_id, experiment_id, batch_id = _workspace_experiment(client, app)
    with app.app_context():
        user_id = db.session.get(Experiment, experiment_id).user_id
        template = RecordTemplate(
            user_id=user_id,
            name="WB 观察模板",
            conditions="湿转 90 分钟",
            content="记录条带位置与背景",
            remark="复核曝光时间",
        )
        db.session.add(template)
        db.session.commit()
        template_id = template.id

    template_page = client.get(
        f"/batches/{batch_id}?record_template_id={template_id}"
    ).get_data(as_text=True)
    assert "WB 观察模板" in template_page
    assert "湿转 90 分钟" in template_page
    assert f'name="batch_id" value="{batch_id}"' in template_page

    for index in range(2):
        response = client.post(f"/batches/{batch_id}/records", data={
            "batch_id": batch_id,
            "content": f"批次内记录 {index + 1}",
        })
        assert response.status_code == 302
    with app.app_context():
        record_ids = [record.id for record in ExperimentRecord.query.filter_by(batch_id=batch_id).all()]

    response = client.post(f"/batches/{batch_id}/records/bulk", data={
        "record_ids": [str(value) for value in record_ids],
        "action": "update",
        "result": "成功",
        "operator_mode": "replace",
        "operator": "统一记录人",
        "remark_mode": "keep",
        "shift_days": "0",
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/batches/{batch_id}#batch-records")
    with app.app_context():
        records = ExperimentRecord.query.filter_by(batch_id=batch_id).all()
        assert {record.result for record in records} == {"成功"}
        assert {record.operator for record in records} == {"统一记录人"}


def test_deleted_experiment_blocks_old_batch_url(client, auth, app):
    auth.register()
    _project_id, experiment_id, batch_id = _workspace_experiment(client, app)

    client.post(f"/experiments/{experiment_id}/delete")
    assert client.get(f"/batches/{batch_id}").status_code == 404


def test_finalized_record_requires_reason_and_keeps_revision(client, auth, app):
    auth.register()
    _project_id, experiment_id, batch_id = _workspace_experiment(client, app)
    client.post(f"/experiments/{experiment_id}/records", data={
        "batch_id": batch_id, "content": "原始实验过程", "conditions": "37 C",
    })
    with app.app_context():
        record_id = ExperimentRecord.query.filter_by(experiment_id=experiment_id).one().id

    client.post(f"/records/{record_id}/finalize")
    response = client.post(f"/records/{record_id}", data={
        "content": "不应覆盖的过程", "conditions": "38 C", "result": "成功",
    }, follow_redirects=True)
    assert "请填写修订原因".encode() in response.data
    with app.app_context():
        assert db.session.get(ExperimentRecord, record_id).content == "原始实验过程"
        assert RecordRevision.query.count() == 0

    client.post(f"/records/{record_id}", data={
        "content": "修订后的实验过程", "conditions": "38 C", "result": "成功",
        "revision_reason": "更正培养温度记录",
    })
    with app.app_context():
        record = db.session.get(ExperimentRecord, record_id)
        revision = RecordRevision.query.one()
        assert record.lifecycle_status == "修订"
        assert record.content == "修订后的实验过程"
        assert revision.reason == "更正培养温度记录"
        assert "原始实验过程" in revision.before_json
        assert "修订后的实验过程" in revision.after_json


def test_recycle_restore_and_purge_managed_attachment(client, auth, app):
    auth.register()
    _project_id, experiment_id, batch_id = _workspace_experiment(client, app)
    client.post(f"/experiments/{experiment_id}/records", data={
        "batch_id": batch_id, "content": "带附件记录",
    })
    with app.app_context():
        record_id = ExperimentRecord.query.filter_by(experiment_id=experiment_id).one().id
    client.post(f"/records/{record_id}/attachments", data={
        "files": (io.BytesIO(b"raw-data"), "raw.bin"),
    }, content_type="multipart/form-data")
    with app.app_context():
        attachment = ExperimentAttachment.query.one()
        attachment_id = attachment.id
        stored_path = Path(app.config["ATTACHMENT_UPLOAD_DIR"]) / attachment.stored_path

    client.post(f"/attachments/{attachment_id}/delete")
    assert stored_path.exists()
    client.post(f"/recycle-bin/attachment/{attachment_id}/restore")
    with app.app_context():
        assert db.session.get(ExperimentAttachment, attachment_id).is_deleted is False

    client.post(f"/attachments/{attachment_id}/delete")
    response = client.post(f"/recycle-bin/attachment/{attachment_id}/purge")
    assert response.status_code == 302
    assert not stored_path.exists()
    with app.app_context():
        assert db.session.get(ExperimentAttachment, attachment_id) is None


def test_recycle_bulk_purge_removes_selected_managed_attachments(client, auth, app):
    auth.register()
    attachment_ids, stored_paths = _deleted_managed_attachments(client, app)
    assert all(path.is_file() for path in stored_paths)

    response = client.post("/recycle-bin/attachment/purge-bulk", data={
        "item_ids": [str(item_id) for item_id in attachment_ids],
        "selection_scope": "page",
        "q": "bin", "page": "2", "per_page": "50",
    })

    assert response.status_code == 302
    assert all(value in response.headers["Location"] for value in (
        "kind=attachment", "q=bin", "page=2", "per_page=50",
    ))
    assert all(not path.exists() for path in stored_paths)
    with app.app_context():
        assert all(db.session.get(ExperimentAttachment, item_id) is None for item_id in attachment_ids)


def test_recycle_bulk_purge_rejects_missing_or_invalid_selection(client, auth, app):
    auth.register()
    attachment_ids, stored_paths = _deleted_managed_attachments(client, app)

    response = client.post("/recycle-bin/attachment/purge-bulk", data={
        "selection_scope": "page",
    }, follow_redirects=True)
    assert "请先勾选至少一个项目".encode() in response.data

    assert client.post("/recycle-bin/attachment/purge-bulk", data={
        "selection_scope": "invalid",
        "item_ids": [str(item_id) for item_id in attachment_ids],
    }).status_code == 400

    assert client.post("/recycle-bin/attachment/purge-bulk", data={
        "selection_scope": "page", "item_ids": ["not-an-id"],
    }).status_code == 400
    assert all(path.is_file() for path in stored_paths)
    with app.app_context():
        assert all(db.session.get(ExperimentAttachment, item_id) is not None for item_id in attachment_ids)


def test_recycle_bulk_purge_is_atomic_across_user_boundary(client, auth, app):
    auth.register(email="recycle-owner@example.com")
    owned_ids, owned_paths = _deleted_managed_attachments(client, app, ("owned.bin",))

    auth.logout()
    auth.register(email="recycle-foreign@example.com")
    foreign_ids, foreign_paths = _deleted_managed_attachments(client, app, ("foreign.bin",))
    auth.logout()
    auth.login(email="recycle-owner@example.com")

    response = client.post("/recycle-bin/attachment/purge-bulk", data={
        "item_ids": [str(owned_ids[0]), str(foreign_ids[0])],
        "selection_scope": "page",
    })

    assert response.status_code == 404
    assert all(path.is_file() for path in owned_paths + foreign_paths)
    with app.app_context():
        assert db.session.get(ExperimentAttachment, owned_ids[0]) is not None
        assert db.session.get(ExperimentAttachment, foreign_ids[0]) is not None


def test_recycle_bulk_purge_keeps_external_source_file(client, auth, app):
    auth.register()
    app.config["ALLOW_OPEN_LOCAL_FOLDERS"] = True
    _project_id, experiment_id, batch_id = _workspace_experiment(client, app)
    client.post(f"/experiments/{experiment_id}/records", data={
        "batch_id": batch_id, "content": "批量清理外部链接",
    })
    with app.app_context():
        record_id = ExperimentRecord.query.filter_by(experiment_id=experiment_id).one().id
        external_path = Path(app.config["ATTACHMENT_UPLOAD_DIR"]).parent / "bulk-external.bin"
        external_path.write_bytes(b"external-source")
    client.post(f"/records/{record_id}/attachments/external", data={
        "external_path": str(external_path), "attachment_category": "原始数据",
    })
    with app.app_context():
        attachment_id = ExperimentAttachment.query.one().id
    client.post(f"/attachments/{attachment_id}/delete")

    response = client.post("/recycle-bin/attachment/purge-bulk", data={
        "item_ids": [str(attachment_id)], "selection_scope": "page",
    })

    assert response.status_code == 302
    assert external_path.is_file()
    with app.app_context():
        assert db.session.get(ExperimentAttachment, attachment_id) is None


def test_recycle_page_exposes_bulk_purge_controls(client, auth, app):
    auth.register()
    attachment_ids, _stored_paths = _deleted_managed_attachments(client, app)

    body = client.get("/recycle-bin?kind=attachment").get_data(as_text=True)

    assert 'id="recycle-bulk-purge-form"' in body
    assert 'action="/recycle-bin/attachment/purge-bulk"' in body
    assert "data-bulk-form" in body
    assert "data-bulk-select-all" in body
    assert "data-bulk-select-all-matches" in body
    assert 'name="selection_scope" value="page"' in body
    assert f"全选全部 {len(attachment_ids)} 个实验文件" in body
    assert body.count('name="item_ids"') == len(attachment_ids)
    assert body.count('name="action" value="delete"') == 1
    assert "批量永久删除" in body
    assert 'name="confirmation"' not in body
    assert "输入“永久删除”" not in body


def test_recycle_select_all_matches_purges_every_filtered_page(client, auth, app):
    auth.register()
    matching_names = tuple(f"match-{index:02d}.bin" for index in range(21))
    attachment_ids, stored_paths = _deleted_managed_attachments(
        client, app, (*matching_names, "keep.bin"),
    )

    body = client.get(
        "/recycle-bin?kind=attachment&q=match-&per_page=20",
    ).get_data(as_text=True)
    assert body.count('name="item_ids"') == 20
    assert "全选全部 21 个实验文件" in body
    assert "第 1 / 2 页" in body

    response = client.post("/recycle-bin/attachment/purge-bulk", data={
        "selection_scope": "all", "q": "match-", "page": "1", "per_page": "20",
    })

    assert response.status_code == 302
    assert all(not path.exists() for path in stored_paths[:-1])
    assert stored_paths[-1].is_file()
    with app.app_context():
        assert all(
            db.session.get(ExperimentAttachment, item_id) is None
            for item_id in attachment_ids[:-1]
        )
        assert db.session.get(ExperimentAttachment, attachment_ids[-1]) is not None


def test_record_cannot_move_to_another_users_batch(client, auth, app):
    auth.register(email="owner-a@example.com")
    _project_id, experiment_id, own_batch_id = _workspace_experiment(client, app)
    client.post(f"/experiments/{experiment_id}/records", data={
        "batch_id": own_batch_id, "content": "私有记录",
    })
    with app.app_context():
        record_id = ExperimentRecord.query.one().id

    auth.logout()
    auth.register(email="owner-b@example.com")
    _project_b, _experiment_b, foreign_batch_id = _workspace_experiment(client, app)
    auth.logout()
    auth.login(email="owner-a@example.com")

    assert client.post(f"/records/{record_id}/move-batch", data={
        "batch_id": foreign_batch_id,
    }).status_code == 404


def test_project_package_round_trip_with_manifest_and_checksum(client, auth, app):
    auth.register()
    project_id, experiment_id, batch_id = _workspace_experiment(client, app)
    client.post(f"/experiments/{experiment_id}/records", data={
        "batch_id": batch_id, "content": "可追溯实验过程",
    })
    with app.app_context():
        record_id = ExperimentRecord.query.filter_by(experiment_id=experiment_id).one().id
    client.post(f"/records/{record_id}/attachments", data={
        "files": (io.BytesIO(b"package-data"), "result.csv"),
    }, content_type="multipart/form-data")

    response = client.get(f"/projects/{project_id}/package")
    assert response.status_code == 200
    package_bytes = response.data
    with zipfile.ZipFile(io.BytesIO(package_bytes)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format"] == "research-assistant-project"
        assert manifest["schema_version"] == 2
        assert "project.json" in manifest["entries"]
        assert any(name.startswith("files/attachment-") for name in archive.namelist())

    response = client.post("/projects/import", data={
        "project_package": (io.BytesIO(package_bytes), "project.ralab"),
    }, content_type="multipart/form-data")
    assert response.status_code == 302
    with app.app_context():
        assert ResearchProject.query.count() == 2
        assert Experiment.query.count() == 2
        assert ExperimentRecord.query.count() == 2
        attachments = ExperimentAttachment.query.all()
        assert len(attachments) == 2
        assert all((Path(app.config["ATTACHMENT_UPLOAD_DIR"]) / item.stored_path).is_file() for item in attachments)


def test_external_link_is_never_deleted(client, auth, app):
    auth.register()
    app.config["ALLOW_OPEN_LOCAL_FOLDERS"] = True
    _project_id, experiment_id, batch_id = _workspace_experiment(client, app)
    client.post(f"/experiments/{experiment_id}/records", data={
        "batch_id": batch_id, "content": "外部数据记录",
    })
    with app.app_context():
        record_id = ExperimentRecord.query.filter_by(experiment_id=experiment_id).one().id
        external_path = Path(app.config["ATTACHMENT_UPLOAD_DIR"]).parent / "large-data.bin"
        external_path.write_bytes(b"large-external-data")
    client.post(f"/records/{record_id}/attachments/external", data={
        "external_path": str(external_path), "attachment_category": "原始数据",
    })
    with app.app_context():
        attachment = ExperimentAttachment.query.one()
        attachment_id = attachment.id
        assert attachment.storage_mode == "external"

    client.post(f"/attachments/{attachment_id}/delete")
    client.post(f"/recycle-bin/attachment/{attachment_id}/purge")
    assert external_path.is_file()
