from datetime import timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import db, limiter
from .mailer import send_email
from .models import AuditLog, Invitation, User, utcnow
from .security import ROLES, admin_required, hash_token, new_token, normalize_email, record_audit, valid_email


bp = Blueprint("admin", __name__, url_prefix="/admin")


def _invitation_url(token):
    path = url_for("auth.register", token=token)
    base = current_app.config.get("PUBLIC_BASE_URL", "")
    return f"{base}{path}" if base else url_for("auth.register", token=token, _external=True)


@bp.get("")
@login_required
@admin_required
def dashboard():
    users = User.query.order_by(User.created_at.desc()).all()
    invitations = Invitation.query.order_by(Invitation.created_at.desc()).limit(30).all()
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(80).all()
    return render_template("admin.html", users=users, invitations=invitations, logs=logs,
                           roles=sorted(ROLES), invite_link=None, now=utcnow())


@bp.post("/invitations")
@login_required
@admin_required
@limiter.limit("20 per hour")
def create_invitation():
    email = normalize_email(request.form.get("email", ""))
    role = request.form.get("role", "researcher")
    if not valid_email(email) or role not in {"researcher", "viewer"}:
        flash("请填写有效邮箱并选择允许的角色。", "danger")
        return redirect(url_for("admin.dashboard"))
    if User.query.filter_by(email=email).first():
        flash("该邮箱已经拥有账户。", "warning")
        return redirect(url_for("admin.dashboard"))
    raw_token = new_token()
    item = Invitation(email=email, role=role, token_hash=hash_token(raw_token), invited_by_id=current_user.id,
                      expires_at=utcnow() + timedelta(days=7))
    db.session.add(item)
    db.session.flush()
    record_audit("admin.invitation_created", target_type="invitation", target_id=item.id,
                 details={"email": email, "role": role})
    db.session.commit()
    invite_link = _invitation_url(raw_token)
    sent = send_email(email, "R/LAB 账户邀请", f"你已被邀请加入 R/LAB。链接 7 天内有效：\n\n{invite_link}")
    users = User.query.order_by(User.created_at.desc()).all()
    invitations = Invitation.query.order_by(Invitation.created_at.desc()).limit(30).all()
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(80).all()
    flash("邀请已创建。" + ("邮件已发送。" if sent else "SMTP 未配置，请安全地发送下方链接。"), "success")
    return render_template("admin.html", users=users, invitations=invitations, logs=logs,
                           roles=sorted(ROLES), invite_link=invite_link, now=utcnow())


@bp.post("/users/<int:user_id>/update")
@login_required
@admin_required
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("用户不存在。", "danger")
        return redirect(url_for("admin.dashboard"))
    action = request.form.get("action", "")
    if user.id == current_user.id and action in {"toggle_active", "change_role"}:
        flash("不能停用或修改自己的管理员角色。", "danger")
        return redirect(url_for("admin.dashboard"))
    if action == "toggle_active":
        user.is_active = not user.is_active
        user.session_version += 1
    elif action == "revoke_sessions":
        user.session_version += 1
    elif action == "change_role":
        role = request.form.get("role", "")
        if role not in ROLES:
            flash("角色无效。", "danger")
            return redirect(url_for("admin.dashboard"))
        user.role = role
        user.session_version += 1
    else:
        flash("未知操作。", "danger")
        return redirect(url_for("admin.dashboard"))
    record_audit(f"admin.user_{action}", target_type="user", target_id=user.id,
                 details={"role": user.role, "is_active": user.is_active})
    db.session.commit()
    flash("用户设置已更新。", "success")
    return redirect(url_for("admin.dashboard"))
