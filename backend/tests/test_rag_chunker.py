import json
import pytest
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session, select

from app.database.models import Project, Document, DocumentChunk
from app.rag.chunker import SyntaxAwareChunker
from app.rag.indexer import ProjectIndexer
from app.rag.embeddings import EmbeddingService


@pytest.fixture
def rag_test_env(tmp_path):
    """Isolated database and workspace directory for RAG testing."""
    test_db = tmp_path / "test_rag.db"
    db_url = f"sqlite:///{test_db}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    def session_factory():
        return Session(engine)

    return session_factory, tmp_path


def test_python_ast_chunking():
    chunker = SyntaxAwareChunker()
    python_code = """
import os
import sys
from math import sqrt

class GeometryCalculator:
    \"\"\"Utility class for geometric calculations.\"\"\"
    def __init__(self, scale=1.0):
        self.scale = scale

    def compute_hypotenuse(self, a, b):
        return sqrt(a**2 + b**2) * self.scale

def standalone_helper(x, y):
    return x + y
"""
    chunks = chunker.chunk_file(
        file_path="src/geometry.py",
        content=python_code,
        project_id="proj_1"
    )

    assert len(chunks) == 2
    
    # Class chunk
    class_chunk = next(c for c in chunks if c.symbol_type == "class")
    assert class_chunk.symbol_name == "GeometryCalculator"
    assert "class GeometryCalculator" in class_chunk.content
    assert "compute_hypotenuse" in class_chunk.content
    assert "math.sqrt" in class_chunk.imports

    # Standalone function chunk
    func_chunk = next(c for c in chunks if c.symbol_type == "function")
    assert func_chunk.symbol_name == "standalone_helper"
    assert "def standalone_helper" in func_chunk.content


def test_cpp_unreal_engine_chunking():
    chunker = SyntaxAwareChunker()
    cpp_code = """
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "NexusCharacter.generated.h"

UCLASS()
class NEXUS_API ANexusCharacter : public AActor
{
    GENERATED_BODY()

public:
    ANexusCharacter();

    UFUNCTION(BlueprintCallable, Category = "Combat")
    void FireWeapon();
};

USTRUCT(BlueprintType)
struct FWeaponData
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere)
    float Damage;
};
"""
    chunks = chunker.chunk_file(
        file_path="Source/NexusCharacter.h",
        content=cpp_code,
        project_id="proj_ue5"
    )

    assert len(chunks) >= 2
    class_chunk = next(c for c in chunks if c.symbol_name == "ANexusCharacter")
    assert class_chunk.symbol_type == "class"
    assert "class NEXUS_API ANexusCharacter" in class_chunk.content
    assert any("CoreMinimal.h" in imp for imp in class_chunk.imports)


def test_recursive_markdown_chunking():
    chunker = SyntaxAwareChunker(chunk_size=150, chunk_overlap=30)
    markdown_text = """# Project Nexus Overview
Project Nexus is a local-first AI command center and software development assistant.

## Features
- Hardware Resource Governor protecting the 8GB RTX 4060 GPU.
- AST and Syntax-aware chunking for Python and Unreal Engine C++.
- Hybrid vector and keyword retrieval with CPU-only reranker.
- Deterministic safety permissions and workspace isolation.
"""
    chunks = chunker.chunk_file(
        file_path="docs/overview.md",
        content=markdown_text,
        project_id="proj_docs"
    )

    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.language == "markdown"
        assert chunk.start_line <= chunk.end_line
        assert len(chunk.content) > 0


def test_project_indexer_persists_chunks_and_skips_unchanged(rag_test_env):
    session_factory, tmp_path = rag_test_env

    # 1. Create a project in the database
    with session_factory() as session:
        proj = Project(
            id="proj_indexer_test",
            name="Indexer Test Workspace",
            workspace_path=str(tmp_path)
        )
        session.add(proj)
        session.commit()

    # 2. Create sample source files in workspace
    project_files_dir = tmp_path / "projects" / "proj_indexer_test" / "files"
    project_files_dir.mkdir(parents=True, exist_ok=True)

    math_file = project_files_dir / "math_utils.py"
    math_file.write_text("def add_numbers(a, b):\n    return a + b\n", encoding="utf-8")

    emb_service = EmbeddingService(device="cpu", embedding_dim=64)
    indexer = ProjectIndexer(
        session_factory=session_factory,
        embedding_service=emb_service
    )

    # 3. Index file first time
    results = indexer.index_file(math_file, project_id="proj_indexer_test")
    assert len(results) == 1
    assert results[0]["symbol_name"] == "add_numbers"
    assert len(results[0]["embedding"]) == 64

    # Verify DB records
    with session_factory() as session:
        doc = session.exec(select(Document).where(Document.project_id == "proj_indexer_test")).first()
        assert doc is not None
        assert doc.file_name == "math_utils.py"
        
        chunks = session.exec(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)).all()
        assert len(chunks) == 1
        meta = json.loads(chunks[0].metadata_json)
        assert meta["symbol_name"] == "add_numbers"
        assert meta["language"] == "python"

    # 4. Index file second time without changes -> must skip (hash match)
    second_run = indexer.index_file(math_file, project_id="proj_indexer_test")
    assert len(second_run) == 0  # skipped
