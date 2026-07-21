from app import _load_or_create_secret_key, db
from app.models import ApiSetting, Experiment, ExperimentRecord, ExperimentStep, Sample, Task, User


def test_register_login_logout(client, auth):
    response = auth.register()
    assert response.status_code == 200
    assert "早上好".encode() in response.data

    response = auth.logout()
    assert "登录科研工作台".encode() in response.data

    response = auth.login(password="wrong-password")
    assert "邮箱或密码不正确".encode() in response.data


def test_task_crud_and_toggle(client, auth, app):
    auth.register()
    response = client.post("/tasks", data={
        "title": "完成 PCR", "category": "实验", "priority": "高", "deadline": "2026-07-20"
    }, follow_redirects=True)
    assert "完成 PCR".encode() in response.data

    with app.app_context():
        task = Task.query.one()
        task_id = task.id
        assert task.status == "待办"

    client.post(f"/tasks/{task_id}/toggle")
    with app.app_context():
        assert db.session.get(Task, task_id).status == "完成"

    client.post(f"/tasks/{task_id}/delete")
    with app.app_context():
        assert db.session.get(Task, task_id) is None


def test_experiment_steps_and_records(client, auth, app):
    auth.register()
    response = client.post("/experiments", data={
        "title": "WB 验证", "code": "EXP-001", "status": "进行中", "objective": "验证蛋白表达"
    })
    assert response.status_code == 302

    with app.app_context():
        experiment_id = Experiment.query.one().id

    client.post(f"/experiments/{experiment_id}/steps", data={
        "title": "细胞铺板", "planned_date": "2026-07-20", "operator": "张同学",
        "description": "每孔接种 2×10^5 个细胞",
    })
    client.post(f"/experiments/{experiment_id}/records", data={
        "record_date": "2026-07-20", "operator": "研究员", "conditions": "5 μM, 24h",
        "content": "完成处理并收样。", "result": "成功", "remark": "重复一次。"
    })
    response = client.get(f"/experiments/{experiment_id}")
    assert "细胞铺板".encode() in response.data
    assert "张同学".encode() in response.data
    assert "每孔接种".encode() in response.data
    assert "完成处理并收样".encode() in response.data
    with app.app_context():
        assert ExperimentRecord.query.count() == 1


def test_step_and_record_can_be_viewed_edited_and_exported(client, auth, app):
    auth.register()
    client.post("/experiments", data={
        "title": "药物处理实验", "code": "EXP-EDIT-001", "status": "进行中",
        "owner": "李同学", "objective": "验证药物响应", "start_date": "2026-07-20",
    })
    with app.app_context():
        experiment_id = Experiment.query.one().id

    client.post(f"/experiments/{experiment_id}/steps", data={
        "title": "加药", "operator": "李同学", "planned_date": "2026-07-21",
        "description": "终浓度 5 μM",
    })
    client.post(f"/experiments/{experiment_id}/records", data={
        "record_date": "2026-07-21", "operator": "李同学", "conditions": "37°C",
        "content": "完成加药并观察细胞。", "result": "待确认", "remark": "24h 后复查。",
    })
    with app.app_context():
        step_id = ExperimentStep.query.one().id
        record_id = ExperimentRecord.query.one().id

    response = client.post(f"/steps/{step_id}/edit", data={
        "title": "加药处理", "operator": "王同学", "planned_date": "2026-07-22",
        "description": "终浓度调整为 10 μM",
    }, follow_redirects=True)
    assert "加药处理".encode() in response.data
    assert "10 μM".encode() in response.data

    client.post(f"/steps/{step_id}/toggle")
    with app.app_context():
        step = db.session.get(ExperimentStep, step_id)
        assert step.is_done is True
        assert step.completed_date is not None

    response = client.get(f"/records/{record_id}")
    assert response.status_code == 200
    assert "完成加药并观察细胞".encode() in response.data
    response = client.post(f"/records/{record_id}", data={
        "record_date": "2026-07-22", "operator": "王同学", "conditions": "5% CO2",
        "content": "复查后细胞状态稳定。", "result": "成功", "remark": "进入下一步骤。",
    }, follow_redirects=True)
    assert "复查后细胞状态稳定".encode() in response.data
    assert "进入下一步骤".encode() in response.data

    export = client.get(f"/experiments/{experiment_id}/export.md")
    assert export.status_code == 200
    assert export.mimetype == "text/markdown"
    assert "EXP-EDIT-001".encode() in export.data
    assert "加药处理".encode() in export.data
    assert "复查后细胞状态稳定".encode() in export.data
    assert "filename*=UTF-8''" in export.headers["Content-Disposition"]


def test_experiment_children_and_export_are_scoped_to_owner(client, auth, app):
    auth.register(email="owner@example.com")
    client.post("/experiments", data={"title": "私有实验", "status": "进行中"})
    with app.app_context():
        experiment = Experiment.query.one()
        step = ExperimentStep(experiment_id=experiment.id, title="私有步骤")
        record = ExperimentRecord(experiment_id=experiment.id, content="私有记录")
        db.session.add_all([step, record])
        db.session.commit()
        experiment_id, step_id, record_id = experiment.id, step.id, record.id

    auth.logout()
    auth.register(email="other@example.com")
    assert client.get(f"/steps/{step_id}/edit").status_code == 404
    assert client.get(f"/records/{record_id}").status_code == 404
    assert client.get(f"/experiments/{experiment_id}/export.md").status_code == 404


def test_user_cannot_access_another_users_data(client, auth, app):
    auth.register(email="one@example.com")
    with app.app_context():
        first = User.query.filter_by(email="one@example.com").one()
        sample = Sample(user_id=first.id, sample_code="PRIVATE-001")
        db.session.add(sample)
        db.session.commit()
        sample_id = sample.id
    auth.logout()
    auth.register(email="two@example.com")
    assert client.get(f"/samples/{sample_id}/edit").status_code == 404
    assert client.post(f"/samples/{sample_id}/delete").status_code == 404


def test_ai_local_mode_can_save_record(client, auth, app, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    auth.register()
    client.post("/experiments", data={"title": "AI 测试实验", "status": "进行中"})
    with app.app_context():
        experiment_id = Experiment.query.one().id

    response = client.post("/ai", data={"note": "WB 已完成，β-actin 正常，目标蛋白下降。"})
    assert "本地规则生成的草稿".encode() in response.data

    client.post("/ai/save", data={
        "experiment_id": experiment_id, "record_date": "2026-07-20", "content": "WB 已完成。",
        "conditions": "", "result": "成功", "remark": "人工核对完成。"
    })
    with app.app_context():
        assert ExperimentRecord.query.one().result == "成功"


def test_csv_export_is_scoped_to_current_user(client, auth, app):
    auth.register()
    client.post("/samples", data={"sample_code": "OS-001", "status": "可用"})
    response = client.get("/export/samples.csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert b"OS-001" in response.data


def test_api_settings_encrypt_key_and_drive_ai_request(client, auth, app, monkeypatch):
    auth.register()
    raw_key = "sk-secret-value"
    response = client.post("/settings/api", data={
        "action": "save",
        "is_enabled": "1",
        "api_url": "http://127.0.0.1:1234/v1/chat/completions",
        "api_key": raw_key,
        "model": "local-medical-model",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert raw_key.encode() not in response.data

    with app.app_context():
        setting = ApiSetting.query.one()
        assert raw_key not in setting.encrypted_api_key
        assert setting.get_api_key() == raw_key

    captured = {}

    def fake_organize(note, config):
        captured.update({"note": note, "config": config})
        return {"title": "记录", "objective": "", "conditions": "", "content": note,
                "result": "待确认", "remark": ""}, "api"

    monkeypatch.setattr("app.main.organize_note", fake_organize)
    client.post("/ai", data={"note": "完成 WB。"})
    assert captured["config"].api_url == "http://127.0.0.1:1234/v1/chat/completions"
    assert captured["config"].api_key == raw_key
    assert captured["config"].model == "local-medical-model"
    assert captured["config"].source == "user"


def test_api_settings_can_test_models_without_saving_key(client, auth, app, monkeypatch):
    auth.register()
    monkeypatch.setattr("app.main.fetch_models", lambda config: ["lab-model-1", "lab-model-2"])
    response = client.post("/settings/api", data={
        "action": "test",
        "is_enabled": "1",
        "api_url": "http://127.0.0.1:1234/v1",
        "api_key": "temporary-key",
        "model": "lab-model-1",
    })
    assert response.status_code == 200
    assert "连接成功".encode() in response.data
    assert b"lab-model-2" in response.data
    with app.app_context():
        assert ApiSetting.query.count() == 0


def test_generated_secret_key_is_random_and_persistent(tmp_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    first = _load_or_create_secret_key(tmp_path)
    second = _load_or_create_secret_key(tmp_path)

    assert first == second
    assert len(first) >= 48
    assert (tmp_path / "secret_key").read_text(encoding="utf-8") == first
