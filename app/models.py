from datetime import date, datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class SoftDeleteMixin:
    is_deleted = db.Column(db.Boolean, nullable=False, default=False, index=True)
    deleted_at = db.Column(db.DateTime)


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


class ApiPreset(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    api_url = db.Column(db.String(500), nullable=False, default="https://api.openai.com/v1")
    encrypted_api_key = db.Column(db.Text, default="")
    text_model = db.Column(db.String(160), default="")
    model_capabilities_json = db.Column(db.Text, nullable=False, default="{}")
    vision_model = db.Column(db.String(160), default="")
    embedding_model = db.Column(db.String(160), default="")
    image_model = db.Column(db.String(160), default="")
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False, index=True)
    sensitive_warning_enabled = db.Column(db.Boolean, nullable=False, default=True)

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
    selected_experiment_ids_json = db.Column(db.Text, nullable=False, default="[]")
    selected_batch_ids_json = db.Column(db.Text, nullable=False, default="[]")
    selected_knowledge_base_ids_json = db.Column(db.Text, nullable=False, default="[]")
    messages = db.relationship(
        "AIMessage", backref="conversation", cascade="all, delete-orphan",
        order_by="AIMessage.created_at, AIMessage.id",
    )


class AIMessage(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("ai_conversation.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    references_json = db.Column(db.Text, nullable=False, default="[]")
    proposal_json = db.Column(db.Text, nullable=False, default="")
    before_json = db.Column(db.Text, nullable=False, default="")
    model_name = db.Column(db.String(160), nullable=False, default="")
    prompt_snapshot = db.Column(db.Text, nullable=False, default="")
    context_snapshot_json = db.Column(db.Text, nullable=False, default="{}")
    requires_human_review = db.Column(db.Boolean, nullable=False, default=False)
    applied_at = db.Column(db.DateTime)
    undo_json = db.Column(db.Text, nullable=False, default="")
    after_json = db.Column(db.Text, nullable=False, default="")
    reverted_at = db.Column(db.DateTime)
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


class AIAssistantPreference(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True, index=True)
    custom_prompt = db.Column(db.Text, nullable=False, default="")


class AIKnowledgeBase(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    custom_instructions = db.Column(db.Text, nullable=False, default="")
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    documents = db.relationship(
        "AIKnowledgeDocument", backref="knowledge_base", cascade="all, delete-orphan",
        order_by="AIKnowledgeDocument.created_at",
    )


class AIKnowledgeDocument(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    knowledge_base_id = db.Column(
        db.Integer, db.ForeignKey("ai_knowledge_base.id"), nullable=False, index=True
    )
    title = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False, default="")
    stored_path = db.Column(db.String(1000), nullable=False, default="")
    mime_type = db.Column(db.String(160), nullable=False, default="text/plain")
    size_bytes = db.Column(db.BigInteger, nullable=False, default=0)
    text_content = db.Column(db.Text, nullable=False, default="")
    sha256 = db.Column(db.String(64), nullable=False, default="", index=True)
    version_number = db.Column(db.Integer, nullable=False, default=1)
    parsing_status = db.Column(db.String(30), nullable=False, default="metadata_only")
    chunks = db.relationship(
        "AIKnowledgeChunk", backref="document", cascade="all, delete-orphan",
        order_by="AIKnowledgeChunk.position",
    )

    @property
    def size_label(self):
        if self.size_bytes >= 1024 * 1024:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"
        if self.size_bytes >= 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        return f"{self.size_bytes} B"


class AIKnowledgeChunk(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer, db.ForeignKey("ai_knowledge_document.id"), nullable=False, index=True
    )
    position = db.Column(db.Integer, nullable=False, default=1)
    content = db.Column(db.Text, nullable=False, default="")
    source_locator = db.Column(db.String(255), nullable=False, default="")
    content_sha256 = db.Column(db.String(64), nullable=False, default="", index=True)


class ResearchProject(SoftDeleteMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    code = db.Column(db.String(80), default="")
    objective = db.Column(db.Text, default="")
    status = db.Column(db.String(30), nullable=False, default="进行中", index=True)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    notes = db.Column(db.Text, default="")
    experiments = db.relationship(
        "Experiment", backref="project", order_by="Experiment.updated_at.desc()"
    )
    tasks = db.relationship("Task", backref="project", order_by="Task.deadline")


class Task(SoftDeleteMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), index=True)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(40), nullable=False, default="实验")
    priority = db.Column(db.String(10), nullable=False, default="中")
    deadline = db.Column(db.Date, index=True)
    status = db.Column(db.String(20), nullable=False, default="待办", index=True)
    notes = db.Column(db.Text, default="")


class Experiment(SoftDeleteMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), index=True)
    title = db.Column(db.String(160), nullable=False)
    code = db.Column(db.String(60), default="")
    objective = db.Column(db.Text, default="")
    owner = db.Column(db.String(80), default="")
    status = db.Column(db.String(20), nullable=False, default="未开始", index=True)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    sample_requirements_json = db.Column(db.Text, nullable=False, default="[]")
    record_conditions_template = db.Column(db.Text, default="")
    record_content_template = db.Column(db.Text, default="")
    record_remark_template = db.Column(db.Text, default="")
    steps = db.relationship("ExperimentStep", backref="experiment", cascade="all, delete-orphan", order_by="ExperimentStep.position")
    records = db.relationship("ExperimentRecord", backref="experiment", cascade="all, delete-orphan", order_by="ExperimentRecord.record_date.desc()")
    sample_usages = db.relationship(
        "ExperimentSample", backref="experiment", cascade="all, delete-orphan",
        order_by="ExperimentSample.created_at",
    )
    plan_parameters = db.relationship(
        "ExperimentParameter", backref="experiment", cascade="all, delete-orphan",
        order_by="ExperimentParameter.position",
    )
    batches = db.relationship(
        "ExperimentBatch", backref="experiment", cascade="all, delete-orphan",
        order_by="ExperimentBatch.created_at.desc()",
    )


class ExperimentTemplate(SoftDeleteMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    objective = db.Column(db.Text, default="")
    sample_requirements_json = db.Column(db.Text, nullable=False, default="[]")
    record_conditions_template = db.Column(db.Text, default="")
    record_content_template = db.Column(db.Text, default="")
    record_remark_template = db.Column(db.Text, default="")
    steps = db.relationship(
        "ExperimentTemplateStep", backref="template", cascade="all, delete-orphan",
        order_by="ExperimentTemplateStep.position",
    )
    parameters = db.relationship(
        "ExperimentTemplateParameter", backref="template", cascade="all, delete-orphan",
        order_by="ExperimentTemplateParameter.position",
    )


class ExperimentTemplateParameter(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("experiment_template.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    name = db.Column(db.String(120), nullable=False)
    value = db.Column(db.String(160), default="")
    unit = db.Column(db.String(40), default="")
    notes = db.Column(db.String(255), default="")


class ExperimentTemplateStep(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("experiment_template.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    planned_offset_days = db.Column(db.Integer, nullable=False, default=0)


class RecordTemplate(SoftDeleteMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    conditions = db.Column(db.Text, default="")
    content = db.Column(db.Text, nullable=False, default="")
    remark = db.Column(db.Text, default="")
    parameters = db.relationship(
        "RecordTemplateParameter", backref="template", cascade="all, delete-orphan",
        order_by="RecordTemplateParameter.position",
    )


class RecordTemplateParameter(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("record_template.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    name = db.Column(db.String(120), nullable=False)
    value = db.Column(db.String(160), default="")
    unit = db.Column(db.String(40), default="")
    notes = db.Column(db.String(255), default="")


class ExperimentStep(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey("experiment.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    operator = db.Column(db.String(80), default="")
    planned_date = db.Column(db.Date)


class ExperimentBatch(SoftDeleteMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey("experiment.id"), nullable=False, index=True)
    batch_code = db.Column(db.String(80), default="")
    repeat_kind = db.Column(db.String(30), default="独立实验")
    repeat_number = db.Column(db.Integer, nullable=False, default=1)
    group_name = db.Column(db.String(80), default="")
    operator = db.Column(db.String(80), default="")
    status = db.Column(db.String(20), nullable=False, default="未开始", index=True)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    summary = db.Column(db.Text, default="")
    conclusion = db.Column(db.Text, default="")
    requires_repeat = db.Column(db.Boolean, nullable=False, default=False)
    records = db.relationship(
        "ExperimentRecord", backref="batch", order_by="ExperimentRecord.record_date.desc()"
    )
    sample_usages = db.relationship(
        "BatchSample", backref="batch", cascade="all, delete-orphan",
        order_by="BatchSample.created_at",
    )
    actual_parameters = db.relationship(
        "BatchParameter", backref="batch", cascade="all, delete-orphan",
        order_by="BatchParameter.position",
    )
    steps = db.relationship(
        "BatchStep", backref="batch", cascade="all, delete-orphan",
        order_by="BatchStep.position",
    )


class BatchStep(TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint("batch_id", "source_step_id", name="uq_batch_step_source"),
    )

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("experiment_batch.id"), nullable=False, index=True)
    source_step_id = db.Column(
        db.Integer, db.ForeignKey("experiment_step.id", ondelete="SET NULL"), index=True,
    )
    position = db.Column(db.Integer, nullable=False, default=1)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    operator = db.Column(db.String(80), default="")
    planned_date = db.Column(db.Date)
    completed_date = db.Column(db.Date)
    is_done = db.Column(db.Boolean, nullable=False, default=False)
    source_step = db.relationship("ExperimentStep")

    @classmethod
    def from_plan_step(cls, batch_id, step):
        return cls(
            batch_id=batch_id,
            source_step_id=step.id,
            position=step.position,
            title=step.title,
            description=step.description,
            operator=step.operator,
            planned_date=step.planned_date,
        )


class BatchParameter(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("experiment_batch.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    name = db.Column(db.String(120), nullable=False)
    value = db.Column(db.String(160), default="")
    unit = db.Column(db.String(40), default="")
    notes = db.Column(db.String(255), default="")


class ExperimentRecord(SoftDeleteMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey("experiment.id"), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("experiment_batch.id"), nullable=False, index=True)
    record_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    operator = db.Column(db.String(80), default="")
    conditions = db.Column(db.Text, default="")
    content = db.Column(db.Text, nullable=False)
    result = db.Column(db.String(20), nullable=False, default="待确认")
    remark = db.Column(db.Text, default="")
    lifecycle_status = db.Column(db.String(20), nullable=False, default="草稿", index=True)
    finalized_at = db.Column(db.DateTime)
    source_ai_message_id = db.Column(db.Integer, db.ForeignKey("ai_message.id"), index=True)
    attachments = db.relationship(
        "ExperimentAttachment", backref="record", cascade="all, delete-orphan",
        order_by="ExperimentAttachment.created_at.desc()",
    )
    parameters = db.relationship(
        "RecordParameter", backref="record", cascade="all, delete-orphan",
        order_by="RecordParameter.position",
    )
    revisions = db.relationship(
        "RecordRevision", backref="record", cascade="all, delete-orphan",
        order_by="RecordRevision.created_at.desc()",
    )


class RecordRevision(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey("experiment_record.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    reason = db.Column(db.String(500), nullable=False)
    before_json = db.Column(db.Text, nullable=False, default="{}")
    after_json = db.Column(db.Text, nullable=False, default="{}")
    source_ai_message_id = db.Column(db.Integer, db.ForeignKey("ai_message.id"), index=True)


class ExperimentParameter(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey("experiment.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    name = db.Column(db.String(120), nullable=False)
    value = db.Column(db.String(160), default="")
    unit = db.Column(db.String(40), default="")
    notes = db.Column(db.String(255), default="")


class RecordParameter(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey("experiment_record.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    name = db.Column(db.String(120), nullable=False)
    value = db.Column(db.String(160), default="")
    unit = db.Column(db.String(40), default="")
    notes = db.Column(db.String(255), default="")


class ExperimentAttachment(SoftDeleteMixin, TimestampMixin, db.Model):
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
    sha256 = db.Column(db.String(64), nullable=False, default="", index=True)
    tags = db.Column(db.String(255), default="")
    description = db.Column(db.Text, default="")
    version_number = db.Column(db.Integer, nullable=False, default=1)
    storage_mode = db.Column(db.String(20), nullable=False, default="managed", index=True)
    external_path = db.Column(db.String(2000), default="")
    link_status = db.Column(db.String(30), nullable=False, default="available", index=True)
    ai_readability = db.Column(db.String(30), nullable=False, default="metadata_only")
    last_verified_at = db.Column(db.DateTime)

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
    experiment_usages = db.relationship(
        "ExperimentSample", backref="sample", cascade="all, delete-orphan",
        order_by="ExperimentSample.created_at.desc()",
    )
    batch_usages = db.relationship(
        "BatchSample", back_populates="sample", cascade="all, delete-orphan",
        order_by="BatchSample.created_at.desc()",
    )


class ExperimentSample(TimestampMixin, db.Model):
    __table_args__ = (db.UniqueConstraint("experiment_id", "sample_id", name="uq_experiment_sample"),)

    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey("experiment.id"), nullable=False, index=True)
    sample_id = db.Column(db.Integer, db.ForeignKey("sample.id"), nullable=False, index=True)
    role = db.Column(db.String(80), default="实验样本")
    amount_used = db.Column(db.String(80), default="")
    notes = db.Column(db.String(255), default="")


class BatchSample(TimestampMixin, db.Model):
    __table_args__ = (db.UniqueConstraint("batch_id", "sample_id", name="uq_batch_sample"),)

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("experiment_batch.id"), nullable=False, index=True)
    sample_id = db.Column(db.Integer, db.ForeignKey("sample.id"), nullable=False, index=True)
    role = db.Column(db.String(80), default="实验样本")
    amount_used = db.Column(db.String(80), default="")
    notes = db.Column(db.String(255), default="")
    sample = db.relationship("Sample", back_populates="batch_usages")


class PresentationSkill(SoftDeleteMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    instructions = db.Column(db.Text, nullable=False, default="")
    slide_schema_json = db.Column(db.Text, nullable=False, default="[]")
    theme = db.Column(db.String(40), nullable=False, default="research")
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)


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
