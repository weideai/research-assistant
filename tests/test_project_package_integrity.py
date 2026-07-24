import pytest

from app import db
from app.models import Experiment, ExperimentBatch, ExperimentRecord, ResearchProject
from app.project_package import ProjectPackageError, build_project_package


def test_project_package_refuses_to_silently_drop_unassigned_record(client, auth, app, monkeypatch):
    auth.register()
    client.post("/projects", data={"title": "数据完整性项目", "code": "INTEGRITY-01"})
    with app.app_context():
        project = ResearchProject.query.filter_by(code="INTEGRITY-01").one()
        experiment = Experiment(
            user_id=project.user_id,
            project_id=project.id,
            title="旧实验记录归档检查",
            code="LEGACY-01",
        )
        db.session.add(experiment)
        db.session.flush()
        other_experiment = Experiment(
            user_id=project.user_id,
            project_id=project.id,
            title="错误归属目标",
            code="OTHER-01",
        )
        db.session.add(other_experiment)
        db.session.flush()
        wrong_batch = ExperimentBatch(
            experiment_id=other_experiment.id,
            batch_code="WRONG-OWNER",
        )
        db.session.add(wrong_batch)
        db.session.flush()
        db.session.add(ExperimentRecord(
            experiment_id=experiment.id,
            batch_id=wrong_batch.id,
            content="这条旧记录不能在项目包中被静默遗漏。",
        ))
        db.session.commit()

        monkeypatch.setattr(
            "app.project_package.tempfile.NamedTemporaryFile",
            lambda *_args, **_kwargs: pytest.fail("不应开始生成不完整的项目包"),
        )

        with pytest.raises(ProjectPackageError, match="未归档或执行归属异常"):
            build_project_package(project, app.config["ATTACHMENT_UPLOAD_DIR"])
