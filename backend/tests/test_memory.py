import os
import uuid
import pytest
import httpx
from app.main import app, memory_store, compactor
from app.memory.store import MemoryStore
from app.memory.compactor import (
    ContextCompactor,
    estimate_tokens,
    estimate_messages_tokens,
    prune_tool_outputs,
)


@pytest.fixture
def temp_store(tmp_path):
    db_file = str(tmp_path / "test_memory.db")
    return MemoryStore(db_path=db_file)


# --- Unit Tests for SQLite Store ---

def test_store_session_and_messages(temp_store):
    session = temp_store.get_or_create_session("session_1", title="Test Session")
    assert session["session_id"] == "session_1"

    temp_store.append_message("session_1", role="user", content="Hello Jarvis")
    temp_store.append_message("session_1", role="assistant", content="Hello! How can I help?")

    messages = temp_store.get_messages("session_1")
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello Jarvis"
    assert messages[1]["role"] == "assistant"


def test_store_delete_session(temp_store):
    temp_store.append_message("session_to_del", role="user", content="Test")
    assert len(temp_store.get_messages("session_to_del")) == 1

    deleted = temp_store.delete_session("session_to_del")
    assert deleted is True
    assert len(temp_store.get_messages("session_to_del")) == 0


def test_store_record_compaction(temp_store):
    temp_store.get_or_create_session("sess_comp")
    event = temp_store.record_compaction(
        session_id="sess_comp",
        strategy="tool_pruning",
        tokens_before=500,
        tokens_after=150,
        details="Pruned 2 bulky tool outputs"
    )
    assert event["strategy"] == "tool_pruning"

    events = temp_store.get_compaction_events("sess_comp")
    assert len(events) == 1
    assert events[0]["tokens_before"] == 500
    assert events[0]["tokens_after"] == 150


# --- Unit Tests for Context Compactor ---

def test_token_estimation():
    text = "Hello world! This is a test string."
    tokens = estimate_tokens(text)
    assert tokens == len(text) // 4

    messages = [
        {"role": "user", "content": "Short query"},
        {"role": "assistant", "content": "Short reply"}
    ]
    total_tokens = estimate_messages_tokens(messages)
    assert total_tokens > 0


def test_tool_output_pruning():
    large_tool_content = "FILE CONTENT LINE\n" * 100  # ~1800 chars
    messages = [
        {"role": "user", "content": "Read the file"},
        {"role": "tool", "name": "read_file", "content": large_tool_content},
        {"role": "assistant", "content": "Here is what I found"},
        {"role": "user", "content": "Next request"}
    ]

    pruned, count = prune_tool_outputs(messages, char_threshold=200)
    assert count == 1
    assert "Tool output pruned" in pruned[1]["content"]
    assert len(pruned[1]["content"]) < len(large_tool_content)


# --- Integration Tests with FastAPI app ---

@pytest.mark.anyio
async def test_multi_turn_conversation_memory():
    """Verify that assistant remembers facts stated in prior turns within the same session."""
    session_id = f"test_memory_{uuid.uuid4().hex[:8]}"

    try:
        # Turn 1: User introduces a fact
        turn1_payload = {
            "message": "My favorite programming language is Python 3.11. Please acknowledge with 'Understood'.",
            "session_id": session_id,
            "model": "qwen2.5:0.5b"
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=45.0) as ac:
            res1 = await ac.post("/chat", json=turn1_payload)
        
        assert res1.status_code == 200
        assert res1.json()["session_id"] == session_id

        # Turn 2: User asks for the stored fact
        turn2_payload = {
            "message": "What is my favorite programming language?",
            "session_id": session_id,
            "model": "qwen2.5:0.5b"
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=45.0) as ac:
            res2 = await ac.post("/chat", json=turn2_payload)
        
        assert res2.status_code == 200
        content = res2.json()["response"]
        assert "Python" in content or "3.11" in content

        # Verify messages stored in database
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            history_res = await ac.get(f"/sessions/{session_id}/messages")
        
        assert history_res.status_code == 200
        messages = history_res.json()
        assert len(messages) >= 4

    finally:
        # Cleanup session
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            await ac.delete(f"/sessions/{session_id}")


@pytest.mark.anyio
async def test_compaction_triggered_and_logged():
    """Verify that exceeding token limits triggers compaction, logs it, and surfaces in response."""
    session_id = f"test_compaction_{uuid.uuid4().hex[:8]}"

    try:
        # Seed session with bulky tool messages in store
        bulky_text = "DENSE SYSTEM LOG ENTRY DETAILS - " * 50  # ~1700 chars
        memory_store.append_message(session_id, role="user", content="Please inspect the logs")
        memory_store.append_message(session_id, role="tool", content=bulky_text, name="read_file")
        memory_store.append_message(session_id, role="assistant", content="Logs inspected.")

        # Set tight compaction threshold on compactor temporarily
        orig_threshold = compactor.max_context_tokens
        compactor.max_context_tokens = 50  # Force Stage 1 or Stage 2 compaction

        payload = {
            "message": "Continue with the next step.",
            "session_id": session_id,
            "model": "qwen2.5:0.5b"
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=45.0) as ac:
            response = await ac.post("/chat", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify compaction was performed and surfaced
        assert data["compaction_performed"] is not None
        assert "strategy" in data["compaction_performed"]
        assert data["compaction_performed"]["tokens_before"] > data["compaction_performed"]["tokens_after"]

        # Verify compaction event in audit endpoint
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            audit_res = await ac.get(f"/sessions/{session_id}/compactions")
        
        assert audit_res.status_code == 200
        events = audit_res.json()
        assert len(events) >= 1

    finally:
        compactor.max_context_tokens = orig_threshold
        memory_store.delete_session(session_id)
