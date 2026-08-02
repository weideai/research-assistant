from app import create_app, db
from app.models import User


def _local_app(tmp_path):
    return create_app({
        "TESTING": True,
        "LOCAL_MODE": True,
        "AUTO_CREATE_DB": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "local-test-key",
        "CREDENTIAL_ENCRYPTION_KEY": "local-test-credential-key",
        "RATELIMIT_ENABLED": False,
        "UPDATE_CHECK_ENABLED": False,
        "ATTACHMENT_UPLOAD_DIR": str(tmp_path / "experiment-files"),
        "APPEARANCE_UPLOAD_DIR": str(tmp_path / "backgrounds"),
        "AI_UPLOAD_DIR": str(tmp_path / "assistant-files"),
        "KNOWLEDGE_UPLOAD_DIR": str(tmp_path / "knowledge-files"),
        "WEEKLY_REPORT_UPLOAD_DIR": str(tmp_path / "weekly-reports"),
        "BACKUP_DIR": str(tmp_path / "backups"),
    })


def test_local_mode_opens_workspace_and_creates_local_user(tmp_path):
    app = _local_app(tmp_path)
    client = app.test_client()

    response = client.get("/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "科研工作台" in body
    assert "本地工作区" in body
    assert "数据保存在此设备" in body
    for removed_text in ("退出登录", "账号安全", "系统管理", "人员管理"):
        assert removed_text not in body
    with app.app_context():
        user = User.query.one()
        assert user.name == "本地研究者"
        assert user.email == "local@research-assistant.invalid"


def test_local_mode_does_not_register_account_or_admin_routes(tmp_path):
    app = _local_app(tmp_path)
    client = app.test_client()

    for path in (
        "/login", "/register", "/forgot-password", "/reset-password/example",
        "/account/security", "/logout", "/admin", "/admin/invitations",
    ):
        assert client.get(path).status_code == 404
