from app import db
from app.models import Executor, Experiment, ExperimentBatch, ResearchProject, User, WorkspaceSetting


def test_settings_is_reachable(client, auth):
    auth.register()

    settings = client.get("/settings")
    assert settings.status_code == 200
    assert "实验执行保存".encode() in settings.data
    assert "API 设置".encode() in settings.data


def test_experiment_creation_clears_identity_prefill_and_hides_project_selector(client, auth, app):
    auth.register(name="本地研究者")
    page = client.get("/experiments")
    assert page.status_code == 200
    assert "所属项目".encode() not in page.data
    assert "全部项目".encode() not in page.data
    assert 'value="本地研究者"'.encode() not in page.data
    assert "可选：便于检索的计划编号".encode() in page.data

    response = client.post("/experiments", data={"title": "空白身份实验"})
    assert response.status_code == 302
    with app.app_context():
        item = Experiment.query.one()
        assert item.owner == ""
        assert item.code == ""
        experiment_id = item.id
    detail = client.get(f"/experiments/{experiment_id}")
    assert detail.status_code == 200
    assert "所属项目".encode() not in detail.data


def test_executor_can_be_selected_saved_and_reused(client, auth, app):
    auth.register()
    client.post("/settings", data={
        "execution_save_mode": "stay",
        "execution_autosave": "1",
        "execution_autosave_interval": "60",
        "executor_options": "样本管理员\n实验一组",
    })
    with app.app_context():
        setting = WorkspaceSetting.query.one()
        assert setting.execution_autosave is True
        assert setting.executor_options_json == '["样本管理员", "实验一组"]'

    client.post("/experiments", data={"title": "执行者回显测试"})
    with app.app_context():
        experiment_id = Experiment.query.one().id
    response = client.post(f"/experiments/{experiment_id}/batches", data={
        "batch_code": "RUN-EXECUTOR", "operator": "样本管理员",
    })
    assert response.status_code == 302
    with app.app_context():
        batch = ExperimentBatch.query.one()
        assert batch.operator == "样本管理员"
        batch_id = batch.id

    page = client.get(f"/batches/{batch_id}")
    assert "样本管理员".encode() in page.data
    response = client.post(f"/batches/{batch_id}", data={
        "batch_code": "RUN-EXECUTOR", "repeat_kind": "独立实验", "repeat_number": "1",
        "operator": "实验一组", "status": "未开始",
    })
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(ExperimentBatch, batch_id).operator == "实验一组"


def test_managed_executor_can_be_added_and_disabled(client, auth, app):
    auth.register()

    page = client.get("/settings")
    assert page.status_code == 200
    assert "添加执行者".encode() in page.data
    assert b'name="executor_options"' not in page.data

    response = client.post("/settings/executors", data={
        "name": "张研究员", "role": "样本管理员",
    })
    assert response.status_code == 302
    with app.app_context():
        executor = Executor.query.one()
        assert executor.name == "张研究员"
        assert executor.role == "样本管理员"
        executor_id = executor.id

    client.post(f"/settings/executors/{executor_id}/toggle")
    with app.app_context():
        assert db.session.get(Executor, executor_id).is_active is False
    client.post("/settings/executors", data={"name": "张研究员", "role": "实验执行"})
    with app.app_context():
        executor = db.session.get(Executor, executor_id)
        assert executor.is_active is True
        assert executor.role == "实验执行"


def test_project_can_choose_its_executors_and_scope_execution_suggestions(client, auth, app):
    auth.register()
    with app.app_context():
        user_id = User.query.filter_by(email="researcher@example.com").one().id
        project = ResearchProject(user_id=user_id, title="项目甲")
        first = Executor(user_id=user_id, name="项目执行者", role="实验组")
        second = Executor(user_id=user_id, name="未选执行者", role="备用")
        db.session.add_all([project, first, second])
        db.session.commit()
        project_id, first_id, second_id = project.id, first.id, second.id

    page = client.get(f"/experiments?project_id={project_id}")
    assert page.status_code == 200
    assert "项目甲 的执行者".encode() in page.data
    assert "项目执行者".encode() in page.data
    response = client.post(f"/projects/{project_id}/executors", data={
        "executor_ids": [str(first_id)],
    })
    assert response.status_code == 302
    with app.app_context():
        project = db.session.get(ResearchProject, project_id)
        assert [executor.id for executor in project.executors] == [first_id]

    client.post("/experiments", data={"title": "项目执行实验", "project_id": str(project_id)})
    with app.app_context():
        experiment = Experiment.query.one()
        experiment_id = experiment.id
    client.post(f"/experiments/{experiment_id}/batches", data={"operator": ""})
    with app.app_context():
        batch_id = ExperimentBatch.query.one().id
    batch_page = client.get(f"/batches/{batch_id}")
    assert "项目执行者".encode() in batch_page.data
    assert batch_page.data.index("项目执行者".encode()) < batch_page.data.index("未选执行者".encode())


def test_project_executor_selection_rejects_another_users_executor(client, auth, app):
    auth.register()
    with app.app_context():
        first_user_id = User.query.filter_by(email="researcher@example.com").one().id
        project = ResearchProject(user_id=first_user_id, title="项目甲")
        executor = Executor(user_id=first_user_id, name="私有执行者")
        db.session.add_all([project, executor])
        db.session.commit()
        project_id, executor_id = project.id, executor.id

    auth.logout()
    auth.register(email="second@example.com", name="第二位研究者")
    with app.app_context():
        second_user_project = ResearchProject(
            user_id=User.query.filter_by(email="second@example.com").one().id,
            title="项目乙",
        )
        db.session.add(second_user_project)
        db.session.commit()
        second_project_id = second_user_project.id
    response = client.post(f"/projects/{second_project_id}/executors", data={
        "executor_ids": [str(executor_id)],
    })
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(ResearchProject, project_id).executors == []
