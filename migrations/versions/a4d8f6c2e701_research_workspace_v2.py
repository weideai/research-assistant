"""Add project-centered research workspace models.

Revision ID: a4d8f6c2e701
Revises: f1a2b3c4d5e6
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "a4d8f6c2e701"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def _soft_delete_columns(table_name):
    with op.batch_alter_table(table_name) as batch:
        batch.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index(f"ix_{table_name}_is_deleted", ["is_deleted"], unique=False)


def upgrade():
    op.create_table(
        "research_project",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="进行中"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_research_project_user_id", "research_project", ["user_id"])
    op.create_index("ix_research_project_status", "research_project", ["status"])
    op.create_index("ix_research_project_is_deleted", "research_project", ["is_deleted"])

    op.create_table(
        "api_preset",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("api_url", sa.String(length=500), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("text_model", sa.String(length=160), nullable=True),
        sa.Column("vision_model", sa.String(length=160), nullable=True),
        sa.Column("embedding_model", sa.String(length=160), nullable=True),
        sa.Column("image_model", sa.String(length=160), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("sensitive_warning_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_api_preset_user_id", "api_preset", ["user_id"])
    op.create_index("ix_api_preset_is_default", "api_preset", ["is_default"])

    with op.batch_alter_table("task") as batch:
        batch.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_task_project_id", "research_project", ["project_id"], ["id"])
        batch.create_index("ix_task_project_id", ["project_id"], unique=False)
    _soft_delete_columns("task")

    with op.batch_alter_table("experiment") as batch:
        batch.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_experiment_project_id", "research_project", ["project_id"], ["id"])
        batch.create_index("ix_experiment_project_id", ["project_id"], unique=False)
    _soft_delete_columns("experiment")
    _soft_delete_columns("experiment_template")
    _soft_delete_columns("record_template")

    op.create_table(
        "experiment_batch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiment.id"), nullable=False),
        sa.Column("batch_code", sa.String(length=80), nullable=True),
        sa.Column("repeat_kind", sa.String(length=30), nullable=True),
        sa.Column("repeat_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("group_name", sa.String(length=80), nullable=True),
        sa.Column("operator", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="未开始"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("conclusion", sa.Text(), nullable=True),
        sa.Column("requires_repeat", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_experiment_batch_experiment_id", "experiment_batch", ["experiment_id"])
    op.create_index("ix_experiment_batch_status", "experiment_batch", ["status"])
    op.create_index("ix_experiment_batch_is_deleted", "experiment_batch", ["is_deleted"])

    op.create_table(
        "batch_parameter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("experiment_batch.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("value", sa.String(length=160), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_batch_parameter_batch_id", "batch_parameter", ["batch_id"])

    op.create_table(
        "batch_sample",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("experiment_batch.id"), nullable=False),
        sa.Column("sample_id", sa.Integer(), sa.ForeignKey("sample.id"), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column("amount_used", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("batch_id", "sample_id", name="uq_batch_sample"),
    )
    op.create_index("ix_batch_sample_batch_id", "batch_sample", ["batch_id"])
    op.create_index("ix_batch_sample_sample_id", "batch_sample", ["sample_id"])

    with op.batch_alter_table("experiment_record") as batch:
        batch.add_column(sa.Column("batch_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("lifecycle_status", sa.String(length=20), nullable=False, server_default="草稿"))
        batch.add_column(sa.Column("finalized_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("source_ai_message_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_record_batch_id", "experiment_batch", ["batch_id"], ["id"])
        batch.create_foreign_key("fk_record_source_ai_message", "ai_message", ["source_ai_message_id"], ["id"])
        batch.create_index("ix_experiment_record_batch_id", ["batch_id"], unique=False)
        batch.create_index("ix_experiment_record_lifecycle_status", ["lifecycle_status"], unique=False)
        batch.create_index("ix_experiment_record_source_ai_message_id", ["source_ai_message_id"], unique=False)
    _soft_delete_columns("experiment_record")

    op.create_table(
        "record_revision",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("experiment_record.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("after_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("source_ai_message_id", sa.Integer(), sa.ForeignKey("ai_message.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_record_revision_record_id", "record_revision", ["record_id"])
    op.create_index("ix_record_revision_user_id", "record_revision", ["user_id"])
    op.create_index("ix_record_revision_source_ai_message_id", "record_revision", ["source_ai_message_id"])

    with op.batch_alter_table("experiment_attachment") as batch:
        batch.add_column(sa.Column("storage_mode", sa.String(length=20), nullable=False, server_default="managed"))
        batch.add_column(sa.Column("external_path", sa.String(length=2000), nullable=True))
        batch.add_column(sa.Column("link_status", sa.String(length=30), nullable=False, server_default="available"))
        batch.add_column(sa.Column("ai_readability", sa.String(length=30), nullable=False, server_default="metadata_only"))
        batch.add_column(sa.Column("last_verified_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_experiment_attachment_storage_mode", ["storage_mode"], unique=False)
        batch.create_index("ix_experiment_attachment_link_status", ["link_status"], unique=False)
    _soft_delete_columns("experiment_attachment")

    with op.batch_alter_table("ai_knowledge_document") as batch:
        batch.add_column(sa.Column("sha256", sa.String(length=64), nullable=False, server_default=""))
        batch.add_column(sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("parsing_status", sa.String(length=30), nullable=False, server_default="metadata_only"))
        batch.create_index("ix_ai_knowledge_document_sha256", ["sha256"], unique=False)

    op.create_table(
        "ai_knowledge_chunk",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("ai_knowledge_document.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("content_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ai_knowledge_chunk_document_id", "ai_knowledge_chunk", ["document_id"])
    op.create_index("ix_ai_knowledge_chunk_content_sha256", "ai_knowledge_chunk", ["content_sha256"])

    op.create_table(
        "presentation_skill",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("slide_schema_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("theme", sa.String(length=40), nullable=False, server_default="research"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_presentation_skill_user_id", "presentation_skill", ["user_id"])
    op.create_index("ix_presentation_skill_is_deleted", "presentation_skill", ["is_deleted"])

    _backfill_workspace()


def _backfill_workspace():
    connection = op.get_bind()
    metadata = sa.MetaData()
    metadata.reflect(
        bind=connection,
        only=["user", "research_project", "experiment", "experiment_batch", "experiment_record", "experiment_sample", "batch_sample", "ai_knowledge_document"],
    )
    users = metadata.tables["user"]
    projects = metadata.tables["research_project"]
    experiments = metadata.tables["experiment"]
    batches = metadata.tables["experiment_batch"]
    records = metadata.tables["experiment_record"]
    experiment_samples = metadata.tables["experiment_sample"]
    batch_samples = metadata.tables["batch_sample"]
    knowledge_documents = metadata.tables["ai_knowledge_document"]
    now = datetime.utcnow()

    for user_id in connection.execute(sa.select(users.c.id)).scalars():
        project_result = connection.execute(projects.insert().values(
            user_id=user_id,
            title="未分类项目",
            code="",
            objective="升级前创建的实验计划",
            status="进行中",
            notes="由 Research Assistant V2 自动创建",
            is_deleted=False,
            created_at=now,
            updated_at=now,
        ))
        project_id = project_result.inserted_primary_key[0]
        experiment_rows = connection.execute(
            sa.select(experiments).where(experiments.c.user_id == user_id)
        ).mappings().all()
        for experiment in experiment_rows:
            connection.execute(
                experiments.update().where(experiments.c.id == experiment["id"]).values(project_id=project_id)
            )
            batch_result = connection.execute(batches.insert().values(
                experiment_id=experiment["id"],
                batch_code=experiment.get("batch_code") or "BATCH-01",
                repeat_kind=experiment.get("repeat_kind") or "独立实验",
                repeat_number=experiment.get("repeat_number") or 1,
                group_name=experiment.get("group_name") or "",
                operator=experiment.get("owner") or "",
                status=experiment.get("status") or "未开始",
                start_date=experiment.get("start_date"),
                end_date=experiment.get("end_date"),
                summary="",
                conclusion="",
                requires_repeat=False,
                is_deleted=False,
                created_at=experiment.get("created_at") or now,
                updated_at=experiment.get("updated_at") or now,
            ))
            batch_id = batch_result.inserted_primary_key[0]
            connection.execute(
                records.update().where(records.c.experiment_id == experiment["id"]).values(batch_id=batch_id)
            )
            usages = connection.execute(
                sa.select(experiment_samples).where(experiment_samples.c.experiment_id == experiment["id"])
            ).mappings().all()
            for usage in usages:
                connection.execute(batch_samples.insert().values(
                    batch_id=batch_id,
                    sample_id=usage["sample_id"],
                    role=usage.get("role") or "实验样本",
                    amount_used=usage.get("amount_used") or "",
                    notes=usage.get("notes") or "",
                    created_at=usage.get("created_at") or now,
                    updated_at=usage.get("updated_at") or now,
                ))

    connection.execute(
        knowledge_documents.update().where(
            sa.func.length(knowledge_documents.c.text_content) > 0
        ).values(parsing_status="text_extracted")
    )


def downgrade():
    op.drop_table("presentation_skill")
    op.drop_table("ai_knowledge_chunk")
    with op.batch_alter_table("ai_knowledge_document") as batch:
        batch.drop_index("ix_ai_knowledge_document_sha256")
        batch.drop_column("parsing_status")
        batch.drop_column("version_number")
        batch.drop_column("sha256")
    with op.batch_alter_table("experiment_attachment") as batch:
        batch.drop_index("ix_experiment_attachment_is_deleted")
        batch.drop_index("ix_experiment_attachment_link_status")
        batch.drop_index("ix_experiment_attachment_storage_mode")
        batch.drop_column("deleted_at")
        batch.drop_column("is_deleted")
        batch.drop_column("last_verified_at")
        batch.drop_column("ai_readability")
        batch.drop_column("link_status")
        batch.drop_column("external_path")
        batch.drop_column("storage_mode")
    op.drop_table("record_revision")
    with op.batch_alter_table("experiment_record") as batch:
        batch.drop_index("ix_experiment_record_is_deleted")
        batch.drop_index("ix_experiment_record_source_ai_message_id")
        batch.drop_index("ix_experiment_record_lifecycle_status")
        batch.drop_index("ix_experiment_record_batch_id")
        batch.drop_constraint("fk_record_source_ai_message", type_="foreignkey")
        batch.drop_constraint("fk_record_batch_id", type_="foreignkey")
        batch.drop_column("deleted_at")
        batch.drop_column("is_deleted")
        batch.drop_column("source_ai_message_id")
        batch.drop_column("finalized_at")
        batch.drop_column("lifecycle_status")
        batch.drop_column("batch_id")
    op.drop_table("batch_sample")
    op.drop_table("batch_parameter")
    op.drop_table("experiment_batch")
    for table_name in ("record_template", "experiment_template"):
        with op.batch_alter_table(table_name) as batch:
            batch.drop_index(f"ix_{table_name}_is_deleted")
            batch.drop_column("deleted_at")
            batch.drop_column("is_deleted")
    with op.batch_alter_table("experiment") as batch:
        batch.drop_index("ix_experiment_is_deleted")
        batch.drop_index("ix_experiment_project_id")
        batch.drop_constraint("fk_experiment_project_id", type_="foreignkey")
        batch.drop_column("deleted_at")
        batch.drop_column("is_deleted")
        batch.drop_column("project_id")
    with op.batch_alter_table("task") as batch:
        batch.drop_index("ix_task_is_deleted")
        batch.drop_index("ix_task_project_id")
        batch.drop_constraint("fk_task_project_id", type_="foreignkey")
        batch.drop_column("deleted_at")
        batch.drop_column("is_deleted")
        batch.drop_column("project_id")
    op.drop_table("api_preset")
    op.drop_table("research_project")
