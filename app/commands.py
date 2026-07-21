import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext

from . import db
from .models import User, utcnow
from .security import normalize_email, record_audit, validate_password, valid_email


def register_commands(app):
    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt=True)
    @click.password_option(confirmation_prompt=True)
    @with_appcontext
    def create_admin(email, name, password):
        """Create or promote the initial system administrator."""
        email = normalize_email(email)
        if not valid_email(email):
            raise click.ClickException("邮箱格式不正确。")
        error = validate_password(password)
        if error:
            raise click.ClickException(error)
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(name=name.strip(), email=email, role="system_admin", is_active=True, email_verified_at=utcnow())
            user.set_password(password)
            db.session.add(user)
            action = "created"
        else:
            user.name = name.strip() or user.name
            user.role = "system_admin"
            user.is_active = True
            user.email_verified_at = user.email_verified_at or utcnow()
            user.set_password(password)
            user.session_version += 1
            action = "promoted"
        db.session.flush()
        record_audit("admin.bootstrap", actor=user, target_type="user", target_id=user.id, details={"action": action})
        db.session.commit()
        click.echo(f"管理员已就绪：{email}")

    @app.cli.command("promote-admin")
    @click.option("--email", required=True)
    @with_appcontext
    def promote_admin(email):
        """Promote an existing account without changing its password."""
        email = normalize_email(email)
        user = User.query.filter_by(email=email).first()
        if not user:
            raise click.ClickException("找不到该邮箱对应的账户。")
        user.role = "system_admin"
        user.is_active = True
        user.email_verified_at = user.email_verified_at or utcnow()
        user.session_version += 1
        record_audit("admin.promoted", actor=user, target_type="user", target_id=user.id)
        db.session.commit()
        click.echo(f"已提升为系统管理员：{email}")

    @app.cli.command("backup-local")
    @click.option("--output", type=click.Path(path_type=Path), help="备份 ZIP 的输出路径。")
    @with_appcontext
    def backup_local(output):
        """Back up the local SQLite database, uploads, and local keys."""
        if db.engine.url.get_backend_name() != "sqlite" or not db.engine.url.database:
            raise click.ClickException("本地完整备份目前只支持 SQLite 数据库。")
        database_path = Path(db.engine.url.database).resolve()
        if not database_path.is_file():
            raise click.ClickException(f"找不到数据库：{database_path}")
        backup_dir = Path(current_app.config["BACKUP_DIR"])
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = (output or backup_dir / f"research-assistant-{timestamp}.zip").resolve()
        output.parent.mkdir(parents=True, exist_ok=True)

        upload_roots = {
            "experiments": Path(current_app.config["ATTACHMENT_UPLOAD_DIR"]),
            "assistant": Path(current_app.config["AI_UPLOAD_DIR"]),
            "backgrounds": Path(current_app.config["APPEARANCE_UPLOAD_DIR"]),
        }
        with tempfile.TemporaryDirectory(prefix="research-backup-") as temporary_dir:
            snapshot_path = Path(temporary_dir) / "research.db"
            source = sqlite3.connect(database_path)
            target = sqlite3.connect(snapshot_path)
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
            manifest = {
                "format": "research-assistant-local-backup",
                "version": 1,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "database": "database/research.db",
                "uploads": {name: f"uploads/{name}" for name in upload_roots},
                "contains_local_keys": True,
            }
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                archive.write(snapshot_path, "database/research.db")
                for name, root in upload_roots.items():
                    if root.is_dir():
                        for file_path in root.rglob("*"):
                            if file_path.is_file():
                                archive.write(file_path, f"uploads/{name}/{file_path.relative_to(root).as_posix()}")
                for key_name in ("secret_key", "credential_key"):
                    key_path = Path(current_app.instance_path) / key_name
                    if key_path.is_file():
                        archive.write(key_path, f"keys/{key_name}")
        click.echo(f"备份已创建：{output}")
        click.echo("该文件包含账户、实验数据和本地密钥，请存放在受保护的位置。")

    @app.cli.command("restore-local")
    @click.option("--archive", "archive_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
    @click.option("--yes", is_flag=True, help="跳过交互确认。")
    @with_appcontext
    def restore_local(archive_path, yes):
        """Restore a backup created by backup-local. Stop the web server first."""
        if db.engine.url.get_backend_name() != "sqlite" or not db.engine.url.database:
            raise click.ClickException("本地恢复目前只支持 SQLite 数据库。")
        if not yes and not click.confirm("恢复会替换当前数据库和上传目录，是否继续？"):
            raise click.Abort()
        database_path = Path(db.engine.url.database).resolve()
        upload_roots = {
            "experiments": Path(current_app.config["ATTACHMENT_UPLOAD_DIR"]),
            "assistant": Path(current_app.config["AI_UPLOAD_DIR"]),
            "backgrounds": Path(current_app.config["APPEARANCE_UPLOAD_DIR"]),
        }
        with tempfile.TemporaryDirectory(prefix="research-restore-") as temporary_dir:
            extract_root = Path(temporary_dir).resolve()
            with zipfile.ZipFile(archive_path) as archive:
                try:
                    manifest = json.loads(archive.read("manifest.json"))
                except (KeyError, json.JSONDecodeError) as exc:
                    raise click.ClickException("备份包缺少有效的 manifest.json。") from exc
                if manifest.get("format") != "research-assistant-local-backup" or manifest.get("version") != 1:
                    raise click.ClickException("不支持的备份格式或版本。")
                for member in archive.infolist():
                    target = (extract_root / member.filename).resolve()
                    if target != extract_root and extract_root not in target.parents:
                        raise click.ClickException("备份包包含不安全的文件路径。")
                archive.extractall(extract_root)

            restored_database = extract_root / "database" / "research.db"
            if not restored_database.is_file():
                raise click.ClickException("备份包中缺少数据库文件。")
            db.session.remove()
            db.engine.dispose()
            database_path.parent.mkdir(parents=True, exist_ok=True)
            if database_path.exists():
                safety_copy = database_path.with_name(f"{database_path.stem}.before-restore-{datetime.now():%Y%m%d-%H%M%S}{database_path.suffix}")
                shutil.copy2(database_path, safety_copy)
                click.echo(f"当前数据库副本：{safety_copy}")
            shutil.copy2(restored_database, database_path)

            for name, target_root in upload_roots.items():
                source_root = extract_root / "uploads" / name
                if target_root.exists():
                    shutil.rmtree(target_root)
                if source_root.is_dir():
                    shutil.copytree(source_root, target_root)
                else:
                    target_root.mkdir(parents=True, exist_ok=True)
            for key_name in ("secret_key", "credential_key"):
                source_key = extract_root / "keys" / key_name
                if source_key.is_file():
                    shutil.copy2(source_key, Path(current_app.instance_path) / key_name)
        click.echo("恢复完成。请重新启动本地服务并重新登录。")
