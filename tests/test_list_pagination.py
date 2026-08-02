from datetime import date, datetime, timedelta
from html import unescape
import re
from urllib.parse import parse_qs, urlsplit

from app import db
from app.models import (
    BatchParameter, BatchSample, BatchStep, Experiment, ExperimentBatch,
    ExperimentParameter, ExperimentRecord, ExperimentSample, ExperimentStep,
    ResearchProject, Sample, Task, User,
)


def _page_link_queries(body, page_key="page", page_number="2"):
    queries = []
    for href in re.findall(r'href="([^"]+)"', body):
        query = parse_qs(urlsplit(unescape(href)).query)
        if query.get(page_key) == [page_number]:
            queries.append(query)
    return queries


def test_project_pages_do_not_repeat_items_and_keep_filters(client, auth, app):
    auth.register()
    with app.app_context():
        user_id = User.query.one().id
        base_time = datetime(2026, 8, 1, 8, 0)
        for index in range(13):
            db.session.add(ResearchProject(
                user_id=user_id,
                title=f"筛选分页项目 {index:02d}",
                code=f"PAGE-{index:02d}",
                status="进行中",
                updated_at=base_time + timedelta(minutes=index),
            ))
        db.session.commit()

    path = "/projects?q=筛选分页项目&status=进行中&per_page=12"
    first = client.get(path)
    first_body = first.get_data(as_text=True)
    assert first.status_code == 200
    assert first_body.count('class="project-card"') == 12
    assert "筛选分页项目 12" in first_body
    assert "筛选分页项目 00" not in first_body
    assert any(
        query.get("q") == ["筛选分页项目"]
        and query.get("status") == ["进行中"]
        and query.get("per_page") == ["12"]
        for query in _page_link_queries(first_body)
    )

    second_body = client.get(f"{path}&page=2").get_data(as_text=True)
    assert second_body.count('class="project-card"') == 1
    assert "筛选分页项目 00" in second_body
    assert "筛选分页项目 12" not in second_body


def test_task_experiment_and_sample_pages_keep_their_filters(client, auth, app):
    auth.register()
    with app.app_context():
        user_id = User.query.one().id
        project = ResearchProject(user_id=user_id, title="分页归属项目", status="进行中")
        db.session.add(project)
        db.session.flush()
        base_time = datetime(2026, 8, 1, 8, 0)
        for index in range(13):
            stamp = base_time + timedelta(minutes=index)
            db.session.add(Task(
                user_id=user_id, project_id=project.id,
                title=f"筛选任务 {index:02d}", category="实验", status="待办",
                created_at=stamp, updated_at=stamp,
            ))
            db.session.add(Experiment(
                user_id=user_id, project_id=project.id,
                title=f"筛选计划 {index:02d}", status="进行中", updated_at=stamp,
            ))
            db.session.add(Sample(
                user_id=user_id, sample_code=f"FILTER-SAMPLE-{index:02d}",
                sample_type="分页样本", status="可用", updated_at=stamp,
            ))
        db.session.commit()
        project_id = project.id

    cases = (
        (
            f"/tasks?q=筛选任务&status=待办&category=实验&project_id={project_id}&per_page=12",
            "筛选任务 12", "筛选任务 00",
            {"q": "筛选任务", "status": "待办", "category": "实验", "project_id": str(project_id)},
        ),
        (
            f"/experiments?q=筛选计划&status=进行中&project_id={project_id}&per_page=12",
            "筛选计划 12", "筛选计划 00",
            {"q": "筛选计划", "status": "进行中", "project_id": str(project_id)},
        ),
        (
            "/samples?q=FILTER-SAMPLE&status=可用&per_page=12",
            "FILTER-SAMPLE-12", "FILTER-SAMPLE-00",
            {"q": "FILTER-SAMPLE", "status": "可用"},
        ),
    )
    for path, first_item, second_item, expected_filters in cases:
        first_body = client.get(path).get_data(as_text=True)
        assert first_item in first_body
        assert second_item not in first_body
        assert any(
            query.get("per_page") == ["12"]
            and all(query.get(key) == [value] for key, value in expected_filters.items())
            for query in _page_link_queries(first_body)
        )
        second_body = client.get(f"{path}&page=2").get_data(as_text=True)
        assert second_item in second_body
        assert first_item not in second_body


def test_project_bulk_update_rejects_resources_from_another_project(client, auth, app):
    auth.register()
    with app.app_context():
        user_id = User.query.one().id
        first_project = ResearchProject(user_id=user_id, title="项目内批量 A")
        second_project = ResearchProject(user_id=user_id, title="项目内批量 B")
        db.session.add_all((first_project, second_project))
        db.session.flush()
        foreign_experiment = Experiment(
            user_id=user_id, project_id=second_project.id,
            title="不可跨项目编辑的计划", status="未开始",
        )
        db.session.add(foreign_experiment)
        db.session.flush()
        foreign_batch = ExperimentBatch(
            experiment_id=foreign_experiment.id,
            batch_code="FOREIGN-RUN", status="未开始",
        )
        db.session.add(foreign_batch)
        db.session.commit()
        first_project_id = first_project.id
        foreign_experiment_id = foreign_experiment.id
        foreign_batch_id = foreign_batch.id

    base_form = {
        "experiment_status": "完成", "batch_status": "完成",
        "owner_mode": "keep", "operator_mode": "keep",
    }
    assert client.post(
        f"/projects/{first_project_id}/resources/bulk",
        data={**base_form, "experiment_ids": str(foreign_experiment_id)},
    ).status_code == 404
    assert client.post(
        f"/projects/{first_project_id}/resources/bulk",
        data={**base_form, "batch_ids": str(foreign_batch_id)},
    ).status_code == 404
    with app.app_context():
        assert db.session.get(Experiment, foreign_experiment_id).status == "未开始"
        assert db.session.get(ExperimentBatch, foreign_batch_id).status == "未开始"


def test_index_bulk_endpoints_reject_another_users_ids(client, auth, app):
    auth.register(email="bulk-owner@example.com")
    with app.app_context():
        owner_id = User.query.filter_by(email="bulk-owner@example.com").one().id
        task = Task(user_id=owner_id, title="私有批量任务", status="待办")
        experiment = Experiment(user_id=owner_id, title="私有批量计划", status="未开始")
        sample = Sample(user_id=owner_id, sample_code="PRIVATE-BULK-SAMPLE", status="可用")
        db.session.add_all((task, experiment, sample))
        db.session.commit()
        task_id, experiment_id, sample_id = task.id, experiment.id, sample.id

    auth.logout()
    auth.register(email="bulk-other@example.com")
    assert client.post("/tasks/bulk", data={
        "task_ids": str(task_id), "bulk_status": "完成",
        "bulk_category": "__keep__", "bulk_priority": "__keep__",
        "project_mode": "keep",
    }).status_code == 404
    assert client.post("/experiments/bulk", data={
        "experiment_ids": str(experiment_id), "bulk_status": "完成",
        "owner_mode": "keep", "project_mode": "keep",
    }).status_code == 404
    assert client.post("/samples/bulk", data={
        "sample_ids": str(sample_id), "bulk_status": "已用完",
        "location_mode": "keep",
    }).status_code == 404
    with app.app_context():
        assert db.session.get(Task, task_id).status == "待办"
        assert db.session.get(Experiment, experiment_id).status == "未开始"
        assert db.session.get(Sample, sample_id).status == "可用"


def test_detail_page_paginators_are_independent(client, auth, app):
    auth.register()
    with app.app_context():
        user_id = User.query.one().id
        project = ResearchProject(user_id=user_id, title="详情分页项目")
        experiment = Experiment(user_id=user_id, project=project, title="详情分页计划")
        db.session.add_all((project, experiment))
        db.session.flush()

        batches = []
        samples = []
        for index in range(9):
            batch = ExperimentBatch(
                experiment_id=experiment.id, batch_code=f"PAGE-BATCH-{index:02d}",
                status="进行中",
            )
            sample = Sample(
                user_id=user_id, sample_code=f"PAGE-SAMPLE-{index:02d}", status="可用",
            )
            db.session.add_all((batch, sample))
            batches.append(batch)
            samples.append(sample)
        db.session.flush()

        for index in range(9):
            position = index + 1
            db.session.add(ExperimentStep(
                experiment_id=experiment.id, position=position,
                title=f"PAGE STEP {position:02d}",
            ))
            db.session.add(ExperimentParameter(
                experiment_id=experiment.id, position=position,
                name=f"PAGE PARAM {position:02d}",
            ))
            db.session.add(ExperimentSample(
                experiment_id=experiment.id, sample_id=samples[index].id,
                role=f"PAGE ROLE {position:02d}",
            ))
            db.session.add(ExperimentRecord(
                experiment_id=experiment.id, batch_id=batches[0].id,
                record_date=date(2026, 7, 1) + timedelta(days=index),
                content=f"PAGE RECORD {index:02d}",
            ))
            db.session.add(BatchStep(
                batch_id=batches[0].id, position=position,
                title=f"BATCH STEP {position:02d}",
            ))
            db.session.add(BatchParameter(
                batch_id=batches[0].id, position=position,
                name=f"BATCH PARAM {position:02d}",
            ))
            db.session.add(BatchSample(
                batch_id=batches[0].id, sample_id=samples[index].id,
                role=f"BATCH ROLE {position:02d}",
            ))
        db.session.commit()
        experiment_id = experiment.id
        batch_id = batches[0].id

    experiment_body = client.get(
        f"/experiments/{experiment_id}?batch_page=2&record_page=2&step_page=2"
        "&sample_page=2&parameter_page=2"
    ).get_data(as_text=True)
    assert experiment_body.count("第 2 / 2 页") >= 5
    for label in (
        "PAGE-BATCH-00", "PAGE RECORD 00", "PAGE STEP 09",
        "PAGE PARAM 09", "PAGE ROLE 09",
    ):
        assert label in experiment_body

    batch_body = client.get(
        f"/batches/{batch_id}?step_page=2&record_page=2"
        "&parameter_page=2&sample_page=2"
    ).get_data(as_text=True)
    assert batch_body.count("第 2 / 2 页") >= 4
    for label in (
        "BATCH STEP 09", "PAGE RECORD 00", "BATCH PARAM 09", "BATCH ROLE 09",
    ):
        assert label in batch_body
