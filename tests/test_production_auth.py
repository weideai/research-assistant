import re
from datetime import timedelta

import pytest

from app import create_app, db
from app.models import AuditLog, Invitation, User, utcnow


def test_registration_can_be_invitation_only(client, app):
    app.config["ALLOW_PUBLIC_REGISTRATION"] = False
    response = client.get("/register")
    assert response.status_code == 403
    assert "注册需要邀请".encode() in response.data


def test_admin_invitation_creates_account_with_selected_role(client, auth, app):
    auth.register()
    response = client.post("/admin/invitations", data={"email": "viewer@example.com", "role": "viewer"})
    assert response.status_code == 200
    match = re.search(rb"/register\?token=([^&<\s]+)", response.data)
    assert match
    token = match.group(1).decode()

    auth.logout()
    response = client.post(f"/register?token={token}", data={
        "token": token, "name": "只读成员", "email": "changed@example.com", "password": "ViewerPassword1"
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="viewer@example.com").one()
        assert user.role == "viewer"
        assert Invitation.query.one().accepted_at is not None


def test_login_failures_lock_account(client, auth, app):
    auth.register()
    auth.logout()
    app.config["MAX_LOGIN_ATTEMPTS"] = 2
    client.post("/login", data={"email": "researcher@example.com", "password": "WrongPassword1"})
    client.post("/login", data={"email": "researcher@example.com", "password": "WrongPassword1"})
    with app.app_context():
        user = User.query.filter_by(email="researcher@example.com").one()
        assert user.locked_until > utcnow()
    response = auth.login()
    assert "账户暂时不可用".encode() in response.data


def test_password_reset_revokes_previous_sessions(client, auth, app):
    auth.register()
    auth.logout()
    response = client.post("/forgot-password", data={"email": "researcher@example.com"})
    match = re.search(rb"/reset-password/([A-Za-z0-9_-]+)", response.data)
    assert match
    token = match.group(1).decode()
    client.post(f"/reset-password/{token}", data={"password": "NewPassword123"})
    with app.app_context():
        user = User.query.filter_by(email="researcher@example.com").one()
        assert user.session_version == 2
        assert user.check_password("NewPassword123")


def test_admin_can_change_role_disable_and_revoke_sessions(client, auth, app):
    auth.register()
    with app.app_context():
        member = User(name="成员", email="member@example.com", role="researcher", is_active=True,
                      email_verified_at=utcnow())
        member.set_password("MemberPassword1")
        db.session.add(member)
        db.session.commit()
        member_id = member.id

    client.post(f"/admin/users/{member_id}/update", data={"action": "change_role", "role": "viewer"})
    client.post(f"/admin/users/{member_id}/update", data={"action": "revoke_sessions"})
    client.post(f"/admin/users/{member_id}/update", data={"action": "toggle_active"})
    with app.app_context():
        member = db.session.get(User, member_id)
        assert member.role == "viewer"
        assert member.is_active is False
        assert member.session_version == 4
        assert AuditLog.query.filter(AuditLog.event_type.like("admin.user_%")).count() == 3


def test_non_admin_cannot_open_admin_or_api_settings(client, auth, app):
    auth.register()
    with app.app_context():
        user = User.query.filter_by(email="researcher@example.com").one()
        user.role = "researcher"
        user.session_version += 1
        db.session.commit()
    auth.login()
    assert client.get("/admin").status_code == 403
    app.config["AI_SETTINGS_ADMIN_ONLY"] = True
    assert client.get("/settings/api").status_code == 403


def test_viewer_can_read_but_cannot_modify_research_data(client, auth, app):
    auth.register()
    with app.app_context():
        user = User.query.filter_by(email="researcher@example.com").one()
        user.role = "viewer"
        user.session_version += 1
        db.session.commit()
    auth.login()
    assert client.get("/tasks").status_code == 200
    assert client.post("/tasks", data={"title": "不应创建"}).status_code == 403


def test_security_headers_and_health_check(client):
    response = client.get("/login")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json == {"status": "ok"}


def test_production_requires_explicit_distinct_keys(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY", raising=False)

    with pytest.raises(RuntimeError, match="Production requires explicit"):
        create_app()

    monkeypatch.setenv("SECRET_KEY", "same-production-key")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "same-production-key")
    with pytest.raises(RuntimeError, match="must be different"):
        create_app()
