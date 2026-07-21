import csv
import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import tempfile
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from . import db
from .ai_service import (
    AIConfig,
    AIServiceError,
    chat_with_assistant,
    config_from_environment,
    list_models as fetch_models,
    organize_note,
    validate_api_url,
)
from .models import (
    AIChatAttachment, AIConversation, AIMessage, AppearanceSetting, ApiSetting, Experiment,
    ExperimentAttachment, ExperimentParameter, ExperimentRecord, ExperimentSample, ExperimentStep,
    ExperimentTemplate, ExperimentTemplateParameter, ExperimentTemplateStep, Paper, RecordParameter,
    RecordTemplate, RecordTemplateParameter, ReviewerComment, Sample, Task, utcnow,
)
from .secrets import SecretDecryptionError


bp = Blueprint("main", __name__)
APPEARANCE_THEMES = {"research", "tech", "minimal", "cute"}
MAX_BACKGROUND_BYTES = 5 * 1024 * 1024
DATA_EXTENSIONS = {".csv", ".tsv", ".xls", ".xlsx", ".json", ".xml", ".txt", ".dat", ".sav", ".rds"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".md", ".rtf"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".gz", ".tar", ".bz2", ".xz"}
ATTACHMENT_MANUAL_CATEGORIES = ("原始数据", "结果图片", "分析结果", "实验文档", "其他")
ATTACHMENT_METADATA_CATEGORIES = ("图片", "数据", "文档", "压缩包", *ATTACHMENT_MANUAL_CATEGORIES)
REPEAT_KINDS = ("独立实验", "预实验", "生物学重复", "技术重复")
ASSISTANT_TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".log", ".py", ".r", ".html", ".css", ".js",
}
EXPERIMENT_AI_FIELDS = {"title", "code", "objective", "owner", "status", "start_date", "end_date"}
RECORD_AI_FIELDS = {"record_date", "operator", "conditions", "content", "result", "remark"}
AI_FIELD_LABELS = {
    "title": "实验名称", "code": "实验编号", "objective": "实验目的", "owner": "负责人",
    "status": "状态", "start_date": "开始日期", "end_date": "结束日期", "record_date": "记录日期",
    "operator": "实验人员", "conditions": "实验条件", "content": "实验过程", "result": "实验结果",
    "remark": "结论与备注", "steps": "新增实验步骤",
}
AI_FIELD_LIMITS = {"title": 160, "code": 60, "owner": 80, "status": 20, "operator": 80, "result": 20}
AI_RESEARCH_TERMS = ("历史", "对比", "比较", "周报", "本周", "检索", "查找", "记录", "参数", "结果", "计划", "当前")
AI_REVIEW_TERMS = (
    "剂量", "浓度", "给药", "临床", "诊断", "治疗", "患者", "统计", "显著", "p值", "p 值",
    "置信区间", "效应量", "生存分析", "毒性", "处方",
)


@bp.before_request
def enforce_read_only_role():
    personal_endpoints = {"main.appearance_settings", "main.assistant_new", "main.assistant_chat"}
    if (current_user.is_authenticated and current_user.role == "viewer"
            and request.method not in {"GET", "HEAD", "OPTIONS"}
            and request.endpoint not in personal_endpoints):
        abort(403)


def _appearance_upload_dir():
    return Path(current_app.config["APPEARANCE_UPLOAD_DIR"])


def _background_extension(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _preview_image_type(data):
    extension = _background_extension(data)
    if extension:
        return extension, {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[extension]
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif", "image/gif"
    return None, None


def _attachment_storage_root():
    return Path(current_app.config["ATTACHMENT_UPLOAD_DIR"])


def _clean_upload_relative_path(filename):
    raw_parts = (filename or "").replace("\\", "/").split("/")
    if any(part.strip() == ".." for part in raw_parts):
        raise ValueError("文件夹路径不能包含上级目录。")
    parts = []
    for raw_part in raw_parts:
        part = re.sub(r'[\x00-\x1f<>:"|?*]', "_", raw_part.strip())
        if part and part != ".":
            parts.append(part[:120])
    if not parts:
        raise ValueError("文件名不能为空。")
    if len(parts) > 12:
        raise ValueError("文件夹层级不能超过 12 层。")
    return "/".join(parts)


def _attachment_record_dir(record, record_date=None):
    target_date = record_date or record.record_date
    return (_attachment_storage_root() / f"user-{record.experiment.user_id}"
            / f"experiment-{record.experiment_id}" / target_date.isoformat() / f"record-{record.id}")


def _attachment_category(original_name, is_image):
    if is_image:
        return "图片"
    extension = Path(original_name).suffix.lower()
    if extension in DATA_EXTENSIONS:
        return "数据"
    if extension in DOCUMENT_EXTENSIONS:
        return "文档"
    if extension in ARCHIVE_EXTENSIONS:
        return "压缩包"
    return "其他"


def _requested_attachment_category():
    category = request.form.get("attachment_category", "自动分类").strip()
    if category == "自动分类":
        return None
    if category not in ATTACHMENT_MANUAL_CATEGORIES:
        abort(400)
    return category


def _save_record_attachment(record, uploaded_file, category=None):
    relative_path = _clean_upload_relative_path(uploaded_file.filename)
    original_name = relative_path.rsplit("/", 1)[-1]
    relative_parent = relative_path.split("/")[:-1]
    target_dir = _attachment_record_dir(record).joinpath(*relative_parent)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / original_name
    counter = 2
    while target_path.exists():
        suffix = Path(original_name).suffix
        stem = original_name[:-len(suffix)] if suffix else original_name
        target_path = target_dir / f"{stem} ({counter}){suffix}"
        counter += 1
    temporary_path = target_dir / f".{uuid4().hex}.upload"
    size = 0
    prefix = b""
    file_hash = hashlib.sha256()
    try:
        with temporary_path.open("wb") as output:
            while True:
                chunk = uploaded_file.stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                limit = current_app.config.get("MAX_ATTACHMENT_BYTES")
                if limit and size > limit:
                    raise ValueError("单个文件超过大小限制。")
                if len(prefix) < 16:
                    prefix += chunk[:16 - len(prefix)]
                file_hash.update(chunk)
                output.write(chunk)
        if size == 0:
            raise ValueError("不能上传空文件。")
        temporary_path.replace(target_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    image_extension, image_mimetype = _preview_image_type(prefix)
    guessed_mimetype = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    version_number = (db.session.query(func.max(ExperimentAttachment.version_number)).filter_by(
        record_id=record.id, relative_path=relative_path
    ).scalar() or 0) + 1
    attachment = ExperimentAttachment(
        experiment_id=record.experiment_id,
        record_id=record.id,
        original_name=original_name,
        relative_path=relative_path,
        stored_path=target_path.relative_to(_attachment_storage_root()).as_posix(),
        size_bytes=size,
        mime_type=image_mimetype or guessed_mimetype,
        category=category or _attachment_category(original_name, bool(image_extension)),
        is_previewable_image=bool(image_extension),
        sha256=file_hash.hexdigest(),
        version_number=version_number,
    )
    db.session.add(attachment)
    return attachment


def _attachment_path(attachment):
    root = _attachment_storage_root().resolve()
    path = (root / attachment.stored_path).resolve()
    if root not in path.parents:
        abort(404)
    return path


def _remove_attachment_file(attachment):
    path = _attachment_path(attachment)
    path.unlink(missing_ok=True)
    root = _attachment_storage_root().resolve()
    parent = path.parent
    while parent != root and root in parent.parents:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def _move_record_attachment_files(record, new_date):
    old_dir = _attachment_record_dir(record)
    new_dir = _attachment_record_dir(record, new_date)
    for attachment in record.attachments:
        old_path = _attachment_path(attachment)
        try:
            inside_record = old_path.relative_to(old_dir.resolve())
        except ValueError:
            continue
        new_path = new_dir / inside_record
        new_path.parent.mkdir(parents=True, exist_ok=True)
        if old_path.is_file():
            shutil.move(str(old_path), str(new_path))
        attachment.stored_path = new_path.relative_to(_attachment_storage_root()).as_posix()
    if old_dir.exists():
        shutil.rmtree(old_dir, ignore_errors=True)


def _remove_backgrounds(user_id):
    upload_dir = _appearance_upload_dir()
    if not upload_dir.exists():
        return
    for item in upload_dir.glob(f"user-{user_id}.*"):
        if item.is_file():
            item.unlink(missing_ok=True)


def _appearance_return_url():
    next_url = request.form.get("next", "")
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return url_for("main.dashboard")


@bp.app_context_processor
def inject_appearance():
    appearance = {"theme": "research", "color_mode": "light", "background_url": ""}
    if not current_user.is_authenticated:
        return {"appearance": appearance}
    setting = AppearanceSetting.query.filter_by(user_id=current_user.id).first()
    if not setting:
        return {"appearance": appearance}
    appearance["theme"] = setting.theme if setting.theme in APPEARANCE_THEMES else "research"
    appearance["color_mode"] = setting.color_mode if setting.color_mode in {"light", "dark"} else "light"
    background_path = _appearance_upload_dir() / (setting.background_filename or "")
    if setting.background_filename and background_path.is_file():
        appearance["background_url"] = url_for(
            "main.appearance_background", version=int(setting.updated_at.timestamp())
        )
    return {"appearance": appearance}


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else None
    except ValueError:
        return None


def _positive_int(value, default=1, maximum=999):
    try:
        parsed = int(value)
        return parsed if 1 <= parsed <= maximum else default
    except (TypeError, ValueError):
        return default


def _parameter_rows(prefix):
    names = request.form.getlist(f"{prefix}_name")
    values = request.form.getlist(f"{prefix}_value")
    units = request.form.getlist(f"{prefix}_unit")
    notes = request.form.getlist(f"{prefix}_notes")
    rows = []
    for index, raw_name in enumerate(names):
        name = raw_name.strip()[:120]
        if not name:
            continue
        rows.append({
            "position": len(rows) + 1,
            "name": name,
            "value": (values[index] if index < len(values) else "").strip()[:160],
            "unit": (units[index] if index < len(units) else "").strip()[:40],
            "notes": (notes[index] if index < len(notes) else "").strip()[:255],
        })
    return rows


def owned_or_404(model, item_id):
    item = db.session.get(model, item_id)
    if not item or item.user_id != current_user.id:
        abort(404)
    return item


def experiment_child_or_404(model, item_id):
    item = db.session.get(model, item_id)
    if not item or item.experiment.user_id != current_user.id:
        abort(404)
    return item


def attachment_owned_or_404(item_id):
    item = db.session.get(ExperimentAttachment, item_id)
    if not item or item.record.experiment.user_id != current_user.id:
        abort(404)
    return item


def template_or_404(item_id):
    item = db.session.get(ExperimentTemplate, item_id)
    if not item or item.user_id != current_user.id:
        abort(404)
    return item


def template_child_or_404(model, item_id):
    item = db.session.get(model, item_id)
    if not item or item.template.user_id != current_user.id:
        abort(404)
    return item


def record_template_or_404(item_id):
    item = db.session.get(RecordTemplate, item_id)
    if not item or item.user_id != current_user.id:
        abort(404)
    return item


def record_template_child_or_404(item_id):
    item = db.session.get(RecordTemplateParameter, item_id)
    if not item or item.template.user_id != current_user.id:
        abort(404)
    return item


def _json_list(value):
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _selected_experiment_ids(values, limit=20):
    selected = []
    for value in values:
        try:
            item_id = int(value)
        except (TypeError, ValueError):
            continue
        if item_id > 0 and item_id not in selected:
            selected.append(item_id)
    if not selected:
        return []
    owned_ids = {
        row[0] for row in db.session.query(Experiment.id).filter(
            Experiment.user_id == current_user.id, Experiment.id.in_(selected[:limit])
        ).all()
    }
    return [item_id for item_id in selected[:limit] if item_id in owned_ids]


def _experiment_sample_requirements(item):
    return [
        {
            "role": usage.role or "实验样本",
            "amount_used": usage.amount_used or "",
            "notes": usage.notes or "",
        }
        for usage in item.sample_usages
    ]


def _apply_step_template(template, item, start_date, replace=False):
    if replace:
        for step in list(item.steps):
            db.session.delete(step)
        db.session.flush()
    step_position = 0 if replace else len(item.steps)
    for index, step in enumerate(template.steps, start=1):
        db.session.add(ExperimentStep(
            experiment_id=item.id, position=step_position + index, title=step.title,
            description=step.description, operator=item.owner,
            planned_date=start_date + timedelta(days=step.planned_offset_days),
        ))


def experiment_sample_or_404(item_id):
    item = db.session.get(ExperimentSample, item_id)
    if not item or item.experiment.user_id != current_user.id:
        abort(404)
    return item


def experiment_parameter_or_404(item_id):
    item = db.session.get(ExperimentParameter, item_id)
    if not item or item.experiment.user_id != current_user.id:
        abort(404)
    return item


def record_parameter_or_404(item_id):
    item = db.session.get(RecordParameter, item_id)
    if not item or item.record.experiment.user_id != current_user.id:
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


@bp.app_context_processor
def inject_assistant_page():
    page_type = ""
    page_id = None
    view_args = request.view_args or {}
    endpoint = request.endpoint or ""
    if endpoint == "main.experiment_detail":
        page_type, page_id = "experiment", view_args.get("item_id")
    elif endpoint == "main.record_detail":
        page_type, page_id = "record", view_args.get("record_id")
    return {"assistant_page": {"type": page_type, "id": page_id}}


def _serialize_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def _assistant_page_context(page_type, page_id):
    if page_type == "experiment" and page_id:
        item = owned_or_404(Experiment, page_id)
        fields = {field: _serialize_value(getattr(item, field)) for field in EXPERIMENT_AI_FIELDS}
        return {
            "page_type": "experiment", "page_id": item.id, "fields": fields,
            "steps": [
                {
                    "title": step.title, "description": step.description, "operator": step.operator,
                    "planned_date": _serialize_value(step.planned_date), "is_done": step.is_done,
                }
                for step in item.steps
            ],
        }
    if page_type == "record" and page_id:
        item = experiment_child_or_404(ExperimentRecord, page_id)
        return {
            "page_type": "record", "page_id": item.id, "experiment_id": item.experiment_id,
            "experiment_title": item.experiment.title,
            "fields": {field: _serialize_value(getattr(item, field)) for field in RECORD_AI_FIELDS},
        }
    return {"page_type": "", "page_id": None, "fields": {}}


def _short_ai_text(value, limit=700):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _assistant_research_context(page_context, query, selected_ids=None):
    current_experiment_id = page_context.get("page_id") if page_context.get("page_type") == "experiment" else page_context.get("experiment_id")
    research_requested = any(term in query for term in AI_RESEARCH_TERMS)
    explicit_scope = selected_ids is not None
    selected_ids = selected_ids or []
    if not current_experiment_id and not research_requested and not selected_ids:
        return {
            "period": None, "experiments": [], "records": [],
            "instructions": "当前问题未请求科研数据库上下文，因此没有附加实验数据。",
        }, []

    experiments = []
    if explicit_scope:
        experiments = Experiment.query.filter(
            Experiment.user_id == current_user.id, Experiment.id.in_(selected_ids)
        ).all() if selected_ids else []
        order = {item_id: index for index, item_id in enumerate(selected_ids)}
        experiments.sort(key=lambda item: order.get(item.id, len(order)))
    elif research_requested:
        experiments = Experiment.query.filter_by(user_id=current_user.id).order_by(Experiment.updated_at.desc()).limit(8).all()
    if current_experiment_id and not explicit_scope:
        current_item = db.session.get(Experiment, current_experiment_id)
        if current_item and current_item.user_id == current_user.id:
            experiments = [current_item, *[item for item in experiments if item.id != current_item.id]][:8]

    record_query = ExperimentRecord.query.join(Experiment).filter(Experiment.user_id == current_user.id)
    if explicit_scope:
        record_query = record_query.filter(ExperimentRecord.experiment_id.in_(selected_ids)) if selected_ids else record_query.filter(ExperimentRecord.id == -1)
    elif current_experiment_id and not research_requested:
        record_query = record_query.filter(ExperimentRecord.experiment_id == current_experiment_id)
    weekly = any(term in query for term in ("周报", "本周"))
    period = None
    if weekly:
        start = date.today() - timedelta(days=date.today().weekday())
        end = start + timedelta(days=6)
        record_query = record_query.filter(ExperimentRecord.record_date.between(start, end))
        period = {"start": start.isoformat(), "end": end.isoformat()}
    records = record_query.order_by(ExperimentRecord.record_date.desc(), ExperimentRecord.updated_at.desc()).limit(16).all()
    if page_context.get("page_type") == "record":
        current_record = db.session.get(ExperimentRecord, page_context.get("page_id"))
        if current_record and current_record.experiment.user_id == current_user.id:
            records = [current_record, *[item for item in records if item.id != current_record.id]][:16]

    references = []
    experiment_rows = []
    for item in experiments:
        citation = f"R{len(references) + 1}"
        references.append({
            "citation": citation, "type": "experiment", "id": item.id,
            "title": f"{item.code or '未编号'} · {item.title}",
            "url": url_for("main.experiment_detail", item_id=item.id),
            "excerpt": _short_ai_text(item.objective, 180) or f"状态：{item.status}",
        })
        experiment_rows.append({
            "reference": f"[{citation}]", "id": item.id, "title": item.title, "code": item.code,
            "batch": item.batch_code, "repeat": f"{item.repeat_kind} #{item.repeat_number}",
            "group": item.group_name, "objective": _short_ai_text(item.objective), "status": item.status,
            "dates": [_serialize_value(item.start_date), _serialize_value(item.end_date)],
            "plan_parameters": [
                {"name": parameter.name, "value": parameter.value, "unit": parameter.unit, "notes": parameter.notes}
                for parameter in item.plan_parameters[:16]
            ],
        })

    record_rows = []
    for item in records:
        citation = f"R{len(references) + 1}"
        references.append({
            "citation": citation, "type": "experiment_record", "id": item.id,
            "title": f"{item.experiment.code or item.experiment.title} · {item.record_date.isoformat()}",
            "url": url_for("main.record_detail", record_id=item.id),
            "excerpt": _short_ai_text(item.content, 180),
        })
        record_rows.append({
            "reference": f"[{citation}]", "id": item.id, "experiment_id": item.experiment_id,
            "experiment": item.experiment.title, "date": item.record_date.isoformat(), "operator": item.operator,
            "conditions": _short_ai_text(item.conditions), "process": _short_ai_text(item.content),
            "result": item.result, "remark": _short_ai_text(item.remark),
            "parameters": [
                {"name": parameter.name, "value": parameter.value, "unit": parameter.unit, "notes": parameter.notes}
                for parameter in item.parameters[:20]
            ],
            "attachments": [
                {
                    "name": attachment.original_name, "category": attachment.category,
                    "tags": attachment.tags, "description": _short_ai_text(attachment.description, 300),
                }
                for attachment in item.attachments[:12]
            ],
        })
    return {
        "period": period, "experiments": experiment_rows, "records": record_rows,
        "instructions": (
            "仅依据用户勾选的实验范围回答；引用时使用对应的 [R编号]，数据缺失时明确说明。"
            if explicit_scope else
            "仅依据这些数据回答；引用时使用对应的 [R编号]，数据缺失时明确说明。"
        ),
    }, references


def _assistant_system_prompt(page_context, file_context, research_context):
    return f"""你是医学科研实验助手。回答必须严谨，不得编造实验数据、文献或引用。
你的作用是基于现有数据辅助用户，不替用户决定实验结论。涉及剂量、临床解释、统计结论或风险时，必须在回答中明确提醒人工核验。
你可以根据历史实验生成下一次计划、对比多次实验参数和结果、整理 CSV/文档节选及图片的已有说明、生成实验周报，并检索实验记录。
引用内部资料时必须使用上下文给出的 [R编号]；没有资料支持的内容必须标注为建议或未知。不得声称已读取无法解析的二进制文件或图片像素。
你可以规划实验、分析记录、整理附件，并在用户明确要求时生成结构化页面修改提案。生成“下一次实验计划”时使用新建实验计划提案。
始终只输出一个合法 JSON 对象，格式为：
{{"reply":"给用户的中文回答","proposal":null}}
proposal 只允许以下格式之一：
1. 修改当前实验：{{"action":"update_experiment","changes":{{"title":"","code":"","objective":"","owner":"","status":"未开始/进行中/完成/暂停","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD"}},"steps":[{{"title":"","description":"","operator":"","planned_date":"YYYY-MM-DD"}}]}}
2. 修改当前记录：{{"action":"update_record","changes":{{"record_date":"YYYY-MM-DD","operator":"","conditions":"","content":"","result":"待确认/成功/失败","remark":""}}}}
3. 新建实验计划：{{"action":"create_experiment","changes":{{"title":"","code":"","objective":"","owner":"","status":"未开始/进行中/完成/暂停","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD"}},"steps":[{{"title":"","description":"","operator":"","planned_date":"YYYY-MM-DD"}}]}}
只有用户要求添加、修改或生成可保存实验计划时才返回 proposal；不要返回不在格式中的字段。页面写入前仍需用户确认。
当前页面上下文：{json.dumps(page_context, ensure_ascii=False)}
用户上传文件信息与可读取节选：{json.dumps(file_context, ensure_ascii=False)}
用户可访问的科研数据与内部引用：{json.dumps(research_context, ensure_ascii=False)}"""


def _assistant_requires_review(query, reply):
    haystack = f"{query}\n{reply}".lower()
    return any(term.lower() in haystack for term in AI_REVIEW_TERMS)


def _assistant_internal_references(references, query, reply):
    cited = set(re.findall(r"\[R(\d+)\]", reply, re.I))
    if cited:
        return [item for item in references if item["citation"][1:] in cited]
    if any(term in query for term in AI_RESEARCH_TERMS):
        return references[:6]
    return []


def _safe_json(value, fallback):
    try:
        return json.loads(value) if value else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def _clean_ai_step(raw):
    if not isinstance(raw, dict) or not str(raw.get("title", "")).strip():
        return None
    return {
        "title": str(raw.get("title", "")).strip()[:160],
        "description": str(raw.get("description", "")).strip(),
        "operator": str(raw.get("operator", "")).strip()[:80],
        "planned_date": str(raw.get("planned_date", "")).strip(),
    }


def _normalize_assistant_proposal(raw, page_context):
    if not isinstance(raw, dict):
        return None, {}
    action = str(raw.get("action", "")).strip()
    if action == "update_experiment" and page_context.get("page_type") == "experiment":
        allowed = EXPERIMENT_AI_FIELDS
    elif action == "update_record" and page_context.get("page_type") == "record":
        allowed = RECORD_AI_FIELDS
    elif action == "create_experiment":
        allowed = EXPERIMENT_AI_FIELDS
    else:
        return None, {}

    changes = {
        key: str(value if value is not None else "").strip()[:AI_FIELD_LIMITS.get(key)]
        if AI_FIELD_LIMITS.get(key) else str(value if value is not None else "").strip()
        for key, value in (raw.get("changes") or {}).items() if key in allowed
    }
    if action == "create_experiment" and not changes.get("title"):
        return None, {}
    current_fields = page_context.get("fields", {})
    if action != "create_experiment":
        changes = {key: value for key, value in changes.items() if value != current_fields.get(key, "")}
    steps = []
    if action in {"update_experiment", "create_experiment"}:
        steps = [step for step in (_clean_ai_step(item) for item in (raw.get("steps") or [])[:50]) if step]
    if not changes and not steps:
        return None, {}

    proposal = {
        "action": action, "target_id": page_context.get("page_id"),
        "changes": changes, "steps": steps,
    }
    before = {key: current_fields.get(key, "") for key in changes} if action != "create_experiment" else {}
    diff = [
        {"field": AI_FIELD_LABELS.get(key, key), "before": before.get(key, "（新建）"), "after": value}
        for key, value in changes.items()
    ]
    if steps:
        diff.append({
            "field": AI_FIELD_LABELS["steps"], "before": "0 条" if action == "create_experiment" else "不删除现有步骤",
            "after": "\n".join(f"{index}. {step['title']}" for index, step in enumerate(steps, 1)),
        })
    proposal["diff"] = diff
    return proposal, before


def _ai_upload_root():
    return Path(current_app.config["AI_UPLOAD_DIR"])


def _extract_text_excerpt(path, original_name):
    extension = Path(original_name).suffix.lower()
    try:
        if extension in ASSISTANT_TEXT_EXTENSIONS:
            data = path.read_bytes()[:200_000]
            return data.decode("utf-8", errors="replace")[:120_000]
        if extension == ".docx":
            with zipfile.ZipFile(path) as archive:
                xml = archive.read("word/document.xml")[:1_000_000].decode("utf-8", errors="replace")
            return re.sub(r"<[^>]+>", " ", xml)[:120_000]
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""
    return ""


def _save_ai_attachment(message, uploaded_file):
    clean_name = _clean_upload_relative_path(uploaded_file.filename).rsplit("/", 1)[-1]
    target_dir = _ai_upload_root() / f"user-{current_user.id}" / f"conversation-{message.conversation_id}" / f"message-{message.id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / clean_name
    counter = 2
    while target.exists():
        suffix = Path(clean_name).suffix
        stem = clean_name[:-len(suffix)] if suffix else clean_name
        target = target_dir / f"{stem} ({counter}){suffix}"
        counter += 1
    size = 0
    with target.open("wb") as output:
        while True:
            chunk = uploaded_file.stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            output.write(chunk)
    attachment = AIChatAttachment(
        message_id=message.id, original_name=clean_name,
        stored_path=target.relative_to(_ai_upload_root()).as_posix(), size_bytes=size,
        mime_type=mimetypes.guess_type(clean_name)[0] or "application/octet-stream",
        text_excerpt=_extract_text_excerpt(target, clean_name),
    )
    db.session.add(attachment)
    return attachment


def _conversation_or_404(conversation_id):
    item = db.session.get(AIConversation, conversation_id)
    if not item or item.user_id != current_user.id:
        abort(404)
    return item


def _assistant_message_payload(message):
    references = [
        item for item in _safe_json(message.references_json, [])
        if isinstance(item, dict) and str(item.get("url", "")).startswith(("/", "http://", "https://"))
    ]
    proposal = _safe_json(message.proposal_json, None)
    return {
        "id": message.id, "role": message.role, "content": message.content,
        "created_at": message.created_at.strftime("%Y-%m-%d %H:%M"),
        "model_name": message.model_name,
        "has_prompt_snapshot": bool(message.prompt_snapshot),
        "requires_human_review": bool(message.requires_human_review),
        "references": references,
        "attachments": [
            {"id": item.id, "name": item.original_name, "size": item.size_label}
            for item in message.attachments
        ],
        "proposal": proposal,
        "applied": bool(message.applied_at),
    }


@bp.post("/settings/appearance")
@login_required
def appearance_settings():
    setting = AppearanceSetting.query.filter_by(user_id=current_user.id).first()
    if not setting:
        setting = AppearanceSetting(user_id=current_user.id)
        db.session.add(setting)

    action = request.form.get("action", "save")
    if action == "reset":
        _remove_backgrounds(current_user.id)
        setting.theme = "research"
        setting.color_mode = "light"
        setting.background_filename = ""
        db.session.commit()
        flash("外观已恢复默认。", "success")
        return redirect(_appearance_return_url())

    if action == "clear_background":
        _remove_backgrounds(current_user.id)
        setting.background_filename = ""
        db.session.commit()
        flash("自定义背景已移除。", "success")
        return redirect(_appearance_return_url())

    theme = request.form.get("theme", "research")
    color_mode = "dark" if request.form.get("dark_mode") else "light"
    if theme not in APPEARANCE_THEMES:
        abort(400)
    setting.theme = theme
    setting.color_mode = color_mode

    background = request.files.get("background")
    if background and background.filename:
        data = background.read(MAX_BACKGROUND_BYTES + 1)
        if len(data) > MAX_BACKGROUND_BYTES:
            flash("背景图片不能超过 5 MB。", "danger")
            return redirect(_appearance_return_url())
        extension = _background_extension(data)
        if not extension:
            flash("背景只支持 PNG、JPEG 或 WebP 图片。", "danger")
            return redirect(_appearance_return_url())
        upload_dir = _appearance_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)
        _remove_backgrounds(current_user.id)
        filename = f"user-{current_user.id}.{extension}"
        temporary = upload_dir / f".{filename}.tmp"
        temporary.write_bytes(data)
        temporary.replace(upload_dir / filename)
        setting.background_filename = filename

    db.session.commit()
    flash("外观设置已保存。", "success")
    return redirect(_appearance_return_url())


@bp.get("/settings/appearance/background")
@login_required
def appearance_background():
    setting = AppearanceSetting.query.filter_by(user_id=current_user.id).first()
    if not setting or not setting.background_filename:
        abort(404)
    background_path = _appearance_upload_dir() / setting.background_filename
    if not background_path.is_file():
        abort(404)
    mimetype = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}.get(
        background_path.suffix.lower(), "application/octet-stream"
    )
    return send_file(
        io.BytesIO(background_path.read_bytes()), mimetype=mimetype,
        download_name=setting.background_filename, max_age=3600
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
                end_date=parse_date(request.form.get("end_date")),
                batch_code=request.form.get("batch_code", "").strip(),
                repeat_kind=request.form.get("repeat_kind", "独立实验") if request.form.get("repeat_kind") in REPEAT_KINDS else "独立实验",
                repeat_number=_positive_int(request.form.get("repeat_number")),
                group_name=request.form.get("group_name", "").strip())
            db.session.add(item)
            db.session.commit()
            flash("实验计划已创建。", "success")
            return redirect(url_for("main.experiment_detail", item_id=item.id))
        flash("实验名称不能为空。", "danger")
    status = request.args.get("status", "全部")
    query = Experiment.query.filter_by(user_id=current_user.id)
    if status != "全部":
        query = query.filter_by(status=status)
    return render_template(
        "experiments.html", experiments=query.order_by(Experiment.updated_at.desc()).all(), selected_status=status,
        templates=ExperimentTemplate.query.filter_by(user_id=current_user.id).order_by(ExperimentTemplate.name).all(),
        repeat_kinds=REPEAT_KINDS, today=date.today(),
    )


@bp.post("/experiments/from-template")
@login_required
def experiment_from_template():
    template = template_or_404(_positive_int(request.form.get("template_id"), default=0))
    start_date = parse_date(request.form.get("start_date")) or date.today()
    item = Experiment(
        user_id=current_user.id,
        title=request.form.get("title", "").strip() or template.name,
        code=request.form.get("code", "").strip(),
        objective="",
        owner=request.form.get("owner", "").strip() or current_user.name,
        status="未开始",
        start_date=start_date,
        batch_code=request.form.get("batch_code", "").strip(),
        repeat_kind=request.form.get("repeat_kind", "独立实验") if request.form.get("repeat_kind") in REPEAT_KINDS else "独立实验",
        repeat_number=_positive_int(request.form.get("repeat_number")),
        group_name=request.form.get("group_name", "").strip(),
    )
    db.session.add(item)
    db.session.flush()
    _apply_step_template(template, item, start_date)
    db.session.commit()
    flash(f"已从模板“{template.name}”创建实验。", "success")
    return redirect(url_for("main.experiment_detail", item_id=item.id))


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
        item.batch_code = request.form.get("batch_code", "").strip()
        item.repeat_kind = request.form.get("repeat_kind", "独立实验") if request.form.get("repeat_kind") in REPEAT_KINDS else "独立实验"
        item.repeat_number = _positive_int(request.form.get("repeat_number"))
        item.group_name = request.form.get("group_name", "").strip()
        if not item.title:
            flash("实验名称不能为空。", "danger")
        else:
            db.session.commit()
            flash("实验信息已更新。", "success")
            return redirect(url_for("main.experiment_detail", item_id=item.id))
    selected_record_template = None
    record_template_id = request.args.get("record_template_id", type=int)
    if record_template_id:
        selected_record_template = record_template_or_404(record_template_id)
    return render_template(
        "experiment_detail.html", experiment=item, today=date.today(),
        attachment_categories=ATTACHMENT_MANUAL_CATEGORIES,
        repeat_kinds=REPEAT_KINDS,
        sample_requirements=_json_list(item.sample_requirements_json),
        step_templates=ExperimentTemplate.query.filter_by(user_id=current_user.id).order_by(ExperimentTemplate.name).all(),
        record_templates=RecordTemplate.query.filter_by(user_id=current_user.id).order_by(RecordTemplate.name).all(),
        selected_record_template=selected_record_template,
        available_samples=Sample.query.filter_by(user_id=current_user.id).order_by(Sample.sample_code).all(),
    )


@bp.post("/experiments/<int:item_id>/save-template")
@login_required
def experiment_save_template(item_id):
    item = owned_or_404(Experiment, item_id)
    if not item.steps:
        flash("请先添加实验步骤，再保存步骤模板。", "danger")
        return redirect(url_for("main.experiment_detail", item_id=item.id, _anchor="step-templates"))
    name = request.form.get("name", "").strip() or item.title
    template = ExperimentTemplate(
        user_id=current_user.id, name=name,
        description=request.form.get("description", "").strip(), objective="",
    )
    db.session.add(template)
    db.session.flush()
    for step in item.steps:
        offset = (step.planned_date - item.start_date).days if item.start_date and step.planned_date else max(step.position - 1, 0)
        db.session.add(ExperimentTemplateStep(
            template_id=template.id, position=step.position, title=step.title,
            description=step.description, planned_offset_days=offset,
        ))
    db.session.commit()
    flash(f"已保存步骤模板“{name}”，包含 {len(item.steps)} 个步骤。", "success")
    return redirect(url_for("main.experiment_template_detail", item_id=template.id))


@bp.route("/templates/<int:item_id>", methods=["GET", "POST"])
@login_required
def experiment_template_detail(item_id):
    template = template_or_404(item_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("模板名称不能为空。", "danger")
        else:
            template.name = name
            template.description = request.form.get("description", "").strip()
            db.session.commit()
            flash("步骤模板信息已保存。", "success")
            return redirect(url_for("main.experiment_template_detail", item_id=template.id))
    return render_template(
        "template_detail.html", template=template,
        experiments=Experiment.query.filter_by(user_id=current_user.id).order_by(Experiment.updated_at.desc()).all(),
    )


@bp.post("/templates/<int:item_id>/steps")
@login_required
def experiment_template_step_add(item_id):
    template = template_or_404(item_id)
    title = request.form.get("title", "").strip()
    if title:
        db.session.add(ExperimentTemplateStep(
            template_id=template.id, position=len(template.steps) + 1, title=title,
            description=request.form.get("description", "").strip(),
            planned_offset_days=max(0, _positive_int(request.form.get("planned_offset_days"), default=0)),
        ))
        db.session.commit()
        flash("模板步骤已添加。", "success")
    else:
        flash("步骤标题不能为空。", "danger")
    return redirect(url_for("main.experiment_template_detail", item_id=template.id))


@bp.post("/template-steps/<int:item_id>/delete")
@login_required
def experiment_template_step_delete(item_id):
    step = template_child_or_404(ExperimentTemplateStep, item_id)
    template_id = step.template_id
    db.session.delete(step)
    db.session.commit()
    return redirect(url_for("main.experiment_template_detail", item_id=template_id))


@bp.post("/templates/<int:item_id>/parameters")
@login_required
def experiment_template_parameter_add(item_id):
    template = template_or_404(item_id)
    rows = _parameter_rows("template_parameter")
    for row in rows:
        row["position"] = len(template.parameters) + row["position"]
        db.session.add(ExperimentTemplateParameter(template_id=template.id, **row))
    if rows:
        db.session.commit()
        flash(f"已添加 {len(rows)} 个模板参数。", "success")
    else:
        flash("参数名称不能为空。", "danger")
    return redirect(url_for("main.experiment_template_detail", item_id=template.id))


@bp.post("/template-parameters/<int:item_id>/delete")
@login_required
def experiment_template_parameter_delete(item_id):
    parameter = template_child_or_404(ExperimentTemplateParameter, item_id)
    template_id = parameter.template_id
    db.session.delete(parameter)
    db.session.commit()
    return redirect(url_for("main.experiment_template_detail", item_id=template_id))


@bp.post("/templates/<int:item_id>/apply")
@login_required
def experiment_template_apply(item_id):
    template = template_or_404(item_id)
    experiment = owned_or_404(Experiment, _positive_int(request.form.get("experiment_id"), default=0))
    start_date = experiment.start_date or date.today()
    replace = request.form.get("apply_mode", "replace") == "replace"
    _apply_step_template(template, experiment, start_date, replace=replace)
    db.session.commit()
    flash(f"已将步骤模板“{template.name}”{('替换' if replace else '追加')}到实验。", "success")
    return redirect(url_for("main.experiment_detail", item_id=experiment.id))


@bp.post("/experiments/<int:item_id>/apply-step-template")
@login_required
def experiment_apply_step_template(item_id):
    experiment = owned_or_404(Experiment, item_id)
    template = template_or_404(_positive_int(request.form.get("template_id"), default=0))
    start_date = experiment.start_date or date.today()
    replace = request.form.get("apply_mode", "append") == "replace"
    _apply_step_template(template, experiment, start_date, replace=replace)
    db.session.commit()
    flash(f"步骤模板“{template.name}”已{('替换当前步骤' if replace else '追加到当前步骤')}。", "success")
    return redirect(url_for("main.experiment_detail", item_id=experiment.id, _anchor="step-templates"))


@bp.post("/experiments/<int:item_id>/record-template")
@login_required
def experiment_record_template_update(item_id):
    item = owned_or_404(Experiment, item_id)
    item.record_conditions_template = request.form.get("record_conditions_template", "").strip()
    item.record_content_template = request.form.get("record_content_template", "").strip()
    item.record_remark_template = request.form.get("record_remark_template", "").strip()
    db.session.commit()
    flash("新增实验记录的默认内容已保存。", "success")
    return redirect(url_for("main.experiment_detail", item_id=item.id, _anchor="record-template"))


@bp.post("/templates/<int:item_id>/delete")
@login_required
def experiment_template_delete(item_id):
    template = template_or_404(item_id)
    db.session.delete(template)
    db.session.commit()
    flash("实验模板已删除。", "success")
    return redirect(url_for("main.experiments"))


@bp.post("/experiments/<int:item_id>/parameters")
@login_required
def experiment_parameter_add(item_id):
    item = owned_or_404(Experiment, item_id)
    rows = _parameter_rows("plan_parameter")
    for row in rows:
        row["position"] = len(item.plan_parameters) + row["position"]
        db.session.add(ExperimentParameter(experiment_id=item.id, **row))
    if rows:
        db.session.commit()
        flash(f"已添加 {len(rows)} 个计划参数。", "success")
    else:
        flash("参数名称不能为空。", "danger")
    return redirect(url_for("main.experiment_detail", item_id=item.id))


@bp.post("/experiment-parameters/<int:item_id>/delete")
@login_required
def experiment_parameter_delete(item_id):
    parameter = experiment_parameter_or_404(item_id)
    experiment_id = parameter.experiment_id
    db.session.delete(parameter)
    db.session.commit()
    return redirect(url_for("main.experiment_detail", item_id=experiment_id))


@bp.post("/experiments/<int:item_id>/samples")
@login_required
def experiment_sample_add(item_id):
    item = owned_or_404(Experiment, item_id)
    sample = owned_or_404(Sample, _positive_int(request.form.get("sample_id"), default=0))
    existing = ExperimentSample.query.filter_by(experiment_id=item.id, sample_id=sample.id).first()
    if existing:
        existing.role = request.form.get("role", "实验样本").strip()
        existing.amount_used = request.form.get("amount_used", "").strip()
        existing.notes = request.form.get("notes", "").strip()
        flash("样本使用信息已更新。", "success")
    else:
        db.session.add(ExperimentSample(
            experiment_id=item.id, sample_id=sample.id,
            role=request.form.get("role", "实验样本").strip(),
            amount_used=request.form.get("amount_used", "").strip(),
            notes=request.form.get("notes", "").strip(),
        ))
        flash("样本已关联到实验。", "success")
    db.session.commit()
    return redirect(url_for("main.experiment_detail", item_id=item.id))


@bp.post("/experiment-samples/<int:item_id>/delete")
@login_required
def experiment_sample_delete(item_id):
    usage = experiment_sample_or_404(item_id)
    experiment_id = usage.experiment_id
    db.session.delete(usage)
    db.session.commit()
    return redirect(url_for("main.experiment_detail", item_id=experiment_id))


@bp.post("/experiments/<int:item_id>/delete")
@login_required
def experiment_delete(item_id):
    item = owned_or_404(Experiment, item_id)
    for record in item.records:
        for attachment in record.attachments:
            _remove_attachment_file(attachment)
    db.session.delete(item)
    db.session.commit()
    flash("实验及关联步骤、记录和文件已删除。", "success")
    return redirect(url_for("main.experiments"))


@bp.post("/experiments/<int:item_id>/steps")
@login_required
def step_add(item_id):
    item = owned_or_404(Experiment, item_id)
    title = request.form.get("title", "").strip()
    if title:
        position = max([step.position for step in item.steps], default=0) + 1
        db.session.add(ExperimentStep(experiment_id=item.id, title=title, position=position,
            description=request.form.get("description", "").strip(),
            operator=request.form.get("operator", "").strip(),
            planned_date=parse_date(request.form.get("planned_date"))))
        db.session.commit()
        flash("实验步骤已添加。", "success")
    else:
        flash("步骤标题不能为空。", "danger")
    return redirect(url_for("main.experiment_detail", item_id=item.id))


@bp.route("/steps/<int:step_id>/edit", methods=["GET", "POST"])
@login_required
def step_edit(step_id):
    step = experiment_child_or_404(ExperimentStep, step_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("步骤标题不能为空。", "danger")
        else:
            step.title = title
            step.description = request.form.get("description", "").strip()
            step.operator = request.form.get("operator", "").strip()
            step.planned_date = parse_date(request.form.get("planned_date"))
            step.completed_date = parse_date(request.form.get("completed_date")) if step.is_done else None
            db.session.commit()
            flash("实验步骤已更新。", "success")
            return redirect(url_for("main.experiment_detail", item_id=step.experiment_id))
    return render_template("step_edit.html", step=step)


@bp.post("/steps/<int:step_id>/toggle")
@login_required
def step_toggle(step_id):
    step = experiment_child_or_404(ExperimentStep, step_id)
    step.is_done = not step.is_done
    step.completed_date = date.today() if step.is_done else None
    db.session.commit()
    return redirect(url_for("main.experiment_detail", item_id=step.experiment_id))


@bp.post("/steps/<int:step_id>/delete")
@login_required
def step_delete(step_id):
    step = experiment_child_or_404(ExperimentStep, step_id)
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
        record = ExperimentRecord(experiment_id=item.id,
            record_date=parse_date(request.form.get("record_date")) or date.today(),
            operator=request.form.get("operator", "").strip(), conditions=request.form.get("conditions", "").strip(),
            content=content, result=request.form.get("result", "待确认"), remark=request.form.get("remark", "").strip())
        db.session.add(record)
        db.session.flush()

        for row in _parameter_rows("record_parameter"):
            db.session.add(RecordParameter(record_id=record.id, **row))

        files = [uploaded for uploaded in request.files.getlist("files") if uploaded and uploaded.filename]
        category = _requested_attachment_category()
        saved = 0
        errors = []
        for uploaded_file in files:
            try:
                _save_record_attachment(record, uploaded_file, category)
                saved += 1
            except ValueError as exc:
                errors.append(f"{uploaded_file.filename}: {exc}")
        db.session.commit()
        message = "实验记录已保存。"
        if saved:
            message += f" 已同时导入 {saved} 个文件。"
        flash(message, "success")
        if errors:
            flash(f"有 {len(errors)} 个文件未导入：{'；'.join(errors[:3])}", "warning")
        if files:
            return redirect(url_for("main.record_detail", record_id=record.id))
    return redirect(url_for("main.experiment_detail", item_id=item.id))


@bp.route("/records/<int:record_id>", methods=["GET", "POST"])
@login_required
def record_detail(record_id):
    record = experiment_child_or_404(ExperimentRecord, record_id)
    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if not content:
            flash("实验过程不能为空。", "danger")
        else:
            new_date = parse_date(request.form.get("record_date")) or record.record_date
            if new_date != record.record_date:
                _move_record_attachment_files(record, new_date)
                record.record_date = new_date
            record.operator = request.form.get("operator", "").strip()
            record.conditions = request.form.get("conditions", "").strip()
            record.content = content
            record.result = request.form.get("result", "待确认")
            record.remark = request.form.get("remark", "").strip()
            db.session.commit()
            flash("实验记录已更新。", "success")
            return redirect(url_for("main.record_detail", record_id=record.id))
    attachment_groups = {}
    for attachment in record.attachments:
        attachment_groups.setdefault(attachment.category, []).append(attachment)
    return render_template(
        "record_detail.html", record=record, attachment_groups=attachment_groups,
        attachment_storage_path=str(_attachment_record_dir(record).resolve()),
        attachment_categories=ATTACHMENT_MANUAL_CATEGORIES,
        attachment_metadata_categories=tuple(dict.fromkeys(ATTACHMENT_METADATA_CATEGORIES)),
        record_templates=RecordTemplate.query.filter_by(user_id=current_user.id).order_by(RecordTemplate.name).all(),
    )


@bp.post("/records/<int:record_id>/save-template")
@login_required
def record_template_save(record_id):
    record = experiment_child_or_404(ExperimentRecord, record_id)
    name = request.form.get("name", "").strip() or f"{record.experiment.title}记录模板"
    template = RecordTemplate(
        user_id=current_user.id, name=name,
        description=request.form.get("description", "").strip(),
        conditions=record.conditions or "", content=record.content or "", remark=record.remark or "",
    )
    db.session.add(template)
    db.session.flush()
    for parameter in record.parameters:
        db.session.add(RecordTemplateParameter(
            template_id=template.id, position=parameter.position, name=parameter.name,
            value=parameter.value, unit=parameter.unit, notes=parameter.notes,
        ))
    db.session.commit()
    flash(f"已保存记录模板“{name}”，包含 {len(record.parameters)} 个参数。", "success")
    return redirect(url_for("main.record_template_detail", item_id=template.id))


@bp.route("/record-templates/<int:item_id>", methods=["GET", "POST"])
@login_required
def record_template_detail(item_id):
    template = record_template_or_404(item_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        content = request.form.get("content", "").strip()
        if not name or not content:
            flash("模板名称和实验过程不能为空。", "danger")
        else:
            template.name = name
            template.description = request.form.get("description", "").strip()
            template.conditions = request.form.get("conditions", "").strip()
            template.content = content
            template.remark = request.form.get("remark", "").strip()
            db.session.commit()
            flash("实验记录模板已保存。", "success")
            return redirect(url_for("main.record_template_detail", item_id=template.id))
    return render_template(
        "record_template_detail.html", template=template,
        experiments=Experiment.query.filter_by(user_id=current_user.id).order_by(Experiment.updated_at.desc()).all(),
    )


@bp.post("/record-templates/<int:item_id>/parameters")
@login_required
def record_template_parameter_add(item_id):
    template = record_template_or_404(item_id)
    rows = _parameter_rows("record_template_parameter")
    for row in rows:
        row["position"] = len(template.parameters) + row["position"]
        db.session.add(RecordTemplateParameter(template_id=template.id, **row))
    if rows:
        db.session.commit()
        flash(f"已添加 {len(rows)} 个模板参数。", "success")
    else:
        flash("参数名称不能为空。", "danger")
    return redirect(url_for("main.record_template_detail", item_id=template.id))


@bp.post("/record-template-parameters/<int:item_id>/delete")
@login_required
def record_template_parameter_delete(item_id):
    parameter = record_template_child_or_404(item_id)
    template_id = parameter.template_id
    db.session.delete(parameter)
    db.session.commit()
    return redirect(url_for("main.record_template_detail", item_id=template_id))


@bp.post("/record-templates/<int:item_id>/delete")
@login_required
def record_template_delete(item_id):
    template = record_template_or_404(item_id)
    db.session.delete(template)
    db.session.commit()
    flash("实验记录模板已删除。", "success")
    return redirect(request.form.get("next") or url_for("main.experiments"))


@bp.get("/record-templates/<int:item_id>/use")
@login_required
def record_template_use(item_id):
    template = record_template_or_404(item_id)
    experiment_id = request.args.get("experiment_id", type=int)
    if not experiment_id:
        abort(404)
    experiment = owned_or_404(Experiment, experiment_id)
    return redirect(url_for(
        "main.experiment_detail", item_id=experiment.id,
        record_template_id=template.id, _anchor="new-record",
    ))


@bp.post("/records/<int:record_id>/attachments")
@login_required
def attachment_upload(record_id):
    record = experiment_child_or_404(ExperimentRecord, record_id)
    category = _requested_attachment_category()
    files = [item for item in request.files.getlist("files") if item and item.filename]
    if not files:
        flash("请先选择文件或文件夹。", "danger")
        return redirect(url_for("main.record_detail", record_id=record.id))

    saved = 0
    errors = []
    for uploaded_file in files:
        try:
            _save_record_attachment(record, uploaded_file, category)
            saved += 1
        except ValueError as exc:
            errors.append(f"{uploaded_file.filename}: {exc}")
    if saved:
        db.session.commit()
        flash(f"已导入 {saved} 个结果或数据文件。", "success")
    if errors:
        flash(f"有 {len(errors)} 个文件未导入：{'；'.join(errors[:3])}", "warning")
    return redirect(url_for("main.record_detail", record_id=record.id))


@bp.post("/records/<int:record_id>/parameters")
@login_required
def record_parameter_add(record_id):
    record = experiment_child_or_404(ExperimentRecord, record_id)
    rows = _parameter_rows("record_parameter")
    for row in rows:
        row["position"] = len(record.parameters) + row["position"]
        db.session.add(RecordParameter(record_id=record.id, **row))
    if rows:
        db.session.commit()
        flash(f"已添加 {len(rows)} 个记录参数。", "success")
    else:
        flash("参数名称不能为空。", "danger")
    return redirect(url_for("main.record_detail", record_id=record.id))


@bp.post("/record-parameters/<int:item_id>/delete")
@login_required
def record_parameter_delete(item_id):
    parameter = record_parameter_or_404(item_id)
    record_id = parameter.record_id
    db.session.delete(parameter)
    db.session.commit()
    return redirect(url_for("main.record_detail", record_id=record_id))


@bp.get("/attachments/<int:item_id>/download")
@login_required
def attachment_download(item_id):
    attachment = attachment_owned_or_404(item_id)
    path = _attachment_path(attachment)
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype=attachment.mime_type, as_attachment=True,
                     download_name=attachment.original_name)


@bp.get("/attachments/<int:item_id>/preview")
@login_required
def attachment_preview(item_id):
    attachment = attachment_owned_or_404(item_id)
    if not attachment.is_previewable_image:
        abort(404)
    path = _attachment_path(attachment)
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype=attachment.mime_type, max_age=3600)


@bp.post("/records/<int:record_id>/open-folder")
@login_required
def attachment_open_folder(record_id):
    record = experiment_child_or_404(ExperimentRecord, record_id)
    if not current_app.config.get("ALLOW_OPEN_LOCAL_FOLDERS"):
        abort(404)
    if request.remote_addr not in {"127.0.0.1", "::1", None}:
        abort(403)
    folder = _attachment_record_dir(record).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if os.name != "nt" or not hasattr(os, "startfile"):
        flash(f"文件目录：{folder}", "warning")
    else:
        os.startfile(str(folder))
        flash("已在资源管理器中打开实验文件夹。", "success")
    return redirect(url_for("main.record_detail", record_id=record.id))


@bp.post("/attachments/<int:item_id>/delete")
@login_required
def attachment_delete(item_id):
    attachment = attachment_owned_or_404(item_id)
    record_id = attachment.record_id
    _remove_attachment_file(attachment)
    db.session.delete(attachment)
    db.session.commit()
    flash("文件已删除。", "success")
    return redirect(url_for("main.record_detail", record_id=record_id))


@bp.post("/attachments/<int:item_id>/metadata")
@login_required
def attachment_metadata(item_id):
    attachment = attachment_owned_or_404(item_id)
    category = request.form.get("category", "其他").strip()
    if category not in ATTACHMENT_METADATA_CATEGORIES:
        abort(400)
    attachment.category = category
    attachment.tags = request.form.get("tags", "").strip()[:255]
    attachment.description = request.form.get("description", "").strip()
    db.session.commit()
    flash("文件说明和标签已保存。", "success")
    return redirect(url_for("main.record_detail", record_id=attachment.record_id))


@bp.post("/attachments/<int:item_id>/verify")
@login_required
def attachment_verify(item_id):
    attachment = attachment_owned_or_404(item_id)
    path = _attachment_path(attachment)
    if not path.is_file():
        abort(404)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    current_digest = digest.hexdigest()
    if not attachment.sha256:
        attachment.sha256 = current_digest
        db.session.commit()
        flash("已为旧文件建立 SHA-256 校验基线。", "success")
    elif current_digest == attachment.sha256:
        flash("文件完整性校验通过。", "success")
    else:
        flash("文件内容已发生变化，请核对本地原始文件。", "danger")
    return redirect(url_for("main.record_detail", record_id=attachment.record_id))


@bp.post("/records/<int:record_id>/delete")
@login_required
def record_delete(record_id):
    record = experiment_child_or_404(ExperimentRecord, record_id)
    experiment_id = record.experiment_id
    for attachment in record.attachments:
        _remove_attachment_file(attachment)
    db.session.delete(record)
    db.session.commit()
    return redirect(url_for("main.experiment_detail", item_id=experiment_id))


def _markdown_value(value, fallback="未填写"):
    return str(value).strip() if value not in (None, "") else fallback


def _experiment_markdown(item):
    lines = [
        f"# {item.title}",
        "",
        f"- 实验编号：{_markdown_value(item.code, '未设置')}",
        f"- 实验批次：{_markdown_value(item.batch_code, '未设置')}",
        f"- 重复类型：{item.repeat_kind} #{item.repeat_number}",
        f"- 实验分组：{_markdown_value(item.group_name)}",
        f"- 状态：{item.status}",
        f"- 负责人：{_markdown_value(item.owner)}",
        f"- 计划开始：{_markdown_value(item.start_date, '未安排')}",
        f"- 计划结束：{_markdown_value(item.end_date, '未安排')}",
        f"- 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 实验目的",
        "",
        _markdown_value(item.objective),
        "",
        "## 关联样本",
        "",
    ]
    if item.sample_usages:
        for usage in item.sample_usages:
            lines.append(
                f"- {usage.sample.sample_code} · {usage.role} · 用量 {_markdown_value(usage.amount_used)}"
                f" · {_markdown_value(usage.notes)}"
            )
    else:
        lines.append("暂无关联样本。")
    lines.extend(["", "## 计划参数", ""])
    if item.plan_parameters:
        lines.extend([
            f"- {parameter.name}：{_markdown_value(parameter.value)} {parameter.unit}".rstrip()
            + (f"（{parameter.notes}）" if parameter.notes else "")
            for parameter in item.plan_parameters
        ])
    else:
        lines.append("暂无结构化计划参数。")
    lines.extend([
        "",
        "## 实验步骤",
        "",
    ])
    if item.steps:
        for step in item.steps:
            marker = "x" if step.is_done else " "
            lines.extend([
                f"{step.position}. [{marker}] {step.title}",
                f"   - 执行人：{_markdown_value(step.operator)}",
                f"   - 计划日期：{_markdown_value(step.planned_date, '未安排')}",
                f"   - 完成日期：{_markdown_value(step.completed_date, '未完成')}",
                f"   - 步骤说明：{_markdown_value(step.description)}",
            ])
    else:
        lines.append("暂无实验步骤。")

    lines.extend(["", "## 实验记录", ""])
    records = sorted(item.records, key=lambda record: (record.record_date, record.id))
    if records:
        for index, record in enumerate(records, start=1):
            lines.extend([
                f"### {index}. {record.record_date} · {record.result}",
                "",
                f"- 实验人员：{_markdown_value(record.operator)}",
                "",
                "#### 结构化参数",
                "",
            ])
            if record.parameters:
                lines.extend([
                    f"- {parameter.name}：{_markdown_value(parameter.value)} {parameter.unit}".rstrip()
                    + (f"（{parameter.notes}）" if parameter.notes else "")
                    for parameter in record.parameters
                ])
            else:
                lines.append("暂无结构化记录参数。")
            lines.extend([
                "",
                "#### 实验条件",
                "",
                _markdown_value(record.conditions),
                "",
                "#### 实验过程",
                "",
                record.content,
                "",
                "#### 结论与备注",
                "",
                _markdown_value(record.remark),
                "",
            ])
            if record.attachments:
                lines.extend(["#### 结果与数据文件", ""])
                for attachment in sorted(record.attachments, key=lambda item: item.relative_path.lower()):
                    lines.append(
                        f"- [{attachment.category}] {attachment.relative_path} · v{attachment.version_number}"
                        f" · {attachment.size_label} · SHA-256 {attachment.sha256 or '旧文件未计算'}"
                    )
                lines.append("")
    else:
        lines.append("暂无实验记录。")

    return "\ufeff" + "\n".join(lines).rstrip() + "\n"


@bp.get("/experiments/<int:item_id>/export.md")
@login_required
def experiment_export(item_id):
    item = owned_or_404(Experiment, item_id)
    content = _experiment_markdown(item)
    display_name = f"{item.code or f'experiment-{item.id}'}-{item.title}.md"
    return Response(
        content,
        mimetype="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": (
                f"attachment; filename=experiment-{item.id}.md; filename*=UTF-8''{quote(display_name, safe='')}"
            )
        },
    )


@bp.get("/experiments/<int:item_id>/archive.zip")
@login_required
def experiment_archive(item_id):
    item = owned_or_404(Experiment, item_id)
    archive = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    manifest_output = io.StringIO()
    manifest_writer = csv.writer(manifest_output)
    manifest_writer.writerow([
        "record_date", "record_id", "category", "relative_path", "version", "size_bytes",
        "mime_type", "sha256", "tags", "description", "archive_path",
    ])
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("report.md", _experiment_markdown(item).encode("utf-8"))
        for record in sorted(item.records, key=lambda value: (value.record_date, value.id)):
            for attachment in sorted(record.attachments, key=lambda value: (value.relative_path, value.version_number)):
                relative_path = attachment.relative_path.replace("\\", "/")
                path_parts = relative_path.split("/")
                if attachment.version_number > 1:
                    path_parts[-1] = f"v{attachment.version_number}-{path_parts[-1]}"
                archive_path = "/".join([
                    "files", record.record_date.isoformat(), f"record-{record.id}", attachment.category, *path_parts,
                ])
                source_path = _attachment_path(attachment)
                exists = source_path.is_file()
                if exists:
                    bundle.write(source_path, archive_path)
                manifest_writer.writerow([
                    record.record_date, record.id, attachment.category, attachment.relative_path,
                    attachment.version_number, attachment.size_bytes, attachment.mime_type,
                    attachment.sha256, attachment.tags, attachment.description,
                    archive_path if exists else "文件缺失",
                ])
        bundle.writestr("file-manifest.csv", ("\ufeff" + manifest_output.getvalue()).encode("utf-8"))
    archive.seek(0)
    display_name = f"{item.code or f'experiment-{item.id}'}-{item.title}-archive.zip"
    return send_file(archive, mimetype="application/zip", as_attachment=True, download_name=display_name)


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


def _presentation_payload(items, start, end, title, include_images):
    item_ids = [item.id for item in items]
    records = ExperimentRecord.query.filter(
        ExperimentRecord.experiment_id.in_(item_ids), ExperimentRecord.record_date.between(start, end)
    ).order_by(ExperimentRecord.record_date.desc(), ExperimentRecord.updated_at.desc()).all()
    attachments = []
    if include_images and records:
        record_ids = [record.id for record in records]
        attachments = ExperimentAttachment.query.filter(
            ExperimentAttachment.record_id.in_(record_ids), ExperimentAttachment.is_previewable_image.is_(True)
        ).order_by(ExperimentAttachment.created_at.desc()).limit(12).all()
    status_counts = {}
    for item in items:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
    success_count = sum(1 for record in records if record.result == "成功")
    attention_count = sum(1 for record in records if record.result in {"失败", "待确认"})
    experiment_rows = []
    for item in items:
        item_records = [record for record in records if record.experiment_id == item.id]
        latest = item_records[0] if item_records else None
        completed_steps = sum(1 for step in item.steps if step.is_done)
        experiment_rows.append({
            "id": item.id, "title": item.title, "code": item.code or f"EXP-{item.id}",
            "objective": _short_ai_text(item.objective, 260), "status": item.status,
            "record_count": len(item_records), "step_count": len(item.steps),
            "completed_steps": completed_steps,
            "latest_result": (
                f"{latest.record_date.isoformat()} · {latest.result} · {_short_ai_text(latest.remark or latest.content, 100)}"
                if latest else "所选日期内暂无记录"
            ),
        })
    evidence = []
    for record in records[:12]:
        parameter_text = "；".join(
            f"{parameter.name} {parameter.value} {parameter.unit}".strip() for parameter in record.parameters
        ) or _short_ai_text(record.conditions, 160) or "未填写结构化参数"
        evidence.append({
            "date": record.record_date.isoformat(), "experiment": record.experiment.title,
            "result": record.result, "parameters": parameter_text,
            "summary": _short_ai_text(record.remark or record.content, 260),
        })
    image_rows = []
    for attachment in attachments:
        source = Path(attachment.stored_path)
        if source.is_file():
            image_rows.append({
                "path": str(source.resolve()), "mime_type": attachment.mime_type,
                "name": attachment.original_name, "experiment": attachment.record.experiment.title,
                "description": attachment.description or attachment.tags or attachment.relative_path,
                "alt": f"{attachment.record.experiment.title} 的实验结果：{attachment.original_name}",
            })
    next_actions = []
    for item in items:
        for step in item.steps:
            if not step.is_done:
                next_actions.append(f"{item.title}：{step.title}" + (f"（{step.planned_date.isoformat()}）" if step.planned_date else ""))
    return {
        "title": title,
        "author": current_user.name,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "metrics": {
            "experiment_count": len(items), "record_count": len(records),
            "success_count": success_count, "attention_count": attention_count,
            "image_count": len(image_rows),
        },
        "status_counts": status_counts,
        "experiments": experiment_rows,
        "evidence": evidence,
        "images": image_rows,
        "next_actions": next_actions,
    }


@bp.route("/reports/presentation", methods=["GET", "POST"])
@login_required
def presentation_report():
    week_start = date.today() - timedelta(days=date.today().weekday())
    week_end = week_start + timedelta(days=6)
    experiments = Experiment.query.filter_by(user_id=current_user.id).order_by(Experiment.updated_at.desc()).all()
    selected_ids = _selected_experiment_ids(
        request.form.getlist("experiment_ids") if request.method == "POST" else request.args.getlist("experiment_id")
    )
    if request.method == "POST":
        start = parse_date(request.form.get("start_date")) or week_start
        end = parse_date(request.form.get("end_date")) or week_end
        if end < start:
            flash("结束日期不能早于开始日期。", "danger")
        elif not selected_ids:
            flash("请至少选择一个实验。", "danger")
        else:
            selected = [item for item in experiments if item.id in selected_ids]
            title = request.form.get("title", "").strip()[:120] or f"实验周报 · {start.isoformat()}"
            payload = _presentation_payload(selected, start, end, title, bool(request.form.get("include_images")))
            try:
                from .presentation_service import PresentationBuildError, build_weekly_presentation

                presentation = build_weekly_presentation(payload)
            except PresentationBuildError as exc:
                current_app.logger.exception("Weekly presentation build failed")
                flash(str(exc), "danger")
            else:
                return send_file(
                    io.BytesIO(presentation),
                    mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    as_attachment=True,
                    download_name=f"{title}.pptx",
                )
    return render_template(
        "presentation_report.html", experiments=experiments, selected_ids=selected_ids,
        week_start=week_start, week_end=week_end,
    )


@bp.get("/assistant/state")
@login_required
def assistant_state():
    conversation_id = request.args.get("conversation_id", type=int)
    if conversation_id:
        conversation = _conversation_or_404(conversation_id)
    else:
        conversation = AIConversation.query.filter_by(user_id=current_user.id).order_by(
            AIConversation.updated_at.desc()
        ).first()
    try:
        config = current_ai_config()
        enabled = config.enabled
        web_capable = config.enabled and (config.api_url.startswith("https://api.openai.com/") or config.api_url == "https://api.openai.com")
        model = config.model
    except SecretDecryptionError:
        enabled, web_capable, model = False, False, ""
    experiment_options = Experiment.query.filter_by(user_id=current_user.id).order_by(
        Experiment.updated_at.desc()
    ).limit(100).all()
    return {
        "conversation": ({
            "id": conversation.id, "title": conversation.title,
            "selected_experiment_ids": _json_list(conversation.selected_experiment_ids_json),
            "messages": [_assistant_message_payload(message) for message in conversation.messages],
        } if conversation else None),
        "experiments": [
            {
                "id": item.id, "title": item.title, "code": item.code or "未编号",
                "status": item.status, "updated_at": item.updated_at.date().isoformat(),
            }
            for item in experiment_options
        ],
        "api": {"enabled": enabled, "web_capable": web_capable, "model": model},
    }


@bp.post("/assistant/conversations")
@login_required
def assistant_new():
    page_type = request.form.get("page_type", "").strip()
    page_id = request.form.get("page_id", type=int)
    context = _assistant_page_context(page_type, page_id) if page_type and page_id else {"page_type": "", "page_id": None}
    item = AIConversation(
        user_id=current_user.id, title="新对话",
        page_type=context.get("page_type", ""), page_id=context.get("page_id"),
        selected_experiment_ids_json=json.dumps(
            _selected_experiment_ids(request.form.getlist("experiment_ids")), ensure_ascii=False
        ),
    )
    db.session.add(item)
    db.session.commit()
    return {"id": item.id, "title": item.title}


@bp.post("/assistant/chat")
@login_required
def assistant_chat():
    content = request.form.get("message", "").strip()
    uploads = [item for item in request.files.getlist("files") if item and item.filename]
    if not content and not uploads:
        return {"error": "请输入消息或选择文件。"}, 400

    conversation_id = request.form.get("conversation_id", type=int)
    page_type = request.form.get("page_type", "").strip()
    page_id = request.form.get("page_id", type=int)
    page_context = _assistant_page_context(page_type, page_id) if page_type and page_id else {
        "page_type": "", "page_id": None, "fields": {},
    }
    if conversation_id:
        conversation = _conversation_or_404(conversation_id)
    else:
        conversation = AIConversation(
            user_id=current_user.id, title=(content or uploads[0].filename)[:60],
            page_type=page_context.get("page_type", ""), page_id=page_context.get("page_id"),
        )
        db.session.add(conversation)
        db.session.flush()
    if request.form.get("experiment_scope_present"):
        selected_ids = _selected_experiment_ids(request.form.getlist("experiment_ids"))
        conversation.selected_experiment_ids_json = json.dumps(selected_ids, ensure_ascii=False)
    else:
        stored_scope = _selected_experiment_ids(_json_list(conversation.selected_experiment_ids_json))
        selected_ids = stored_scope if stored_scope else None
    if conversation.title == "新对话" and content:
        conversation.title = content[:60]

    user_message = AIMessage(conversation_id=conversation.id, role="user", content=content or "请分析上传的文件。")
    db.session.add(user_message)
    conversation.updated_at = utcnow()
    db.session.flush()
    saved_attachments = []
    for upload in uploads:
        try:
            saved_attachments.append(_save_ai_attachment(user_message, upload))
        except ValueError as exc:
            db.session.rollback()
            return {"error": str(exc)}, 400
    db.session.commit()

    file_context = [
        {
            "name": item.original_name, "mime_type": item.mime_type, "size": item.size_label,
            "text_excerpt": item.text_excerpt,
        }
        for item in saved_attachments
    ]
    history = [
        {"role": item.role, "content": item.content}
        for item in conversation.messages[-16:] if item.role in {"user", "assistant"}
    ]
    research_context, internal_references = _assistant_research_context(page_context, content, selected_ids)
    prompt_snapshot = _assistant_system_prompt(page_context, file_context, research_context)
    try:
        ai_config = current_ai_config()
        result = chat_with_assistant(
            history, prompt_snapshot, ai_config,
            web_access=bool(request.form.get("web_access")),
        )
        proposal, before = _normalize_assistant_proposal(result.get("proposal"), page_context)
        reply = result["reply"]
        if result.get("web_requested") and not result.get("web_used"):
            reply += "\n\n当前兼容 API 未启用内置网页检索，本次回答未声称使用网络来源。"
        references = [
            *_assistant_internal_references(internal_references, content, reply),
            *result.get("references", []),
        ]
        assistant_message = AIMessage(
            conversation_id=conversation.id, role="assistant", content=reply,
            references_json=json.dumps(references, ensure_ascii=False),
            proposal_json=json.dumps(proposal, ensure_ascii=False) if proposal else "",
            before_json=json.dumps(before, ensure_ascii=False) if before else "",
            model_name=ai_config.model,
            prompt_snapshot=prompt_snapshot,
            context_snapshot_json=json.dumps({
                "page": page_context, "files": file_context, "research": research_context,
            }, ensure_ascii=False),
            requires_human_review=_assistant_requires_review(content, reply),
        )
        db.session.add(assistant_message)
        db.session.commit()
        return {
            "conversation_id": conversation.id,
            "user_message": _assistant_message_payload(user_message),
            "assistant_message": _assistant_message_payload(assistant_message),
        }
    except (AIServiceError, SecretDecryptionError) as exc:
        error_message = AIMessage(
            conversation_id=conversation.id, role="assistant",
            content=f"AI 调用失败：{exc}",
            prompt_snapshot=prompt_snapshot,
        )
        db.session.add(error_message)
        db.session.commit()
        return {
            "conversation_id": conversation.id,
            "user_message": _assistant_message_payload(user_message),
            "assistant_message": _assistant_message_payload(error_message),
            "error": str(exc),
        }, 502


def _set_ai_fields(item, changes, date_fields=()):
    for field, value in changes.items():
        setattr(item, field, parse_date(value) if field in date_fields else value)


def _invalid_ai_date(changes, fields):
    return next((field for field in fields if field in changes and changes[field] and not parse_date(changes[field])), None)


@bp.post("/assistant/proposals/<int:message_id>/apply")
@login_required
def assistant_apply_proposal(message_id):
    message = db.session.get(AIMessage, message_id)
    if not message or message.conversation.user_id != current_user.id or message.role != "assistant":
        abort(404)
    if message.applied_at:
        return {"error": "这个修改提案已经保存过。"}, 409
    proposal = _safe_json(message.proposal_json, None)
    before = _safe_json(message.before_json, {})
    if not isinstance(proposal, dict):
        return {"error": "没有可应用的页面修改提案。"}, 400
    action = proposal.get("action")
    changes = proposal.get("changes") or {}
    steps = proposal.get("steps") or []
    redirect_url = ""

    if action == "update_experiment":
        item = owned_or_404(Experiment, proposal.get("target_id"))
        if any(_serialize_value(getattr(item, field)) != old for field, old in before.items()):
            return {"error": "页面内容在提案生成后已发生变化，请重新让 AI 生成修改建议。"}, 409
        if changes.get("status") and changes["status"] not in {"未开始", "进行中", "完成", "暂停"}:
            return {"error": "实验状态不合法。"}, 400
        invalid_date = _invalid_ai_date(changes, {"start_date", "end_date"})
        if invalid_date:
            return {"error": f"{AI_FIELD_LABELS[invalid_date]}格式不合法。"}, 400
        if "title" in changes and not changes["title"]:
            return {"error": "实验名称不能为空。"}, 400
        _set_ai_fields(item, changes, {"start_date", "end_date"})
        if not item.title:
            return {"error": "实验名称不能为空。"}, 400
        position = max([step.position for step in item.steps], default=0)
        for raw in steps:
            position += 1
            db.session.add(ExperimentStep(
                experiment_id=item.id, position=position, title=raw["title"],
                description=raw.get("description", ""), operator=raw.get("operator", ""),
                planned_date=parse_date(raw.get("planned_date")),
            ))
        redirect_url = url_for("main.experiment_detail", item_id=item.id)
    elif action == "update_record":
        item = experiment_child_or_404(ExperimentRecord, proposal.get("target_id"))
        if any(_serialize_value(getattr(item, field)) != old for field, old in before.items()):
            return {"error": "页面内容在提案生成后已发生变化，请重新让 AI 生成修改建议。"}, 409
        if changes.get("result") and changes["result"] not in {"待确认", "成功", "失败"}:
            return {"error": "实验结果不合法。"}, 400
        if "record_date" in changes and not parse_date(changes["record_date"]):
            return {"error": "记录日期格式不合法。"}, 400
        if "content" in changes and not changes["content"]:
            return {"error": "实验过程不能为空。"}, 400
        new_date = parse_date(changes.get("record_date")) if "record_date" in changes else item.record_date
        if new_date and new_date != item.record_date:
            _move_record_attachment_files(item, new_date)
        _set_ai_fields(item, changes, {"record_date"})
        if not item.content:
            return {"error": "实验过程不能为空。"}, 400
        redirect_url = url_for("main.record_detail", record_id=item.id)
    elif action == "create_experiment":
        if changes.get("status") and changes["status"] not in {"未开始", "进行中", "完成", "暂停"}:
            return {"error": "实验状态不合法。"}, 400
        invalid_date = _invalid_ai_date(changes, {"start_date", "end_date"})
        if invalid_date:
            return {"error": f"{AI_FIELD_LABELS[invalid_date]}格式不合法。"}, 400
        item = Experiment(user_id=current_user.id, title=changes.get("title", "").strip())
        if not item.title:
            return {"error": "实验名称不能为空。"}, 400
        _set_ai_fields(item, changes, {"start_date", "end_date"})
        db.session.add(item)
        db.session.flush()
        for position, raw in enumerate(steps, 1):
            db.session.add(ExperimentStep(
                experiment_id=item.id, position=position, title=raw["title"],
                description=raw.get("description", ""), operator=raw.get("operator", ""),
                planned_date=parse_date(raw.get("planned_date")),
            ))
        redirect_url = url_for("main.experiment_detail", item_id=item.id)
    else:
        return {"error": "不支持的修改类型。"}, 400

    message.applied_at = utcnow()
    db.session.commit()
    return {"ok": True, "redirect_url": redirect_url}


@bp.get("/assistant/files/<int:item_id>/download")
@login_required
def assistant_file_download(item_id):
    item = db.session.get(AIChatAttachment, item_id)
    if not item or item.message.conversation.user_id != current_user.id:
        abort(404)
    root = _ai_upload_root().resolve()
    path = (root / item.stored_path).resolve()
    if root not in path.parents or not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=item.original_name, mimetype=item.mime_type)


@bp.get("/assistant/messages/<int:message_id>/prompt.txt")
@login_required
def assistant_prompt_snapshot(message_id):
    item = db.session.get(AIMessage, message_id)
    if not item or item.conversation.user_id != current_user.id or not item.prompt_snapshot:
        abort(404)
    content = "\ufeff" + item.prompt_snapshot.rstrip() + "\n"
    return Response(content, mimetype="text/plain; charset=utf-8", headers={
        "Content-Disposition": f"inline; filename=ai-prompt-{item.id}.txt"
    })


@bp.get("/assistant/conversations/<int:conversation_id>/export.md")
@login_required
def assistant_export(conversation_id):
    conversation = _conversation_or_404(conversation_id)
    lines = [f"# AI 对话：{conversation.title}", "", f"- 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    for message in conversation.messages:
        lines.extend([f"## {'用户' if message.role == 'user' else 'AI 助手'} · {message.created_at.strftime('%Y-%m-%d %H:%M')}", "", message.content, ""])
        if message.role == "assistant" and message.model_name:
            lines.extend([f"- 模型：{message.model_name}", f"- 生成时间：{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}"])
            if message.requires_human_review:
                lines.append("- 人工核验：此回复涉及剂量、临床解释或统计结论，不能直接作为最终判断。")
            lines.append("")
        if message.attachments:
            lines.extend(["### 附件", ""])
            lines.extend(f"- {item.original_name}（{item.size_label}）" for item in message.attachments)
            lines.append("")
        references = _safe_json(message.references_json, [])
        if references:
            lines.extend(["### 引用", ""])
            lines.extend(f"- [{item.get('title') or item.get('url')}]({item.get('url')})" for item in references if item.get("url"))
            lines.append("")
        proposal = _safe_json(message.proposal_json, None)
        if proposal:
            lines.extend(["### 页面修改提案", ""])
            for item in proposal.get("diff", []):
                lines.extend([f"- {item['field']}", f"  - 修改前：{item['before']}", f"  - 修改后：{item['after']}"])
            lines.extend(["", f"状态：{'已保存' if message.applied_at else '未保存'}", ""])
        if message.role == "assistant" and message.prompt_snapshot:
            lines.extend(["<details>", "<summary>本次生成提示词与数据上下文</summary>", "", "```text", message.prompt_snapshot, "```", "", "</details>", ""])
    content = "\ufeff" + "\n".join(lines).rstrip() + "\n"
    return Response(content, mimetype="text/markdown; charset=utf-8", headers={
        "Content-Disposition": f"attachment; filename=ai-chat-{conversation.id}.md"
    })


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
