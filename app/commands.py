import click
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
