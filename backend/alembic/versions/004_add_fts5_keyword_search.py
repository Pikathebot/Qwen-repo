"""Add FTS5 virtual table for exact keyword and symbol search.

Revision ID: 004
Revises: 003
Create Date: 2026-08-31 17:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "sqlite":
        # Create SQLite FTS5 table with tokenchars for C++ and Python code symbols
        op.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
                chunk_id UNINDEXED,
                project_id UNINDEXED,
                file_path,
                symbol_name,
                content,
                metadata_json UNINDEXED,
                tokenize = "unicode61 tokenchars '_:'"
            );
            """
        )
    else:
        # Fallback / Future PostgreSQL compatibility
        pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "sqlite":
        op.execute("DROP TABLE IF EXISTS document_chunks_fts;")
