"""Add the complete record-centric desktop workspace modules.

Revision ID: l8e0a2c4d6f8
Revises: k7d9f1a3b5c7
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError


revision = "l8e0a2c4d6f8"
down_revision = "k7d9f1a3b5c7"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )


def _link(name, left, left_table, right, right_table, *extra):
    op.create_table(
        name,
        sa.Column(left, sa.Integer(), sa.ForeignKey(f"{left_table}.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(right, sa.Integer(), sa.ForeignKey(f"{right_table}.id", ondelete="CASCADE"), primary_key=True),
        *extra,
    )


def _created_at():
    return sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp())


def upgrade():
    with op.batch_alter_table("weekly_report") as batch:
        batch.add_column(sa.Column("workspace_id", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("body", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("issues_and_feedback", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("next_week_plan", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("source_snapshot_json", sa.Text(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("is_finalized", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("finalized_at", sa.DateTime()))
        batch.add_column(sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("generated_by_ai_message_id", sa.Integer()))
        batch.create_foreign_key("fk_weekly_report_workspace", "workspace", ["workspace_id"], ["id"])
        batch.create_foreign_key("fk_weekly_report_ai_message", "ai_message", ["generated_by_ai_message_id"], ["id"])
        batch.create_index("ix_weekly_report_workspace_id", ["workspace_id"])

    with op.batch_alter_table("task") as batch:
        batch.add_column(sa.Column("workspace_id", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("lab_record_id", sa.Integer()))
        batch.add_column(sa.Column("completed_at", sa.DateTime()))
        batch.add_column(sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"))
        batch.create_foreign_key("fk_task_workspace", "workspace", ["workspace_id"], ["id"])
        batch.create_foreign_key("fk_task_lab_record", "lab_record", ["lab_record_id"], ["id"])
        batch.create_index("ix_task_workspace_id", ["workspace_id"])
        batch.create_index("ix_task_lab_record_id", ["lab_record_id"])

    op.create_table(
        "zotero_connection",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False, server_default="http://127.0.0.1:23119"),
        sa.Column("library_key", sa.String(120), nullable=False, server_default=""),
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("last_sync_at", sa.DateTime()),
        sa.Column("last_success_at", sa.DateTime()),
        sa.Column("connection_state", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("last_error_code", sa.String(80), nullable=False, server_default=""),
        sa.Column("last_error_message", sa.Text(), nullable=False, server_default=""),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", name="uq_zotero_connection_workspace"),
    )
    op.create_index("ix_zotero_connection_workspace_id", "zotero_connection", ["workspace_id"])

    op.create_table(
        "literature_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("zotero_version", sa.Integer()),
        sa.Column("zotero_modified_at", sa.DateTime()),
        sa.Column("synced_at", sa.DateTime()),
        sa.Column("source_missing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("authors_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("year", sa.Integer()),
        sa.Column("journal", sa.String(255), nullable=False, server_default=""),
        sa.Column("volume", sa.String(40), nullable=False, server_default=""),
        sa.Column("issue", sa.String(40), nullable=False, server_default=""),
        sa.Column("pages", sa.String(80), nullable=False, server_default=""),
        sa.Column("doi", sa.String(255), nullable=False, server_default=""),
        sa.Column("doi_normalized", sa.String(255), nullable=False, server_default=""),
        sa.Column("url", sa.String(1000), nullable=False, server_default=""),
        sa.Column("abstract", sa.Text(), nullable=False, server_default=""),
        sa.Column("keywords_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("read_status", sa.String(20), nullable=False, server_default="unread"),
        sa.Column("reading_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_snapshot_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime()),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "source_key", name="uq_literature_workspace_source_key"),
    )
    for column in ("workspace_id", "source", "year", "doi_normalized", "read_status", "is_deleted"):
        op.create_index(f"ix_literature_item_{column}", "literature_item", [column])

    op.create_table(
        "library_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("kind", sa.String(30), nullable=False, server_default="other"),
        sa.Column("storage_mode", sa.String(20), nullable=False, server_default="managed"),
        sa.Column("managed_relative_path", sa.String(1000)),
        sa.Column("external_path", sa.String(2000)),
        sa.Column("path_normalized", sa.String(2000), nullable=False, server_default=""),
        sa.Column("mime_type", sa.String(160), nullable=False, server_default="application/octet-stream"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(64), nullable=False, server_default=""),
        sa.Column("link_status", sa.String(20), nullable=False, server_default="unchecked"),
        sa.Column("ai_readability", sa.String(20), nullable=False, server_default="metadata_only"),
        sa.Column("last_verified_at", sa.DateTime()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime()),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "managed_relative_path", name="uq_library_managed_path"),
    )
    for column in ("workspace_id", "kind", "storage_mode", "path_normalized", "sha256", "link_status", "is_deleted"):
        op.create_index(f"ix_library_item_{column}", "library_item", [column])

    op.create_table(
        "file_operation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("library_item_id", sa.Integer(), sa.ForeignKey("library_item.id")),
        sa.Column("operation_type", sa.String(30), nullable=False),
        sa.Column("source_path", sa.String(2000), nullable=False, server_default=""),
        sa.Column("target_path", sa.String(2000), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="prepared"),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        *_timestamps(),
    )
    op.create_index("ix_file_operation_library_item_id", "file_operation", ["library_item_id"])
    op.create_index("ix_file_operation_status", "file_operation", ["status"])

    op.create_table(
        "note",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_project.id")),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False, server_default="general"),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime()),
        *_timestamps(),
    )
    for column in ("workspace_id", "project_id", "kind", "is_deleted"):
        op.create_index(f"ix_note_{column}", "note", [column])

    op.create_table(
        "tag",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("color_token", sa.String(40), nullable=False, server_default="accent"),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "normalized_name", name="uq_tag_workspace_normalized"),
    )
    op.create_index("ix_tag_workspace_id", "tag", ["workspace_id"])

    op.create_table(
        "calendar_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_project.id")),
        sa.Column("lab_record_id", sa.Integer(), sa.ForeignKey("lab_record.id")),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False, server_default="meeting"),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime()),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime()),
        *_timestamps(),
    )
    for column in ("workspace_id", "project_id", "lab_record_id", "event_type", "starts_at", "is_deleted"):
        op.create_index(f"ix_calendar_event_{column}", "calendar_event", [column])

    op.create_table(
        "weekly_report_entry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("weekly_report.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_title", sa.String(500), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_date", sa.Date()),
        sa.Column("include_state", sa.String(20), nullable=False, server_default="included"),
        *_timestamps(),
    )
    op.create_index("ix_weekly_report_entry_report_id", "weekly_report_entry", ["report_id"])

    op.create_table(
        "ai_change_set",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("ai_message.id"), nullable=False),
        sa.Column("target_type", sa.String(30), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("base_row_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="proposed"),
        sa.Column("proposal_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("before_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("after_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("accepted_fields_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("rejected_fields_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("source_snapshot_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("model_name", sa.String(160), nullable=False, server_default=""),
        sa.Column("prompt_snapshot", sa.Text(), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("applied_at", sa.DateTime()),
        sa.Column("reverted_at", sa.DateTime()),
        *_timestamps(),
    )
    for column in ("message_id", "target_type", "target_id", "status"):
        op.create_index(f"ix_ai_change_set_{column}", "ai_change_set", [column])
    with op.batch_alter_table("lab_record_revision") as batch:
        batch.create_foreign_key(
            "fk_lab_record_revision_ai_change_set", "ai_change_set", ["source_ai_change_set_id"], ["id"]
        )

    op.create_table(
        "search_document",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("keywords", sa.Text(), nullable=False, server_default=""),
        sa.Column("view_key", sa.String(80), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "entity_type", "entity_id", name="uq_search_document_entity"),
    )
    op.create_index("ix_search_document_workspace_id", "search_document", ["workspace_id"])
    op.create_index("ix_search_document_entity_type", "search_document", ["entity_type"])
    try:
        op.execute(
            "CREATE VIRTUAL TABLE search_fts USING fts5(title, body, keywords, "
            "content='search_document', content_rowid='id', tokenize='trigram')"
        )
        op.execute(
            "CREATE TRIGGER search_document_ai AFTER INSERT ON search_document BEGIN "
            "INSERT INTO search_fts(rowid,title,body,keywords) VALUES(new.id,new.title,new.body,new.keywords); END"
        )
        op.execute(
            "CREATE TRIGGER search_document_ad AFTER DELETE ON search_document BEGIN "
            "INSERT INTO search_fts(search_fts,rowid,title,body,keywords) "
            "VALUES('delete',old.id,old.title,old.body,old.keywords); END"
        )
        op.execute(
            "CREATE TRIGGER search_document_au AFTER UPDATE ON search_document BEGIN "
            "INSERT INTO search_fts(search_fts,rowid,title,body,keywords) "
            "VALUES('delete',old.id,old.title,old.body,old.keywords); "
            "INSERT INTO search_fts(rowid,title,body,keywords) VALUES(new.id,new.title,new.body,new.keywords); END"
        )
    except OperationalError:
        # SearchService exposes the missing tokenizer and uses explicit LIKE fallback.
        pass

    op.create_table(
        "activity_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_project.id")),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("lab_record.id")),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("source_table", sa.String(80), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
    )
    for column in ("workspace_id", "project_id", "record_id", "event_type", "occurred_at"):
        op.create_index(f"ix_activity_event_{column}", "activity_event", [column])

    _link("project_literature", "project_id", "research_project", "literature_id", "literature_item",
          sa.Column("purpose", sa.String(120), nullable=False, server_default="reference"), _created_at())
    _link("lab_record_literature", "record_id", "lab_record", "literature_id", "literature_item",
          sa.Column("citation_role", sa.String(80), nullable=False, server_default="reference"),
          sa.Column("locator", sa.String(255), nullable=False, server_default=""),
          sa.Column("notes", sa.Text(), nullable=False, server_default=""), _created_at())
    _link("project_library_item", "project_id", "research_project", "library_item_id", "library_item",
          sa.Column("relation_role", sa.String(80), nullable=False, server_default="evidence"), _created_at())
    _link("lab_record_library_item", "record_id", "lab_record", "library_item_id", "library_item",
          sa.Column("section_key", sa.String(80), nullable=False, server_default="files"),
          sa.Column("relation_role", sa.String(80), nullable=False, server_default="evidence"), _created_at())
    _link("literature_library_item", "literature_id", "literature_item", "library_item_id", "library_item",
          sa.Column("attachment_role", sa.String(80), nullable=False, server_default="full_text"), _created_at())
    _link("weekly_report_library_item", "report_id", "weekly_report", "library_item_id", "library_item",
          sa.Column("relation_role", sa.String(80), nullable=False, server_default="archive"), _created_at())
    _link("note_lab_record", "note_id", "note", "record_id", "lab_record", _created_at())
    _link("note_literature", "note_id", "note", "literature_id", "literature_item", _created_at())
    _link("project_tag", "project_id", "research_project", "tag_id", "tag")
    _link("lab_record_tag", "record_id", "lab_record", "tag_id", "tag")
    _link("literature_tag", "literature_id", "literature_item", "tag_id", "tag")
    _link("library_item_tag", "library_item_id", "library_item", "tag_id", "tag")
    _link("note_tag", "note_id", "note", "tag_id", "tag")


def downgrade():
    for table in (
        "note_tag", "library_item_tag", "literature_tag", "lab_record_tag", "project_tag",
        "note_literature", "note_lab_record", "weekly_report_library_item",
        "literature_library_item", "lab_record_library_item", "project_library_item",
        "lab_record_literature", "project_literature",
    ):
        op.drop_table(table)
    op.drop_table("activity_event")
    op.execute("DROP TRIGGER IF EXISTS search_document_au")
    op.execute("DROP TRIGGER IF EXISTS search_document_ad")
    op.execute("DROP TRIGGER IF EXISTS search_document_ai")
    op.execute("DROP TABLE IF EXISTS search_fts")
    op.drop_table("search_document")
    with op.batch_alter_table("lab_record_revision") as batch:
        batch.drop_constraint("fk_lab_record_revision_ai_change_set", type_="foreignkey")
    for table in (
        "ai_change_set", "weekly_report_entry", "calendar_event", "tag", "note",
        "file_operation", "library_item", "literature_item", "zotero_connection",
    ):
        op.drop_table(table)
    with op.batch_alter_table("task") as batch:
        batch.drop_index("ix_task_lab_record_id")
        batch.drop_index("ix_task_workspace_id")
        batch.drop_constraint("fk_task_lab_record", type_="foreignkey")
        batch.drop_constraint("fk_task_workspace", type_="foreignkey")
        for column in ("row_version", "position", "completed_at", "lab_record_id", "workspace_id"):
            batch.drop_column(column)
    with op.batch_alter_table("weekly_report") as batch:
        batch.drop_index("ix_weekly_report_workspace_id")
        batch.drop_constraint("fk_weekly_report_ai_message", type_="foreignkey")
        batch.drop_constraint("fk_weekly_report_workspace", type_="foreignkey")
        for column in (
            "generated_by_ai_message_id", "row_version", "finalized_at", "is_finalized",
            "source_snapshot_json", "next_week_plan", "issues_and_feedback", "body", "workspace_id",
        ):
            batch.drop_column(column)
