"""Enhance artifacts and artifact_versions schema, add file_versions table.

Revision ID: 005
Revises: 004
Create Date: 2026-09-02 10:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # 1. Update artifacts table columns if present
    if "artifacts" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("artifacts")]
        with op.batch_alter_table("artifacts") as batch_op:
            if "language" not in columns:
                batch_op.add_column(sa.Column("language", sa.String(), nullable=True))
            if "conversation_id" not in columns:
                batch_op.add_column(sa.Column("conversation_id", sa.String(), nullable=True))

    # 2. Update artifact_versions table columns if present
    if "artifact_versions" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("artifact_versions")]
        with op.batch_alter_table("artifact_versions") as batch_op:
            if "created_by" not in columns:
                batch_op.add_column(sa.Column("created_by", sa.String(), nullable=False, server_default="agent"))

    # 3. Create file_versions table if not exists
    if "file_versions" not in existing_tables:
        op.create_table(
            "file_versions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("file_path", sa.String(), nullable=False),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(), nullable=False, server_default="agent"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_file_versions_file_path", "file_versions", ["file_path"])
        op.create_index("ix_file_versions_session_id", "file_versions", ["session_id"])
        op.create_index("ix_file_versions_version_number", "file_versions", ["version_number"])


def downgrade() -> None:
    op.drop_table("file_versions")
