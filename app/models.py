from datetime import date, datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class User(UserMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="researcher", index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    email_verified_at = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    failed_login_count = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    session_version = db.Column(db.Integer, nullable=False, default=1)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f"{self.id}:{self.session_version}"

    @property
    def is_admin(self):
        return self.role == "system_admin"


class Invitation(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), nullable=False, index=True)
    role = db.Column(db.String(30), nullable=False, default="researcher")
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    invited_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    accepted_at = db.Column(db.DateTime)
    invited_by = db.relationship("User", foreign_keys=[invited_by_id])


class PasswordResetToken(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime)
    user = db.relationship("User")


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    event_type = db.Column(db.String(80), nullable=False, index=True)
    target_type = db.Column(db.String(50), default="")
    target_id = db.Column(db.String(80), default="")
    ip_address = db.Column(db.String(64), default="")
    user_agent = db.Column(db.String(255), default="")
    details = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    actor = db.relationship("User", foreign_keys=[actor_user_id])


class ApiSetting(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True, index=True)
    api_url = db.Column(db.String(500), nullable=False, default="https://api.openai.com/v1")
    model = db.Column(db.String(160), nullable=False, default="gpt-5.6-terra")
    encrypted_api_key = db.Column(db.Text, default="")
    is_enabled = db.Column(db.Boolean, nullable=False, default=False)

    def set_api_key(self, value):
        from .secrets import encrypt_secret

        self.encrypted_api_key = encrypt_secret(value.strip())

    def get_api_key(self):
        from .secrets import decrypt_secret

        return decrypt_secret(self.encrypted_api_key)


class AppearanceSetting(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True, index=True)
    theme = db.Column(db.String(20), nullable=False, default="research")
    color_mode = db.Column(db.String(10), nullable=False, default="light")
    background_filename = db.Column(db.String(120), default="")


class AIConversation(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False, default="新对话")
    page_type = db.Column(db.String(30), default="")
    page_id = db.Column(db.Integer)
    messages = db.relationship(
        "AIMessage", backref="conversation", cascade="all, delete-orphan",
        order_by="AIMessage.created_at",
    )


class AIMessage(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("ai_conversation.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    references_json = db.Column(db.Text, nullable=False, default="[]")
    proposal_json = db.Column(db.Text, nullable=False, default="")
    before_json = db.Column(db.Text, nullable=False, default="")
    applied_at = db.Column(db.DateTime)
    attachments = db.relationship(
        "AIChatAttachment", backref="message", cascade="all, delete-orphan",
        order_by="AIChatAttachment.created_at",
    )


class AIChatAttachment(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("ai_message.id"), nullable=False, index=True)
    original_name = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(1000), nullable=False, unique=True)
    size_bytes = db.Column(db.BigInteger, nullable=False, default=0)
    mime_type = db.Column(db.String(160), nullable=False, default="application/octet-stream")
    text_excerpt = db.Column(db.Text, nullable=False, default="")

    @property
    def size_label(self):
        if self.size_bytes >= 1024 * 1024:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"
        if self.size_bytes >= 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        return f"{self.size_bytes} B"


class Task(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(40), nullable=False, default="实验")
    priority = db.Column(db.String(10), nullable=False, default="中")
    deadline = db.Column(db.Date, index=True)
    status = db.Column(db.String(20), nullable=False, default="待办", index=True)
    notes = db.Column(db.Text, default="")


class Experiment(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    code = db.Column(db.String(60), default="")
    objective = db.Column(db.Text, default="")
    owner = db.Column(db.String(80), default="")
    status = db.Column(db.String(20), nullable=False, default="未开始", index=True)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    steps = db.relationship("ExperimentStep", backref="experiment", cascade="all, delete-orphan", order_by="ExperimentStep.position")
    records = db.relationship("ExperimentRecord", backref="experiment", cascade="all, delete-orphan", order_by="ExperimentRecord.record_date.desc()")


class ExperimentStep(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey("experiment.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    operator = db.Column(db.String(80), default="")
    planned_date = db.Column(db.Date)
    completed_date = db.Column(db.Date)
    is_done = db.Column(db.Boolean, nullable=False, default=False)


class ExperimentRecord(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey("experiment.id"), nullable=False, index=True)
    record_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    operator = db.Column(db.String(80), default="")
    conditions = db.Column(db.Text, default="")
    content = db.Column(db.Text, nullable=False)
    result = db.Column(db.String(20), nullable=False, default="待确认")
    remark = db.Column(db.Text, default="")
    attachments = db.relationship(
        "ExperimentAttachment", backref="record", cascade="all, delete-orphan",
        order_by="ExperimentAttachment.created_at.desc()",
    )


class ExperimentAttachment(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey("experiment.id"), nullable=False, index=True)
    record_id = db.Column(db.Integer, db.ForeignKey("experiment_record.id"), nullable=False, index=True)
    original_name = db.Column(db.String(255), nullable=False)
    relative_path = db.Column(db.String(1000), nullable=False)
    stored_path = db.Column(db.String(1000), nullable=False, unique=True)
    size_bytes = db.Column(db.BigInteger, nullable=False, default=0)
    mime_type = db.Column(db.String(160), nullable=False, default="application/octet-stream")
    category = db.Column(db.String(20), nullable=False, default="其他")
    is_previewable_image = db.Column(db.Boolean, nullable=False, default=False)

    @property
    def size_label(self):
        if self.size_bytes >= 1024 * 1024:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"
        if self.size_bytes >= 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        return f"{self.size_bytes} B"


class Sample(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    sample_code = db.Column(db.String(80), nullable=False, index=True)
    sample_type = db.Column(db.String(80), default="")
    source = db.Column(db.String(120), default="")
    location = db.Column(db.String(180), default="")
    quantity = db.Column(db.String(60), default="")
    status = db.Column(db.String(20), nullable=False, default="可用")
    notes = db.Column(db.Text, default="")


class Paper(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(240), nullable=False)
    journal = db.Column(db.String(160), default="")
    status = db.Column(db.String(40), nullable=False, default="准备中")
    submission_date = db.Column(db.Date)
    revision_deadline = db.Column(db.Date)
    notes = db.Column(db.Text, default="")
    comments = db.relationship("ReviewerComment", backref="paper", cascade="all, delete-orphan", order_by="ReviewerComment.reviewer")


class ReviewerComment(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey("paper.id"), nullable=False, index=True)
    reviewer = db.Column(db.String(40), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="待回复")
