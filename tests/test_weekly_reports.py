import io
import zipfile
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app import db
from app.models import (
    Experiment, ExperimentAttachment, ExperimentBatch, ExperimentRecord, Task,
    ResearchProject, User, WeeklyReport, WeeklyReportUpdate, utcnow,
)


def _create_record(client, app, title="文件中心实验"):
    client.post("/experiments", data={"title": title, "code": "FILE-01"})
    with app.app_context():
        experiment_id = Experiment.query.filter_by(title=title).one().id
    client.post(f"/experiments/{experiment_id}/batches", data={"batch_code": "RUN-01"})
    with app.app_context():
        batch_id = ExperimentBatch.query.filter_by(experiment_id=experiment_id).one().id
    client.post(f"/experiments/{experiment_id}/records", data={
        "batch_id": str(batch_id),
        "record_date": "2026-07-31",
        "content": "完成检测并保存原始数据。",
        "result": "成功",
    })
    with app.app_context():
        record_id = ExperimentRecord.query.filter_by(experiment_id=experiment_id).one().id
    return experiment_id, record_id


def test_weekly_report_library_upload_search_update_and_download(client, auth, app):
    auth.register()
    response = client.post(
        "/reports/weekly/upload",
        data={
            "report_file": (io.BytesIO(b"weekly presentation"), "2026-W31-lab-report.pptx"),
            "title": "第 31 周实验进展",
            "report_date": "2026-07-31",
            "period_start": "2026-07-25",
            "period_end": "2026-07-31",
            "status": "待反馈",
            "summary": "完成温度条件复核。",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302

    with app.app_context():
        report = WeeklyReport.query.one()
        report_id = report.id
        stored_path = app.config["WEEKLY_REPORT_UPLOAD_DIR"] + "/" + report.stored_path
        assert report.title == "第 31 周实验进展"
        assert report.original_name == "2026-W31-lab-report.pptx"
        assert report.report_date.isoformat() == "2026-07-31"
        assert report.folder_path.endswith(f"report-{report.id}")

    assert app.config["WEEKLY_REPORT_UPLOAD_DIR"]
    assert Path(stored_path).is_file()

    page = client.get(f"/reports/presentation?report_id={report_id}")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "周报资料库" in body
    assert "第 31 周实验进展" in body
    assert "2026-W31-lab-report.pptx" in body
    assert "反馈与修改日常" in body

    search = client.get("/reports/presentation?q=W31-lab")
    assert search.status_code == 200
    assert "第 31 周实验进展" in search.get_data(as_text=True)

    update = client.post(f"/reports/weekly/{report_id}/updates", data={
        "entry_date": "2026-08-01",
        "kind": "反馈",
        "update_status": "待处理",
        "content": "补充对照组说明。",
    })
    assert update.status_code == 302
    with app.app_context():
        item = WeeklyReportUpdate.query.one()
        update_id = item.id
        assert item.content == "补充对照组说明。"

    toggle = client.post(f"/reports/weekly-updates/{update_id}/toggle")
    assert toggle.status_code == 302
    with app.app_context():
        assert WeeklyReportUpdate.query.one().status == "已完成"

    download = client.get(f"/reports/weekly/{report_id}/download")
    assert download.status_code == 200
    assert download.data == b"weekly presentation"
    assert download.mimetype == "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def test_weekly_report_page_exposes_bulk_edit_and_delete_controls(client, auth, app):
    auth.register()
    with app.app_context():
        user_id = User.query.one().id
        db.session.add_all([
            WeeklyReport(
                user_id=user_id, title=f"可批量周报 {index}",
                original_name=f"bulk-{index}.pptx", report_date=date(2026, 8, index + 1),
            )
            for index in range(2)
        ])
        db.session.commit()

    body = client.get("/reports/presentation").get_data(as_text=True)
    assert 'id="weekly-report-bulk-form"' in body
    assert 'action="/reports/weekly/bulk"' in body
    assert "批量管理当前页周报" in body
    assert "批量保存" in body
    assert "批量移入回收站" in body
    assert body.count('name="report_ids"') == 2
    assert "删除周报" in body


def test_weekly_generator_uses_bounded_searchable_selection_directories(client, auth, app):
    auth.register()
    with app.app_context():
        user_id = User.query.one().id
        db.session.add_all([
            Experiment(user_id=user_id, title=f"目录实验 {index:02d}", code=f"DIR-{index:02d}")
            for index in range(9)
        ])
        db.session.commit()

    body = client.get("/reports/presentation").get_data(as_text=True)
    assert body.count("data-local-directory") == 2
    assert 'data-directory-mode="multiple"' in body
    assert 'data-directory-mode="single"' in body
    assert "查找实验名称、编号或状态" in body
    assert "查找 Skill 名称、用途或主题" in body
    assert body.count('data-directory-page-size') == 2
    assert all(f'<option value="{value}">{value}</option>' in body for value in (8, 16, 32))
    assert "全选本页" in body
    assert "选择筛选全部" in body
    assert "翻页不会清除已选择实验" in body
    assert body.count("data-directory-item") >= 11


def test_weekly_report_bulk_update_and_delete_preserve_files(client, auth, app):
    auth.register()
    client.post("/projects", data={"title": "周报归档项目"})
    with app.app_context():
        user_id = User.query.one().id
        project_id = ResearchProject.query.filter_by(title="周报归档项目").one().id
        reports = [
            WeeklyReport(
                user_id=user_id, title=f"待整理周报 {index}",
                original_name=f"weekly-{index}.pptx", report_date=date(2026, 8, index + 1),
                summary="原摘要",
            )
            for index in range(3)
        ]
        db.session.add_all(reports)
        db.session.flush()
        selected_ids = [reports[0].id, reports[1].id]
        selected_report_id = reports[0].id
        untouched_id = reports[2].id
        report_dir = Path(app.config["WEEKLY_REPORT_UPLOAD_DIR"]) / f"user-{user_id}" / f"report-{reports[0].id}"
        report_dir.mkdir(parents=True, exist_ok=True)
        stored_file = report_dir / reports[0].original_name
        stored_file.write_bytes(b"weekly")
        reports[0].stored_path = stored_file.relative_to(app.config["WEEKLY_REPORT_UPLOAD_DIR"]).as_posix()
        db.session.commit()

    updated = client.post("/reports/weekly/bulk", data={
        "report_ids": [str(item_id) for item_id in selected_ids],
        "action": "update", "bulk_status": "已归档",
        "project_mode": "replace", "bulk_project_id": str(project_id),
        "summary_mode": "append", "bulk_summary": "批量补充",
        "q": "待整理", "return_status": "全部", "page": "1", "per_page": "20",
        "return_report_id": str(selected_report_id),
    })
    assert updated.status_code == 302
    redirect_query = parse_qs(urlparse(updated.headers["Location"]).query)
    assert redirect_query == {
        "report_id": [str(selected_report_id)], "q": ["待整理"],
        "status": ["全部"], "page": ["1"], "per_page": ["20"],
    }
    with app.app_context():
        selected = [db.session.get(WeeklyReport, item_id) for item_id in selected_ids]
        untouched = db.session.get(WeeklyReport, untouched_id)
        assert {item.status for item in selected} == {"archived"}
        assert {item.project_id for item in selected} == {project_id}
        assert all(item.summary == "原摘要\n批量补充" for item in selected)
        assert untouched.status == "draft"
        assert untouched.project_id is None
        assert untouched.summary == "原摘要"

    deleted = client.post("/reports/weekly/bulk", data={
        "report_ids": [str(item_id) for item_id in selected_ids],
        "action": "delete", "return_report_id": str(selected_report_id),
    })
    assert deleted.status_code == 302
    assert "report_id=" not in deleted.headers["Location"]
    assert stored_file.is_file()
    with app.app_context():
        assert all(db.session.get(WeeklyReport, item_id).is_deleted for item_id in selected_ids)
        assert not db.session.get(WeeklyReport, untouched_id).is_deleted


def test_weekly_report_bulk_rejects_another_users_ids(client, auth, app):
    auth.register(email="weekly-owner@example.com")
    with app.app_context():
        owner_id = User.query.filter_by(email="weekly-owner@example.com").one().id
        report = WeeklyReport(
            user_id=owner_id, title="私有周报", original_name="private.pptx",
            report_date=date(2026, 8, 1),
        )
        db.session.add(report)
        db.session.commit()
        report_id = report.id

    auth.logout()
    auth.register(email="weekly-other@example.com")
    response = client.post("/reports/weekly/bulk", data={
        "report_ids": str(report_id), "action": "delete",
    })
    assert response.status_code == 404
    with app.app_context():
        assert not db.session.get(WeeklyReport, report_id).is_deleted


def test_file_center_search_and_bulk_download_preserve_experiment_folder(client, auth, app):
    auth.register()
    experiment_id, record_id = _create_record(client, app)
    response = client.post(
        f"/records/{record_id}/attachments",
        data={"files": [
            (io.BytesIO(b"a"), "raw.csv"),
            (io.BytesIO(b"b"), "raw.csv"),
        ]},
        content_type="multipart/form-data",
    )
    assert response.status_code == 302

    with app.app_context():
        attachments = ExperimentAttachment.query.order_by(ExperimentAttachment.id).all()
        attachment_ids = [item.id for item in attachments]
        assert len(attachments) == 2

    center = client.get("/file-center?q=raw.csv")
    assert center.status_code == 200
    assert "文件中心" in center.get_data(as_text=True)
    assert center.get_data(as_text=True).count("raw.csv") >= 2

    archive = client.post("/file-center/download", data={
        "attachment_ids": [str(item_id) for item_id in attachment_ids],
    })
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.data)) as bundle:
        names = bundle.namelist()
    assert names[0].startswith("文件中心实验/")
    assert len(names) == 2
    assert len(set(names)) == 2
    assert all(name.startswith("文件中心实验/") for name in names)


def test_file_center_pagination_and_select_all_matches_cover_every_page(client, auth, app):
    auth.register()
    experiment_id, record_id = _create_record(client, app, title="跨页文件实验")
    uploads = [
        (io.BytesIO(f"row-{index}".encode()), f"raw-{index:02d}.csv")
        for index in range(23)
    ]
    response = client.post(
        f"/records/{record_id}/attachments",
        data={"files": uploads}, content_type="multipart/form-data",
    )
    assert response.status_code == 302

    first_page = client.get("/file-center?q=raw-&per_page=20").get_data(as_text=True)
    assert first_page.count("data-attachment-select form=") == 20
    assert "全选本页" in first_page
    assert "全选全部 23 个匹配文件" in first_page
    assert "第 1 / 2 页" in first_page

    second_page = client.get("/file-center?q=raw-&per_page=20&page=2").get_data(as_text=True)
    assert second_page.count("data-attachment-select form=") == 3
    experiment_page = client.get(
        f"/experiments/{experiment_id}/files?q=raw-&per_page=20"
    ).get_data(as_text=True)
    assert "全选全部 23 个匹配文件" in experiment_page

    archive = client.post("/file-center/bulk", data={
        "selection_scope": "all", "q": "raw-", "category": "全部",
        "per_page": "20", "page": "1", "action": "download",
    })
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.data)) as bundle:
        assert len(bundle.namelist()) == 23

    updated = client.post("/file-center/bulk", data={
        "selection_scope": "all", "q": "raw-", "category": "全部",
        "per_page": "20", "page": "1", "action": "update",
        "bulk_category": "分析结果", "tags_mode": "replace",
        "bulk_tags": "跨页已整理", "description_mode": "replace",
        "bulk_description": "由文件中心批量更新",
    })
    assert updated.status_code == 302
    with app.app_context():
        items = ExperimentAttachment.query.filter_by(experiment_id=experiment_id).all()
        assert len(items) == 23
        assert {item.category for item in items} == {"分析结果"}
        assert {item.tags for item in items} == {"跨页已整理"}

    deleted = client.post("/file-center/bulk", data={
        "selection_scope": "all", "q": "raw-", "category": "分析结果",
        "per_page": "20", "page": "1", "action": "delete",
    })
    assert deleted.status_code == 302
    with app.app_context():
        assert ExperimentAttachment.query.filter_by(
            experiment_id=experiment_id, is_deleted=True,
        ).count() == 23


def test_weekly_and_recycle_indexes_paginate_without_losing_selected_detail(client, auth, app):
    auth.register()
    with app.app_context():
        user_id = User.query.one().id
        reports = []
        for index in range(13):
            report = WeeklyReport(
                user_id=user_id, title=f"分页周报 {index:02d}",
                original_name=f"weekly-{index:02d}.pptx",
                report_date=date(2026, 8, 1) - timedelta(days=index),
            )
            db.session.add(report)
            reports.append(report)
        for index in range(23):
            db.session.add(Task(
                user_id=user_id, title=f"已删除任务 {index:02d}",
                is_deleted=True, deleted_at=utcnow(),
            ))
        db.session.commit()
        oldest_report_id = reports[-1].id

    weekly_first = client.get("/reports/presentation?per_page=10").get_data(as_text=True)
    assert weekly_first.count('class="weekly-index-item ') == 10
    assert "第 1 / 2 页" in weekly_first
    weekly_second = client.get("/reports/presentation?per_page=10&page=2").get_data(as_text=True)
    assert weekly_second.count('class="weekly-index-item ') == 3

    selected = client.get(
        f"/reports/presentation?per_page=10&page=1&report_id={oldest_report_id}"
    ).get_data(as_text=True)
    assert "分页周报 12" in selected
    assert "weekly-12.pptx" in selected

    recycle_first = client.get(
        "/recycle-bin?kind=task&per_page=20"
    ).get_data(as_text=True)
    assert recycle_first.count('class="recycle-row"') == 20
    assert "23 个匹配项目" in recycle_first
    assert "第 1 / 2 页" in recycle_first
    recycle_second = client.get(
        "/recycle-bin?kind=task&per_page=20&page=2"
    ).get_data(as_text=True)
    assert recycle_second.count('class="recycle-row"') == 3
