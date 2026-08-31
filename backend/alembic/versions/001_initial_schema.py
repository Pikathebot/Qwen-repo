"""Initial database schema merge and extension.

Revision ID: 001
Revises: None
Create Date: 2026-08-31 11:45:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # 1. Ensure core existing tables exist (for fresh databases)
    if "sessions" not in existing_tables:
        op.create_table(
            "sessions",
            sa.Column("session_id", sa.String(), primary_key=True),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("chat_mode", sa.String(), nullable=True, server_default="WORKSPACE"),
            sa.Column("created_at", sa.Float(), nullable=True),
            sa.Column("updated_at", sa.Float(), nullable=True),
        )

    if "messages" not in existing_tables:
        op.create_table(
            "messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("tool_calls_json", sa.Text(), nullable=True),
            sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_summary", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.Float(), nullable=True),
        )
        op.create_index("idx_messages_session", "messages", ["session_id", "id"])

    if "compaction_events" not in existing_tables:
        op.create_table(
            "compaction_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False),
            sa.Column("strategy", sa.String(), nullable=False),
            sa.Column("tokens_before", sa.Integer(), nullable=False),
            sa.Column("tokens_after", sa.Integer(), nullable=False),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("created_at", sa.Float(), nullable=True),
        )

    if "tool_call_audit" not in existing_tables:
        op.create_table(
            "tool_call_audit",
            sa.Column("call_id", sa.String(), primary_key=True),
            sa.Column("turn_id", sa.String(), nullable=False),
            sa.Column("timestamp", sa.Float(), nullable=False),
            sa.Column("tool_name", sa.String(), nullable=False),
            sa.Column("args_json", sa.Text(), nullable=False),
            sa.Column("model_tier", sa.String(), nullable=False),
            sa.Column("validation_result", sa.String(), nullable=False),
            sa.Column("permission_result", sa.String(), nullable=False),
            sa.Column("executed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("repair_attempt", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("idx_tool_audit_turn", "tool_call_audit", ["turn_id", "timestamp"])

    if "reliability_events" not in existing_tables:
        op.create_table(
            "reliability_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("timestamp", sa.Float(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("backend_from", sa.String(), nullable=False),
            sa.Column("backend_to", sa.String(), nullable=False),
            sa.Column("reliability_rate", sa.Float(), nullable=False),
            sa.Column("window_size", sa.Integer(), nullable=False),
            sa.Column("failed_calls_count", sa.Integer(), nullable=False),
            sa.Column("failed_calls_json", sa.Text(), nullable=False),
            sa.Column("details", sa.Text(), nullable=True),
        )
        op.create_index("idx_rel_events_ts", "reliability_events", [sa.text("timestamp DESC")])

    # 2. Add Extended Schema Tables
    if "projects" not in existing_tables:
        op.create_table(
            "projects",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("instructions", sa.Text(), nullable=True),
            sa.Column("workspace_path", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_projects_name", "projects", ["name"])

    if "artifacts" not in existing_tables:
        op.create_table(
            "artifacts",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
            sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.session_id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_artifacts_project_id", "artifacts", ["project_id"])
        op.create_index("ix_artifacts_session_id", "artifacts", ["session_id"])
        op.create_index("ix_artifacts_name", "artifacts", ["name"])

    if "memories" not in existing_tables:
        op.create_table(
            "memories",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("source_session_id", sa.String(), sa.ForeignKey("sessions.session_id", ondelete="SET NULL"), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_memories_project_id", "memories", ["project_id"])
        op.create_index("ix_memories_category", "memories", ["category"])
        op.create_index("ix_memories_source_session_id", "memories", ["source_session_id"])

    if "documents" not in existing_tables:
        op.create_table(
            "documents",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("file_path", sa.String(), nullable=False),
            sa.Column("file_name", sa.String(), nullable=False),
            sa.Column("language", sa.String(), nullable=True),
            sa.Column("file_hash", sa.String(), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("last_indexed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_documents_project_id", "documents", ["project_id"])
        op.create_index("ix_documents_file_path", "documents", ["file_path"])

    if "document_chunks" not in existing_tables:
        op.create_table(
            "document_chunks",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("start_line", sa.Integer(), nullable=True),
            sa.Column("end_line", sa.Integer(), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("embedding_vector_id", sa.String(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])

    if "tool_calls" not in existing_tables:
        op.create_table(
            "tool_calls",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
            sa.Column("call_id", sa.String(), nullable=False),
            sa.Column("tool_name", sa.String(), nullable=False),
            sa.Column("arguments_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("result", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_tool_calls_session_id", "tool_calls", ["session_id"])
        op.create_index("ix_tool_calls_message_id", "tool_calls", ["message_id"])
        op.create_index("ix_tool_calls_call_id", "tool_calls", ["call_id"])
        op.create_index("ix_tool_calls_tool_name", "tool_calls", ["tool_name"])
        op.create_index("ix_tool_calls_status", "tool_calls", ["status"])

    if "agent_runs" not in existing_tables:
        op.create_table(
            "agent_runs",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False),
            sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="running"),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tool_calls_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("files_modified_json", sa.Text(), nullable=True),
            sa.Column("errors_json", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_agent_runs_session_id", "agent_runs", ["session_id"])
        op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])
        op.create_index("ix_agent_runs_status", "agent_runs", ["status"])

    # 3. Seed Default "Workspace" Project
    now_str = datetime.utcnow().isoformat()
    op.execute(
        sa.text(
            "INSERT OR IGNORE INTO projects (id, name, description, instructions, workspace_path, created_at, updated_at) "
            "VALUES ('default-workspace', 'Default Workspace', 'Default workspace project', NULL, '.', :now, :now)"
        ).bindparams(now=now_str)
    )


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_table("tool_calls")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("memories")
    op.drop_table("artifacts")
    op.drop_table("projects")
