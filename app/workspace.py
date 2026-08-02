import json
from datetime import date
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, func, or_

from . import db
from .models import (
    BatchParameter, BatchSample, BatchStep, Experiment, ExperimentAttachment, ExperimentBatch,
    ExperimentRecord, ExperimentTemplate, RecordTemplate, ResearchProject, Sample,
    PresentationSkill, Task, WeeklyReport, utcnow,
)
from .project_package import ProjectPackageError, build_project_package, import_project_package


bp = Blueprint("workspace", __name__)
PROJECT_STATUSES = ("进行中", "规划中", "已完成", "已暂停")
EXPERIMENT_STATUSES = ("未开始", "进行中", "完成", "暂停")
BATCH_STATUSES = ("未开始", "进行中", "已完成", "暂停")
REPEAT_KINDS = ("独立实验", "预实验", "生物学重复", "技术重复")
ATTACHMENT_MANUAL_CATEGORIES = ("原始数据", "结果图片", "分析结果", "实验文档", "其他")
RECYCLE_PAGE_SIZES = (20, 50, 100)
PROJECT_PAGE_SIZES = (12, 24, 48)
PROJECT_DETAIL_PAGE_SIZES = (6, 12, 24)
BATCH_MINI_PAGE_SIZES = (4, 8, 16)
DETAIL_PAGE_SIZE = 8
RECYCLE_KINDS = (
    {"key": "attachment", "label": "实验文件", "icon": "file-archive"},
    {"key": "weekly_report", "label": "周报", "icon": "calendar-days"},
    {"key": "record", "label": "过程记录", "icon": "notebook-pen"},
    {"key": "experiment", "label": "实验计划", "icon": "flask-conical"},
    {"key": "project", "label": "科研项目", "icon": "panels-top-left"},
    {"key": "task", "label": "任务", "icon": "check-square-2"},
    {"key": "step_template", "label": "步骤模板", "icon": "list-ordered"},
    {"key": "record_template", "label": "记录模板", "icon": "copy"},
    {"key": "presentation_skill", "label": "PPT Skill", "icon": "presentation"},
)


@bp.before_request
def reject_viewer_writes():
    if (not current_app.config.get("LOCAL_MODE")
            and current_user.is_authenticated and current_user.role == "viewer"
            and request.method not in {"GET", "HEAD", "OPTIONS"}):
        abort(403)


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _positive_int(value, default=1):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _page_size(value, choices, default):
    parsed = _positive_int(value, default)
    return parsed if parsed in choices else default


def _paginate(query, page_key="page", per_page=DETAIL_PAGE_SIZE, per_page_key=None, page_sizes=PROJECT_PAGE_SIZES):
    page = _positive_int(request.args.get(page_key), 1)
    if per_page_key:
        per_page = _page_size(request.args.get(per_page_key), page_sizes, per_page)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    if pagination.pages and page > pagination.pages:
        pagination = query.paginate(page=pagination.pages, per_page=per_page, error_out=False)
    return pagination, per_page


def _form_ids(name):
    try:
        return {int(value) for value in request.form.getlist(name)}
    except (TypeError, ValueError):
        abort(400)


def _project_or_404(item_id, include_deleted=False):
    item = db.session.get(ResearchProject, item_id)
    if not item or item.user_id != current_user.id or (item.is_deleted and not include_deleted):
        abort(404)
    return item


def _experiment_or_404(item_id, include_deleted=False):
    item = db.session.get(Experiment, item_id)
    if not item or item.user_id != current_user.id or (item.is_deleted and not include_deleted):
        abort(404)
    return item


def _batch_or_404(item_id, include_deleted=False):
    item = db.session.get(ExperimentBatch, item_id)
    if (not item or item.experiment.user_id != current_user.id
            or (item.experiment.is_deleted and not include_deleted)
            or (item.is_deleted and not include_deleted)):
        abort(404)
    return item


def _record_or_404(item_id, include_deleted=False):
    item = db.session.get(ExperimentRecord, item_id)
    if (not item or item.experiment.user_id != current_user.id
            or (item.experiment.is_deleted and not include_deleted)
            or (item.is_deleted and not include_deleted)):
        abort(404)
    return item


def _batch_step_or_404(item_id, batch_id=None):
    item = db.session.get(BatchStep, item_id)
    if (not item or item.batch.experiment.user_id != current_user.id
            or item.batch.is_deleted or item.batch.experiment.is_deleted
            or (batch_id is not None and item.batch_id != batch_id)):
        abort(404)
    return item


def _active_experiments(project):
    return [item for item in project.experiments if not item.is_deleted]


@bp.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("项目名称不能为空。", "danger")
        else:
            item = ResearchProject(
                user_id=current_user.id,
                title=title[:180],
                code=request.form.get("code", "").strip()[:80],
                objective=request.form.get("objective", "").strip(),
                status=request.form.get("status") if request.form.get("status") in PROJECT_STATUSES else "进行中",
                start_date=_parse_date(request.form.get("start_date")),
                end_date=_parse_date(request.form.get("end_date")),
            )
            db.session.add(item)
            db.session.commit()
            flash("科研项目已创建。", "success")
            return redirect(url_for("workspace.project_detail", item_id=item.id))

    search = request.args.get("q", "").strip()[:120]
    selected_status = request.args.get("status", "全部")
    if selected_status not in {"全部", *PROJECT_STATUSES}:
        selected_status = "全部"
    query = ResearchProject.query.filter_by(user_id=current_user.id, is_deleted=False)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            ResearchProject.title.ilike(pattern), ResearchProject.code.ilike(pattern),
            ResearchProject.objective.ilike(pattern),
        ))
    if selected_status != "全部":
        query = query.filter(ResearchProject.status == selected_status)
    pagination, page_size = _paginate(
        query.order_by(ResearchProject.updated_at.desc(), ResearchProject.id.desc()),
        per_page=PROJECT_PAGE_SIZES[0], per_page_key="per_page",
    )
    cards = []
    for item in pagination.items:
        experiments = _active_experiments(item)
        records = [record for experiment in experiments for record in experiment.records if not record.is_deleted]
        cards.append({
            "project": item,
            "experiments": len(experiments),
            "batches": sum(len([batch for batch in experiment.batches if not batch.is_deleted]) for experiment in experiments),
            "records": len(records),
            "finalized": sum(record.lifecycle_status in {"已定稿", "修订"} for record in records),
        })
    active_experiment_query = Experiment.query.filter_by(user_id=current_user.id, is_deleted=False)
    active_record_query = ExperimentRecord.query.join(Experiment).filter(
        Experiment.user_id == current_user.id, Experiment.is_deleted.is_(False),
        ExperimentRecord.is_deleted.is_(False),
    )
    return render_template(
        "projects.html", project_cards=cards, statuses=PROJECT_STATUSES, today=date.today(),
        pagination=pagination, page_size=page_size, page_sizes=PROJECT_PAGE_SIZES,
        search=search, selected_status=selected_status,
        workspace_metrics={
            "projects": ResearchProject.query.filter_by(user_id=current_user.id, is_deleted=False).count(),
            "experiments": active_experiment_query.count(),
            "records": active_record_query.count(),
        },
    )


@bp.route("/projects/<int:item_id>", methods=["GET", "POST"])
@login_required
def project_detail(item_id):
    item = _project_or_404(item_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("项目名称不能为空。", "danger")
        else:
            item.title = title[:180]
            item.code = request.form.get("code", "").strip()[:80]
            item.objective = request.form.get("objective", "").strip()
            item.notes = request.form.get("notes", "").strip()
            item.status = request.form.get("status") if request.form.get("status") in PROJECT_STATUSES else item.status
            item.start_date = _parse_date(request.form.get("start_date"))
            item.end_date = _parse_date(request.form.get("end_date"))
            db.session.commit()
            flash("项目信息已保存。", "success")
            return redirect(url_for("workspace.project_detail", item_id=item.id))
    search = request.args.get("q", "").strip()[:120]
    selected_experiment_status = request.args.get("experiment_status", "全部")
    selected_batch_status = request.args.get("batch_status", "全部")
    if selected_experiment_status not in {"全部", *EXPERIMENT_STATUSES}:
        selected_experiment_status = "全部"
    if selected_batch_status not in {"全部", *BATCH_STATUSES}:
        selected_batch_status = "全部"

    experiment_query = Experiment.query.filter_by(
        user_id=current_user.id, project_id=item.id, is_deleted=False,
    )
    if search:
        pattern = f"%{search}%"
        experiment_query = experiment_query.filter(or_(
            Experiment.title.ilike(pattern), Experiment.code.ilike(pattern),
            Experiment.objective.ilike(pattern), Experiment.owner.ilike(pattern),
            Experiment.batches.any(and_(
                ExperimentBatch.is_deleted.is_(False),
                or_(
                    ExperimentBatch.batch_code.ilike(pattern),
                    ExperimentBatch.group_name.ilike(pattern),
                    ExperimentBatch.operator.ilike(pattern),
                ),
            )),
        ))
    if selected_experiment_status != "全部":
        experiment_query = experiment_query.filter(Experiment.status == selected_experiment_status)
    if selected_batch_status != "全部":
        experiment_query = experiment_query.filter(Experiment.batches.any(and_(
            ExperimentBatch.is_deleted.is_(False),
            ExperimentBatch.status == selected_batch_status,
        )))
    experiment_pagination, page_size = _paginate(
        experiment_query.order_by(Experiment.updated_at.desc(), Experiment.id.desc()),
        per_page=PROJECT_DETAIL_PAGE_SIZES[0], per_page_key="per_page",
        page_sizes=PROJECT_DETAIL_PAGE_SIZES,
    )
    experiments = experiment_pagination.items

    selected_batch_experiment_id = request.args.get("batch_experiment_id", type=int)
    if selected_batch_experiment_id:
        selected_batch_experiment = Experiment.query.filter_by(
            id=selected_batch_experiment_id, user_id=current_user.id,
            project_id=item.id, is_deleted=False,
        ).first()
        if not selected_batch_experiment:
            abort(404)
    batch_page_size = _page_size(
        request.args.get("batch_per_page"), BATCH_MINI_PAGE_SIZES, BATCH_MINI_PAGE_SIZES[0],
    )
    batch_views = {}
    for experiment in experiments:
        batch_query = ExperimentBatch.query.filter_by(
            experiment_id=experiment.id, is_deleted=False,
        )
        if selected_batch_status != "全部":
            batch_query = batch_query.filter(ExperimentBatch.status == selected_batch_status)
        batch_query = batch_query.order_by(ExperimentBatch.created_at.desc(), ExperimentBatch.id.desc())
        total = batch_query.count()
        if experiment.id == selected_batch_experiment_id:
            batch_pagination, _ = _paginate(
                batch_query, page_key="batch_page", per_page=batch_page_size,
            )
            batch_views[experiment.id] = {
                "items": batch_pagination.items, "total": total,
                "pagination": batch_pagination, "expanded": True,
            }
        else:
            batch_views[experiment.id] = {
                "items": batch_query.limit(3).all(), "total": total,
                "pagination": None, "expanded": False,
            }

    task_query = Task.query.filter_by(
        user_id=current_user.id, project_id=item.id, is_deleted=False,
    )
    task_total = task_query.count()
    tasks = task_query.order_by(
        Task.status, Task.deadline.is_(None), Task.deadline, Task.created_at.desc(),
    ).limit(6).all()
    experiment_total = Experiment.query.filter_by(
        user_id=current_user.id, project_id=item.id, is_deleted=False,
    ).count()
    execution_count = ExperimentBatch.query.join(Experiment).filter(
        Experiment.user_id == current_user.id, Experiment.project_id == item.id,
        Experiment.is_deleted.is_(False), ExperimentBatch.is_deleted.is_(False),
    ).count()
    return render_template(
        "project_detail.html", project=item, experiments=experiments, tasks=tasks,
        statuses=PROJECT_STATUSES, experiment_statuses=EXPERIMENT_STATUSES,
        batch_statuses=BATCH_STATUSES, execution_count=execution_count,
        experiment_total=experiment_total, task_total=task_total,
        experiment_pagination=experiment_pagination, page_size=page_size,
        page_sizes=PROJECT_DETAIL_PAGE_SIZES, batch_page_size=batch_page_size,
        batch_page_sizes=BATCH_MINI_PAGE_SIZES, batch_views=batch_views,
        search=search, selected_experiment_status=selected_experiment_status,
        selected_batch_status=selected_batch_status,
        selected_batch_experiment_id=selected_batch_experiment_id,
    )


@bp.post("/projects/<int:item_id>/resources/bulk")
@login_required
def project_resource_bulk(item_id):
    project = _project_or_404(item_id)
    experiment_ids = _form_ids("experiment_ids")
    batch_ids = _form_ids("batch_ids")
    if not experiment_ids and not batch_ids:
        flash("请先勾选至少一个实验计划或实验批次。", "warning")
    else:
        experiments = Experiment.query.filter(
            Experiment.user_id == current_user.id,
            Experiment.project_id == project.id,
            Experiment.is_deleted.is_(False),
            Experiment.id.in_(experiment_ids),
        ).all() if experiment_ids else []
        batches = ExperimentBatch.query.join(Experiment).filter(
            Experiment.user_id == current_user.id,
            Experiment.project_id == project.id,
            Experiment.is_deleted.is_(False),
            ExperimentBatch.is_deleted.is_(False),
            ExperimentBatch.id.in_(batch_ids),
        ).all() if batch_ids else []
        if {experiment.id for experiment in experiments} != experiment_ids:
            abort(404)
        if {batch.id for batch in batches} != batch_ids:
            abort(404)

        experiment_status = request.form.get("experiment_status", "__keep__")
        batch_status = request.form.get("batch_status", "__keep__")
        owner_mode = request.form.get("owner_mode", "keep")
        operator_mode = request.form.get("operator_mode", "keep")
        if experiment_status not in {"__keep__", *EXPERIMENT_STATUSES}:
            abort(400)
        if batch_status not in {"__keep__", *BATCH_STATUSES}:
            abort(400)
        if owner_mode not in {"keep", "replace", "clear"}:
            abort(400)
        if operator_mode not in {"keep", "replace", "clear"}:
            abort(400)

        owner = request.form.get("owner", "").strip()[:80]
        operator = request.form.get("operator", "").strip()[:80]
        for experiment in experiments:
            if experiment_status != "__keep__":
                experiment.status = experiment_status
            if owner_mode != "keep":
                experiment.owner = owner if owner_mode == "replace" else ""
        for batch in batches:
            if batch_status != "__keep__":
                batch.status = batch_status
            if operator_mode != "keep":
                batch.operator = operator if operator_mode == "replace" else ""
        db.session.commit()
        flash(f"已批量更新 {len(experiments)} 个实验计划和 {len(batches)} 个实验批次。", "success")

    values = {
        key: request.form.get(key) for key in (
            "q", "page", "per_page", "batch_experiment_id", "batch_page", "batch_per_page",
        ) if request.form.get(key)
    }
    values["experiment_status"] = request.form.get("return_experiment_status", "全部")
    values["batch_status"] = request.form.get("return_batch_status", "全部")
    return redirect(url_for("workspace.project_detail", item_id=project.id, **values, _anchor="project-experiment-directory"))


@bp.post("/projects/<int:item_id>/delete")
@login_required
def project_delete(item_id):
    item = _project_or_404(item_id)
    deleted_at = utcnow()
    item.is_deleted = True
    item.deleted_at = deleted_at
    for experiment in item.experiments:
        experiment.is_deleted = True
        experiment.deleted_at = deleted_at
        for batch in experiment.batches:
            batch.is_deleted = True
            batch.deleted_at = deleted_at
        for record in experiment.records:
            record.is_deleted = True
            record.deleted_at = deleted_at
            for attachment in record.attachments:
                attachment.is_deleted = True
                attachment.deleted_at = deleted_at
    db.session.commit()
    flash("项目已移入回收站，所有本地文件仍保留。", "success")
    return redirect(url_for("workspace.projects"))


@bp.get("/projects/<int:item_id>/package")
@login_required
def project_package_export(item_id):
    project = _project_or_404(item_id)
    try:
        path, manifest = build_project_package(project, current_app.config["ATTACHMENT_UPLOAD_DIR"])
    except ProjectPackageError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("workspace.project_detail", item_id=project.id))

    code = "".join(char if char.isalnum() or char in "-_" else "_" for char in (project.code or f"project-{project.id}"))
    response = send_file(
        path, as_attachment=True, download_name=f"{code}.ralab",
        mimetype="application/zip", etag=manifest["entries"]["project.json"],
    )
    response.call_on_close(lambda: path.unlink(missing_ok=True))
    return response


@bp.post("/projects/import")
@login_required
def project_package_import():
    uploaded = request.files.get("project_package")
    if not uploaded or not uploaded.filename:
        flash("请选择 Research Assistant 项目包。", "danger")
        return redirect(url_for("workspace.projects"))
    try:
        project, manifest = import_project_package(
            uploaded.stream, current_user.id, current_app.config["ATTACHMENT_UPLOAD_DIR"]
        )
    except ProjectPackageError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("workspace.projects"))
    flash(
        f"项目包已校验并导入（结构版本 {manifest['schema_version']}）。外部路径仅恢复为链接。",
        "success",
    )
    return redirect(url_for("workspace.project_detail", item_id=project.id))


@bp.post("/experiments/<int:item_id>/batches")
@login_required
def batch_create(item_id):
    experiment = _experiment_or_404(item_id)
    batch = ExperimentBatch(
        experiment_id=experiment.id,
        batch_code=request.form.get("batch_code", "").strip()[:80] or f"RUN-{len(experiment.batches) + 1:02d}",
        repeat_kind=request.form.get("repeat_kind") if request.form.get("repeat_kind") in REPEAT_KINDS else "独立实验",
        repeat_number=_positive_int(request.form.get("repeat_number"), len(experiment.batches) + 1),
        group_name=request.form.get("group_name", "").strip()[:80],
        operator=request.form.get("operator", "").strip()[:80] or current_user.name,
        status="未开始",
        start_date=_parse_date(request.form.get("start_date")) or date.today(),
    )
    db.session.add(batch)
    db.session.flush()
    for step in experiment.steps:
        db.session.add(BatchStep.from_plan_step(batch.id, step))
    for usage in experiment.sample_usages:
        db.session.add(BatchSample(
            batch_id=batch.id, sample_id=usage.sample_id, role=usage.role,
            amount_used=usage.amount_used, notes=usage.notes,
        ))
    db.session.commit()
    flash("实验批次已创建，并复制了当前计划步骤和样本要求。", "success")
    return redirect(url_for("workspace.batch_detail", item_id=batch.id))


@bp.route("/batches/<int:item_id>", methods=["GET", "POST"])
@login_required
def batch_detail(item_id):
    batch = _batch_or_404(item_id)
    if request.method == "POST":
        raw_start_date = request.form.get("start_date", "").strip()
        raw_end_date = request.form.get("end_date", "").strip()
        start_date = _parse_date(raw_start_date)
        end_date = _parse_date(raw_end_date)
        if (raw_start_date and not start_date) or (raw_end_date and not end_date):
            flash("请输入有效的实验批次日期。", "danger")
            return redirect(url_for("workspace.batch_detail", item_id=batch.id, _anchor="batch-profile"))
        from .main import _batch_date_error

        status = request.form.get("status") if request.form.get("status") in BATCH_STATUSES else batch.status
        date_error = _batch_date_error(batch, start_date, end_date, status)
        if date_error:
            flash(date_error, "danger")
            return redirect(url_for("workspace.batch_detail", item_id=batch.id, _anchor="batch-profile"))
        batch.batch_code = request.form.get("batch_code", "").strip()[:80]
        batch.repeat_kind = request.form.get("repeat_kind") if request.form.get("repeat_kind") in REPEAT_KINDS else batch.repeat_kind
        batch.repeat_number = _positive_int(request.form.get("repeat_number"))
        batch.group_name = request.form.get("group_name", "").strip()[:80]
        batch.operator = request.form.get("operator", "").strip()[:80]
        batch.status = status
        batch.start_date = start_date
        batch.end_date = end_date
        batch.summary = request.form.get("summary", "").strip()
        batch.conclusion = request.form.get("conclusion", "").strip()
        batch.requires_repeat = request.form.get("requires_repeat") == "1"
        db.session.commit()
        flash("实验批次信息已保存。", "success")
        return redirect(url_for("workspace.batch_detail", item_id=batch.id))
    selected_record_template = None
    record_template_id = request.args.get("record_template_id", type=int)
    if record_template_id:
        selected_record_template = db.session.get(RecordTemplate, record_template_id)
        if (not selected_record_template or selected_record_template.user_id != current_user.id
                or selected_record_template.is_deleted):
            abort(404)
    step_query = BatchStep.query.filter_by(batch_id=batch.id).order_by(
        BatchStep.position, BatchStep.id,
    )
    step_pagination, _ = _paginate(step_query, page_key="step_page")
    record_query = ExperimentRecord.query.filter_by(
        batch_id=batch.id, is_deleted=False,
    ).order_by(ExperimentRecord.record_date.desc(), ExperimentRecord.created_at.desc())
    record_pagination, _ = _paginate(record_query, page_key="record_page")
    parameter_query = BatchParameter.query.filter_by(batch_id=batch.id).order_by(
        BatchParameter.position, BatchParameter.id,
    )
    parameter_pagination, _ = _paginate(parameter_query, page_key="parameter_page")
    sample_query = BatchSample.query.filter_by(batch_id=batch.id).order_by(
        BatchSample.created_at, BatchSample.id,
    )
    sample_pagination, _ = _paginate(sample_query, page_key="sample_page")
    samples = Sample.query.filter_by(user_id=current_user.id).order_by(Sample.sample_code).all()
    return render_template(
        "batch_detail.html", batch=batch, records=record_pagination.items, samples=samples,
        batch_steps=step_pagination.items, actual_parameters=parameter_pagination.items,
        sample_usages=sample_pagination.items,
        step_pagination=step_pagination, record_pagination=record_pagination,
        parameter_pagination=parameter_pagination, sample_pagination=sample_pagination,
        completed_step_count=BatchStep.query.filter_by(batch_id=batch.id, is_done=True).count(),
        statuses=BATCH_STATUSES, repeat_kinds=REPEAT_KINDS, today=date.today(),
        attachment_categories=ATTACHMENT_MANUAL_CATEGORIES,
        record_templates=RecordTemplate.query.filter_by(
            user_id=current_user.id, is_deleted=False
        ).order_by(RecordTemplate.name).all(),
        selected_record_template=selected_record_template,
    )


@bp.post("/batch-steps/<int:item_id>/edit")
@login_required
def batch_step_edit(item_id):
    step = _batch_step_or_404(item_id)
    title = request.form.get("title", "").strip()
    raw_planned_date = request.form.get("planned_date", "").strip()
    raw_completed_date = request.form.get("completed_date", "").strip()
    planned_date = _parse_date(raw_planned_date)
    completed_date = _parse_date(raw_completed_date)
    if not title:
        flash("批次步骤标题不能为空。", "danger")
    elif raw_planned_date and not planned_date:
        flash("请输入有效的计划日期。", "danger")
    elif step.is_done and raw_completed_date and not completed_date:
        flash("请输入有效的完成日期。", "danger")
    else:
        step.title = title[:160]
        step.description = request.form.get("description", "").strip()
        step.operator = request.form.get("operator", "").strip()[:80]
        step.planned_date = planned_date
        if step.is_done:
            step.completed_date = completed_date or step.completed_date or date.today()
        db.session.commit()
        flash("本批次步骤已保存。", "success")
    return redirect(url_for("workspace.batch_detail", item_id=step.batch_id, _anchor="batch-steps"))


@bp.post("/batch-steps/<int:item_id>/toggle")
@login_required
def batch_step_toggle(item_id):
    step = _batch_step_or_404(item_id)
    step.is_done = not step.is_done
    step.completed_date = date.today() if step.is_done else None
    db.session.commit()
    return redirect(url_for("workspace.batch_detail", item_id=step.batch_id, _anchor="batch-steps"))


@bp.post("/batches/<int:item_id>/steps/bulk")
@login_required
def batch_step_bulk(item_id):
    batch = _batch_or_404(item_id)
    raw_ids = request.form.getlist("step_ids")
    if not raw_ids:
        flash("请先勾选至少一个批次步骤。", "warning")
        return redirect(url_for("workspace.batch_detail", item_id=batch.id, _anchor="batch-steps"))
    try:
        selected_ids = {int(value) for value in raw_ids}
    except (TypeError, ValueError):
        abort(400)
    selected = [step for step in batch.steps if step.id in selected_ids]
    if {step.id for step in selected} != selected_ids:
        abort(404)

    action = request.form.get("action", "")
    if action not in {"complete", "pending"}:
        abort(400)
    raw_completed_date = request.form.get("completed_date", "").strip()
    completed_date = _parse_date(raw_completed_date) if action == "complete" else None
    if action == "complete" and raw_completed_date and not completed_date:
        flash("请输入有效的完成日期。", "danger")
        return redirect(url_for("workspace.batch_detail", item_id=batch.id, _anchor="batch-steps"))
    for step in selected:
        step.is_done = action == "complete"
        step.completed_date = (completed_date or date.today()) if step.is_done else None
    db.session.commit()
    label = "完成" if action == "complete" else "未完成"
    flash(f"已将 {len(selected)} 个批次步骤标记为{label}。", "success")
    return redirect(url_for("workspace.batch_detail", item_id=batch.id, _anchor="batch-steps"))


@bp.post("/batches/<int:item_id>/records")
@login_required
def batch_record_create(item_id):
    batch = _batch_or_404(item_id)
    if request.form.get("batch_id", type=int) != batch.id:
        abort(400)

    # Keep record and attachment persistence in the established implementation;
    # this adapter only fixes the batch-scoped workflow and return location.
    from .main import record_add

    return record_add(batch.experiment_id)


@bp.post("/batches/<int:item_id>/records/bulk")
@login_required
def batch_record_bulk(item_id):
    batch = _batch_or_404(item_id)
    raw_ids = request.form.getlist("record_ids")
    if not raw_ids:
        flash("请先勾选至少一条过程记录。", "warning")
        return redirect(url_for("workspace.batch_detail", item_id=batch.id, _anchor="batch-records"))
    try:
        selected_ids = {int(value) for value in raw_ids}
    except (TypeError, ValueError):
        abort(400)
    owned_ids = {
        row[0] for row in db.session.query(ExperimentRecord.id).filter(
            ExperimentRecord.batch_id == batch.id,
            ExperimentRecord.is_deleted.is_(False),
            ExperimentRecord.id.in_(selected_ids),
        ).all()
    }
    if owned_ids != selected_ids:
        abort(404)

    from .main import record_bulk

    record_bulk(batch.experiment_id)
    return redirect(url_for("workspace.batch_detail", item_id=batch.id, _anchor="batch-records"))


@bp.post("/batches/<int:item_id>/parameters")
@login_required
def batch_parameter_add(item_id):
    batch = _batch_or_404(item_id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("参数名称不能为空。", "danger")
    else:
        db.session.add(BatchParameter(
            batch_id=batch.id, position=len(batch.actual_parameters) + 1, name=name[:120],
            value=request.form.get("value", "").strip()[:160],
            unit=request.form.get("unit", "").strip()[:40],
            notes=request.form.get("notes", "").strip()[:255],
        ))
        db.session.commit()
        flash("本实验批次的实际参数已添加。", "success")
    return redirect(url_for("workspace.batch_detail", item_id=batch.id, _anchor="batch-parameters"))


@bp.post("/batches/<int:item_id>/samples")
@login_required
def batch_sample_add(item_id):
    batch = _batch_or_404(item_id)
    sample_id = request.form.get("sample_id", type=int)
    sample = db.session.get(Sample, sample_id) if sample_id else None
    if not sample or sample.user_id != current_user.id:
        flash("请选择有效样本。", "danger")
    elif BatchSample.query.filter_by(batch_id=batch.id, sample_id=sample.id).first():
        flash("这个样本已经关联到当前实验批次。", "warning")
    else:
        db.session.add(BatchSample(
            batch_id=batch.id, sample_id=sample.id,
            role=request.form.get("role", "").strip()[:80] or "实验样本",
            amount_used=request.form.get("amount_used", "").strip()[:80],
            notes=request.form.get("notes", "").strip()[:255],
        ))
        db.session.commit()
        flash("实际使用样本已关联。", "success")
    return redirect(url_for("workspace.batch_detail", item_id=batch.id, _anchor="batch-samples"))


@bp.post("/records/<int:item_id>/move-batch")
@login_required
def record_move_batch(item_id):
    record = _record_or_404(item_id)
    batch = _batch_or_404(request.form.get("batch_id", type=int) or 0)
    if batch.experiment_id != record.experiment_id:
        abort(400)
    from .main import FINALIZED_RECORD_STATUSES, _prepare_batch_for_record

    if record.lifecycle_status in FINALIZED_RECORD_STATUSES:
        flash("已定稿过程记录不能更换实验批次。请保留原归属，并通过单条修订说明更正。", "danger")
        return redirect(url_for("main.record_detail", record_id=record.id))
    if batch.id == record.batch_id:
        flash("过程记录已经属于当前实验批次。", "info")
        return redirect(url_for("main.record_detail", record_id=record.id))
    date_error = _prepare_batch_for_record(batch, record.record_date)
    if date_error:
        flash(date_error, "danger")
        return redirect(url_for("main.record_detail", record_id=record.id))
    record.batch_id = batch.id
    db.session.commit()
    flash("过程记录已归入所选实验批次。", "success")
    return redirect(url_for("main.record_detail", record_id=record.id))


def _restore_graph(kind, item):
    item.is_deleted = False
    item.deleted_at = None
    if kind == "project":
        for experiment in item.experiments:
            _restore_graph("experiment", experiment)
    elif kind == "experiment":
        if item.project and item.project.is_deleted:
            item.project.is_deleted = False
            item.project.deleted_at = None
        for batch in item.batches:
            batch.is_deleted = False
            batch.deleted_at = None
        for record in item.records:
            _restore_graph("record", record)
    elif kind == "record":
        if item.experiment.is_deleted:
            item.experiment.is_deleted = False
            item.experiment.deleted_at = None
        for attachment in item.attachments:
            attachment.is_deleted = False
            attachment.deleted_at = None


def _recycle_item(kind, item_id):
    if kind == "project":
        return _project_or_404(item_id, include_deleted=True)
    if kind == "experiment":
        return _experiment_or_404(item_id, include_deleted=True)
    if kind == "record":
        return _record_or_404(item_id, include_deleted=True)
    if kind == "task":
        item = db.session.get(Task, item_id)
        if not item or item.user_id != current_user.id:
            abort(404)
        return item
    if kind == "step_template":
        item = db.session.get(ExperimentTemplate, item_id)
        if not item or item.user_id != current_user.id:
            abort(404)
        return item
    if kind == "record_template":
        item = db.session.get(RecordTemplate, item_id)
        if not item or item.user_id != current_user.id:
            abort(404)
        return item
    if kind == "presentation_skill":
        item = db.session.get(PresentationSkill, item_id)
        if not item or item.user_id != current_user.id:
            abort(404)
        return item
    if kind == "weekly_report":
        item = db.session.get(WeeklyReport, item_id)
        if not item or item.user_id != current_user.id:
            abort(404)
        return item
    if kind == "attachment":
        item = db.session.get(ExperimentAttachment, item_id)
        if not item or item.record.experiment.user_id != current_user.id:
            abort(404)
        return item
    abort(404)


def _recycle_query(kind, search=""):
    if kind == "project":
        query = ResearchProject.query.filter_by(user_id=current_user.id, is_deleted=True)
        fields = (ResearchProject.title, ResearchProject.code, ResearchProject.notes)
    elif kind == "experiment":
        deleted_projects = db.session.query(ResearchProject.id).filter(
            ResearchProject.user_id == current_user.id,
            ResearchProject.is_deleted.is_(True),
        )
        query = Experiment.query.filter(
            Experiment.user_id == current_user.id,
            Experiment.is_deleted.is_(True),
            or_(Experiment.project_id.is_(None), Experiment.project_id.notin_(deleted_projects)),
        )
        fields = (Experiment.title, Experiment.code, Experiment.objective)
    elif kind == "record":
        query = ExperimentRecord.query.join(Experiment).filter(
            Experiment.user_id == current_user.id,
            Experiment.is_deleted.is_(False),
            ExperimentRecord.is_deleted.is_(True),
        )
        fields = (ExperimentRecord.content, ExperimentRecord.result, Experiment.title)
    elif kind == "attachment":
        query = ExperimentAttachment.query.join(
            Experiment, Experiment.id == ExperimentAttachment.experiment_id
        ).join(
            ExperimentRecord, ExperimentRecord.id == ExperimentAttachment.record_id
        ).filter(
            Experiment.user_id == current_user.id,
            Experiment.is_deleted.is_(False),
            ExperimentRecord.is_deleted.is_(False),
            ExperimentAttachment.is_deleted.is_(True),
        )
        fields = (
            ExperimentAttachment.original_name, ExperimentAttachment.relative_path,
            ExperimentAttachment.tags, Experiment.title,
        )
    elif kind == "weekly_report":
        query = WeeklyReport.query.filter_by(user_id=current_user.id, is_deleted=True)
        fields = (WeeklyReport.title, WeeklyReport.original_name, WeeklyReport.summary)
    elif kind == "task":
        query = Task.query.filter_by(user_id=current_user.id, is_deleted=True)
        fields = (Task.title, Task.notes)
    elif kind == "step_template":
        query = ExperimentTemplate.query.filter_by(user_id=current_user.id, is_deleted=True)
        fields = (ExperimentTemplate.name, ExperimentTemplate.description)
    elif kind == "record_template":
        query = RecordTemplate.query.filter_by(user_id=current_user.id, is_deleted=True)
        fields = (RecordTemplate.name, RecordTemplate.description)
    elif kind == "presentation_skill":
        query = PresentationSkill.query.filter_by(user_id=current_user.id, is_deleted=True)
        fields = (PresentationSkill.name, PresentationSkill.description)
    else:
        abort(404)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(*(field.ilike(pattern) for field in fields)))
    return query


def _recycle_redirect(kind):
    per_page = _positive_int(request.form.get("per_page"), RECYCLE_PAGE_SIZES[0])
    if per_page not in RECYCLE_PAGE_SIZES:
        per_page = RECYCLE_PAGE_SIZES[0]
    return redirect(url_for(
        "workspace.recycle_bin", kind=kind,
        q=request.form.get("q", "").strip()[:120],
        page=_positive_int(request.form.get("page"), 1), per_page=per_page,
    ))


@bp.get("/recycle-bin")
@login_required
def recycle_bin():
    kind_keys = {item["key"] for item in RECYCLE_KINDS}
    counts = {kind: _recycle_query(kind).count() for kind in kind_keys}
    selected_kind = request.args.get("kind", "").strip()
    if selected_kind not in kind_keys:
        selected_kind = next(
            (item["key"] for item in RECYCLE_KINDS if counts[item["key"]]),
            RECYCLE_KINDS[0]["key"],
        )
    search = request.args.get("q", "").strip()[:120]
    page = _positive_int(request.args.get("page"), 1)
    per_page = _positive_int(request.args.get("per_page"), RECYCLE_PAGE_SIZES[0])
    if per_page not in RECYCLE_PAGE_SIZES:
        per_page = RECYCLE_PAGE_SIZES[0]
    query = _recycle_query(selected_kind, search)
    entity = query.column_descriptions[0]["entity"]
    query = query.order_by(entity.deleted_at.desc(), entity.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    if pagination.pages and page > pagination.pages:
        pagination = query.paginate(
            page=pagination.pages, per_page=per_page, error_out=False,
        )
    selected_meta = next(item for item in RECYCLE_KINDS if item["key"] == selected_kind)
    return render_template(
        "recycle_bin.html", recycle_kinds=RECYCLE_KINDS,
        recycle_counts=counts, selected_kind=selected_kind,
        selected_meta=selected_meta, items=pagination.items,
        pagination=pagination, search=search, page_size=per_page,
        page_sizes=RECYCLE_PAGE_SIZES,
    )


@bp.post("/recycle-bin/<kind>/<int:item_id>/restore")
@login_required
def recycle_restore(kind, item_id):
    item = _recycle_item(kind, item_id)
    if not getattr(item, "is_deleted", False):
        abort(400)
    _restore_graph(kind, item)
    db.session.commit()
    flash("内容已从回收站恢复。", "success")
    return _recycle_redirect(kind)


def _remove_managed_files(item):
    if isinstance(item, WeeklyReport):
        root = Path(current_app.config["WEEKLY_REPORT_UPLOAD_DIR"]).resolve()
        if item.stored_path:
            path = (root / item.stored_path).resolve()
            if path != root and root in path.parents:
                path.unlink(missing_ok=True)
        return
    attachments = []
    if isinstance(item, ResearchProject):
        attachments = [attachment for experiment in item.experiments for record in experiment.records for attachment in record.attachments]
    elif isinstance(item, Experiment):
        attachments = [attachment for record in item.records for attachment in record.attachments]
    elif isinstance(item, ExperimentRecord):
        attachments = list(item.attachments)
    elif isinstance(item, ExperimentAttachment):
        attachments = [item]
    root = Path(current_app.config["ATTACHMENT_UPLOAD_DIR"]).resolve()
    for attachment in attachments:
        if attachment.storage_mode != "managed" or not attachment.stored_path:
            continue
        path = (root / attachment.stored_path).resolve()
        if path != root and root in path.parents:
            path.unlink(missing_ok=True)


@bp.post("/recycle-bin/<kind>/<int:item_id>/purge")
@login_required
def recycle_purge(kind, item_id):
    item = _recycle_item(kind, item_id)
    if not getattr(item, "is_deleted", False):
        abort(400)
    confirmation = request.form.get("confirmation", "").strip()
    if confirmation != "永久删除":
        flash("请输入“永久删除”完成二次确认。", "danger")
        return _recycle_redirect(kind)
    _remove_managed_files(item)
    db.session.delete(item)
    db.session.commit()
    flash("内容已永久删除。外部链接对应的原始文件未被删除。", "success")
    return _recycle_redirect(kind)


@bp.post("/recycle-bin/<kind>/purge-bulk")
@login_required
def recycle_purge_bulk(kind):
    query = _recycle_query(kind)
    raw_ids = request.form.getlist("item_ids")
    if not raw_ids:
        flash("请先勾选至少一个项目。", "warning")
        return _recycle_redirect(kind)
    try:
        selected_ids = {int(value) for value in raw_ids}
    except (TypeError, ValueError):
        abort(400)

    entity = query.column_descriptions[0]["entity"]
    selected = query.filter(entity.id.in_(selected_ids)).all()
    if {item.id for item in selected} != selected_ids:
        abort(404)
    if request.form.get("confirmation", "").strip() != "永久删除":
        flash("请输入“永久删除”完成批量操作的二次确认。", "danger")
        return _recycle_redirect(kind)

    for item in selected:
        _remove_managed_files(item)
        db.session.delete(item)
    db.session.commit()
    flash(
        f"已永久删除 {len(selected)} 个项目。外部链接对应的原始文件未被删除。",
        "success",
    )
    return _recycle_redirect(kind)
