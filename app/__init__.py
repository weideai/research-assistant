import os
from datetime import timedelta
from pathlib import Path
import secrets as stdlib_secrets

from dotenv import load_dotenv
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect

from .version import APP_VERSION, GITHUB_REPOSITORY, UPDATE_CACHE_HOURS


db = SQLAlchemy()
migrate = Migrate(compare_type=True, render_as_batch=True)


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _optional_megabytes(name):
    value = os.getenv(name, "").strip()
    if not value or value == "0":
        return None
    return int(value) * 1024 * 1024


def _load_or_create_key(instance_path, env_name, filename):
    environment_key = os.getenv(env_name, "").strip()
    if environment_key:
        return environment_key
    key_path = Path(instance_path) / filename
    if key_path.exists():
        saved_key = key_path.read_text(encoding="utf-8").strip()
        if saved_key:
            return saved_key
    generated_key = stdlib_secrets.token_urlsafe(48)
    key_path.write_text(generated_key, encoding="utf-8")
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return generated_key


def _load_or_create_secret_key(instance_path):
    return _load_or_create_key(instance_path, "SECRET_KEY", "secret_key")


def _database_url(instance_path):
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        return f"sqlite:///{Path(instance_path) / 'research.db'}"
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value

def create_app(test_config=None):
    load_dotenv()
    configured_instance_path = os.getenv("RESEARCH_ASSISTANT_INSTANCE_DIR", "").strip()
    app = Flask(
        __name__, instance_relative_config=True,
        instance_path=configured_instance_path or None,
    )
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    production = os.getenv("APP_ENV", "development").strip().lower() == "production"
    testing = bool((test_config or {}).get("TESTING"))
    configured_local_mode = (test_config or {}).get("LOCAL_MODE")
    local_mode = (
        bool(configured_local_mode)
        if configured_local_mode is not None
        else _env_bool("LOCAL_MODE", not testing)
    )
    explicit_secret_key = str((test_config or {}).get("SECRET_KEY") or os.getenv("SECRET_KEY", "")).strip()
    explicit_credential_key = str(
        (test_config or {}).get("CREDENTIAL_ENCRYPTION_KEY") or os.getenv("CREDENTIAL_ENCRYPTION_KEY", "")
    ).strip()
    if production and not local_mode:
        if not explicit_secret_key or not explicit_credential_key:
            raise RuntimeError(
                "Production requires explicit SECRET_KEY and CREDENTIAL_ENCRYPTION_KEY values."
            )
        if stdlib_secrets.compare_digest(explicit_secret_key, explicit_credential_key):
            raise RuntimeError("SECRET_KEY and CREDENTIAL_ENCRYPTION_KEY must be different.")

    app.config.from_mapping(
        APP_ENV="production" if production else "development",
        LOCAL_MODE=local_mode,
        SECRET_KEY=explicit_secret_key or _load_or_create_key(app.instance_path, "SECRET_KEY", "secret_key"),
        CREDENTIAL_ENCRYPTION_KEY=explicit_credential_key or _load_or_create_key(
            app.instance_path, "CREDENTIAL_ENCRYPTION_KEY", "credential_key"
        ),
        SQLALCHEMY_DATABASE_URI=_database_url(app.instance_path),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        MAX_CONTENT_LENGTH=_optional_megabytes("MAX_UPLOAD_REQUEST_MB"),
        MAX_ATTACHMENT_BYTES=_optional_megabytes("MAX_ATTACHMENT_MB"),
        SESSION_COOKIE_SECURE=production and not local_mode,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_SECURE=production and not local_mode,
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=int(os.getenv("SESSION_HOURS", "12"))),
        ALLOW_PUBLIC_REGISTRATION=_env_bool("ALLOW_PUBLIC_REGISTRATION", not local_mode and not production),
        BOOTSTRAP_FIRST_USER_ADMIN=_env_bool("BOOTSTRAP_FIRST_USER_ADMIN", not local_mode and not production),
        EXPOSE_DEV_EMAIL_LINKS=_env_bool("EXPOSE_DEV_EMAIL_LINKS", not local_mode and not production),
        AI_SETTINGS_ADMIN_ONLY=_env_bool("AI_SETTINGS_ADMIN_ONLY", False if local_mode else production),
        ALLOW_PRIVATE_API_URLS=_env_bool("ALLOW_PRIVATE_API_URLS", not production),
        AI_ALLOWED_HOSTS=tuple(host.strip().lower() for host in os.getenv("AI_ALLOWED_HOSTS", "").split(",") if host.strip()),
        MAX_LOGIN_ATTEMPTS=int(os.getenv("MAX_LOGIN_ATTEMPTS", "5")),
        LOGIN_LOCK_MINUTES=int(os.getenv("LOGIN_LOCK_MINUTES", "15")),
        RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
        AUTO_CREATE_DB=_env_bool("AUTO_CREATE_DB", local_mode or not production),
        SMTP_HOST=os.getenv("SMTP_HOST", ""),
        SMTP_PORT=int(os.getenv("SMTP_PORT", "587")),
        SMTP_USERNAME=os.getenv("SMTP_USERNAME", ""),
        SMTP_PASSWORD=os.getenv("SMTP_PASSWORD", ""),
        SMTP_USE_TLS=_env_bool("SMTP_USE_TLS", True),
        MAIL_FROM=os.getenv("MAIL_FROM", ""),
        PUBLIC_BASE_URL=os.getenv("PUBLIC_BASE_URL", "").rstrip("/"),
        APPEARANCE_UPLOAD_DIR=os.getenv(
            "APPEARANCE_UPLOAD_DIR", str(Path(app.instance_path) / "uploads" / "backgrounds")
        ),
        ATTACHMENT_UPLOAD_DIR=os.getenv(
            "ATTACHMENT_UPLOAD_DIR", str(Path(app.instance_path) / "uploads" / "experiments")
        ),
        AI_UPLOAD_DIR=os.getenv(
            "AI_UPLOAD_DIR", str(Path(app.instance_path) / "uploads" / "assistant")
        ),
        KNOWLEDGE_UPLOAD_DIR=os.getenv(
            "KNOWLEDGE_UPLOAD_DIR", str(Path(app.instance_path) / "uploads" / "knowledge")
        ),
        WEEKLY_REPORT_UPLOAD_DIR=os.getenv(
            "WEEKLY_REPORT_UPLOAD_DIR", str(Path(app.instance_path) / "uploads" / "weekly-reports")
        ),
        MAX_WEEKLY_REPORT_BYTES=_optional_megabytes("MAX_WEEKLY_REPORT_MB"),
        BACKUP_DIR=os.getenv("BACKUP_DIR", str(Path(app.instance_path) / "backups")),
        ALLOW_OPEN_LOCAL_FOLDERS=_env_bool("ALLOW_OPEN_LOCAL_FOLDERS", not production),
        APP_VERSION=APP_VERSION,
        UPDATE_CHECK_ENABLED=_env_bool("UPDATE_CHECK_ENABLED", True),
        UPDATE_REPOSITORY=os.getenv("UPDATE_REPOSITORY", GITHUB_REPOSITORY).strip() or GITHUB_REPOSITORY,
        UPDATE_CACHE_HOURS=int(os.getenv("UPDATE_CACHE_HOURS", str(UPDATE_CACHE_HOURS))),
    )

    trusted_hosts = [host.strip() for host in os.getenv("TRUSTED_HOSTS", "").split(",") if host.strip()]
    if trusted_hosts:
        app.config["TRUSTED_HOSTS"] = trusted_hosts
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)

    from .export_service import PDF_FONT_MISSING_MESSAGE, find_pdf_font_path

    pdf_font_path = find_pdf_font_path()
    app.config["PDF_FONT_PATH"] = pdf_font_path
    if not pdf_font_path:
        app.logger.warning("PDF 导出不可用：%s", PDF_FONT_MISSING_MESSAGE)

    if app.config["AUTO_CREATE_DB"]:
        with app.app_context():
            if not inspect(db.engine).get_table_names():
                db.create_all()

    from .commands import register_commands

    register_commands(app)
    return app
