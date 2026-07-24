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


def test_new_executions_clone_independent_plan_step_snapshots(client, auth, app):
    auth.register()
    experiment_id = _experiment(client, app, "步骤快照实验")
    client.post(f"/experiments/{experiment_id}/steps", data={
        "title": "原计划步骤", "description": "版本一", "operator": "甲",
        "planned_date": "2026-07-20",
    })
    first_batch_id = _execution(client, app, experiment_id, "RUN-01")
    with app.app_context():
        plan_step = ExperimentStep.query.filter_by(experiment_id=experiment_id).one()
        plan_step_id = plan_step.id
        first_step = BatchStep.query.filter_by(batch_id=first_batch_id).one()
        assert first_step.source_step_id == plan_step.id
        assert first_step.title == "原计划步骤"

    client.post(f"/steps/{plan_step_id}/edit", data={
        "title": "更新后的计划步骤", "description": "版本二", "operator": "乙",
        "planned_date": "2026-07-22",
    })
    second_batch_id = _execution(client, app, experiment_id, "RUN-02")
    with app.app_context():
        first_step = BatchStep.query.filter_by(batch_id=first_batch_id).one()
        second_step = BatchStep.query.filter_by(batch_id=second_batch_id).one()
        assert (first_step.title, first_step.description, first_step.operator) == (
            "原计划步骤", "版本一", "甲",
        )
        assert (second_step.title, second_step.description, second_step.operator) == (
            "更新后的计划步骤", "版本二", "乙",
        )
        assert first_step.planned_date == date(2026, 7, 20)
        assert second_step.planned_date == date(2026, 7, 22)


def test_execution_step_edit_toggle_bulk_and_scope(client, auth, app):
    auth.register()
    experiment_id = _experiment(client, app, "当前执行")
    client.post(f"/experiments/{experiment_id}/steps", data={"title": "步骤 A"})
    client.post(f"/experiments/{experiment_id}/steps", data={"title": "步骤 B"})
    batch_id = _execution(client, app, experiment_id, "RUN-CURRENT")

    other_experiment_id = _experiment(client, app, "其他执行")
    client.post(f"/experiments/{other_experiment_id}/steps", data={"title": "其他步骤"})
    other_batch_id = _execution(client, app, other_experiment_id, "RUN-OTHER")
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
    assert "1 个计划步骤" in plan_html

    execution_html = client.get(f"/batches/{batch_id}").get_data(as_text=True)
    assert "本次执行步骤" in execution_html
    assert "批量更新完成状态" in execution_html
    assert "/batch-steps/" in execution_html
