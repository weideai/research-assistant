from app import _load_or_create_secret_key, db
from app.models import ApiSetting, Experiment, ExperimentRecord, Sample, Task, User


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

    client.post(f"/experiments/{experiment_id}/steps", data={"title": "细胞铺板", "planned_date": "2026-07-20"})
    client.post(f"/experiments/{experiment_id}/records", data={
        "record_date": "2026-07-20", "operator": "研究员", "conditions": "5 μM, 24h",
        "content": "完成处理并收样。", "result": "成功", "remark": "重复一次。"
    })
    response = client.get(f"/experiments/{experiment_id}")
    assert "细胞铺板".encode() in response.data
    assert "完成处理并收样".encode() in response.data
    with app.app_context():
        assert ExperimentRecord.query.count() == 1


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
