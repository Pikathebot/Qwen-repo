import json
import pytest
from unittest.mock import AsyncMock, patch

from app.memory.context_compactor import (
    ContextCompactor,
    CompactionSummary,
    prune_tool_outputs,
    estimate_tokens,
    estimate_messages_tokens,
    should_compact,
    compact,
)
from app.memory.store import MemoryStore
from app.memory.token_counter import TokenCounter
from app.memory.context_manager import ContextManager
from app.agent.model_router import ModelRouter, TaskType


@pytest.fixture
def isolated_store(tmp_path):
    """Isolated test database inside pytest tmp_path."""
    db_file = str(tmp_path / "compaction_test.db")
    return MemoryStore(db_path=db_file)


@pytest.fixture
def mock_fast_llm_provider():
    """Mock LLM provider returning structured JSON compaction summaries."""
    mock = AsyncMock()
    mock_payload = {
        "conversation_summary": "User designed a REST API and requested automated tests for the auth module.",
        "important_facts": ["User prefers Python 3.11", "Database is SQLite with WAL mode"],
        "decisions": ["Adopted FastAPI with Pydantic v2", "Enforced CPU-only embeddings"],
        "open_tasks": ["Add rate limiting", "Implement JWT refresh tokens"],
        "files_modified": ["app/main.py", "app/routers/auth.py"],
        "artifacts_created": ["auth_spec_v1"],
        "tool_state": {"write_file": 2, "read_file": 5},
    }
    mock.chat.return_value = {
        "message": {
            "role": "assistant",
            "content": json.dumps(mock_payload)
        }
    }
    return mock


def test_should_compact_thresholds(isolated_store):
    """Test should_compact evaluates message count and token budget thresholds."""
    session_id = "sess_thresh_test"
    compactor = ContextCompactor(
        memory_store=isolated_store,
        max_message_count=5,
        max_context_tokens=100
    )

    # 1. Empty conversation should not compact
    assert compactor.should_compact(session_id) is False

    # 2. Add 4 short messages (below both thresholds)
    for i in range(4):
        isolated_store.append_message(session_id, role="user", content=f"msg {i}")
    assert compactor.should_compact(session_id) is False

    # 3. Add 6th message (exceeds max_message_count = 5)
    for i in range(4, 7):
        isolated_store.append_message(session_id, role="user", content=f"msg {i}")
    assert compactor.should_compact(session_id) is True

    # 4. Functional helper test
    assert should_compact(session_id, message_count_threshold=5, memory_store=isolated_store) is True


def test_prune_tool_outputs_behavior():
    """Test Stage 1 compaction tool pruning."""
    large_output = "Line of code output\n" * 50
    messages = [
        {"role": "user", "content": "Fetch file"},
        {"role": "tool", "name": "read_file", "content": large_output},
        {"role": "assistant", "content": "I found it"},
        {"role": "user", "content": "Latest query"},
    ]

    pruned, count = prune_tool_outputs(messages, char_threshold=100)
    assert count == 1
    assert "Tool output pruned" in pruned[1]["content"]
    assert len(pruned[1]["content"]) < len(large_output)


def test_token_estimation_helpers():
    """Test fast token estimation heuristics."""
    assert estimate_tokens("") == 0
    assert estimate_tokens("Hello World") == len("Hello World") // 4

    messages = [
        {"role": "user", "content": "Query text"},
        {"role": "assistant", "content": "Reply text", "name": "assistant"},
    ]
    tokens = estimate_messages_tokens(messages)
    assert tokens > 0


@pytest.mark.anyio
async def test_compact_generates_7_fields(isolated_store, mock_fast_llm_provider):
    """Test that compact() produces a strongly typed CompactionSummary with all 7 fields."""
    session_id = "sess_summary_test"

    # Populate conversation
    isolated_store.append_message(session_id, role="user", content="Let's build a REST API with FastAPI.")
    isolated_store.append_message(session_id, role="assistant", content="Sure! I will create app/main.py.")
    isolated_store.append_message(
        session_id,
        role="assistant",
        content="I modified app/main.py",
        tool_calls=[{"function": {"name": "write_file", "arguments": {"path": "app/main.py"}}}]
    )
    isolated_store.append_message(session_id, role="user", content="Remember: I prefer Python 3.11.")
    isolated_store.append_message(session_id, role="assistant", content="Noted. What next?")

    compactor = ContextCompactor(memory_store=isolated_store)
    summary: CompactionSummary = await compactor.compact(
        conversation_id=session_id,
        model_provider=mock_fast_llm_provider
    )

    # Verify structured summary model and all 7 fields
    assert isinstance(summary, CompactionSummary)
    assert len(summary.conversation_summary) > 0
    assert "Python 3.11" in summary.important_facts[0] or len(summary.important_facts) >= 1
    assert len(summary.decisions) >= 1
    assert len(summary.open_tasks) >= 1
    assert "app/main.py" in summary.files_modified or len(summary.files_modified) >= 1
    assert isinstance(summary.artifacts_created, list)
    assert isinstance(summary.tool_state, dict)


@pytest.mark.anyio
async def test_compaction_deterministic_routing(isolated_store, mock_fast_llm_provider):
    """Test that compaction routes deterministically to FAST_MODEL via ModelRouter."""
    session_id = "sess_routing_test"
    isolated_store.append_message(session_id, role="user", content="Hello, let's compress.")

    router = ModelRouter()
    compactor = ContextCompactor(memory_store=isolated_store, model_router=router)

    with patch.object(router, "route_task", wraps=router.route_task) as spy_route:
        await compactor.compact(conversation_id=session_id, model_provider=mock_fast_llm_provider)

        spy_route.assert_called_once()
        call_kwargs = spy_route.call_args
        assert call_kwargs.kwargs.get("task_type") == TaskType.COMPACTION or call_kwargs.args[0] == TaskType.COMPACTION


@pytest.mark.anyio
async def test_compaction_fallback_on_llm_error(isolated_store):
    """Test that compaction gracefully constructs fallback summary when LLM fails."""
    session_id = "sess_fallback_test"
    isolated_store.append_message(session_id, role="user", content="Start project")
    isolated_store.append_message(session_id, role="assistant", content="Project started")

    failing_provider = AsyncMock()
    failing_provider.chat.side_effect = RuntimeError("Inference connection failed")

    compactor = ContextCompactor(memory_store=isolated_store)
    summary = await compactor.compact(conversation_id=session_id, model_provider=failing_provider)

    assert isinstance(summary, CompactionSummary)
    assert "Conversation spanning" in summary.conversation_summary


@pytest.mark.anyio
async def test_compaction_persists_event_and_feeds_context_manager(isolated_store, mock_fast_llm_provider):
    """Test that compaction events are persisted to database and consumed by ContextManager Tier 5."""
    session_id = "sess_tier5_test"

    for i in range(10):
        isolated_store.append_message(session_id, role="user", content=f"User discussion step {i}")
        isolated_store.append_message(session_id, role="assistant", content=f"Assistant response step {i}")

    compactor = ContextCompactor(memory_store=isolated_store)
    await compactor.compact(conversation_id=session_id, model_provider=mock_fast_llm_provider)

    # 1. Verify compaction_events table record
    events = isolated_store.get_compaction_events(session_id)
    assert len(events) >= 1
    last_event = events[-1]
    assert last_event["strategy"] == "structured_summarization"
    assert last_event["tokens_before"] > 0
    assert last_event["tokens_after"] > 0
    assert "summary" in last_event["details"]

    # 2. Verify ContextManager feeds Tier 5 compaction summary
    ctx_mgr = ContextManager(memory_store=isolated_store, reserved_output_tokens=50)
    package = ctx_mgr.build_context(
        session_id=session_id,
        user_message="Next question",
        max_context_tokens=150,  # tight budget forcing Tier 5 summary inclusion
    )

    assert package is not None
    messages_content = " ".join([m.get("content", "") for m in package.messages])
    assert "Prior Conversation" in messages_content or package.budget_report.get("tier5_summary_included") is True
