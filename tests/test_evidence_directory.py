from datetime import date
from html import unescape
import re
from urllib.parse import parse_qs, urlsplit

from app import db
from app.models import (
    Experiment, ExperimentAttachment, ExperimentBatch, ExperimentRecord,
    ResearchProject, User,
)


def _build_evidence_tree(app):
    with app.app_context():
        user = User.query.one()
        first_project = ResearchProject(user_id=user.id, title="肿瘤耐药项目", code="PRJ-A")
        second_project = ResearchProject(user_id=user.id, title="代谢对照项目", code="PRJ-B")
        db.session.add_all((first_project, second_project))
        db.session.flush()
        first_experiment = Experiment(
            user_id=user.id, project_id=first_project.id,
            title="药物敏感性计划", code="EXP-A",
        )
        second_experiment = Experiment(
            user_id=user.id, project_id=second_project.id,
            title="代谢检测计划", code="EXP-B",
        )
        db.session.add_all((first_experiment, second_experiment))
        db.session.flush()
        first_batch = ExperimentBatch(
            experiment_id=first_experiment.id, batch_code="RUN-A", status="进行中",
        )
        second_batch = ExperimentBatch(
            experiment_id=second_experiment.id, batch_code="RUN-B", status="进行中",
        )
        db.session.add_all((first_batch, second_batch))
        db.session.flush()
        first_record = ExperimentRecord(
            experiment_id=first_experiment.id, batch_id=first_batch.id,
            record_date=date(2026, 8, 1), content="A 项目独有结果", result="成功",
        )
        second_record = ExperimentRecord(
            experiment_id=second_experiment.id, batch_id=second_batch.id,
            record_date=date(2026, 8, 1), content="B 项目独有结果", result="待确认",
        )
        db.session.add_all((first_record, second_record))
        db.session.flush()
        first_attachment = ExperimentAttachment(
            experiment_id=first_experiment.id, record_id=first_record.id,
            original_name="project-a.csv", relative_path="raw/project-a.csv",
            stored_path="evidence/project-a.csv", category="原始数据",
        )
        second_attachment = ExperimentAttachment(
            experiment_id=second_experiment.id, record_id=second_record.id,
            original_name="project-b.csv", relative_path="raw/project-b.csv",
            stored_path="evidence/project-b.csv", category="原始数据",
        )
        db.session.add_all((first_attachment, second_attachment))
        db.session.commit()
        return {
            "project_a": first_project.id,
            "project_b": second_project.id,
            "experiment_a": first_experiment.id,
            "experiment_b": second_experiment.id,
            "batch_a": first_batch.id,
            "batch_b": second_batch.id,
            "attachment_a": first_attachment.id,
            "attachment_b": second_attachment.id,
        }


def test_reports_and_files_show_project_plan_batch_directory(client, auth, app):
    auth.register()
    ids = _build_evidence_tree(app)

    for path in ("/experiment-reports", "/file-center"):
        response = client.get(path)
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "资料目录" in body
        assert "项目 / 实验计划 / 实验批次" in body
        assert "肿瘤耐药项目" in body
        assert "药物敏感性计划" in body
        assert "RUN-A" in body

    report_scope = client.get(f"/experiment-reports?batch_id={ids['batch_a']}").get_data(as_text=True)
    assert "A 项目独有结果" in report_scope
    assert "B 项目独有结果" not in report_scope
    file_scope = client.get(f"/file-center?project_id={ids['project_a']}").get_data(as_text=True)
    assert "project-a.csv" in file_scope
    assert "project-b.csv" not in file_scope


def test_evidence_scope_rejects_cross_hierarchy_ids(client, auth, app):
    auth.register()
    ids = _build_evidence_tree(app)

    assert client.get(
        f"/experiment-reports?project_id={ids['project_a']}&experiment_id={ids['experiment_b']}"
    ).status_code == 404
    assert client.get(
        f"/file-center?experiment_id={ids['experiment_a']}&batch_id={ids['batch_b']}"
    ).status_code == 404


def test_file_bulk_action_stays_inside_selected_directory(client, auth, app):
    auth.register()
    ids = _build_evidence_tree(app)

    response = client.post("/file-center/bulk", data={
        "index_view": "file_center",
        "project_id": str(ids["project_a"]),
        "experiment_id": str(ids["experiment_a"]),
        "batch_id": str(ids["batch_a"]),
        "selection_scope": "all",
        "category": "全部",
        "action": "delete",
    })

    assert response.status_code == 302
    assert f"project_id={ids['project_a']}" in response.headers["Location"]
    assert f"experiment_id={ids['experiment_a']}" in response.headers["Location"]
    assert f"batch_id={ids['batch_a']}" in response.headers["Location"]
    with app.app_context():
        assert db.session.get(ExperimentAttachment, ids["attachment_a"]).is_deleted is True
        assert db.session.get(ExperimentAttachment, ids["attachment_b"]).is_deleted is False


def test_directory_pagination_keeps_directory_and_result_filters(client, auth, app):
    auth.register()
    with app.app_context():
        user_id = User.query.one().id
        for index in range(9):
            project = ResearchProject(
                user_id=user_id, title=f"目录筛选项目 {index:02d}", code=f"DIR-{index:02d}",
            )
            db.session.add(project)
            db.session.flush()
            experiment = Experiment(
                user_id=user_id, project_id=project.id,
                title=f"目录筛选计划 {index:02d}", code=f"DIR-EXP-{index:02d}",
            )
            db.session.add(experiment)
            db.session.flush()
            batch = ExperimentBatch(
                experiment_id=experiment.id, batch_code=f"DIR-RUN-{index:02d}",
            )
            db.session.add(batch)
            db.session.flush()
            db.session.add(ExperimentRecord(
                experiment_id=experiment.id, batch_id=batch.id,
                record_date=date(2026, 8, 1), content=f"目录结果 {index:02d}",
            ))
        db.session.commit()

    path = (
        "/experiment-reports?directory_q=目录筛选项目&q=目录结果"
        "&category=全部&per_page=12"
    )
    first_body = client.get(path).get_data(as_text=True)
    directory = first_body.split('<aside class="evidence-directory"', 1)[1].split("</aside>", 1)[0]
    assert "目录筛选项目 08" in directory
    assert "目录筛选项目 00" not in directory

    next_queries = []
    for href in re.findall(r'href="([^"]+)"', directory):
        query = parse_qs(urlsplit(unescape(href)).query)
        if query.get("directory_page") == ["2"]:
            next_queries.append(query)
    assert any(
        query.get("directory_q") == ["目录筛选项目"]
        and query.get("q") == ["目录结果"]
        and query.get("category") == ["全部"]
        and query.get("per_page") == ["12"]
        for query in next_queries
    )

    second_body = client.get(f"{path}&directory_page=2").get_data(as_text=True)
    second_directory = second_body.split('<aside class="evidence-directory"', 1)[1].split("</aside>", 1)[0]
    assert "目录筛选项目 00" in second_directory
    assert "目录筛选项目 08" not in second_directory
