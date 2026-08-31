"""Add attachments and artifact_versions tables.

Revision ID: 003
Revises: 002
Create Date: 2026-08-31 16:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Drop any leftover tmp tables
    for tmp in ["_alembic_tmp_attachments", "_alembic_tmp_artifact_versions"]:
        if tmp in existing_tables:
            op.execute(f"DROP TABLE IF EXISTS {tmp}")

    # 1. Create attachments table
    if "attachments" not in existing_tables:
        op.create_table(
            "attachments",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.session_id", name="fk_attachments_session_id", ondelete="SET NULL"), nullable=True),
            sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", name="fk_attachments_project_id", ondelete="SET NULL"), nullable=True),
            sa.Column("filename", sa.String(), nullable=False),
            sa.Column("path", sa.String(), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("content_type", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_attachments_session_id", "attachments", ["session_id"])
        op.create_index("ix_attachments_project_id", "attachments", ["project_id"])
        op.create_index("ix_attachments_filename", "attachments", ["filename"])

    # 2. Create artifact_versions table
    if "artifact_versions" not in existing_tables:
        op.create_table(
            "artifact_versions",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("artifact_id", sa.String(), sa.ForeignKey("artifacts.id", name="fk_artifact_versions_artifact_id", ondelete="CASCADE"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_artifact_versions_artifact_id", "artifact_versions", ["artifact_id"])
        op.create_index("ix_artifact_versions_version", "artifact_versions", ["version"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "artifact_versions" in existing_tables:
        op.drop_table("artifact_versions")

    if "attachments" in existing_tables:
        op.drop_table("attachments")
