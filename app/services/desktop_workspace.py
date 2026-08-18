from __future__ import annotations

from datetime import date, datetime
import re

from sqlalchemy import func, or_, update
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app import db
from app.models import LabRecord, LabRecordRevision, LabRecordStep, ResearchProject, User, Workspace, utcnow
from .desktop_modules import DesktopModuleServiceMixin, _page_result, _sorted
from .errors import ConflictError, NotFoundError, ServiceError, ValidationError


RECORD_FIELDS = (
    "title", "status", "experiment_date", "executor_snapshot", "location", "objective",
    "background", "hypothesis", "design", "materials_conditions", "expected_result",
    "actual_process_summary", "actual_result", "analysis", "conclusion", "next_steps",
)
RECORD_STATUSES = {"draft", "in_progress", "awaiting_analysis", "completed", "archived"}
PROJECT_STATUS_LABELS = {
    "active": "进行中",
    "paused": "已暂停",
    "completed": "已完成",
    "archived": "已归档",
    "进行中": "进行中",
    "已暂停": "已暂停",
    "已完成": "已完成",
    "已归档": "已归档",
}


def _text(value, maximum, field, *, required=False):
    result = str(value or "").strip()
    if required and not result:
        raise ValidationError("请填写必填字段。", field_errors={field: "此字段不能为空"})
    if len(result) > maximum:
        raise ValidationError("字段内容过长。", field_errors={field: f"最多 {maximum} 个字符"})
    return result


def _date(value, field):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError("日期格式无效。", field_errors={field: "请使用 YYYY-MM-DD"}) from exc


def _iso(value):
    return value.isoformat() if value else None


class DesktopApplicationService(DesktopModuleServiceMixin):
    """Small record-centric service layer with one transaction per command."""

    def __init__(self, flask_app):
        self.flask_app = flask_app

    def _workspace(self):
        workspace = db.session.get(Workspace, 1)
        user = User.query.filter_by(is_active=True).order_by(User.id).first()
        if user is None:
            user = User(
                name="本地研究者",
                email="local@research-assistant.invalid",
                password_hash="local-mode",
                role="system_admin",
                is_active=True,
                email_verified_at=utcnow(),
            )
            db.session.add(user)
            db.session.flush()
        if workspace:
            if workspace.legacy_user_id is None:
                workspace.legacy_user_id = user.id
                db.session.commit()
            return workspace
        workspace = Workspace(id=1, legacy_user_id=user.id)
        db.session.add(workspace)
        db.session.commit()
        return workspace

    def _run(self, callback):
        with self.flask_app.app_context():
            try:
                workspace = self._workspace()
                result = callback(workspace)
                db.session.commit()
                return result
            except StaleDataError as exc:
                db.session.rollback()
                raise ConflictError("对象已被其他操作更新，请重新加载后合并修改。") from exc
            except Exception:
                db.session.rollback()
                raise
            finally:
                db.session.remove()

    @staticmethod
    def _project_dto(project):
        return {
            "id": project.id,
            "title": project.title,
            "code": project.code or "",
            "objective": project.objective or "",
            "status": project.status,
            "status_label": PROJECT_STATUS_LABELS.get(project.status, project.status),
            "record_count": len(project.lab_records),
            "row_version": project.row_version,
            "updated_at": _iso(project.updated_at),
        }

    @staticmethod
    def _record_dto(record, *, detail=False):
        payload = {
            "id": record.id,
            "project_id": record.project_id,
            "project_title": record.project.title,
            "record_code": record.record_code,
            "title": record.title,
            "status": record.status,
            "experiment_date": _iso(record.experiment_date),
            "executor_snapshot": record.executor_snapshot,
            "location": record.location,
            "is_finalized": record.is_finalized,
            "row_version": record.row_version,
            "updated_at": _iso(record.updated_at),
        }
        if detail:
            payload.update({field: _iso(getattr(record, field)) if field == "experiment_date" else getattr(record, field) for field in RECORD_FIELDS})
            payload["steps"] = [
                {
                    "id": step.id,
                    "position": step.position,
                    "title": step.title,
                    "instruction": step.instruction,
                    "planned_duration_minutes": step.planned_duration_minutes,
                    "checkpoint": step.checkpoint,
                    "risk": step.risk,
                    "is_done": step.is_done,
                    "actual_deviation": step.actual_deviation,
                }
                for step in record.steps
            ]
            payload["revisions"] = [
                {
                    "id": revision.id,
                    "scope": revision.scope,
                    "reason": revision.reason,
                    "actor_kind": revision.actor_kind,
                    "source_ai_change_set_id": revision.source_ai_change_set_id,
                    "created_at": _iso(revision.created_at),
                }
                for revision in record.revisions
            ]
        return payload

    def dashboard(self):
        def query(workspace):
            projects = (
                ResearchProject.query.options(selectinload(ResearchProject.lab_records)).filter_by(workspace_id=workspace.id, is_deleted=False)
                .order_by(ResearchProject.updated_at.desc()).limit(5).all()
            )
            records = (
                LabRecord.query.options(joinedload(LabRecord.project)).filter_by(workspace_id=workspace.id, is_deleted=False)
                .order_by(LabRecord.updated_at.desc()).limit(6).all()
            )
            counts = dict(
                db.session.query(LabRecord.status, func.count(LabRecord.id))
                .filter_by(workspace_id=workspace.id, is_deleted=False)
                .group_by(LabRecord.status).all()
            )
            return {
                "workspace": {"name": workspace.name, "schema_generation": workspace.schema_generation},
                "projects": [self._project_dto(item) for item in projects],
                "recent_records": [self._record_dto(item) for item in records],
                "counts": {"projects": len(projects), "records": sum(counts.values()), **counts},
            }
        return self._run(query)

    def list_projects(self, payload=None):
        payload = payload or {}
        search = _text(payload.get("search"), 120, "search")

        def query(workspace):
            items = ResearchProject.query.options(selectinload(ResearchProject.lab_records)).filter_by(workspace_id=workspace.id, is_deleted=False)
            if search:
                escaped = search.replace("%", r"\%").replace("_", r"\_")
                pattern = f"%{escaped}%"
                items = items.filter(or_(
                    ResearchProject.title.ilike(pattern, escape="\\"),
                    ResearchProject.code.ilike(pattern, escape="\\"),
                    ResearchProject.objective.ilike(pattern, escape="\\"),
                ))
            return [self._project_dto(item) for item in items.order_by(ResearchProject.updated_at.desc()).all()]
        return self._run(query)

    def create_project(self, payload):
        title = _text(payload.get("title"), 180, "title", required=True)
        code = _text(payload.get("code"), 80, "code")
        objective = _text(payload.get("objective"), 12000, "objective")

        def create(workspace):
            user_id = workspace.legacy_user_id
            if not user_id:
                user = User.query.filter_by(is_active=True).order_by(User.id).first()
                user_id = user.id
                workspace.legacy_user_id = user_id
            project = ResearchProject(
                user_id=user_id, workspace_id=workspace.id, title=title, code=code,
                objective=objective, status="active", row_version=1,
            )
            db.session.add(project)
            db.session.flush()
            self._index_entity(workspace, "project", project)
            return self._project_dto(project)
        return self._run(create)

    def update_project(self, payload, expected_row_version):
        """Update project metadata with optimistic concurrency protection."""
        project_id = self._positive_id(payload.get("id"), "id")
        try:
            expected = int(expected_row_version)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "缺少有效的项目版本。",
                field_errors={"expected_row_version": "必须为整数"},
            ) from exc
        title = _text(payload.get("title"), 180, "title", required=True)
        code = _text(payload.get("code"), 80, "code")
        objective = _text(payload.get("objective"), 12000, "objective")
        status = _text(payload.get("status"), 30, "status") or "active"
        if status not in {"active", "paused", "completed", "archived"}:
            raise ValidationError("项目状态无效。", field_errors={"status": "不支持的状态"})

        def save(workspace):
            current = ResearchProject.query.filter_by(
                id=project_id, workspace_id=workspace.id, is_deleted=False,
            ).first()
            if not current:
                raise NotFoundError("项目不存在或已移入回收站。")
            if current.row_version != expected:
                raise ConflictError("项目已在其他操作中更新，请重新加载后合并修改。")
            result = db.session.execute(
                update(ResearchProject)
                .where(
                    ResearchProject.id == project_id,
                    ResearchProject.workspace_id == workspace.id,
                    ResearchProject.row_version == expected,
                )
                .values(
                    title=title,
                    code=code,
                    objective=objective,
                    status=status,
                    row_version=expected + 1,
                    updated_at=utcnow(),
                )
            )
            if result.rowcount != 1:
                raise ConflictError("项目版本冲突，未覆盖较新的内容。")
            db.session.flush()
            db.session.expire(current)
            self._index_entity(workspace, "project", current)
            return self._project_dto(current)

        return self._run(save)

    def project_bulk(self, payload=None):
        payload = payload or {}
        raw_ids = payload.get("ids") if isinstance(payload.get("ids"), list) else []
        ids = list(dict.fromkeys(self._positive_id(value, "ids") for value in raw_ids))[:200]
        if not ids:
            raise ValidationError("请至少选择一个项目。")
        action = _text(payload.get("action"), 20, "action", required=True)
        if action not in {"status", "trash"}:
            raise ValidationError("不支持的项目批量操作。")
        status = _text(payload.get("status"), 30, "status") if action == "status" else ""
        if action == "status" and status not in {"active", "paused", "completed", "archived"}:
            raise ValidationError("项目状态无效。", field_errors={"status": "不支持的状态"})

        def bulk(workspace):
            items = ResearchProject.query.filter(
                ResearchProject.workspace_id == workspace.id,
                ResearchProject.is_deleted.is_(False),
                ResearchProject.id.in_(ids),
            ).all()
            found = {item.id for item in items}
            if action == "status":
                for item in items:
                    item.status = status
                    item.row_version += 1
                    self._index_entity(workspace, "project", item)
            else:
                now = utcnow()
                for item in items:
                    item.is_deleted, item.deleted_at = True, now
                    self._index_entity(workspace, "project", item)
            return {"updated": len(items), "skipped": len(ids) - len(found)}
        return self._run(bulk)

    def list_records(self, payload=None):
        payload = payload or {}
        project_id = payload.get("project_id")
        search = _text(payload.get("search"), 120, "search")
        status = _text(payload.get("status"), 30, "status")
        date_start = _date(payload.get("date_start"), "date_start")
        date_end = _date(payload.get("date_end"), "date_end")
        if date_start and date_end and date_end < date_start:
            raise ValidationError("结束日期不能早于开始日期。")

        def query(workspace):
            items = LabRecord.query.options(joinedload(LabRecord.project)).filter_by(workspace_id=workspace.id, is_deleted=False)
            if project_id not in (None, ""):
                try:
                    items = items.filter_by(project_id=int(project_id))
                except (TypeError, ValueError) as exc:
                    raise ValidationError("项目编号无效。", field_errors={"project_id": "必须为整数"}) from exc
            if search:
                escaped = search.replace("%", r"\%").replace("_", r"\_")
                items = items.filter(or_(
                    LabRecord.title.ilike(f"%{escaped}%", escape="\\"),
                    LabRecord.record_code.ilike(f"%{escaped}%", escape="\\"),
                ))
            if status:
                items = items.filter(LabRecord.status == status)
            if date_start:
                items = items.filter(LabRecord.experiment_date >= date_start)
            if date_end:
                items = items.filter(LabRecord.experiment_date <= date_end)
            items = _sorted(items, payload, {
                "updated_desc": (LabRecord.updated_at.desc(),),
                "date_desc": (LabRecord.experiment_date.desc(), LabRecord.updated_at.desc()),
                "title_asc": (LabRecord.title.asc(),),
            }, "updated_desc")
            return _page_result(items, payload, self._record_dto)
        return self._run(query)

    def get_record(self, payload):
        record_id = self._positive_id(payload.get("id"), "id")

        def query(workspace):
            record = LabRecord.query.filter_by(id=record_id, workspace_id=workspace.id, is_deleted=False).first()
            if not record:
                raise NotFoundError("实验记录不存在或已移入回收站。")
            return self._record_dto(record, detail=True)
        return self._run(query)

    def record_bulk(self, payload):
        raw_ids = payload.get("ids") or []
        try: ids = sorted({int(value) for value in raw_ids if int(value) > 0})
        except (TypeError, ValueError) as exc: raise ValidationError("记录编号无效。") from exc
        if not ids or len(ids) > 500: raise ValidationError("请选择 1 至 500 条记录。")
        action = _text(payload.get("action"), 20, "action", required=True)
        if action not in {"status", "project", "trash"}: raise ValidationError("不支持的记录批量操作。")

        def bulk(workspace):
            items = LabRecord.query.filter(LabRecord.workspace_id == workspace.id, LabRecord.is_deleted.is_(False), LabRecord.id.in_(ids)).all()
            if action == "status":
                value = _text(payload.get("value"), 30, "value", required=True)
                if value not in RECORD_STATUSES: raise ValidationError("记录状态无效。")
            elif action == "project":
                try: value = int(payload.get("value"))
                except (TypeError, ValueError) as exc: raise ValidationError("项目编号无效。") from exc
                project = ResearchProject.query.filter_by(id=value, workspace_id=workspace.id, is_deleted=False).first()
                if not project: raise NotFoundError("目标项目不存在。")
            else: value = None
            results = []
            for item in items:
                if action == "trash": item.is_deleted, item.deleted_at = True, utcnow()
                elif action == "status": item.status = value
                else: item.project_id = value
                item.row_version += 1
                self._index_entity(workspace, "record", item)
                results.append({"id": item.id, "status": "updated", "row_version": item.row_version})
            found = {item.id for item in items}
            results.extend({"id": value, "status": "not_found"} for value in ids if value not in found)
            return {"updated": len(items), "skipped": len(ids)-len(items), "results": results}
        return self._run(bulk)

    def create_record(self, payload):
        project_id = self._positive_id(payload.get("project_id"), "project_id")
        title = _text(payload.get("title"), 200, "title", required=True)
        experiment_date = _date(payload.get("experiment_date"), "experiment_date")

        def create(workspace):
            project = ResearchProject.query.filter_by(
                id=project_id, workspace_id=workspace.id, is_deleted=False
            ).first()
            if not project:
                raise NotFoundError("所属项目不存在。")
            prefix = datetime.now().strftime("LAB-%Y%m%d")
            sequence = LabRecord.query.filter(
                LabRecord.workspace_id == workspace.id,
                LabRecord.record_code.like(f"{prefix}-%"),
            ).count() + 1
            code = f"{prefix}-{sequence:03d}"
            while LabRecord.query.filter_by(workspace_id=workspace.id, record_code=code).first():
                sequence += 1
                code = f"{prefix}-{sequence:03d}"
            record = LabRecord(
                workspace_id=workspace.id, project_id=project.id, record_code=code,
                title=title, experiment_date=experiment_date, status="draft", source_kind="new",
            )
            db.session.add(record)
            db.session.flush()
            self._index_entity(workspace, "record", record)
            return self._record_dto(record, detail=True)
        return self._run(create)

    def update_record(self, payload, expected_row_version):
        record_id = self._positive_id(payload.get("id"), "id")
        try:
            expected = int(expected_row_version)
        except (TypeError, ValueError) as exc:
            raise ValidationError("缺少有效的记录版本。", field_errors={"expected_row_version": "必须为整数"}) from exc
        values = {}
        if "project_id" in payload:
            values["project_id"] = self._positive_id(payload.get("project_id"), "project_id")
        for field in RECORD_FIELDS:
            if field not in payload:
                continue
            if field == "title":
                values[field] = _text(payload[field], 200, field, required=True)
            elif field == "status":
                status = _text(payload[field], 24, field, required=True)
                if status not in RECORD_STATUSES:
                    raise ValidationError("实验记录状态无效。", field_errors={field: "不支持的状态"})
                values[field] = status
            elif field == "experiment_date":
                values[field] = _date(payload[field], field)
            elif field in {"executor_snapshot", "location"}:
                values[field] = _text(payload[field], 180, field)
            else:
                values[field] = _text(payload[field], 50000, field)
        steps = payload.get("steps")
        if steps is not None and not isinstance(steps, list):
            raise ValidationError("步骤必须为数组。", field_errors={"steps": "格式无效"})

        def save(workspace):
            current = LabRecord.query.filter_by(id=record_id, workspace_id=workspace.id, is_deleted=False).first()
            if not current:
                raise NotFoundError("实验记录不存在或已移入回收站。")
            if current.row_version != expected:
                raise ConflictError("记录已在其他操作中更新，请重新加载后合并修改。")
            if "project_id" in values:
                project = ResearchProject.query.filter_by(
                    id=values["project_id"], workspace_id=workspace.id, is_deleted=False,
                ).first()
                if not project:
                    raise NotFoundError("新的所属项目不存在。")
            before = self._record_dto(current, detail=True)
            result = db.session.execute(
                update(LabRecord)
                .where(LabRecord.id == record_id, LabRecord.workspace_id == workspace.id, LabRecord.row_version == expected)
                .values(**values, row_version=expected + 1, updated_at=utcnow())
            )
            if result.rowcount != 1:
                raise ConflictError("记录版本冲突，未覆盖较新的内容。")
            if steps is not None:
                LabRecordStep.query.filter_by(record_id=current.id).delete(synchronize_session=False)
                db.session.flush()
                db.session.expire(current, ["steps"])
                for position, raw in enumerate(steps, start=1):
                    if not isinstance(raw, dict):
                        raise ValidationError("步骤格式无效。", field_errors={"steps": "每个步骤必须为对象"})
                    duration = raw.get("planned_duration_minutes")
                    if duration not in (None, ""):
                        try: duration = max(0, int(duration))
                        except (TypeError, ValueError) as exc: raise ValidationError("步骤时长必须为整数。") from exc
                    else: duration = None
                    current.steps.append(LabRecordStep(
                        position=position,
                        title=_text(raw.get("title"), 180, "steps.title"),
                        instruction=_text(raw.get("instruction"), 20000, "steps.instruction"),
                        planned_duration_minutes=duration,
                        checkpoint=_text(raw.get("checkpoint"), 5000, "steps.checkpoint"),
                        risk=_text(raw.get("risk"), 5000, "steps.risk"),
                        actual_deviation=_text(raw.get("actual_deviation"), 5000, "steps.actual_deviation"),
                        is_done=bool(raw.get("is_done")),
                        source_kind="user",
                    ))
            db.session.flush()
            db.session.expire(current)
            after = self._record_dto(current, detail=True)
            self._index_entity(workspace, "record", current)
            db.session.add(LabRecordRevision(
                record_id=record_id,
                scope="record",
                reason="桌面编辑器保存",
                before_json=self._json(before),
                after_json=self._json(after),
                diff_json=self._json({key: after.get(key) for key in values}),
                actor_kind="local_user",
            ))
            return after
        return self._run(save)

    @staticmethod
    def _positive_id(value, field):
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError("编号无效。", field_errors={field: "必须为整数"}) from exc
        if result <= 0:
            raise ValidationError("编号无效。", field_errors={field: "必须大于 0"})
        return result

    @staticmethod
    def _json(value):
        import json
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
