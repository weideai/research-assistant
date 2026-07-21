import hashlib
import json
import re
import secrets
from functools import wraps

from flask import abort, has_request_context, request
from flask_login import current_user

from . import db
from .models import AuditLog


ROLES = {"system_admin", "lab_admin", "researcher", "viewer"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value):
    return value.strip().lower()


def valid_email(value):
    return bool(EMAIL_RE.fullmatch(normalize_email(value)))


def validate_password(value, minimum=12):
    if len(value) < minimum:
        return f"密码至少需要 {minimum} 位。"
    if value.lower() == value or value.upper() == value or not any(char.isdigit() for char in value):
        return "密码需要同时包含大写字母、小写字母和数字。"
    return ""


def new_token():
    return secrets.token_urlsafe(32)


def hash_token(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def record_audit(event_type, actor=None, target_type="", target_id="", details=None):
    if actor is None and has_request_context() and current_user.is_authenticated:
        actor = current_user
    log = AuditLog(
        actor_user_id=getattr(actor, "id", None),
        event_type=event_type,
        target_type=target_type,
        target_id=str(target_id or ""),
        ip_address=(request.remote_addr or "")[:64] if has_request_context() else "",
        user_agent=(request.user_agent.string or "")[:255] if has_request_context() else "",
        details=json.dumps(details or {}, ensure_ascii=False),
    )
    db.session.add(log)
    return log


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped

