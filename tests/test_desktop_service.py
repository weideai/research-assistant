import pytest

from app import db
from app.models import LabRecordRevision, User
from app.services.desktop_workspace import ConflictError, DesktopApplicationService


def service_with_user(app):
    with app.app_context():
        user = User(name="本地研究者", email="desktop@example.invalid", password_hash="local", role="system_admin")
        db.session.add(user)
        db.session.commit()
    return DesktopApplicationService(app)


def test_record_centric_desktop_workflow(app):
    service = service_with_user(app)
    project = service.create_project({"title": "蛋白表达优化", "code": "PRO-01", "objective": "优化诱导条件"})
    record = service.create_record({"project_id": project["id"], "title": "IPTG 梯度实验", "experiment_date": "2026-08-11"})

    saved = service.update_record({
        "id": record["id"],
        "status": "in_progress",
        "objective": "比较不同 IPTG 浓度下的蛋白表达量",
        "expected_result": "中等浓度获得较高可溶表达",
        "steps": [
            {"title": "配置诱导组", "instruction": "设置四个 IPTG 浓度。"},
            {"title": "收集样本", "instruction": "诱导后按时间点取样。"},
        ],
    }, record["row_version"])

    assert saved["row_version"] == 2
    assert saved["project_title"] == "蛋白表达优化"
    assert [step["position"] for step in saved["steps"]] == [1, 2]
    assert service.dashboard()["counts"]["in_progress"] == 1
    with app.app_context():
        assert LabRecordRevision.query.count() == 1


def test_record_update_rejects_stale_row_version(app):
    service = service_with_user(app)
    project = service.create_project({"title": "项目 A"})
    record = service.create_record({"project_id": project["id"], "title": "记录 A"})
    service.update_record({"id": record["id"], "objective": "第一次保存"}, record["row_version"])

    with pytest.raises(ConflictError):
        service.update_record({"id": record["id"], "objective": "过期覆盖"}, record["row_version"])
