from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import threading
import uuid

from app.services.desktop_workspace import ServiceError
from .native import NativeCapabilityError
from .protocol import build_app_info


MAX_BRIDGE_BYTES = 256 * 1024


class DesktopBridge:
    """The sole JS API object exposed by pywebview."""

    def __dir__(self):
        """Expose only the audited dispatch method to pywebview.

        pywebview walks ``dir(js_api)`` recursively when it builds the
        JavaScript proxy.  The bridge owns the service and native window
        adapter, so exposing those objects lets the walker enter COM/WebView2
        internals from a worker thread.  That produces recursive inspection
        errors and can leave the desktop window apparently frozen.  Keep the
        public surface intentionally tiny; private implementation attributes
        remain available to Python code through normal attribute access.
        """
        return ["invoke"]

    def __init__(self, service, native, app_info):
        # pywebview exposes public attributes recursively. Keep the object graph
        # private so JavaScript receives only the audited invoke entry point.
        self._service = service
        self._native = native
        self._app_info = dict(app_info)
        self._zotero_job_lock = threading.Lock()
        self._zotero_jobs = {}
        self._latest_zotero_job_id = ""
        self._commands = {
            "system.ping": lambda payload, version: {"status": "ok"},
            "system.app_info": lambda payload, version: self._app_info,
            "dashboard.get": lambda payload, version: self._service.dashboard(),
            "project.list": lambda payload, version: self._service.list_projects(payload),
            "project.create": lambda payload, version: self._service.create_project(payload),
            "project.update": lambda payload, version: self._service.update_project(payload, version),
            "project.bulk": lambda payload, version: self._service.project_bulk(payload),
            "record.list": lambda payload, version: self._service.list_records(payload),
            "record.get": lambda payload, version: self._service.get_record(payload),
            "record.create": lambda payload, version: self._service.create_record(payload),
            "record.update": lambda payload, version: self._service.update_record(payload, version),
            "record.bulk": lambda payload, version: self._service.record_bulk(payload),
            "record.export": lambda payload, version: self._export_record(payload),
            "record.export.batch": lambda payload, version: self._export_records(payload),
            "record.export_batch": lambda payload, version: self._export_records(payload),
            "literature.list": lambda payload, version: self._service.list_literature(payload),
            "literature.get": lambda payload, version: self._service.get_literature(payload),
            "literature.facets": lambda payload, version: self._service.literature_facets(payload),
            "literature.save": lambda payload, version: self._service.save_literature(payload, version),
            "literature.link": lambda payload, version: self._service.link_literature(payload),
            "literature.unlink": lambda payload, version: self._service.unlink_literature(payload),
            "literature.bulk": lambda payload, version: self._service.literature_bulk(payload),
            "zotero.status": lambda payload, version: self._service.zotero_status(payload),
            "zotero.sync": lambda payload, version: self._service.zotero_sync(payload),
            "zotero.sync.start": lambda payload, version: self._start_zotero_sync(payload),
            "zotero.sync.status": lambda payload, version: self._zotero_sync_status(payload),
            "zotero.sync.cancel": lambda payload, version: self._cancel_zotero_sync(payload),
            "zotero.collections.sync": lambda payload, version: self._service.zotero_collections_sync(payload),
            "zotero.collections.list": lambda payload, version: self._service.zotero_collections(payload),
            "zotero.collections.map": lambda payload, version: self._service.zotero_collection_map(payload),
            "library.list": lambda payload, version: self._service.list_library_items(payload),
            "library.import": lambda payload, version: self._import_library_item(payload),
            "library.verify": lambda payload, version: self._service.verify_library_item(payload),
            "library.open": lambda payload, version: self._open_library_item(payload),
            "note.list": lambda payload, version: self._service.list_notes(payload),
            "note.get": lambda payload, version: self._service.get_note(payload),
            "note.save": lambda payload, version: self._service.save_note(payload, version),
            "note.bulk": lambda payload, version: self._service.note_bulk(payload),
            "task.list": lambda payload, version: self._service.list_tasks(payload),
            "task.save": lambda payload, version: self._service.save_task(payload, version),
            "task.bulk": lambda payload, version: self._service.task_bulk(payload),
            "calendar.list": lambda payload, version: self._service.list_calendar(payload),
            "calendar.create": lambda payload, version: self._service.create_calendar_event(payload),
            "weekly.current": lambda payload, version: self._service.weekly_current(payload),
            "weekly.list": lambda payload, version: self._service.list_weekly(payload),
            "weekly.get": lambda payload, version: self._service.get_weekly(payload),
            "weekly.annotate": lambda payload, version: self._service.add_weekly_annotation(payload, version),
            "weekly.update": lambda payload, version: self._service.update_weekly(payload, version),
            "weekly.bulk": lambda payload, version: self._service.weekly_bulk(payload),
            "weekly.save": lambda payload, version: self._service.save_weekly(payload, version),
            "weekly.import_file": lambda payload, version: self._import_weekly_file(payload, version),
            "weekly.open_file": lambda payload, version: self._open_weekly_file(payload),
            "weekly.open_directory": lambda payload, version: self._open_weekly_directory(payload),
            "weekly.export_file": lambda payload, version: self._export_weekly_file(payload),
            "weekly.ppt": lambda payload, version: self._generate_weekly_ppt(payload),
            "ai.history": lambda payload, version: self._service.ai_history(payload),
            "ai.conversations": lambda payload, version: self._service.ai_conversations(payload),
            "ai.conversation.get": lambda payload, version: self._service.ai_conversation_get(payload),
            "ai.conversation.create": lambda payload, version: self._service.ai_conversation_create(payload),
            "ai.conversations.bulk": lambda payload, version: self._service.ai_conversations_bulk(payload),
            "ai.preview": lambda payload, version: self._service.ai_preview(payload),
            "ai.propose": lambda payload, version: self._service.ai_propose(payload),
            "ai.apply": lambda payload, version: self._service.ai_apply(payload),
            "ai.revert": lambda payload, version: self._service.ai_revert(payload),
            "search.query": lambda payload, version: self._service.search(payload),
            "search.rebuild": lambda payload, version: self._service.rebuild_search(payload),
            "trash.list": lambda payload, version: self._service.trash_list(payload),
            "trash.move": lambda payload, version: self._service.trash_move(payload),
            "trash.restore": lambda payload, version: self._service.trash_restore(payload),
            "trash.purge": lambda payload, version: self._service.trash_purge(payload),
            "settings.get": lambda payload, version: self._service.settings_get(payload),
            "settings.save": lambda payload, version: self._service.settings_save(payload),
            "backup.create": lambda payload, version: self._service.create_backup(payload),
            "dialog.open_file": lambda payload, version: self._native.open_file_dialog(payload),
            "dialog.select_directory": lambda payload, version: self._native.select_directory_dialog(payload),
            "dialog.save_file": lambda payload, version: self._native.save_file_dialog(payload),
            "shell.open_path": lambda payload, version: self._native.open_trusted_path(payload),
            "shell.open_external": lambda payload, version: self._native.open_external_url(payload),
            "window.minimize": lambda payload, version: self._native.window_command("window.minimize"),
            "window.maximize": lambda payload, version: self._native.window_command("window.maximize"),
            "window.restore": lambda payload, version: self._native.window_command("window.restore"),
            "window.close": lambda payload, version: self._native.window_command("window.close"),
        }
        self._app_info = build_app_info(self._app_info, self._commands)

    def _start_zotero_sync(self, payload):
        with self._zotero_job_lock:
            finished = [key for key, value in self._zotero_jobs.items() if value["state"] not in {"queued", "running"}]
            for stale_id in finished[:-20]:
                self._zotero_jobs.pop(stale_id, None)
            if self._latest_zotero_job_id:
                current = self._zotero_jobs.get(self._latest_zotero_job_id)
                if current and current["state"] in {"queued", "running"}:
                    return {"job_id": self._latest_zotero_job_id, "state": current["state"]}
            job_id = str(uuid.uuid4())
            cancel_event = threading.Event()
            self._zotero_jobs[job_id] = {"state": "queued", "result": None, "cancel_event": cancel_event, "progress": 0, "stage": "等待同步"}
            self._latest_zotero_job_id = job_id

        def run():
            with self._zotero_job_lock:
                self._zotero_jobs[job_id]["state"] = "running"
            try:
                def progress(value, stage):
                    with self._zotero_job_lock:
                        job = self._zotero_jobs.get(job_id)
                        if job:
                            job["progress"], job["stage"] = int(value), str(stage)
                result = self._service.zotero_sync({
                    **payload, "_cancel_event": cancel_event, "_progress_callback": progress,
                })
                if not result.get("error") and not result.get("cancelled"):
                    try:
                        result["collections"] = self._service.zotero_collections_sync({"_cancel_event": cancel_event})
                    except Exception as exc:
                        logging.exception("Zotero collection mirror failed")
                        if cancel_event.is_set():
                            result["cancelled"] = True
                        else:
                            result["collection_error"] = str(exc)
            except Exception as exc:  # keep worker failures observable instead of hanging at running
                logging.exception("Background Zotero sync failed")
                result = {"error": str(exc), "error_code": "internal_error"}
            with self._zotero_job_lock:
                job = self._zotero_jobs[job_id]
                job["result"] = result
                job["state"] = "cancelled" if result.get("cancelled") else ("failed" if result.get("error") else "completed")

        threading.Thread(target=run, name=f"zotero-sync-{job_id[:8]}", daemon=True).start()
        return {"job_id": job_id, "state": "queued"}

    def _zotero_sync_status(self, payload):
        job_id = str(payload.get("job_id") or self._latest_zotero_job_id)
        with self._zotero_job_lock:
            job = self._zotero_jobs.get(job_id)
            if not job:
                return {"job_id": job_id, "state": "idle", "result": None}
            response = {"job_id": job_id, "state": job["state"], "result": job["result"], "progress": job["progress"], "stage": job["stage"]}
        response["sync"] = self._service.zotero_status({})
        return response

    def _cancel_zotero_sync(self, payload):
        job_id = str(payload.get("job_id") or self._latest_zotero_job_id)
        with self._zotero_job_lock:
            job = self._zotero_jobs.get(job_id)
            if not job:
                return {"job_id": job_id, "state": "idle"}
            job["cancel_event"].set()
            return {"job_id": job_id, "state": "cancelling"}

    def _import_library_item(self, payload):
        trusted = self._native.assert_trusted_path(payload.get("path"), must_exist=True)
        return self._service.import_library_item({**payload, "path": trusted})

    def _open_library_item(self, payload):
        resolved = self._service.library_item_path(payload)
        return self._native.open_authorized_path(resolved["path"])

    def _export_record(self, payload):
        trusted = self._native.assert_trusted_path(payload.get("path"), must_exist=False)
        return self._service.export_record({**payload, "path": trusted})

    def _export_records(self, payload):
        """Export several records into one user-selected directory.

        The directory is selected once through the native picker.  Each output
        name is derived from the record code/title and sanitized before it is
        passed to the service, so a renderer cannot smuggle a path separator or
        overwrite an arbitrary file outside the selected directory.
        """
        directory = Path(self._native.assert_trusted_path(
            payload.get("directory"), must_exist=True,
        ))
        extension = str(payload.get("format") or "docx").strip().lower().lstrip(".")
        if extension not in {"docx", "pdf", "md", "json"}:
            raise NativeCapabilityError("不支持的批量导出格式。")
        raw_ids = payload.get("ids") if isinstance(payload.get("ids"), list) else []
        try:
            record_ids = list(dict.fromkeys(int(value) for value in raw_ids))
        except (TypeError, ValueError) as exc:
            raise NativeCapabilityError("实验记录编号无效。") from exc
        record_ids = [value for value in record_ids if value > 0]
        if not record_ids or len(record_ids) > 200:
            raise NativeCapabilityError("请选择 1 至 200 条实验记录。")

        outputs = []
        used_names = set()
        for record_id in record_ids:
            record = self._service.get_record({"id": record_id})
            stem = re.sub(
                r"[^\w\-. ()\u4e00-\u9fff]+",
                "_",
                f"{record.get('record_code') or 'record'}-{record.get('title') or record_id}",
            ).strip(" .")[:160] or f"record-{record_id}"
            candidate_name = f"{stem}.{extension}"
            counter = 2
            while candidate_name.casefold() in used_names:
                candidate_name = f"{stem}-{counter}.{extension}"
                counter += 1
            used_names.add(candidate_name.casefold())
            target = directory / candidate_name
            # Never overwrite an existing export from a previous batch.
            counter = 2
            while target.exists():
                target = directory / f"{stem}-{counter}.{extension}"
                counter += 1
            result = self._service.export_record({"id": record_id, "path": str(target)})
            outputs.append(result)
        return {
            "count": len(outputs),
            "items": outputs,
            "size_bytes": sum(int(item.get("size_bytes") or 0) for item in outputs),
        }

    def _generate_weekly_ppt(self, payload):
        trusted = self._native.assert_trusted_path(payload.get("path"), must_exist=False)
        return self._service.generate_weekly_ppt({**payload, "path": trusted})

    def _import_weekly_file(self, payload, expected_row_version=None):
        trusted = self._native.assert_trusted_path(payload.get("path"), must_exist=True)
        return self._service.import_weekly_file(
            {**payload, "path": trusted}, expected_row_version,
        )

    def _open_weekly_file(self, payload):
        resolved = self._service.weekly_file_path(payload)
        return self._native.open_authorized_path(resolved["path"])

    def _open_weekly_directory(self, payload):
        resolved = self._service.weekly_directory_path(payload)
        return self._native.open_authorized_path(resolved["path"])

    def _export_weekly_file(self, payload):
        trusted = self._native.assert_trusted_path(payload.get("path"), must_exist=False)
        return self._service.export_weekly_file({**payload, "path": trusted})

    def invoke(self, request):
        request_id = ""
        try:
            if not isinstance(request, dict):
                raise NativeCapabilityError("Bridge 请求必须为对象。")
            if len(json.dumps(request, ensure_ascii=False).encode("utf-8")) > MAX_BRIDGE_BYTES:
                raise NativeCapabilityError("Bridge 请求超过大小限制。")
            request_id = str(request.get("request_id") or "")
            try:
                uuid.UUID(request_id)
            except (ValueError, TypeError, AttributeError) as exc:
                raise NativeCapabilityError("request_id 必须为 UUID。") from exc
            command = str(request.get("command") or "")
            handler = self._commands.get(command)
            if handler is None:
                raise NativeCapabilityError("未知或未授权的 Bridge 命令。")
            payload = request.get("payload") or {}
            if not isinstance(payload, dict):
                raise NativeCapabilityError("payload 必须为对象。")
            data = handler(payload, request.get("expected_row_version"))
            return {
                "ok": True,
                "data": data,
                "error": None,
                "field_errors": {},
                "request_id": request_id,
            }
        except ServiceError as exc:
            return self._error(request_id, exc.code, exc.message, exc.field_errors)
        except NativeCapabilityError as exc:
            return self._error(request_id, "invalid_native_request", str(exc), {})
        except Exception:
            logging.exception("Unhandled desktop bridge failure")
            return self._error(request_id, "internal_error", "桌面命令执行失败，请查看本地日志。", {})

    @staticmethod
    def _error(request_id, code, message, field_errors):
        return {
            "ok": False,
            "data": None,
            "error": {"code": code, "message": message},
            "field_errors": field_errors,
            "request_id": request_id,
        }
