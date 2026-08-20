from datetime import timedelta
from urllib.parse import urljoin, urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from . import db, limiter
from .mailer import send_email
from .models import Invitation, PasswordResetToken, User, utcnow
from .security import hash_token, new_token, normalize_email, record_audit, validate_password, valid_email


bp = Blueprint("auth", __name__)


def safe_next_url(target):
    if not target:
        return None
    base = urlparse(request.host_url)
    candidate = urlparse(urljoin(request.host_url, target))
    return target if candidate.scheme in {"http", "https"} and candidate.netloc == base.netloc else None


def _absolute_url(endpoint, **values):
    path = url_for(endpoint, **values)
    base = current_app.config.get("PUBLIC_BASE_URL", "")
    return f"{base}{path}" if base else url_for(endpoint, _external=True, **values)


def _invitation(raw_token):
    if not raw_token:
        return None
    item = Invitation.query.filter_by(token_hash=hash_token(raw_token), accepted_at=None).first()
    if not item or item.expires_at < utcnow():
        return None
    return item


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    raw_token = request.values.get("token", "").strip()
    invitation = _invitation(raw_token)
    public_allowed = current_app.config["ALLOW_PUBLIC_REGISTRATION"]
    if not public_allowed and not invitation:
        return render_template("auth.html", mode="registration_closed"), 403

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = invitation.email if invitation else normalize_email(request.form.get("email", ""))
        password = request.form.get("password", "")
        password_error = validate_password(password)
        if not name or not valid_email(email):
            flash("请填写姓名和有效邮箱。", "danger")
        elif password_error:
            flash(password_error, "danger")
        elif User.query.filter_by(email=email).first():
            flash("该邮箱已经注册。", "danger")
        else:
            first_user = User.query.count() == 0
            role = invitation.role if invitation else (
                "system_admin" if first_user and current_app.config["BOOTSTRAP_FIRST_USER_ADMIN"] else "researcher"
            )
            user = User(name=name, email=email, role=role, is_active=True, email_verified_at=utcnow())
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            if invitation:
                invitation.accepted_at = utcnow()
            record_audit("auth.register", actor=user, target_type="user", target_id=user.id, details={"invited": bool(invitation)})
            db.session.commit()
            login_user(user)
            flash("账户已创建，欢迎使用。", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth.html", mode="register", invitation=invitation, token=raw_token)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = normalize_email(request.form.get("email", ""))
        user = User.query.filter_by(email=email).first()
        now = utcnow()
        valid = bool(user and user.is_active and (not user.locked_until or user.locked_until <= now))
        valid = valid and user.check_password(request.form.get("password", ""))
        if not valid:
            if user and user.is_active:
                user.failed_login_count += 1
                if user.failed_login_count >= current_app.config["MAX_LOGIN_ATTEMPTS"]:
                    user.locked_until = now + timedelta(minutes=current_app.config["LOGIN_LOCK_MINUTES"])
                    user.failed_login_count = 0
                record_audit("auth.login_failed", actor=user, target_type="user", target_id=user.id)
                db.session.commit()
            flash("邮箱或密码不正确，或账户暂时不可用。", "danger")
        else:
            user.failed_login_count = 0
            user.locked_until = None
            user.last_login_at = now
            record_audit("auth.login", actor=user, target_type="user", target_id=user.id)
            db.session.commit()
            login_user(user, remember=bool(request.form.get("remember")), duration=timedelta(days=14))
            return redirect(safe_next_url(request.args.get("next")) or url_for("main.dashboard"))
    return render_template("auth.html", mode="login")


@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    dev_link = None
    if request.method == "POST":
        email = normalize_email(request.form.get("email", ""))
        user = User.query.filter_by(email=email, is_active=True).first()
        if user:
            raw_token = new_token()
            token = PasswordResetToken(user_id=user.id, token_hash=hash_token(raw_token),
                                       expires_at=utcnow() + timedelta(minutes=30))
            db.session.add(token)
            record_audit("auth.password_reset_requested", actor=user, target_type="user", target_id=user.id)
            db.session.commit()
            reset_url = _absolute_url("auth.reset_password", token=raw_token)
            sent = send_email(user.email, "R/LAB 密码重置", f"请在 30 分钟内打开以下链接重置密码：\n\n{reset_url}")
            if not sent and current_app.config["EXPOSE_DEV_EMAIL_LINKS"]:
                dev_link = reset_url
        flash("如果该邮箱存在，你将收到密码重置说明。", "success")
    return render_template("forgot_password.html", dev_link=dev_link)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def reset_password(token):
    item = PasswordResetToken.query.filter_by(token_hash=hash_token(token), used_at=None).first()
    if not item or item.expires_at < utcnow() or not item.user.is_active:
        flash("重置链接无效或已经过期。", "danger")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        error = validate_password(password)
        if error:
            flash(error, "danger")
        else:
            item.user.set_password(password)
            item.user.session_version += 1
            item.used_at = utcnow()
            record_audit("auth.password_reset", actor=item.user, target_type="user", target_id=item.user.id)
            db.session.commit()
            flash("密码已重置，请重新登录。", "success")
            return redirect(url_for("auth.login"))
    return render_template("reset_password.html")


@bp.route("/account/security", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per hour")
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        error = validate_password(new_password)
        if not current_user.check_password(current_password):
            flash("当前密码不正确。", "danger")
        elif error:
            flash(error, "danger")
        else:
            current_user.set_password(new_password)
            current_user.session_version += 1
            record_audit("auth.password_changed", target_type="user", target_id=current_user.id)
            db.session.commit()
            login_user(current_user)
            flash("密码已修改，其他登录会话已失效。", "success")
            return redirect(url_for("auth.change_password"))
    return render_template("change_password.html")


@bp.post("/logout")
@login_required
def logout():
    record_audit("auth.logout", target_type="user", target_id=current_user.id)
    db.session.commit()
    logout_user()
    flash("你已安全退出。", "success")
    return redirect(url_for("auth.login"))
