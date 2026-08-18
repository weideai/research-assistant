import json
import uuid
from datetime import date, datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


project_executor = db.Table(
    "project_executor",
    db.Column(
        "project_id", db.Integer,
        db.ForeignKey("research_project.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "executor_id", db.Integer,
        db.ForeignKey("executor.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


def _link_table(name, left_name, left_table, right_name, right_table, *extra_columns):
    """Build a real-FK association table with a stable composite key."""
    return db.Table(
        name,
        db.Column(
            left_name, db.Integer, db.ForeignKey(f"{left_table}.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        db.Column(
            right_name, db.Integer, db.ForeignKey(f"{right_table}.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        *extra_columns,
    )


project_literature = _link_table(
    "project_literature", "project_id", "research_project", "literature_id", "literature_item",
    db.Column("purpose", db.String(120), nullable=False, default="reference"),
    db.Column("created_at", db.DateTime, nullable=False, default=utcnow),
)
lab_record_literature = _link_table(
    "lab_record_literature", "record_id", "lab_record", "literature_id", "literature_item",
    db.Column("citation_role", db.String(80), nullable=False, default="reference"),
    db.Column("locator", db.String(255), nullable=False, default=""),
    db.Column("notes", db.Text, nullable=False, default=""),
    db.Column("created_at", db.DateTime, nullable=False, default=utcnow),
)
project_library_item = _link_table(
    "project_library_item", "project_id", "research_project", "library_item_id", "library_item",
    db.Column("relation_role", db.String(80), nullable=False, default="evidence"),
    db.Column("created_at", db.DateTime, nullable=False, default=utcnow),
)
lab_record_library_item = _link_table(
    "lab_record_library_item", "record_id", "lab_record", "library_item_id", "library_item",
    db.Column("section_key", db.String(80), nullable=False, default="files"),
    db.Column("relation_role", db.String(80), nullable=False, default="evidence"),
    db.Column("created_at", db.DateTime, nullable=False, default=utcnow),
)
literature_library_item = _link_table(
    "literature_library_item", "literature_id", "literature_item", "library_item_id", "library_item",
    db.Column("attachment_role", db.String(80), nullable=False, default="full_text"),
    db.Column("created_at", db.DateTime, nullable=False, default=utcnow),
)
zotero_collection_literature = _link_table(
    "zotero_collection_literature", "collection_id", "zotero_collection",
    "literature_id", "literature_item",
)
project_zotero_collection = _link_table(
    "project_zotero_collection", "project_id", "research_project",
    "collection_id", "zotero_collection",
)
weekly_report_library_item = _link_table(
    "weekly_report_library_item", "report_id", "weekly_report", "library_item_id", "library_item",
    db.Column("relation_role", db.String(80), nullable=False, default="archive"),
    db.Column("created_at", db.DateTime, nullable=False, default=utcnow),
)
note_lab_record = _link_table(
    "note_lab_record", "note_id", "note", "record_id", "lab_record",
    db.Column("created_at", db.DateTime, nullable=False, default=utcnow),
)
note_literature = _link_table(
    "note_literature", "note_id", "note", "literature_id", "literature_item",
    db.Column("created_at", db.DateTime, nullable=False, default=utcnow),
)
project_tag = _link_table("project_tag", "project_id", "research_project", "tag_id", "tag")
lab_record_tag = _link_table("lab_record_tag", "record_id", "lab_record", "tag_id", "tag")
literature_tag = _link_table("literature_tag", "literature_id", "literature_item", "tag_id", "tag")
library_item_tag = _link_table("library_item_tag", "library_item_id", "library_item", "tag_id", "tag")
note_tag = _link_table("note_tag", "note_id", "note", "tag_id", "tag")


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


class WorkspaceSetting(TimestampMixin, db.Model):
    """Per-user workflow preferences that are safe to keep outside research records."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True, index=True)
    execution_save_mode = db.Column(db.String(20), nullable=False, default="stay")
    execution_autosave = db.Column(db.Boolean, nullable=False, default=False)
    execution_autosave_interval = db.Column(db.Integer, nullable=False, default=30)
    executor_options_json = db.Column(db.Text, nullable=False, default="[]")


class Executor(TimestampMixin, db.Model):
    """A user-owned execution participant that can be assigned to projects."""

    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_executor_user_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, default=1, index=True)
    name = db.Column(db.String(120), nullable=False)
    normalized_name = db.Column(db.String(160), nullable=False, default="")
    role = db.Column(db.String(120), nullable=False, default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    projects = db.relationship(
        "ResearchProject", secondary=project_executor, back_populates="executors",
    )


class AIConversation(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False, default="新对话")
    page_type = db.Column(db.String(30), default="")
    page_id = db.Column(db.Integer)
    selected_experiment_ids_json = db.Column(db.Text, nullable=False, default="[]")
    selected_batch_ids_json = db.Column(db.Text, nullable=False, default="[]")
    selected_record_ids_json = db.Column(db.Text, nullable=False, default="[]")
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
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, default=1, index=True)
    title = db.Column(db.String(180), nullable=False)
    code = db.Column(db.String(80), default="")
    objective = db.Column(db.Text, default="")
    status = db.Column(db.String(30), nullable=False, default="进行中", index=True)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    notes = db.Column(db.Text, default="")
    row_version = db.Column(db.Integer, nullable=False, default=1)
    experiments = db.relationship(
        "Experiment", backref="project", order_by="Experiment.updated_at.desc()"
    )
    tasks = db.relationship("Task", backref="project", order_by="Task.deadline")
    executors = db.relationship(
        "Executor", secondary=project_executor, back_populates="projects",
        order_by="Executor.name",
    )
    lab_records = db.relationship(
        "LabRecord", back_populates="project", order_by="LabRecord.updated_at.desc()"
    )


class Workspace(TimestampMixin, db.Model):
    __table_args__ = (
        db.CheckConstraint("id = 1", name="ck_workspace_singleton"),
    )

    id = db.Column(db.Integer, primary_key=True, default=1)
    workspace_uuid = db.Column(db.String(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
    legacy_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)
    name = db.Column(db.String(120), nullable=False, default="R/LAB 工作区")
    timezone = db.Column(db.String(64), nullable=False, default="Asia/Shanghai")
    schema_generation = db.Column(db.String(40), nullable=False, default="record-centric-v1")
    migration_state = db.Column(db.String(30), nullable=False, default="active")


class LabRecord(SoftDeleteMixin, TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "record_code", name="uq_lab_record_workspace_code"),
        db.CheckConstraint(
            "status IN ('draft', 'in_progress', 'awaiting_analysis', 'completed', 'archived')",
            name="ck_lab_record_status",
        ),
        db.CheckConstraint(
            "source_kind IN ('new', 'migration', 'import')", name="ck_lab_record_source_kind"
        ),
        db.CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="ck_lab_record_time_range",
        ),
        db.CheckConstraint(
            "is_finalized = 0 OR finalized_at IS NOT NULL", name="ck_lab_record_finalized_at"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), nullable=False, index=True)
    record_code = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(24), nullable=False, default="draft", index=True)
    experiment_date = db.Column(db.Date, index=True)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    executor_id = db.Column(db.Integer, db.ForeignKey("executor.id"), index=True)
    executor_snapshot = db.Column(db.String(120), nullable=False, default="")
    location = db.Column(db.String(180), nullable=False, default="")
    objective = db.Column(db.Text, nullable=False, default="")
    background = db.Column(db.Text, nullable=False, default="")
    hypothesis = db.Column(db.Text, nullable=False, default="")
    design = db.Column(db.Text, nullable=False, default="")
    materials_conditions = db.Column(db.Text, nullable=False, default="")
    expected_result = db.Column(db.Text, nullable=False, default="")
    actual_process_summary = db.Column(db.Text, nullable=False, default="")
    actual_result = db.Column(db.Text, nullable=False, default="")
    analysis = db.Column(db.Text, nullable=False, default="")
    conclusion = db.Column(db.Text, nullable=False, default="")
    next_steps = db.Column(db.Text, nullable=False, default="")
    is_finalized = db.Column(db.Boolean, nullable=False, default=False)
    finalized_at = db.Column(db.DateTime)
    source_kind = db.Column(db.String(20), nullable=False, default="new")
    row_version = db.Column(db.Integer, nullable=False, default=1)
    project = db.relationship("ResearchProject", back_populates="lab_records")
    executor = db.relationship("Executor")
    steps = db.relationship(
        "LabRecordStep", back_populates="record", cascade="all, delete-orphan",
        order_by="LabRecordStep.position",
    )
    events = db.relationship(
        "LabRecordEvent", back_populates="record", cascade="all, delete-orphan",
        order_by="LabRecordEvent.occurred_at, LabRecordEvent.id",
    )
    parameters = db.relationship(
        "LabRecordParameter", back_populates="record", cascade="all, delete-orphan",
        order_by="LabRecordParameter.phase, LabRecordParameter.position",
    )
    materials = db.relationship(
        "LabRecordMaterial", back_populates="record", cascade="all, delete-orphan",
        order_by="LabRecordMaterial.position",
    )
    revisions = db.relationship(
        "LabRecordRevision", back_populates="record", cascade="all, delete-orphan",
        order_by="LabRecordRevision.created_at.desc()",
    )


class LabRecordStep(TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint("record_id", "position", name="uq_lab_record_step_position"),
        db.CheckConstraint("position > 0", name="ck_lab_record_step_position"),
        db.CheckConstraint("planned_duration_minutes IS NULL OR planned_duration_minutes >= 0", name="ck_lab_record_step_duration"),
    )

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey("lab_record.id", ondelete="CASCADE"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(180), nullable=False, default="")
    instruction = db.Column(db.Text, nullable=False, default="")
    planned_duration_minutes = db.Column(db.Integer)
    checkpoint = db.Column(db.Text, nullable=False, default="")
    risk = db.Column(db.Text, nullable=False, default="")
    planned_executor_id = db.Column(db.Integer, db.ForeignKey("executor.id"))
    executor_snapshot = db.Column(db.String(120), nullable=False, default="")
    planned_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    is_done = db.Column(db.Boolean, nullable=False, default=False)
    actual_deviation = db.Column(db.Text, nullable=False, default="")
    source_kind = db.Column(db.String(20), nullable=False, default="user")
    source_ai_message_id = db.Column(db.Integer, db.ForeignKey("ai_message.id"))
    record = db.relationship("LabRecord", back_populates="steps")


class LabRecordEvent(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey("lab_record.id", ondelete="CASCADE"), nullable=False, index=True)
    occurred_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    event_type = db.Column(db.String(20), nullable=False, default="note")
    content = db.Column(db.Text, nullable=False)
    executor_id = db.Column(db.Integer, db.ForeignKey("executor.id"))
    executor_snapshot = db.Column(db.String(120), nullable=False, default="")
    source_kind = db.Column(db.String(20), nullable=False, default="user")
    source_legacy_record_id = db.Column(db.Integer, unique=True)
    record = db.relationship("LabRecord", back_populates="events")


class LabRecordParameter(TimestampMixin, db.Model):
    __table_args__ = (
        db.CheckConstraint(
            "phase <> 'actual' OR value_origin <> 'ai_organized' OR confirmed_at IS NOT NULL",
            name="ck_lab_record_parameter_ai_actual_confirmed",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey("lab_record.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = db.Column(db.Integer, db.ForeignKey("lab_record_event.id", ondelete="SET NULL"))
    position = db.Column(db.Integer, nullable=False, default=1)
    phase = db.Column(db.String(20), nullable=False, default="planned")
    name = db.Column(db.String(120), nullable=False)
    value_text = db.Column(db.String(240), nullable=False, default="")
    unit = db.Column(db.String(40), nullable=False, default="")
    notes = db.Column(db.Text, nullable=False, default="")
    value_origin = db.Column(db.String(20), nullable=False, default="user")
    confirmed_at = db.Column(db.DateTime)
    source_ai_message_id = db.Column(db.Integer, db.ForeignKey("ai_message.id"))
    record = db.relationship("LabRecord", back_populates="parameters")


class LabRecordMaterial(TimestampMixin, db.Model):
    __table_args__ = (
        db.CheckConstraint(
            "value_origin <> 'ai_organized' OR actual_amount = '' OR confirmed_at IS NOT NULL",
            name="ck_lab_record_material_ai_actual_confirmed",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey("lab_record.id", ondelete="CASCADE"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    kind = db.Column(db.String(30), nullable=False, default="material")
    name = db.Column(db.String(180), nullable=False)
    identifier = db.Column(db.String(120), nullable=False, default="")
    role = db.Column(db.String(120), nullable=False, default="")
    planned_amount = db.Column(db.String(120), nullable=False, default="")
    actual_amount = db.Column(db.String(120), nullable=False, default="")
    unit = db.Column(db.String(40), nullable=False, default="")
    legacy_sample_id = db.Column(db.Integer, db.ForeignKey("sample.id"))
    value_origin = db.Column(db.String(20), nullable=False, default="user")
    confirmed_at = db.Column(db.DateTime)
    record = db.relationship("LabRecord", back_populates="materials")


class LabRecordRevision(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey("lab_record.id", ondelete="CASCADE"), nullable=False, index=True)
    scope = db.Column(db.String(30), nullable=False, default="record")
    reason = db.Column(db.String(500), nullable=False)
    before_json = db.Column(db.Text, nullable=False, default="{}")
    after_json = db.Column(db.Text, nullable=False, default="{}")
    diff_json = db.Column(db.Text, nullable=False, default="{}")
    actor_kind = db.Column(db.String(30), nullable=False, default="local_user")
    executor_id = db.Column(db.Integer, db.ForeignKey("executor.id"))
    source_ai_change_set_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    record = db.relationship("LabRecord", back_populates="revisions")


class WeeklyReport(SoftDeleteMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, default=1, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), index=True)
    title = db.Column(db.String(180), nullable=False)
    original_name = db.Column(db.String(255), nullable=False, default="")
    report_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    period_start = db.Column(db.Date, index=True)
    period_end = db.Column(db.Date, index=True)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    summary = db.Column(db.Text, nullable=False, default="")
    body = db.Column(db.Text, nullable=False, default="")
    issues_and_feedback = db.Column(db.Text, nullable=False, default="")
    next_week_plan = db.Column(db.Text, nullable=False, default="")
    source_snapshot_json = db.Column(db.Text, nullable=False, default="{}")
    is_finalized = db.Column(db.Boolean, nullable=False, default=False)
    finalized_at = db.Column(db.DateTime)
    row_version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": row_version}
    generated_by_ai_message_id = db.Column(db.Integer, db.ForeignKey("ai_message.id"))
    stored_path = db.Column(db.String(1000), nullable=False, default="")
    folder_path = db.Column(db.String(1000), nullable=False, default="")
    mime_type = db.Column(db.String(160), nullable=False, default="application/octet-stream")
    size_bytes = db.Column(db.BigInteger, nullable=False, default=0)
    sha256 = db.Column(db.String(64), nullable=False, default="", index=True)
    project = db.relationship("ResearchProject", backref="weekly_reports")
    updates = db.relationship(
        "WeeklyReportUpdate", backref="report", cascade="all, delete-orphan",
        order_by="WeeklyReportUpdate.entry_date.desc(), WeeklyReportUpdate.created_at.desc()",
    )

    @property
    def size_label(self):
        if self.size_bytes >= 1024 * 1024:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"
        if self.size_bytes >= 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        return f"{self.size_bytes} B"


class WeeklyReportUpdate(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("weekly_report.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    entry_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    kind = db.Column(db.String(20), nullable=False, default="修改日常")
    status = db.Column(db.String(20), nullable=False, default="待处理")
    content = db.Column(db.Text, nullable=False, default="")


class Task(SoftDeleteMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, default=1, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), index=True)
    lab_record_id = db.Column(db.Integer, db.ForeignKey("lab_record.id"), index=True)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(40), nullable=False, default="research")
    priority = db.Column(db.String(10), nullable=False, default="medium")
    deadline = db.Column(db.Date, index=True)
    status = db.Column(db.String(20), nullable=False, default="todo", index=True)
    notes = db.Column(db.Text, default="")
    completed_at = db.Column(db.DateTime)
    position = db.Column(db.Integer, nullable=False, default=0)
    row_version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": row_version}


class ZoteroConnection(TimestampMixin, db.Model):
    __table_args__ = (db.UniqueConstraint("workspace_id", name="uq_zotero_connection_workspace"),)

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    base_url = db.Column(db.String(500), nullable=False, default="http://127.0.0.1:23119")
    library_key = db.Column(db.String(120), nullable=False, default="")
    sync_interval_minutes = db.Column(db.Integer, nullable=False, default=30)
    server_id = db.Column(db.String(120), nullable=False, default="")
    library_version = db.Column(db.Integer, nullable=False, default=0)
    last_full_sync_at = db.Column(db.DateTime)
    last_incremental_sync_at = db.Column(db.DateTime)
    sync_state = db.Column(db.String(24), nullable=False, default="idle")
    sync_progress = db.Column(db.Integer, nullable=False, default=0)
    sync_stage = db.Column(db.String(120), nullable=False, default="")
    last_sync_at = db.Column(db.DateTime)
    last_success_at = db.Column(db.DateTime)
    connection_state = db.Column(db.String(24), nullable=False, default="unknown")
    last_error_code = db.Column(db.String(80), nullable=False, default="")
    last_error_message = db.Column(db.Text, nullable=False, default="")


class ZoteroCollection(TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "library_key", "collection_key", name="uq_zotero_collection_identity"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    library_key = db.Column(db.String(120), nullable=False, default="personal", index=True)
    collection_key = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(500), nullable=False)
    parent_key = db.Column(db.String(120), nullable=False, default="")
    version = db.Column(db.Integer, nullable=False, default=0)
    source_missing = db.Column(db.Boolean, nullable=False, default=False)


class LiteratureItem(SoftDeleteMixin, TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "source_key", name="uq_literature_workspace_source_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    source = db.Column(db.String(20), nullable=False, default="manual", index=True)
    source_key = db.Column(db.String(255), nullable=False)
    zotero_version = db.Column(db.Integer)
    zotero_modified_at = db.Column(db.DateTime)
    synced_at = db.Column(db.DateTime)
    source_missing = db.Column(db.Boolean, nullable=False, default=False)
    title = db.Column(db.String(500), nullable=False)
    authors_json = db.Column(db.Text, nullable=False, default="[]")
    year = db.Column(db.Integer, index=True)
    journal = db.Column(db.String(255), nullable=False, default="")
    volume = db.Column(db.String(40), nullable=False, default="")
    issue = db.Column(db.String(40), nullable=False, default="")
    pages = db.Column(db.String(80), nullable=False, default="")
    doi = db.Column(db.String(255), nullable=False, default="")
    doi_normalized = db.Column(db.String(255), nullable=False, default="", index=True)
    url = db.Column(db.String(1000), nullable=False, default="")
    abstract = db.Column(db.Text, nullable=False, default="")
    keywords_json = db.Column(db.Text, nullable=False, default="[]")
    read_status = db.Column(db.String(20), nullable=False, default="unread", index=True)
    reading_notes = db.Column(db.Text, nullable=False, default="")
    source_snapshot_json = db.Column(db.Text, nullable=False, default="{}")
    row_version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": row_version}


class LibraryItem(SoftDeleteMixin, TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "managed_relative_path", name="uq_library_managed_path"),
        db.UniqueConstraint("workspace_id", "source_key", name="uq_library_workspace_source_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    source_key = db.Column(db.String(255))
    display_name = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False, default="")
    description = db.Column(db.Text, nullable=False, default="")
    kind = db.Column(db.String(30), nullable=False, default="other", index=True)
    storage_mode = db.Column(db.String(20), nullable=False, default="managed", index=True)
    managed_relative_path = db.Column(db.String(1000))
    external_path = db.Column(db.String(2000))
    path_normalized = db.Column(db.String(2000), nullable=False, default="", index=True)
    mime_type = db.Column(db.String(160), nullable=False, default="application/octet-stream")
    size_bytes = db.Column(db.BigInteger, nullable=False, default=0)
    sha256 = db.Column(db.String(64), nullable=False, default="", index=True)
    link_status = db.Column(db.String(20), nullable=False, default="unchecked", index=True)
    ai_readability = db.Column(db.String(20), nullable=False, default="metadata_only")
    last_verified_at = db.Column(db.DateTime)


class FileOperation(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    library_item_id = db.Column(db.Integer, db.ForeignKey("library_item.id"), index=True)
    operation_type = db.Column(db.String(30), nullable=False)
    source_path = db.Column(db.String(2000), nullable=False, default="")
    target_path = db.Column(db.String(2000), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="prepared", index=True)
    error_message = db.Column(db.Text, nullable=False, default="")


class Note(SoftDeleteMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), index=True)
    title = db.Column(db.String(240), nullable=False)
    kind = db.Column(db.String(30), nullable=False, default="general", index=True)
    body = db.Column(db.Text, nullable=False, default="")
    row_version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": row_version}


class Tag(TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "normalized_name", name="uq_tag_workspace_normalized"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    normalized_name = db.Column(db.String(100), nullable=False)
    color_token = db.Column(db.String(40), nullable=False, default="accent")


class CalendarEvent(SoftDeleteMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), index=True)
    lab_record_id = db.Column(db.Integer, db.ForeignKey("lab_record.id"), index=True)
    title = db.Column(db.String(240), nullable=False)
    event_type = db.Column(db.String(30), nullable=False, default="meeting", index=True)
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    ends_at = db.Column(db.DateTime)
    all_day = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text, nullable=False, default="")
    row_version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": row_version}


class WeeklyReportEntry(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("weekly_report.id", ondelete="CASCADE"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    source_type = db.Column(db.String(30), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)
    source_title = db.Column(db.String(500), nullable=False)
    source_excerpt = db.Column(db.Text, nullable=False, default="")
    source_date = db.Column(db.Date)
    include_state = db.Column(db.String(20), nullable=False, default="included")


class AIChangeSet(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("ai_message.id"), nullable=False, index=True)
    target_type = db.Column(db.String(30), nullable=False, index=True)
    target_id = db.Column(db.Integer, nullable=False, index=True)
    base_row_version = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(24), nullable=False, default="proposed", index=True)
    proposal_json = db.Column(db.Text, nullable=False, default="{}")
    before_json = db.Column(db.Text, nullable=False, default="{}")
    after_json = db.Column(db.Text, nullable=False, default="{}")
    accepted_fields_json = db.Column(db.Text, nullable=False, default="[]")
    rejected_fields_json = db.Column(db.Text, nullable=False, default="[]")
    source_snapshot_json = db.Column(db.Text, nullable=False, default="{}")
    model_name = db.Column(db.String(160), nullable=False, default="")
    prompt_snapshot = db.Column(db.Text, nullable=False, default="")
    reviewed_at = db.Column(db.DateTime)
    applied_at = db.Column(db.DateTime)
    reverted_at = db.Column(db.DateTime)


class SearchDocument(TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "entity_type", "entity_id", name="uq_search_document_entity"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    entity_type = db.Column(db.String(30), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(500), nullable=False)
    body = db.Column(db.Text, nullable=False, default="")
    keywords = db.Column(db.Text, nullable=False, default="")
    view_key = db.Column(db.String(80), nullable=False)


class ActivityEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), index=True)
    record_id = db.Column(db.Integer, db.ForeignKey("lab_record.id"), index=True)
    event_type = db.Column(db.String(60), nullable=False, index=True)
    summary = db.Column(db.String(500), nullable=False)
    occurred_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    source_table = db.Column(db.String(80), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)


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
    experiment = db.relationship("Experiment", backref="attachments")
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


def workspace_setting_for_user(user_id):
    setting = WorkspaceSetting.query.filter_by(user_id=user_id).first()
    if setting:
        return setting
    setting = WorkspaceSetting(user_id=user_id)
    db.session.add(setting)
    db.session.flush()
    return setting


def _configured_executor_names(setting):
    if not setting or not setting.executor_options_json:
        return []
    try:
        configured = json.loads(setting.executor_options_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(configured, list):
        return []
    values = []
    for raw_value in configured:
        value = str(raw_value).strip()[:120]
        if value and value not in values:
            values.append(value)
    return values


def sync_legacy_executor_options(user_id, setting=None):
    """Import the old per-line executor setting into the managed list once."""

    setting = setting or WorkspaceSetting.query.filter_by(user_id=user_id).first()
    names = _configured_executor_names(setting)
    for name in names:
        existing = Executor.query.filter_by(user_id=user_id, name=name).first()
        if existing is None:
            db.session.add(Executor(user_id=user_id, name=name))
    return names


def executors_for_user(user_id, include_inactive=False):
    query = Executor.query.filter_by(user_id=user_id)
    if not include_inactive:
        query = query.filter(Executor.is_active.is_(True))
    return query.order_by(Executor.name, Executor.id).all()


def project_executor_ids_for_user(user_id, project_id):
    if not project_id:
        return set()
    rows = db.session.query(project_executor.c.executor_id).join(
        ResearchProject, ResearchProject.id == project_executor.c.project_id,
    ).join(
        Executor, Executor.id == project_executor.c.executor_id,
    ).filter(
        ResearchProject.id == project_id,
        ResearchProject.user_id == user_id,
        ResearchProject.is_deleted.is_(False),
        Executor.user_id == user_id,
    ).all()
    return {executor_id for (executor_id,) in rows}


def executor_options_for_user(user_id, setting=None):
    """Return saved suggestions without exposing another user's operator names."""

    values = set()
    scoped_queries = (
        db.session.query(Experiment.owner)
        .filter(Experiment.user_id == user_id, Experiment.owner.isnot(None), Experiment.owner != ""),
        db.session.query(ExperimentStep.operator)
        .join(Experiment, Experiment.id == ExperimentStep.experiment_id)
        .filter(Experiment.user_id == user_id, ExperimentStep.operator.isnot(None), ExperimentStep.operator != ""),
        db.session.query(ExperimentBatch.operator)
        .join(Experiment, Experiment.id == ExperimentBatch.experiment_id)
        .filter(Experiment.user_id == user_id, ExperimentBatch.operator.isnot(None), ExperimentBatch.operator != ""),
        db.session.query(BatchStep.operator)
        .join(ExperimentBatch, ExperimentBatch.id == BatchStep.batch_id)
        .join(Experiment, Experiment.id == ExperimentBatch.experiment_id)
        .filter(Experiment.user_id == user_id, BatchStep.operator.isnot(None), BatchStep.operator != ""),
        db.session.query(ExperimentRecord.operator)
        .join(Experiment, Experiment.id == ExperimentRecord.experiment_id)
        .filter(Experiment.user_id == user_id, ExperimentRecord.operator.isnot(None), ExperimentRecord.operator != ""),
    )
    for query in scoped_queries:
        values.update(value.strip() for (value,) in query.all() if value and value.strip())
    values.update(
        value.strip() for (value,) in db.session.query(Executor.name).filter(
            Executor.user_id == user_id,
            Executor.is_active.is_(True),
        ).all() if value and value.strip()
    )
    setting = setting or WorkspaceSetting.query.filter_by(user_id=user_id).first()
    if setting and setting.executor_options_json:
        try:
            configured = json.loads(setting.executor_options_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            configured = []
        if isinstance(configured, list):
            values.update(str(value).strip()[:80] for value in configured if str(value).strip())
    return sorted(values, key=lambda value: value.casefold())


def executor_options_for_project(user_id, project_id=None, setting=None):
    """Put active project participants first, then retain global/history fallback."""

    project_values = []
    if project_id:
        project_query = Executor.query.join(
            project_executor, project_executor.c.executor_id == Executor.id,
        ).join(
            ResearchProject, ResearchProject.id == project_executor.c.project_id,
        ).filter(
            ResearchProject.id == project_id,
            ResearchProject.user_id == user_id,
            ResearchProject.is_deleted.is_(False),
            Executor.user_id == user_id,
            Executor.is_active.is_(True),
        ).order_by(Executor.name, Executor.id)
        project_values = [executor.name for executor in project_query.all()]
    values = []
    for value in (*project_values, *executor_options_for_user(user_id, setting)):
        if value and value not in values:
            values.append(value)
    return values
