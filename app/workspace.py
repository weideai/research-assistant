import json
from datetime import date
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from . import db
from .models import (
    BatchParameter, BatchSample, BatchStep, Experiment, ExperimentAttachment, ExperimentBatch,
    ExperimentRecord, ExperimentTemplate, RecordTemplate, ResearchProject, Sample,
    PresentationSkill, Task, utcnow,
)
from .project_package import ProjectPackageError, build_project_package, import_project_package


bp = Blueprint("workspace", __name__)
PROJECT_STATUSES = ("进行中", "规划中", "已完成", "已暂停")
BATCH_STATUSES = ("未开始", "进行中", "已完成", "暂停")
REPEAT_KINDS = ("独立实验", "预实验", "生物学重复", "技术重复")
ATTACHMENT_MANUAL_CATEGORIES = ("原始数据", "结果图片", "分析结果", "实验文档", "其他")


@bp.before_request
def reject_viewer_writes():
    if (current_user.is_authenticated and current_user.role == "viewer"
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

    items = ResearchProject.query.filter_by(
        user_id=current_user.id, is_deleted=False
    ).order_by(ResearchProject.updated_at.desc()).all()
    cards = []
    for item in items:
        experiments = _active_experiments(item)
        records = [record for experiment in experiments for record in experiment.records if not record.is_deleted]
        cards.append({
            "project": item,
            "experiments": len(experiments),
            "batches": sum(len([batch for batch in experiment.batches if not batch.is_deleted]) for experiment in experiments),
            "records": len(records),
            "finalized": sum(record.lifecycle_status in {"已定稿", "修订"} for record in records),
        })
    return render_template("projects.html", project_cards=cards, statuses=PROJECT_STATUSES, today=date.today())


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
    experiments = _active_experiments(item)
    tasks = Task.query.filter_by(user_id=current_user.id, project_id=item.id, is_deleted=False).order_by(Task.deadline).all()
    execution_count = sum(
        1 for experiment in experiments for batch in experiment.batches if not batch.is_deleted
    )
    return render_template(
        "project_detail.html", project=item, experiments=experiments, tasks=tasks,
        statuses=PROJECT_STATUSES, execution_count=execution_count,
    )


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
    flash("实验执行已创建，并复制了当前计划步骤和样本要求。", "success")
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
            flash("请输入有效的实验执行日期。", "danger")
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
        flash("实验执行信息已保存。", "success")
        return redirect(url_for("workspace.batch_detail", item_id=batch.id))
    selected_record_template = None
    record_template_id = request.args.get("record_template_id", type=int)
    if record_template_id:
        selected_record_template = db.session.get(RecordTemplate, record_template_id)
        if (not selected_record_template or selected_record_template.user_id != current_user.id
                or selected_record_template.is_deleted):
            abort(404)
    records = ExperimentRecord.query.filter_by(
        batch_id=batch.id, is_deleted=False
    ).order_by(ExperimentRecord.record_date.desc(), ExperimentRecord.created_at.desc()).all()
    samples = Sample.query.filter_by(user_id=current_user.id).order_by(Sample.sample_code).all()
    return render_template(
        "batch_detail.html", batch=batch, records=records, samples=samples,
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
        flash("执行步骤标题不能为空。", "danger")
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
        flash("本次执行步骤已保存。", "success")
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
        flash("请先勾选至少一个执行步骤。", "warning")
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
    flash(f"已将 {len(selected)} 个执行步骤标记为{label}。", "success")
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
        flash("本次实验执行的实际参数已添加。", "success")
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
        flash("这个样本已经关联到当前实验执行。", "warning")
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
        flash("已定稿过程记录不能更换实验执行。请保留原归属，并通过单条修订说明更正。", "danger")
        return redirect(url_for("main.record_detail", record_id=record.id))
    if batch.id == record.batch_id:
        flash("过程记录已经属于当前实验执行。", "info")
        return redirect(url_for("main.record_detail", record_id=record.id))
    date_error = _prepare_batch_for_record(batch, record.record_date)
    if date_error:
        flash(date_error, "danger")
        return redirect(url_for("main.record_detail", record_id=record.id))
    record.batch_id = batch.id
    db.session.commit()
    flash("过程记录已归入所选实验执行。", "success")
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
    if kind == "attachment":
        item = db.session.get(ExperimentAttachment, item_id)
        if not item or item.record.experiment.user_id != current_user.id:
            abort(404)
        return item
    abort(404)


@bp.get("/recycle-bin")
@login_required
def recycle_bin():
    projects = ResearchProject.query.filter_by(user_id=current_user.id, is_deleted=True).all()
    experiments = Experiment.query.filter_by(user_id=current_user.id, is_deleted=True).filter(
        Experiment.project_id.notin_([item.id for item in projects]) if projects else True
    ).all()
    records = ExperimentRecord.query.join(Experiment).filter(
        Experiment.user_id == current_user.id, ExperimentRecord.is_deleted.is_(True),
        Experiment.is_deleted.is_(False),
    ).all()
    tasks = Task.query.filter_by(user_id=current_user.id, is_deleted=True).all()
    step_templates = ExperimentTemplate.query.filter_by(user_id=current_user.id, is_deleted=True).all()
    record_templates = RecordTemplate.query.filter_by(user_id=current_user.id, is_deleted=True).all()
    presentation_skills = PresentationSkill.query.filter_by(user_id=current_user.id, is_deleted=True).all()
    attachments = ExperimentAttachment.query.join(Experiment).filter(
        Experiment.user_id == current_user.id,
        ExperimentAttachment.is_deleted.is_(True),
        Experiment.is_deleted.is_(False),
        ExperimentAttachment.record.has(ExperimentRecord.is_deleted.is_(False)),
    ).all()
    return render_template(
        "recycle_bin.html", projects=projects, experiments=experiments, records=records,
        tasks=tasks, step_templates=step_templates, record_templates=record_templates,
        presentation_skills=presentation_skills, attachments=attachments,
    )


@bp.post("/recycle-bin/<kind>/<int:item_id>/restore")
@login_required
def recycle_restore(kind, item_id):
    item = _recycle_item(kind, item_id)
    _restore_graph(kind, item)
    db.session.commit()
    flash("内容已从回收站恢复。", "success")
    return redirect(url_for("workspace.recycle_bin"))


def _remove_managed_files(item):
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
        return redirect(url_for("workspace.recycle_bin"))
    _remove_managed_files(item)
    db.session.delete(item)
    db.session.commit()
    flash("内容已永久删除。外部链接对应的原始文件未被删除。", "success")
    return redirect(url_for("workspace.recycle_bin"))
