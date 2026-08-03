from datetime import date

from app import db
from app.models import BatchStep, Experiment, ExperimentBatch, ExperimentStep


def _experiment(client, app, title):
    client.post("/experiments", data={"title": title, "owner": "研究员"})
    with app.app_context():
        return Experiment.query.filter_by(title=title).one().id


def _execution(client, app, experiment_id, code):
    response = client.post(f"/experiments/{experiment_id}/batches", data={
        "batch_code": code,
    })
    assert response.status_code == 302
    with app.app_context():
        return ExperimentBatch.query.filter_by(
            experiment_id=experiment_id, batch_code=code,
        ).one().id


def test_plan_stages_and_batch_steps_are_independent_from_creation(client, auth, app):
    auth.register()
    experiment_id = _experiment(client, app, "方案与执行分离实验")
    client.post(f"/experiments/{experiment_id}/steps", data={
        "title": "样本准备阶段", "description": "完成基线确认", "operator": "方案负责人",
        "planned_date": "2026-07-20",
    })
    first_batch_id = _execution(client, app, experiment_id, "RUN-01")
    with app.app_context():
        assert BatchStep.query.filter_by(batch_id=first_batch_id).count() == 0

    client.post(f"/batches/{first_batch_id}/steps", data={
        "title": "离心收集细胞", "description": "500 g，5 min", "operator": "实验人员",
        "planned_date": "2026-07-21",
    })
    with app.app_context():
        plan_stage = ExperimentStep.query.filter_by(experiment_id=experiment_id).one()
        plan_stage_id = plan_stage.id
        batch_step = BatchStep.query.filter_by(batch_id=first_batch_id).one()
        batch_step_id = batch_step.id
        assert batch_step.source_step_id is None
        assert batch_step.title == "离心收集细胞"

    client.post(f"/steps/{plan_stage_id}/edit", data={
        "title": "更新后的方案阶段", "description": "新的验收要求", "operator": "新负责人",
        "planned_date": "2026-07-22",
    })
    client.post(f"/batch-steps/{batch_step_id}/edit", data={
        "title": "本批次离心操作", "description": "600 g，5 min", "operator": "实际人员",
        "planned_date": "2026-07-23",
    })
    second_batch_id = _execution(client, app, experiment_id, "RUN-02")
    with app.app_context():
        plan_stage = db.session.get(ExperimentStep, plan_stage_id)
        batch_step = db.session.get(BatchStep, batch_step_id)
        assert (plan_stage.title, plan_stage.description, plan_stage.operator) == (
            "更新后的方案阶段", "新的验收要求", "新负责人",
        )
        assert (batch_step.title, batch_step.description, batch_step.operator) == (
            "本批次离心操作", "600 g，5 min", "实际人员",
        )
        assert plan_stage.planned_date == date(2026, 7, 22)
        assert batch_step.planned_date == date(2026, 7, 23)
        assert BatchStep.query.filter_by(batch_id=second_batch_id).count() == 0


def test_execution_step_edit_toggle_bulk_and_scope(client, auth, app):
    auth.register()
    experiment_id = _experiment(client, app, "当前执行")
    batch_id = _execution(client, app, experiment_id, "RUN-CURRENT")
    client.post(f"/batches/{batch_id}/steps", data={"title": "步骤 A"})
    client.post(f"/batches/{batch_id}/steps", data={"title": "步骤 B"})

    other_experiment_id = _experiment(client, app, "其他执行")
    other_batch_id = _execution(client, app, other_experiment_id, "RUN-OTHER")
    client.post(f"/batches/{other_batch_id}/steps", data={"title": "其他步骤"})
    with app.app_context():
        step_ids = [step.id for step in BatchStep.query.filter_by(batch_id=batch_id).all()]
        other_step_id = BatchStep.query.filter_by(batch_id=other_batch_id).one().id

    response = client.post(f"/batch-steps/{step_ids[0]}/edit", data={
        "title": "步骤 A 已校准", "description": "本次执行专用参数",
        "operator": "执行人", "planned_date": "2026-07-24",
    })
    assert response.status_code == 302
    assert client.post(f"/batch-steps/{step_ids[0]}/toggle").status_code == 302
    assert client.post(f"/batches/{batch_id}/steps/bulk", data={
        "step_ids": [str(step_ids[0]), str(other_step_id)], "action": "complete",
    }).status_code == 404
    assert client.post(f"/batches/{batch_id}/steps/bulk", data={
        "step_ids": [str(value) for value in step_ids], "action": "complete",
        "completed_date": "2026-07-25",
    }).status_code == 302
    with app.app_context():
        steps = BatchStep.query.filter_by(batch_id=batch_id).order_by(BatchStep.position).all()
        assert steps[0].title == "步骤 A 已校准"
        assert steps[0].description == "本次执行专用参数"
        assert all(step.is_done for step in steps)
        assert {step.completed_date for step in steps} == {date(2026, 7, 25)}

    assert client.post(f"/batches/{batch_id}/steps/bulk", data={
        "step_ids": [str(value) for value in step_ids], "action": "pending",
    }).status_code == 302
    with app.app_context():
        assert all(
            not step.is_done and step.completed_date is None
            for step in BatchStep.query.filter_by(batch_id=batch_id).all()
        )


def test_batch_step_date_management_reorder_and_delete(client, auth, app):
    auth.register()
    experiment_id = _experiment(client, app, "批次排期")
    batch_id = _execution(client, app, experiment_id, "RUN-DATES")
    for title in ("配液", "加样", "检测"):
        assert client.post(f"/batches/{batch_id}/steps", data={"title": title}).status_code == 302
    with app.app_context():
        steps = BatchStep.query.filter_by(batch_id=batch_id).order_by(BatchStep.position).all()
        step_ids = [step.id for step in steps]

    assert client.post(f"/batch-steps/{step_ids[2]}/move", data={"direction": "up"}).status_code == 302
    assert client.post(f"/batches/{batch_id}/steps/bulk", data={
        "step_ids": [str(value) for value in step_ids],
        "action": "schedule", "date_mode": "sequence",
        "planned_date": "2026-08-10", "interval_days": "2",
    }).status_code == 302
    with app.app_context():
        ordered = BatchStep.query.filter_by(batch_id=batch_id).order_by(BatchStep.position).all()
        assert [step.title for step in ordered] == ["配液", "检测", "加样"]
        assert [step.planned_date for step in ordered] == [
            date(2026, 8, 10), date(2026, 8, 12), date(2026, 8, 14),
        ]

    assert client.post(f"/batches/{batch_id}/steps/bulk", data={
        "step_ids": [str(step_ids[0]), str(step_ids[2])],
        "action": "schedule", "date_mode": "shift", "shift_days": "-1",
    }).status_code == 302
    assert client.post(f"/batches/{batch_id}/steps/bulk", data={
        "step_ids": [str(step_ids[1])],
        "action": "schedule", "date_mode": "clear",
    }).status_code == 302
    with app.app_context():
        assert db.session.get(BatchStep, step_ids[0]).planned_date == date(2026, 8, 9)
        assert db.session.get(BatchStep, step_ids[2]).planned_date == date(2026, 8, 11)
        assert db.session.get(BatchStep, step_ids[1]).planned_date is None

    assert client.post(f"/batch-steps/{step_ids[2]}/delete").status_code == 302
    assert client.post(f"/batches/{batch_id}/steps/bulk", data={
        "step_ids": [str(step_ids[1])], "action": "delete",
    }).status_code == 302
    with app.app_context():
        remaining = BatchStep.query.filter_by(batch_id=batch_id).all()
        assert [(step.title, step.position) for step in remaining] == [("配液", 1)]


def test_plan_page_has_no_completion_controls_and_execution_page_does(client, auth, app):
    auth.register()
    experiment_id = _experiment(client, app, "页面边界")
    client.post(f"/experiments/{experiment_id}/steps", data={"title": "边界步骤"})
    batch_id = _execution(client, app, experiment_id, "RUN-BOUNDARY")
    with app.app_context():
        plan_step_id = ExperimentStep.query.filter_by(experiment_id=experiment_id).one().id

    plan_html = client.get(f"/experiments/{experiment_id}").get_data(as_text=True)
    assert f"/steps/{plan_step_id}/toggle" not in plan_html
    assert "完成状态" not in plan_html
    assert "1 个阶段" in plan_html
    assert "方案阶段" in plan_html
    assert "实验方案层" in plan_html
    assert "独立维护" in plan_html
    assert "执行快照" not in plan_html

    client.post(f"/batches/{batch_id}/steps", data={"title": "边界实验步骤"})
    execution_html = client.get(f"/batches/{batch_id}").get_data(as_text=True)
    assert "本批次实验步骤" in execution_html
    assert "添加本批次实验步骤" in execution_html
    assert "批量管理实验步骤" in execution_html
    assert "日期安排" in execution_html
    assert "方案阶段" not in execution_html
    assert "执行快照" not in execution_html
    assert "/batch-steps/" in execution_html
