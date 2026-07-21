import csv
import io
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from . import db
from .ai_service import (
    AIConfig,
    AIServiceError,
    config_from_environment,
    list_models as fetch_models,
    organize_note,
    validate_api_url,
)
from .models import ApiSetting, Experiment, ExperimentRecord, ExperimentStep, Paper, ReviewerComment, Sample, Task
from .secrets import SecretDecryptionError


bp = Blueprint("main", __name__)


@bp.before_request
def enforce_read_only_role():
    if current_user.is_authenticated and current_user.role == "viewer" and request.method not in {"GET", "HEAD", "OPTIONS"}:
        abort(403)


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else None
    except ValueError:
        return None


def owned_or_404(model, item_id):
    item = db.session.get(model, item_id)
    if not item or item.user_id != current_user.id:
        abort(404)
    return item


def current_ai_config():
    setting = ApiSetting.query.filter_by(user_id=current_user.id).first()
    if not setting:
        return config_from_environment()
    return AIConfig(
        api_url=setting.api_url,
        api_key=setting.get_api_key(),
        model=setting.model,
        enabled=setting.is_enabled,
        source="user",
        allow_private=current_app.config["ALLOW_PRIVATE_API_URLS"],
        allowed_hosts=current_app.config["AI_ALLOWED_HOSTS"],
    )


@bp.get("/")
@login_required
def dashboard():
    today = date.today()
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.status, Task.deadline.is_(None), Task.deadline).limit(7).all()
    experiments = Experiment.query.filter_by(user_id=current_user.id).order_by(Experiment.updated_at.desc()).limit(5).all()
    records = (ExperimentRecord.query.join(Experiment).filter(Experiment.user_id == current_user.id)
               .order_by(ExperimentRecord.record_date.desc()).limit(5).all())
    task_total = Task.query.filter_by(user_id=current_user.id).count()
    task_done = Task.query.filter_by(user_id=current_user.id, status="完成").count()
    stats = {
        "due_today": Task.query.filter_by(user_id=current_user.id, deadline=today).filter(Task.status != "完成").count(),
        "active_experiments": Experiment.query.filter_by(user_id=current_user.id, status="进行中").count(),
        "available_samples": Sample.query.filter_by(user_id=current_user.id, status="可用").count(),
        "completion": round(task_done / task_total * 100) if task_total else 0,
    }
    return render_template("dashboard.html", tasks=tasks, experiments=experiments, records=records, stats=stats, today=today)


@bp.route("/tasks", methods=["GET", "POST"])
@login_required
def tasks():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("任务标题不能为空。", "danger")
        else:
            db.session.add(Task(user_id=current_user.id, title=title,
                category=request.form.get("category", "实验"), priority=request.form.get("priority", "中"),
                deadline=parse_date(request.form.get("deadline")), notes=request.form.get("notes", "").strip()))
            db.session.commit()
            flash("任务已添加。", "success")
            return redirect(url_for("main.tasks"))
    status = request.args.get("status", "全部")
    category = request.args.get("category", "全部")
    query = Task.query.filter_by(user_id=current_user.id)
    if status != "全部":
        query = query.filter_by(status=status)
    if category != "全部":
        query = query.filter_by(category=category)
    items = query.order_by(Task.status, Task.deadline.is_(None), Task.deadline, Task.created_at.desc()).all()
    return render_template("tasks.html", tasks=items, selected_status=status, selected_category=category, today=date.today())


@bp.route("/tasks/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def task_edit(item_id):
    item = owned_or_404(Task, item_id)
    if request.method == "POST":
        item.title = request.form.get("title", "").strip()
        item.category = request.form.get("category", "实验")
        item.priority = request.form.get("priority", "中")
        item.deadline = parse_date(request.form.get("deadline"))
        item.notes = request.form.get("notes", "").strip()
        if not item.title:
            flash("任务标题不能为空。", "danger")
        else:
            db.session.commit()
            flash("任务已更新。", "success")
            return redirect(url_for("main.tasks"))
    return render_template("task_edit.html", task=item)


@bp.post("/tasks/<int:item_id>/toggle")
@login_required
def task_toggle(item_id):
    item = owned_or_404(Task, item_id)
    item.status = "待办" if item.status == "完成" else "完成"
    db.session.commit()
    return redirect(request.referrer or url_for("main.tasks"))


@bp.post("/tasks/<int:item_id>/delete")
@login_required
def task_delete(item_id):
    db.session.delete(owned_or_404(Task, item_id))
    db.session.commit()
    flash("任务已删除。", "success")
    return redirect(url_for("main.tasks"))


@bp.route("/experiments", methods=["GET", "POST"])
@login_required
def experiments():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if title:
            item = Experiment(user_id=current_user.id, title=title, code=request.form.get("code", "").strip(),
                objective=request.form.get("objective", "").strip(), owner=request.form.get("owner", "").strip(),
                status=request.form.get("status", "未开始"), start_date=parse_date(request.form.get("start_date")),
                end_date=parse_date(request.form.get("end_date")))
            db.session.add(item)
            db.session.commit()
            flash("实验计划已创建。", "success")
            return redirect(url_for("main.experiment_detail", item_id=item.id))
        flash("实验名称不能为空。", "danger")
    status = request.args.get("status", "全部")
    query = Experiment.query.filter_by(user_id=current_user.id)
    if status != "全部":
        query = query.filter_by(status=status)
    return render_template("experiments.html", experiments=query.order_by(Experiment.updated_at.desc()).all(), selected_status=status)


@bp.route("/experiments/<int:item_id>", methods=["GET", "POST"])
@login_required
def experiment_detail(item_id):
    item = owned_or_404(Experiment, item_id)
    if request.method == "POST":
        item.title = request.form.get("title", "").strip()
        item.code = request.form.get("code", "").strip()
        item.objective = request.form.get("objective", "").strip()
        item.owner = request.form.get("owner", "").strip()
        item.status = request.form.get("status", "未开始")
        item.start_date = parse_date(request.form.get("start_date"))
        item.end_date = parse_date(request.form.get("end_date"))
        if not item.title:
            flash("实验名称不能为空。", "danger")
        else:
            db.session.commit()
            flash("实验信息已更新。", "success")
            return redirect(url_for("main.experiment_detail", item_id=item.id))
    return render_template("experiment_detail.html", experiment=item, today=date.today())


@bp.post("/experiments/<int:item_id>/delete")
@login_required
def experiment_delete(item_id):
    db.session.delete(owned_or_404(Experiment, item_id))
    db.session.commit()
    flash("实验及关联步骤、记录已删除。", "success")
    return redirect(url_for("main.experiments"))


@bp.post("/experiments/<int:item_id>/steps")
@login_required
def step_add(item_id):
    item = owned_or_404(Experiment, item_id)
    title = request.form.get("title", "").strip()
    if title:
        position = max([step.position for step in item.steps], default=0) + 1
        db.session.add(ExperimentStep(experiment_id=item.id, title=title, position=position,
                                      planned_date=parse_date(request.form.get("planned_date"))))
        db.session.commit()
    return redirect(url_for("main.experiment_detail", item_id=item.id))


@bp.post("/steps/<int:step_id>/toggle")
@login_required
def step_toggle(step_id):
    step = db.session.get(ExperimentStep, step_id)
    if not step or step.experiment.user_id != current_user.id:
        abort(404)
    step.is_done = not step.is_done
    db.session.commit()
    return redirect(url_for("main.experiment_detail", item_id=step.experiment_id))


@bp.post("/steps/<int:step_id>/delete")
@login_required
def step_delete(step_id):
    step = db.session.get(ExperimentStep, step_id)
    if not step or step.experiment.user_id != current_user.id:
        abort(404)
    experiment_id = step.experiment_id
    db.session.delete(step)
    db.session.commit()
    return redirect(url_for("main.experiment_detail", item_id=experiment_id))


@bp.post("/experiments/<int:item_id>/records")
@login_required
def record_add(item_id):
    item = owned_or_404(Experiment, item_id)
    content = request.form.get("content", "").strip()
    if not content:
        flash("实验过程不能为空。", "danger")
    else:
        db.session.add(ExperimentRecord(experiment_id=item.id,
            record_date=parse_date(request.form.get("record_date")) or date.today(),
            operator=request.form.get("operator", "").strip(), conditions=request.form.get("conditions", "").strip(),
            content=content, result=request.form.get("result", "待确认"), remark=request.form.get("remark", "").strip()))
        db.session.commit()
        flash("实验记录已保存。", "success")
    return redirect(url_for("main.experiment_detail", item_id=item.id))


@bp.post("/records/<int:record_id>/delete")
@login_required
def record_delete(record_id):
    record = db.session.get(ExperimentRecord, record_id)
    if not record or record.experiment.user_id != current_user.id:
        abort(404)
    experiment_id = record.experiment_id
    db.session.delete(record)
    db.session.commit()
    return redirect(url_for("main.experiment_detail", item_id=experiment_id))


@bp.route("/samples", methods=["GET", "POST"])
@login_required
def samples():
    if request.method == "POST":
        code = request.form.get("sample_code", "").strip()
        if code:
            db.session.add(Sample(user_id=current_user.id, sample_code=code,
                sample_type=request.form.get("sample_type", "").strip(), source=request.form.get("source", "").strip(),
                location=request.form.get("location", "").strip(), quantity=request.form.get("quantity", "").strip(),
                status=request.form.get("status", "可用"), notes=request.form.get("notes", "").strip()))
            db.session.commit()
            flash("样本已入库。", "success")
            return redirect(url_for("main.samples"))
        flash("样本编号不能为空。", "danger")
    keyword = request.args.get("q", "").strip()
    query = Sample.query.filter_by(user_id=current_user.id)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(or_(Sample.sample_code.ilike(pattern), Sample.sample_type.ilike(pattern),
                                 Sample.source.ilike(pattern), Sample.location.ilike(pattern)))
    return render_template("samples.html", samples=query.order_by(Sample.created_at.desc()).all(), keyword=keyword)


@bp.route("/samples/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def sample_edit(item_id):
    item = owned_or_404(Sample, item_id)
    if request.method == "POST":
        for field in ("sample_code", "sample_type", "source", "location", "quantity", "status", "notes"):
            setattr(item, field, request.form.get(field, "").strip())
        if item.sample_code:
            db.session.commit()
            flash("样本信息已更新。", "success")
            return redirect(url_for("main.samples"))
    return render_template("sample_edit.html", sample=item)


@bp.post("/samples/<int:item_id>/delete")
@login_required
def sample_delete(item_id):
    db.session.delete(owned_or_404(Sample, item_id))
    db.session.commit()
    return redirect(url_for("main.samples"))


@bp.route("/papers", methods=["GET", "POST"])
@login_required
def papers():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if title:
            item = Paper(user_id=current_user.id, title=title, journal=request.form.get("journal", "").strip(),
                status=request.form.get("status", "准备中"), submission_date=parse_date(request.form.get("submission_date")),
                revision_deadline=parse_date(request.form.get("revision_deadline")), notes=request.form.get("notes", "").strip())
            db.session.add(item)
            db.session.commit()
            return redirect(url_for("main.paper_detail", item_id=item.id))
        flash("论文标题不能为空。", "danger")
    items = Paper.query.filter_by(user_id=current_user.id).order_by(Paper.updated_at.desc()).all()
    return render_template("papers.html", papers=items, today=date.today())


@bp.route("/papers/<int:item_id>", methods=["GET", "POST"])
@login_required
def paper_detail(item_id):
    item = owned_or_404(Paper, item_id)
    if request.method == "POST":
        item.title = request.form.get("title", "").strip()
        item.journal = request.form.get("journal", "").strip()
        item.status = request.form.get("status", "准备中")
        item.submission_date = parse_date(request.form.get("submission_date"))
        item.revision_deadline = parse_date(request.form.get("revision_deadline"))
        item.notes = request.form.get("notes", "").strip()
        if item.title:
            db.session.commit()
            flash("论文信息已更新。", "success")
            return redirect(url_for("main.paper_detail", item_id=item.id))
    return render_template("paper_detail.html", paper=item)


@bp.post("/papers/<int:item_id>/comments")
@login_required
def comment_add(item_id):
    item = owned_or_404(Paper, item_id)
    comment = request.form.get("comment", "").strip()
    if comment:
        db.session.add(ReviewerComment(paper_id=item.id, reviewer=request.form.get("reviewer", "Reviewer 1").strip(),
            comment=comment, response=request.form.get("response", "").strip(), status=request.form.get("status", "待回复")))
        db.session.commit()
    return redirect(url_for("main.paper_detail", item_id=item.id))


@bp.post("/comments/<int:comment_id>/delete")
@login_required
def comment_delete(comment_id):
    item = db.session.get(ReviewerComment, comment_id)
    if not item or item.paper.user_id != current_user.id:
        abort(404)
    paper_id = item.paper_id
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("main.paper_detail", item_id=paper_id))


@bp.post("/papers/<int:item_id>/delete")
@login_required
def paper_delete(item_id):
    db.session.delete(owned_or_404(Paper, item_id))
    db.session.commit()
    return redirect(url_for("main.papers"))


@bp.get("/statistics")
@login_required
def statistics():
    month_start = date.today().replace(day=1)
    task_rows = (db.session.query(Task.status, func.count(Task.id)).filter(Task.user_id == current_user.id)
                 .group_by(Task.status).all())
    experiment_rows = (db.session.query(Experiment.status, func.count(Experiment.id)).filter(Experiment.user_id == current_user.id)
                       .group_by(Experiment.status).all())
    result_rows = (db.session.query(ExperimentRecord.result, func.count(ExperimentRecord.id)).join(Experiment)
                   .filter(Experiment.user_id == current_user.id, ExperimentRecord.record_date >= month_start)
                   .group_by(ExperimentRecord.result).all())
    task_counts = dict(task_rows)
    total = sum(task_counts.values())
    done = task_counts.get("完成", 0)
    metrics = {"tasks": total, "completion": round(done / total * 100) if total else 0,
               "monthly_records": sum(count for _, count in result_rows), "failed": dict(result_rows).get("失败", 0)}
    return render_template("statistics.html", metrics=metrics, task_counts=task_counts,
                           experiment_counts=dict(experiment_rows), result_counts=dict(result_rows))


@bp.route("/ai", methods=["GET", "POST"])
@login_required
def ai_assistant():
    result = None
    mode = None
    note = ""
    try:
        ai_config = current_ai_config()
    except SecretDecryptionError as exc:
        ai_config = AIConfig()
        flash(str(exc), "danger")
    if request.method == "POST":
        note = request.form.get("note", "").strip()
        if not note:
            flash("请先输入原始实验笔记。", "danger")
        else:
            try:
                result, mode = organize_note(note, ai_config)
                if mode == "local":
                    flash("未配置 API Key，已使用本地规则生成草稿。", "warning")
            except AIServiceError as exc:
                flash(str(exc), "danger")
    experiments = Experiment.query.filter_by(user_id=current_user.id).order_by(Experiment.updated_at.desc()).all()
    return render_template("ai.html", result=result, mode=mode, note=note, experiments=experiments,
                           today=date.today(), ai_config=ai_config)


@bp.route("/settings/api", methods=["GET", "POST"])
@login_required
def api_settings():
    if current_app.config["AI_SETTINGS_ADMIN_ONLY"] and not current_user.is_admin:
        abort(403)
    setting = ApiSetting.query.filter_by(user_id=current_user.id).first()
    environment = config_from_environment()
    models = []
    form_values = {
        "api_url": setting.api_url if setting else environment.api_url,
        "model": setting.model if setting else environment.model,
        "is_enabled": setting.is_enabled if setting else environment.enabled,
    }
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "use_environment":
            if setting:
                db.session.delete(setting)
                db.session.commit()
            flash("已恢复使用环境变量配置。", "success")
            return redirect(url_for("main.api_settings"))

        form_values = {
            "api_url": request.form.get("api_url", "").strip(),
            "model": request.form.get("model", "").strip(),
            "is_enabled": bool(request.form.get("is_enabled")),
        }
        api_key = request.form.get("api_key", "").strip()
        try:
            form_values["api_url"] = validate_api_url(
                form_values["api_url"], current_app.config["ALLOW_PRIVATE_API_URLS"], current_app.config["AI_ALLOWED_HOSTS"]
            )
            saved_key = setting.get_api_key() if setting and not api_key else ""
        except (AIServiceError, SecretDecryptionError) as exc:
            flash(str(exc), "danger")
            return render_template("api_settings.html", setting=setting, environment=environment,
                                   form_values=form_values, models=models)

        effective_key = api_key or saved_key
        if action == "test":
            try:
                models = fetch_models(AIConfig(api_url=form_values["api_url"], api_key=effective_key,
                                               model=form_values["model"], enabled=True, source="form",
                                               allow_private=current_app.config["ALLOW_PRIVATE_API_URLS"],
                                               allowed_hosts=current_app.config["AI_ALLOWED_HOSTS"]))
                flash(f"连接成功，读取到 {len(models)} 个模型。", "success")
            except AIServiceError as exc:
                flash(str(exc), "danger")
            return render_template("api_settings.html", setting=setting, environment=environment,
                                   form_values=form_values, models=models)

        if not form_values["model"]:
            flash("模型名称不能为空。", "danger")
            return render_template("api_settings.html", setting=setting, environment=environment,
                                   form_values=form_values, models=models)
        if not setting:
            setting = ApiSetting(user_id=current_user.id)
            db.session.add(setting)
        setting.api_url = form_values["api_url"]
        setting.model = form_values["model"]
        setting.is_enabled = form_values["is_enabled"]
        if request.form.get("clear_api_key"):
            setting.set_api_key("")
        elif api_key:
            setting.set_api_key(api_key)
        db.session.commit()
        flash("API 配置已加密保存。", "success")
        return redirect(url_for("main.api_settings"))

    return render_template("api_settings.html", setting=setting, environment=environment,
                           form_values=form_values, models=models)


@bp.post("/ai/save")
@login_required
def ai_save():
    experiment_id = request.form.get("experiment_id", type=int)
    experiment = owned_or_404(Experiment, experiment_id) if experiment_id else None
    content = request.form.get("content", "").strip()
    if not experiment or not content:
        flash("请选择实验并保留有效的实验过程。", "danger")
        return redirect(url_for("main.ai_assistant"))
    db.session.add(ExperimentRecord(
        experiment_id=experiment.id,
        record_date=parse_date(request.form.get("record_date")) or date.today(),
        operator=current_user.name,
        conditions=request.form.get("conditions", "").strip(),
        content=content,
        result=request.form.get("result", "待确认"),
        remark=request.form.get("remark", "").strip(),
    ))
    db.session.commit()
    flash("AI 草稿已保存为实验记录。", "success")
    return redirect(url_for("main.experiment_detail", item_id=experiment.id))


@bp.get("/export/<resource>.csv")
@login_required
def export_csv(resource):
    definitions = {
        "tasks": (Task, ["title", "category", "priority", "deadline", "status", "notes"]),
        "samples": (Sample, ["sample_code", "sample_type", "source", "location", "quantity", "status", "notes"]),
        "papers": (Paper, ["title", "journal", "status", "submission_date", "revision_deadline", "notes"]),
    }
    if resource not in definitions:
        abort(404)
    model, fields = definitions[resource]
    rows = model.query.filter_by(user_id=current_user.id).all()
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(fields)
    for row in rows:
        writer.writerow([getattr(row, field) or "" for field in fields])
    return Response(output.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={resource}.csv"})


@bp.post("/seed-demo")
@login_required
def seed_demo():
    if Task.query.filter_by(user_id=current_user.id).first():
        flash("当前账户已有数据，未重复添加示例。", "warning")
        return redirect(url_for("main.dashboard"))
    today = date.today()
    db.session.add_all([
        Task(user_id=current_user.id, title="完成 WB 一抗孵育", category="实验", priority="高", deadline=today),
        Task(user_id=current_user.id, title="整理本周实验数据", category="论文", priority="中", deadline=today + timedelta(days=2)),
        Sample(user_id=current_user.id, sample_code="OS-001", sample_type="骨肉瘤类器官", source="Patient 01",
               location="液氮 A区 / 2层 / 3号盒 / A5", quantity="3 管"),
        Paper(user_id=current_user.id, title="Organoid models for bone tumor research", journal="Advanced Healthcare Materials", status="返修中",
              revision_deadline=today + timedelta(days=21)),
    ])
    experiment = Experiment(user_id=current_user.id, title="药物处理后蛋白表达验证", code="EXP-2026-001",
                            objective="验证候选药物对目标蛋白表达的影响", owner=current_user.name,
                            status="进行中", start_date=today - timedelta(days=2), end_date=today + timedelta(days=2))
    db.session.add(experiment)
    db.session.flush()
    db.session.add_all([
        ExperimentStep(experiment_id=experiment.id, position=1, title="细胞铺板", planned_date=today - timedelta(days=2), is_done=True),
        ExperimentStep(experiment_id=experiment.id, position=2, title="药物处理 24h", planned_date=today - timedelta(days=1), is_done=True),
        ExperimentStep(experiment_id=experiment.id, position=3, title="Western Blot", planned_date=today),
        ExperimentRecord(experiment_id=experiment.id, record_date=today - timedelta(days=1), operator=current_user.name,
                         conditions="药物 5 μM，处理 24h", content="完成药物处理并收集蛋白样本。", result="成功", remark="细胞状态正常。"),
    ])
    db.session.commit()
    flash("示例数据已添加，可以开始探索。", "success")
    return redirect(url_for("main.dashboard"))
