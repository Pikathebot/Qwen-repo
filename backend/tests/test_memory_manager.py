import pytest
import httpx
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.memory.manager import (
    MemoryManager,
    MemoryCategory,
    MemoryCreate,
    MemoryUpdate,
    CandidateMemory,
)
from app.memory.store import MemoryStore
from app.rag.embeddings import EmbeddingService
from app.agent.model_router import ModelRouter
from app.main import app
from app.routers.memories import get_memory_store, get_memory_manager


@pytest.fixture
def temp_memory_store(tmp_path):
    """Temporary isolated MemoryStore database."""
    db_file = str(tmp_path / "test_memory_mgr.db")
    return MemoryStore(db_path=db_file)


@pytest.fixture
def memory_manager(temp_memory_store):
    """MemoryManager instance bound to temporary database and CPU EmbeddingService."""
    emb_svc = EmbeddingService(device="cpu")
    return MemoryManager(memory_store=temp_memory_store, embedding_service=emb_svc)


def test_memory_manager_dependency_injection(temp_memory_store):
    """Test MemoryManager constructor accepts injected dependencies."""
    emb = EmbeddingService(device="cpu")
    router = ModelRouter()
    mgr = MemoryManager(
        memory_store=temp_memory_store,
        embedding_service=emb,
        model_router=router,
    )
    assert mgr.memory_store is temp_memory_store
    assert mgr.embedding_service is emb
    assert mgr.model_router is router


def test_detect_candidate_memories_filtering(memory_manager):
    """Test detect_candidate_memories ignores noise and extracts high-value signals."""
    noise_messages = [
        {"role": "user", "content": "Hello Jarvis"},
        {"role": "assistant", "content": "Hi! How can I help you today?"},
        {"role": "user", "content": "Thanks a lot, ok got it."},
        {"role": "user", "content": ""},
        {"role": "user", "content": "hey"},
    ]
    assert len(memory_manager.detect_candidate_memories(noise_messages)) == 0

    valuable_messages = [
        {"role": "user", "content": "I prefer Python 3.11 for all backend code."},
        {"role": "user", "content": "We decided to adopt SQLite WAL mode for persistence."},
        {"role": "user", "content": "Workflow rule: always run pytest before merging."},
        {"role": "user", "content": "Remember: my timezone is UTC+5:30."},
        {"role": "user", "content": "Persistent task: complete user authentication flows."},
    ]

    candidates = memory_manager.detect_candidate_memories(valuable_messages)
    assert len(candidates) >= 5
    categories = [c.category for c in candidates]
    assert MemoryCategory.USER_PREFERENCE in categories
    assert MemoryCategory.IMPORTANT_DECISION in categories
    assert MemoryCategory.WORKFLOW_PREFERENCE in categories
    assert MemoryCategory.RECURRING_FACT in categories
    assert MemoryCategory.PERSISTENT_TASK_CONTEXT in categories


def test_store_and_retrieve_semantic_search(memory_manager):
    """Test store_memory and CPU-only semantic retrieval."""
    m1 = memory_manager.store_memory(MemoryCreate(
        category=MemoryCategory.USER_PREFERENCE,
        content="User prefers dark theme and high contrast typography",
        pinned=True
    ))
    m2 = memory_manager.store_memory(MemoryCreate(
        category=MemoryCategory.PROJECT_PREFERENCE,
        content="Project backend requires Python 3.11 with strict static typing"
    ))
    m3 = memory_manager.store_memory(MemoryCreate(
        category=MemoryCategory.WORKFLOW_PREFERENCE,
        content="Deployment must run inside a Docker container on port 8000"
    ))

    # Semantic search: theme query
    theme_results = memory_manager.retrieve_memories("What visual interface theme does user prefer?", limit=2)
    assert len(theme_results) >= 1
    assert theme_results[0]["id"] == m1.id
    assert "dark theme" in theme_results[0]["content"]

    # Semantic search: Python language version query
    lang_results = memory_manager.retrieve_memories("What programming language version do we use?", limit=2)
    assert len(lang_results) >= 1
    assert lang_results[0]["id"] == m2.id

    # Filter by category
    filtered = memory_manager.retrieve_memories("", category=MemoryCategory.WORKFLOW_PREFERENCE)
    assert len(filtered) == 1
    assert filtered[0]["id"] == m3.id


def test_retrieve_memories_project_filter(memory_manager):
    """Test retrieve_memories respects project_id filtering."""
    memory_manager.store_memory(MemoryCreate(
        category=MemoryCategory.PROJECT_PREFERENCE,
        content="Project Alpha uses React 19",
        project_id="proj_alpha"
    ))
    memory_manager.store_memory(MemoryCreate(
        category=MemoryCategory.PROJECT_PREFERENCE,
        content="Project Beta uses Vue 3",
        project_id="proj_beta"
    ))

    res_alpha = memory_manager.retrieve_memories("frontend framework", project_id="proj_alpha")
    assert len(res_alpha) >= 1
    assert "React 19" in res_alpha[0]["content"]


def test_update_and_delete_memory(memory_manager):
    """Test update_memory and delete_memory methods."""
    mem = memory_manager.store_memory(MemoryCreate(
        category=MemoryCategory.USER_PREFERENCE,
        content="User prefers tabs over spaces"
    ))

    # Update content
    updated = memory_manager.update_memory(
        mem.id,
        updates={"content": "User prefers 4 spaces over tabs", "pinned": True}
    )
    assert updated.content == "User prefers 4 spaces over tabs"
    assert updated.pinned is True

    # Attempt updating non-existent memory
    with pytest.raises(KeyError):
        memory_manager.update_memory("nonexistent_id", updates={"content": "test"})

    # Delete
    deleted = memory_manager.delete_memory(mem.id)
    assert deleted is True
    assert memory_manager.delete_memory(mem.id) is False

    # Verify retrieval
    results = memory_manager.retrieve_memories("spaces tabs")
    assert not any(r["id"] == mem.id for r in results)


def test_deduplicate_memories(memory_manager):
    """Test deduplicate_memories merges/purges redundant duplicate memories."""
    # Add identical or near-duplicate memories
    memory_manager.store_memory(MemoryCreate(
        category=MemoryCategory.USER_PREFERENCE,
        content="User prefers Python 3.11",
        confidence=0.9
    ))
    memory_manager.store_memory(MemoryCreate(
        category=MemoryCategory.USER_PREFERENCE,
        content="User prefers Python 3.11",
        confidence=1.0,
        pinned=True
    ))
    memory_manager.store_memory(MemoryCreate(
        category=MemoryCategory.RECURRING_FACT,
        content="User likes Italian pizza"
    ))

    # Execute deduplication
    purged_count = memory_manager.deduplicate_memories(similarity_threshold=0.85)
    assert purged_count == 1

    remaining = memory_manager.retrieve_memories("", limit=10)
    assert len(remaining) == 2


def test_deduplicate_memories_no_duplicates(memory_manager):
    """Test deduplicate_memories when no duplicates exist."""
    memory_manager.store_memory(MemoryCreate(
        category=MemoryCategory.USER_PREFERENCE,
        content="User likes Rust"
    ))
    memory_manager.store_memory(MemoryCreate(
        category=MemoryCategory.IMPORTANT_DECISION,
        content="Use PostgreSQL for production database"
    ))
    purged = memory_manager.deduplicate_memories()
    assert purged == 0


def test_memories_rest_api_crud(tmp_path):
    """Test FastAPI REST endpoints in routers/memories.py."""
    db_file = str(tmp_path / "api_test_memories.db")
    store = MemoryStore(db_path=db_file)
    mgr = MemoryManager(memory_store=store, embedding_service=EmbeddingService(device="cpu"))

    app.dependency_overrides[get_memory_store] = lambda: store
    app.dependency_overrides[get_memory_manager] = lambda: mgr

    try:
        client = TestClient(app)

        # 1. Create memory
        create_payload = {
            "category": "user_preference",
            "content": "User prefers VS Code keybindings",
            "confidence": 0.95,
            "pinned": True
        }
        res_create = client.post("/api/memories", json=create_payload)
        assert res_create.status_code == 201
        data = res_create.json()
        mem_id = data["id"]
        assert data["category"] == "user_preference"
        assert data["pinned"] is True

        # 2. Get memory
        res_get = client.get(f"/api/memories/{mem_id}")
        assert res_get.status_code == 200
        assert res_get.json()["id"] == mem_id

        # 3. List / Search memories
        res_list = client.get("/api/memories?query=keybindings")
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 1

        # 4. Patch memory
        patch_payload = {"content": "User prefers Neovim keybindings"}
        res_patch = client.patch(f"/api/memories/{mem_id}", json=patch_payload)
        assert res_patch.status_code == 200
        assert res_patch.json()["content"] == "User prefers Neovim keybindings"

        # 5. Detect candidate memories endpoint
        detect_payload = {
            "messages": [{"role": "user", "content": "I prefer dark mode in all editors."}]
        }
        res_detect = client.post("/api/memories/detect", json=detect_payload)
        assert res_detect.status_code == 200
        assert len(res_detect.json()) >= 1

        # 6. Delete memory
        res_del = client.delete(f"/api/memories/{mem_id}")
        assert res_del.status_code == 204

    finally:
        app.dependency_overrides.clear()
