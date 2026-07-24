from app import db
from app.models import (
    Experiment,
    ExperimentBatch,
    ExperimentTemplate,
    ExperimentTemplateStep,
    RecordTemplate,
)


def test_template_center_creates_previews_and_duplicates_step_templates(client, auth, app):
    auth.register()

    empty_center = client.get("/templates")
    assert empty_center.status_code == 200
    assert "模板中心".encode() in empty_center.data
    assert "还没有步骤模板".encode() in empty_center.data

    created = client.post("/templates/new", data={
        "kind": "steps",
        "name": "细胞处理流程",
        "description": "适用于 24 小时药物处理",
    })
    assert created.status_code == 302
    with app.app_context():
        template = ExperimentTemplate.query.one()
        template_id = template.id

    client.post(f"/templates/{template_id}/steps", data={
        "title": "细胞铺板",
        "description": "每孔 2×10^5 个细胞",
        "planned_offset_days": "0",
    })
    center = client.get("/templates?kind=steps")
    assert "细胞处理流程".encode() in center.data
    assert "细胞铺板".encode() in center.data
    assert "每孔 2×10^5".encode() in center.data

    duplicated = client.post(f"/templates/{template_id}/duplicate")
    assert duplicated.status_code == 302
    with app.app_context():
        assert ExperimentTemplate.query.count() == 2
        copy = ExperimentTemplate.query.filter(ExperimentTemplate.id != template_id).one()
        assert copy.name == "细胞处理流程（副本）"
        assert [step.title for step in copy.steps] == ["细胞铺板"]


def test_record_template_can_start_blank_and_remains_editable(client, auth, app):
    auth.register()
    created = client.post("/templates/new", data={
        "kind": "records",
        "name": "WB 记录草稿",
        "description": "先建立结构，稍后填写正文",
    }, follow_redirects=True)
    assert created.status_code == 200
    assert "WB 记录草稿".encode() in created.data

    with app.app_context():
        template = RecordTemplate.query.one()
        template_id = template.id
        assert template.content == ""

    updated = client.post(f"/record-templates/{template_id}", data={
        "name": "WB 记录草稿",
        "description": "适用于常规 WB",
        "conditions": "温度：\n时间：",
        "content": "",
        "remark": "",
    }, follow_redirects=True)
    assert updated.status_code == 200
    assert "记录模板已保存".encode() in updated.data

    center = client.get("/templates?kind=records")
    assert "WB 记录草稿".encode() in center.data
    assert "温度：".encode() in center.data


def test_record_template_selects_execution_and_opens_new_record_directly(client, auth, app):
    auth.register()
    client.post("/experiments", data={"title": "目标实验计划"})
    with app.app_context():
        experiment = Experiment.query.one()
        batch = ExperimentBatch(experiment_id=experiment.id, batch_code="RUN-DIRECT")
        template = RecordTemplate(user_id=experiment.user_id, name="直接调用模板", content="记录正文")
        db.session.add_all([batch, template])
        db.session.commit()
        batch_id, template_id = batch.id, template.id

    center = client.get("/templates?kind=records").get_data(as_text=True)
    assert 'name="batch_id"' in center
    assert 'name="experiment_id"' not in center
    assert "目标实验计划 · RUN-DIRECT" in center

    detail = client.get(f"/record-templates/{template_id}").get_data(as_text=True)
    assert 'name="batch_id"' in detail
    assert "目标实验执行" in detail
    assert "目标实验计划 · RUN-DIRECT" in detail

    response = client.get(f"/record-templates/{template_id}/use?batch_id={batch_id}")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/batches/{batch_id}?record_template_id={template_id}#new-record"
    )


def test_record_template_use_rejects_another_users_execution(client, auth, app):
    auth.register(email="owner@example.com")
    client.post("/experiments", data={"title": "本人实验"})
    with app.app_context():
        owner_experiment = Experiment.query.one()
        template = RecordTemplate(user_id=owner_experiment.user_id, name="本人模板")
        db.session.add(template)
        db.session.commit()
        template_id = template.id

    auth.logout()
    auth.register(email="other@example.com")
    client.post("/experiments", data={"title": "他人实验"})
    with app.app_context():
        other_experiment = Experiment.query.filter_by(title="他人实验").one()
        other_batch = ExperimentBatch(experiment_id=other_experiment.id, batch_code="RUN-OTHER")
        db.session.add(other_batch)
        db.session.commit()
        other_batch_id = other_batch.id

    auth.logout()
    auth.login(email="owner@example.com")
    response = client.get(f"/record-templates/{template_id}/use?batch_id={other_batch_id}")
    assert response.status_code == 404


def test_deleted_template_blocks_child_mutations(client, auth, app):
    auth.register()
    client.post("/templates/new", data={"kind": "steps", "name": "待删除模板"})
    with app.app_context():
        template = ExperimentTemplate.query.one()
        step = ExperimentTemplateStep(template_id=template.id, title="临时步骤")
        db.session.add(step)
        db.session.commit()
        template_id, step_id = template.id, step.id

    client.post(f"/templates/{template_id}/delete")
    assert client.post(f"/template-steps/{step_id}/edit", data={"title": "不应成功"}).status_code == 404
    assert client.post(f"/template-steps/{step_id}/delete").status_code == 404


def test_step_template_apply_defaults_to_append(client, auth, app):
    auth.register()
    client.post("/experiments", data={"title": "已有方案"})
    with app.app_context():
        experiment = Experiment.query.filter_by(title="已有方案").one()
        experiment_id = experiment.id

    client.post(f"/experiments/{experiment_id}/steps", data={"title": "保留步骤"})
    client.post("/templates/new", data={"kind": "steps", "name": "追加模板"})
    with app.app_context():
        template_id = ExperimentTemplate.query.filter_by(name="追加模板").one().id
    client.post(f"/templates/{template_id}/steps", data={"title": "模板步骤"})

    response = client.post(f"/templates/{template_id}/apply", data={
        "experiment_id": experiment_id,
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith("#step-templates")
    with app.app_context():
        experiment = db.session.get(Experiment, experiment_id)
        assert [step.title for step in experiment.steps] == ["保留步骤", "模板步骤"]


def test_step_template_replace_requires_explicit_confirmation(client, auth, app):
    auth.register()
    client.post("/experiments", data={"title": "需要确认的实验"})
    with app.app_context():
        experiment_id = Experiment.query.filter_by(title="需要确认的实验").one().id
    client.post(f"/experiments/{experiment_id}/steps", data={"title": "原步骤"})
    client.post("/templates/new", data={"kind": "steps", "name": "替换模板"})
    with app.app_context():
        template_id = ExperimentTemplate.query.filter_by(name="替换模板").one().id
    client.post(f"/templates/{template_id}/steps", data={"title": "新步骤"})

    blocked = client.post(f"/templates/{template_id}/apply", data={
        "experiment_id": experiment_id, "apply_mode": "replace",
    })
    assert blocked.status_code == 302
    with app.app_context():
        experiment = db.session.get(Experiment, experiment_id)
        assert [step.title for step in experiment.steps] == ["原步骤"]

    confirmed = client.post(f"/templates/{template_id}/apply", data={
        "experiment_id": experiment_id, "apply_mode": "replace", "replace_confirmed": "1",
    })
    assert confirmed.status_code == 302
    with app.app_context():
        experiment = db.session.get(Experiment, experiment_id)
        assert [step.title for step in experiment.steps] == ["新步骤"]
