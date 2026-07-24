import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

from . import db
from .models import (
    BatchParameter, BatchSample, BatchStep, Experiment, ExperimentAttachment, ExperimentBatch,
    ExperimentParameter, ExperimentRecord, ExperimentSample, ExperimentStep,
    RecordParameter, ResearchProject, Sample, utcnow,
)


PACKAGE_FORMAT = "research-assistant-project"
PACKAGE_SCHEMA_VERSION = 2
SUPPORTED_PACKAGE_SCHEMA_VERSIONS = {1, PACKAGE_SCHEMA_VERSION}


class ProjectPackageError(ValueError):
    pass


def _value(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def _fields(item, names):
    return {name: _value(getattr(item, name)) for name in names}


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_zip_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not name:
        raise ProjectPackageError("项目包包含不安全的文件路径。")
    return path.as_posix()


def _active(items):
    return [item for item in items if not getattr(item, "is_deleted", False)]


def _sample_payload(sample):
    return _fields(sample, (
        "sample_code", "sample_type", "source", "location", "quantity", "status", "notes",
    ))


def _attachment_payload(attachment, storage_root):
    payload = _fields(attachment, (
        "original_name", "relative_path", "size_bytes", "mime_type", "category",
        "is_previewable_image", "sha256", "tags", "description", "version_number",
        "storage_mode", "external_path", "link_status", "ai_readability",
    ))
    payload["file_entry"] = ""
    if attachment.storage_mode == "managed" and attachment.stored_path:
        path = (storage_root / attachment.stored_path).resolve()
        if path.is_file() and storage_root in path.parents:
            payload["file_entry"] = _safe_zip_name(
                f"files/attachment-{attachment.id}/{attachment.original_name}"
            )
            payload["sha256"] = _sha256_file(path)
            payload["size_bytes"] = path.stat().st_size
    return payload


def _assert_complete_record_ownership(experiment, batches):
    active_records = _active(experiment.records)
    active_batch_ids = {batch.id for batch in batches}
    invalid_record_ids = {
        record.id
        for record in active_records
        if not record.batch_id or record.batch_id not in active_batch_ids
    }
    invalid_record_ids.update(
        record.id
        for batch in batches
        for record in _active(batch.records)
        if record.experiment_id != experiment.id
    )
    if invalid_record_ids:
        identifiers = "、".join(str(item_id) for item_id in sorted(invalid_record_ids)[:8])
        if len(invalid_record_ids) > 8:
            identifiers += " 等"
        raise ProjectPackageError(
            f"实验“{experiment.title}”存在未归档或执行归属异常的过程记录（ID：{identifiers}）。"
            "为避免项目包遗漏数据，导出已停止；请先运行数据库升级（flask db upgrade）后重试。"
        )
    return {record.id for record in active_records}


def _project_payload(project, storage_root):
    data = {
        "project": _fields(project, (
            "title", "code", "objective", "status", "start_date", "end_date", "notes",
        )),
        "experiments": [],
    }
    for experiment in _active(project.experiments):
        active_batches = _active(experiment.batches)
        expected_record_ids = _assert_complete_record_ownership(experiment, active_batches)
        serialized_record_ids = set()
        experiment_data = _fields(experiment, (
            "title", "code", "objective", "owner", "status", "start_date", "end_date",
            "sample_requirements_json", "record_conditions_template",
            "record_content_template", "record_remark_template",
        ))
        plan_step_refs = {
            step.id: f"plan-step-{index:04d}"
            for index, step in enumerate(experiment.steps, start=1)
        }
        experiment_data["steps"] = []
        for step in experiment.steps:
            step_data = _fields(step, (
                "position", "title", "description", "operator", "planned_date",
            ))
            step_data["step_ref"] = plan_step_refs[step.id]
            experiment_data["steps"].append(step_data)
        experiment_data["plan_parameters"] = [_fields(parameter, (
            "position", "name", "value", "unit", "notes",
        )) for parameter in experiment.plan_parameters]
        experiment_data["sample_usages"] = [
            {"sample": _sample_payload(usage.sample), **_fields(usage, ("role", "amount_used", "notes"))}
            for usage in experiment.sample_usages
        ]
        experiment_data["batches"] = []
        for batch in active_batches:
            batch_data = _fields(batch, (
                "batch_code", "repeat_kind", "repeat_number", "group_name", "operator", "status",
                "start_date", "end_date", "summary", "conclusion", "requires_repeat",
            ))
            batch_data["steps"] = []
            for step in batch.steps:
                step_data = _fields(step, (
                    "position", "title", "description", "operator", "planned_date",
                    "completed_date", "is_done",
                ))
                step_data["source_step_ref"] = plan_step_refs.get(step.source_step_id)
                batch_data["steps"].append(step_data)
            batch_data["actual_parameters"] = [_fields(parameter, (
                "position", "name", "value", "unit", "notes",
            )) for parameter in batch.actual_parameters]
            batch_data["sample_usages"] = [
                {"sample": _sample_payload(usage.sample), **_fields(usage, ("role", "amount_used", "notes"))}
                for usage in batch.sample_usages
            ]
            batch_data["records"] = []
            for record in _active(batch.records):
                serialized_record_ids.add(record.id)
                record_data = _fields(record, (
                    "record_date", "operator", "conditions", "content", "result", "remark",
                    "lifecycle_status", "finalized_at",
                ))
                record_data["parameters"] = [_fields(parameter, (
                    "position", "name", "value", "unit", "notes",
                )) for parameter in record.parameters]
                record_data["attachments"] = [
                    _attachment_payload(attachment, storage_root)
                    for attachment in _active(record.attachments)
                ]
                batch_data["records"].append(record_data)
            experiment_data["batches"].append(batch_data)
        if serialized_record_ids != expected_record_ids:
            missing = expected_record_ids - serialized_record_ids
            identifiers = "、".join(str(item_id) for item_id in sorted(missing)[:8]) or "未知"
            raise ProjectPackageError(
                f"实验“{experiment.title}”的过程记录未能完整写入项目包（ID：{identifiers}）。"
                "导出已停止，请先检查实验执行归属。"
            )
        data["experiments"].append(experiment_data)
    return data


def build_project_package(project, storage_root):
    storage_root = Path(storage_root).resolve()
    payload = _project_payload(project, storage_root)
    project_json = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    checksums = {"project.json": _sha256_bytes(project_json)}
    external_links = []
    for experiment in payload["experiments"]:
        for batch in experiment["batches"]:
            for record in batch["records"]:
                for attachment in record["attachments"]:
                    if attachment["storage_mode"] == "external":
                        external_links.append(attachment["external_path"])
                    elif attachment["file_entry"]:
                        checksums[attachment["file_entry"]] = attachment["sha256"]
    manifest = {
        "format": PACKAGE_FORMAT,
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "created_at": utcnow().isoformat() + "Z",
        "project_title": project.title,
        "entries": checksums,
        "external_links_included_as_metadata_only": len(external_links),
    }
    temporary = tempfile.NamedTemporaryFile(prefix="research-project-", suffix=".ralab", delete=False)
    temporary.close()
    output_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
            archive.writestr("project.json", project_json)
            for experiment, experiment_obj in zip(payload["experiments"], _active(project.experiments)):
                attachment_by_id = {
                    attachment.id: attachment
                    for record in _active(experiment_obj.records)
                    for attachment in _active(record.attachments)
                }
                for batch in experiment["batches"]:
                    for record in batch["records"]:
                        for attachment_data in record["attachments"]:
                            entry = attachment_data["file_entry"]
                            if not entry:
                                continue
                            attachment_id = int(entry.split("/")[1].removeprefix("attachment-"))
                            attachment = attachment_by_id.get(attachment_id)
                            if attachment:
                                path = (storage_root / attachment.stored_path).resolve()
                                if path.is_file() and storage_root in path.parents:
                                    archive.write(path, entry)
        return output_path, manifest
    except Exception:
        output_path.unlink(missing_ok=True)
        raise


def _date(value):
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _datetime(value):
    try:
        return datetime.fromisoformat(str(value).removesuffix("Z")) if value else None
    except (TypeError, ValueError):
        return None


def _sample(user_id, data):
    code = str(data.get("sample_code") or "").strip()[:80]
    if not code:
        return None
    item = Sample.query.filter_by(user_id=user_id, sample_code=code).first()
    if item:
        return item
    item = Sample(user_id=user_id, **{
        key: data.get(key) or "" for key in (
            "sample_code", "sample_type", "source", "location", "quantity", "status", "notes",
        )
    })
    db.session.add(item)
    db.session.flush()
    return item


def _verify_archive(archive):
    if len(archive.infolist()) > 10_000:
        raise ProjectPackageError("项目包文件数量异常。")
    names = {_safe_zip_name(info.filename) for info in archive.infolist() if not info.is_dir()}
    if not {"manifest.json", "project.json"}.issubset(names):
        raise ProjectPackageError("不是有效的 Research Assistant 项目包。")
    try:
        manifest = json.loads(archive.read("manifest.json"))
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProjectPackageError("项目包清单无法读取。") from exc
    if manifest.get("format") != PACKAGE_FORMAT:
        raise ProjectPackageError("项目包格式不受支持。")
    if manifest.get("schema_version") not in SUPPORTED_PACKAGE_SCHEMA_VERSIONS:
        raise ProjectPackageError("项目包版本与当前应用不兼容。")
    for entry, expected in manifest.get("entries", {}).items():
        entry = _safe_zip_name(entry)
        if entry not in names:
            raise ProjectPackageError(f"项目包缺少文件：{entry}")
        digest = hashlib.sha256()
        with archive.open(entry) as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ProjectPackageError(f"项目包校验失败：{entry}")
    return manifest


def import_project_package(file_object, user_id, storage_root):
    storage_root = Path(storage_root).resolve()
    import_root = None
    try:
        with zipfile.ZipFile(file_object) as archive:
            manifest = _verify_archive(archive)
            try:
                data = json.loads(archive.read("project.json"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ProjectPackageError("项目结构数据无法读取。") from exc
            project_data = data.get("project") or {}
            title = str(project_data.get("title") or manifest.get("project_title") or "导入项目").strip()
            project = ResearchProject(
                user_id=user_id, title=(title + "（导入）")[:180],
                code=str(project_data.get("code") or "")[:80],
                objective=project_data.get("objective") or "",
                status=project_data.get("status") or "进行中",
                start_date=_date(project_data.get("start_date")),
                end_date=_date(project_data.get("end_date")),
                notes=project_data.get("notes") or "",
            )
            db.session.add(project)
            db.session.flush()
            import_root = storage_root / f"user-{user_id}" / f"project-import-{project.id}-{uuid4().hex[:8]}"
            for experiment_data in data.get("experiments") or []:
                experiment = Experiment(
                    user_id=user_id, project_id=project.id,
                    title=str(experiment_data.get("title") or "未命名实验")[:160],
                    code=str(experiment_data.get("code") or "")[:60],
                    objective=experiment_data.get("objective") or "", owner=experiment_data.get("owner") or "",
                    status=experiment_data.get("status") or "未开始",
                    start_date=_date(experiment_data.get("start_date")), end_date=_date(experiment_data.get("end_date")),
                    sample_requirements_json=experiment_data.get("sample_requirements_json") or "[]",
                    record_conditions_template=experiment_data.get("record_conditions_template") or "",
                    record_content_template=experiment_data.get("record_content_template") or "",
                    record_remark_template=experiment_data.get("record_remark_template") or "",
                )
                db.session.add(experiment)
                db.session.flush()
                plan_rows = experiment_data.get("steps") or []
                imported_plan_steps = []
                plan_step_by_ref = {}
                for index, row in enumerate(plan_rows, start=1):
                    plan_step = ExperimentStep(
                        experiment_id=experiment.id, position=int(row.get("position") or 1),
                        title=str(row.get("title") or "未命名步骤")[:160], description=row.get("description") or "",
                        operator=row.get("operator") or "", planned_date=_date(row.get("planned_date")),
                    )
                    db.session.add(plan_step)
                    imported_plan_steps.append((plan_step, row))
                    step_ref = str(row.get("step_ref") or f"plan-step-{index:04d}")
                    plan_step_by_ref[step_ref] = plan_step
                db.session.flush()
                for row in experiment_data.get("plan_parameters") or []:
                    db.session.add(ExperimentParameter(experiment_id=experiment.id, **{
                        key: row.get(key) or (1 if key == "position" else "")
                        for key in ("position", "name", "value", "unit", "notes")
                    }))
                for usage_data in experiment_data.get("sample_usages") or []:
                    sample = _sample(user_id, usage_data.get("sample") or {})
                    if sample:
                        db.session.add(ExperimentSample(
                            experiment_id=experiment.id, sample_id=sample.id,
                            role=usage_data.get("role") or "实验样本", amount_used=usage_data.get("amount_used") or "",
                            notes=usage_data.get("notes") or "",
                        ))
                for batch_data in experiment_data.get("batches") or []:
                    batch = ExperimentBatch(
                        experiment_id=experiment.id, batch_code=batch_data.get("batch_code") or "",
                        repeat_kind=batch_data.get("repeat_kind") or "独立实验",
                        repeat_number=int(batch_data.get("repeat_number") or 1), group_name=batch_data.get("group_name") or "",
                        operator=batch_data.get("operator") or "", status=batch_data.get("status") or "未开始",
                        start_date=_date(batch_data.get("start_date")), end_date=_date(batch_data.get("end_date")),
                        summary=batch_data.get("summary") or "", conclusion=batch_data.get("conclusion") or "",
                        requires_repeat=bool(batch_data.get("requires_repeat")),
                    )
                    db.session.add(batch)
                    db.session.flush()
                    if manifest["schema_version"] >= 2:
                        batch_step_rows = batch_data.get("steps") or []
                        for row in batch_step_rows:
                            source_step = plan_step_by_ref.get(str(row.get("source_step_ref") or ""))
                            if source_step is None:
                                source_step = next((
                                    plan_step
                                    for plan_step, plan_row in imported_plan_steps
                                    if int(plan_row.get("position") or 1) == int(row.get("position") or 1)
                                    and str(plan_row.get("title") or "") == str(row.get("title") or "")
                                ), None)
                            db.session.add(BatchStep(
                                batch_id=batch.id,
                                source_step_id=source_step.id if source_step else None,
                                position=int(row.get("position") or 1),
                                title=str(row.get("title") or "未命名步骤")[:160],
                                description=row.get("description") or "",
                                operator=row.get("operator") or "",
                                planned_date=_date(row.get("planned_date")),
                                completed_date=_date(row.get("completed_date")),
                                is_done=bool(row.get("is_done")),
                            ))
                    else:
                        # Schema v1 packages stored completion on plan steps. Apply that legacy
                        # state to every imported execution because the old format had no owner.
                        for plan_step, legacy_row in imported_plan_steps:
                            batch_step = BatchStep.from_plan_step(batch.id, plan_step)
                            batch_step.completed_date = _date(legacy_row.get("completed_date"))
                            batch_step.is_done = bool(legacy_row.get("is_done"))
                            db.session.add(batch_step)
                    for row in batch_data.get("actual_parameters") or []:
                        db.session.add(BatchParameter(batch_id=batch.id, **{
                            key: row.get(key) or (1 if key == "position" else "")
                            for key in ("position", "name", "value", "unit", "notes")
                        }))
                    for usage_data in batch_data.get("sample_usages") or []:
                        sample = _sample(user_id, usage_data.get("sample") or {})
                        if sample:
                            db.session.add(BatchSample(
                                batch_id=batch.id, sample_id=sample.id, role=usage_data.get("role") or "实验样本",
                                amount_used=usage_data.get("amount_used") or "", notes=usage_data.get("notes") or "",
                            ))
                    for record_data in batch_data.get("records") or []:
                        record = ExperimentRecord(
                            experiment_id=experiment.id, batch_id=batch.id,
                            record_date=_date(record_data.get("record_date")) or date.today(),
                            operator=record_data.get("operator") or "", conditions=record_data.get("conditions") or "",
                            content=record_data.get("content") or "", result=record_data.get("result") or "待确认",
                            remark=record_data.get("remark") or "", lifecycle_status=record_data.get("lifecycle_status") or "草稿",
                            finalized_at=_datetime(record_data.get("finalized_at")),
                        )
                        db.session.add(record)
                        db.session.flush()
                        for row in record_data.get("parameters") or []:
                            db.session.add(RecordParameter(record_id=record.id, **{
                                key: row.get(key) or (1 if key == "position" else "")
                                for key in ("position", "name", "value", "unit", "notes")
                            }))
                        for attachment_data in record_data.get("attachments") or []:
                            mode = attachment_data.get("storage_mode") or "managed"
                            entry = attachment_data.get("file_entry") or ""
                            stored_path = f"external/{uuid4().hex}.link"
                            if mode == "managed" and entry:
                                entry = _safe_zip_name(entry)
                                logical = PurePosixPath(attachment_data.get("relative_path") or attachment_data.get("original_name") or "file.bin")
                                target = import_root / f"experiment-{experiment.id}" / f"record-{record.id}" / Path(*logical.parts)
                                target.parent.mkdir(parents=True, exist_ok=True)
                                with archive.open(entry) as source, target.open("wb") as output:
                                    shutil.copyfileobj(source, output, length=1024 * 1024)
                                stored_path = target.relative_to(storage_root).as_posix()
                            link_path = attachment_data.get("external_path") or ""
                            db.session.add(ExperimentAttachment(
                                experiment_id=experiment.id, record_id=record.id,
                                original_name=str(attachment_data.get("original_name") or "file")[:255],
                                relative_path=attachment_data.get("relative_path") or attachment_data.get("original_name") or "file",
                                stored_path=stored_path, size_bytes=int(attachment_data.get("size_bytes") or 0),
                                mime_type=attachment_data.get("mime_type") or "application/octet-stream",
                                category=attachment_data.get("category") or "其他",
                                is_previewable_image=bool(attachment_data.get("is_previewable_image")),
                                sha256=attachment_data.get("sha256") or "", tags=attachment_data.get("tags") or "",
                                description=attachment_data.get("description") or "", version_number=int(attachment_data.get("version_number") or 1),
                                storage_mode=mode, external_path=link_path,
                                link_status="available" if mode == "managed" or (link_path and Path(link_path).exists()) else "missing",
                                ai_readability=attachment_data.get("ai_readability") or "metadata_only",
                            ))
            db.session.commit()
            return project, manifest
    except (zipfile.BadZipFile, OSError, KeyError, TypeError, ValueError) as exc:
        db.session.rollback()
        if import_root:
            shutil.rmtree(import_root, ignore_errors=True)
        if isinstance(exc, ProjectPackageError):
            raise
        raise ProjectPackageError(f"项目包导入失败：{exc}") from exc
