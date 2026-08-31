"""Add local_folders_json and is_active to projects, and project_id to sessions.

Revision ID: 002
Revises: 001
Create Date: 2026-08-31 15:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Drop any leftover tmp tables from interrupted migrations
    for tmp in ["_alembic_tmp_projects", "_alembic_tmp_sessions"]:
        if tmp in existing_tables:
            op.execute(f"DROP TABLE IF EXISTS {tmp}")


    if "projects" in existing_tables:
        project_cols = [c["name"] for c in inspector.get_columns("projects")]
        with op.batch_alter_table("projects") as batch_op:
            if "local_folders_json" not in project_cols:
                batch_op.add_column(sa.Column("local_folders_json", sa.Text(), nullable=True))
            if "is_active" not in project_cols:
                batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()))

    # 2. Update sessions table
    if "sessions" in existing_tables:
        session_cols = [c["name"] for c in inspector.get_columns("sessions")]
        with op.batch_alter_table("sessions") as batch_op:
            if "project_id" not in session_cols:
                batch_op.add_column(sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", name="fk_sessions_project_id", ondelete="SET NULL"), nullable=True))
                batch_op.create_index("ix_sessions_project_id", ["project_id"])



def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "sessions" in existing_tables:
        session_cols = [c["name"] for c in inspector.get_columns("sessions")]
        with op.batch_alter_table("sessions") as batch_op:
            if "project_id" in session_cols:
                batch_op.drop_index("ix_sessions_project_id")
                batch_op.drop_column("project_id")

    if "projects" in existing_tables:
        project_cols = [c["name"] for c in inspector.get_columns("projects")]
        with op.batch_alter_table("projects") as batch_op:
            if "is_active" in project_cols:
                batch_op.drop_column("is_active")
            if "local_folders_json" in project_cols:
                batch_op.drop_column("local_folders_json")
