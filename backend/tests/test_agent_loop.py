import json
import pytest
from typing import Any, AsyncIterator
from sqlmodel import SQLModel, create_engine, Session, select

from app.database.models import AgentRun, ToolCall
from app.tools.base import BaseTool, ToolResult, PermissionLevel
from app.tools.registry import ToolRegistry
from app.tools.filesystem import ReadFileTool
from app.agent.loop import AgentLoop, AgentState
from app.agent.model_provider import ModelProvider


class FakeModelProvider(ModelProvider):
    def __init__(self, turns: list[list[dict[str, Any]]]):
        self.turns = turns
        self.current_turn = 0
        self.received_messages_history = []

    @property
    def name(self) -> str:
        return "fake_provider"


    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        profile: str = "general",
        timeout: float | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        self.received_messages_history.append(list(messages))
        chunks = self.turns[self.current_turn] if self.current_turn < len(self.turns) else []
        self.current_turn += 1
        for c in chunks:
            yield c

    async def chat(self, *args, **kwargs) -> dict[str, Any]:
        return {"choices": [{"message": {"role": "assistant", "content": "mock"}}]}

    async def health_check(self) -> bool:
        return True

    async def model_info(self) -> dict[str, Any]:
        return {"model": "fake"}

    async def list_models(self) -> list[str]:
        return ["fake"]

    async def unload_model(self, model: str | None = None) -> bool:
        return True


@pytest.fixture
def agent_test_db(tmp_path):
    test_db = tmp_path / "test_agent_loop.db"
    engine = create_engine(f"sqlite:///{test_db}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    import app.agent.loop
    import app.tools.filesystem
    orig_engine = app.agent.loop.engine
    orig_fs_engine = app.tools.filesystem.engine
    app.agent.loop.engine = engine
    app.tools.filesystem.engine = engine

    yield engine, tmp_path

    app.agent.loop.engine = orig_engine
    app.tools.filesystem.engine = orig_fs_engine




@pytest.mark.anyio
async def test_agent_loop_direct_response(agent_test_db):
    engine, tmp_path = agent_test_db
    provider = FakeModelProvider([
        [
            {"delta": "Hello! "},
            {"delta": "I can help with code."},
        ]
    ])

    loop = AgentLoop()
    events = []
    async for ev in loop.run(
        provider=provider,
        messages=[{"role": "user", "content": "Hi"}],
        session_id="sess_101",
        model="qwen3.5-9b"
    ):
        events.append(ev)

    event_types = [e["event"] for e in events]
    assert "agent_status" in event_types
    assert "token" in event_types
    assert "done" in event_types
    assert loop.state == AgentState.COMPLETED

    # Verify AgentRun record in DB
    with Session(engine) as session:
        runs = session.exec(select(AgentRun).where(AgentRun.session_id == "sess_101")).all()
        assert len(runs) == 1
        assert runs[0].status == "completed"


@pytest.mark.anyio
async def test_agent_loop_executes_tool_call(agent_test_db):
    engine, tmp_path = agent_test_db

    # Create test workspace file and project in DB
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    target_file = workspace_dir / "app.py"
    target_file.write_text("print('Jarvis Active')", encoding="utf-8")

    from app.database.models import Project
    with Session(engine) as session:
        proj = Project(
            id="proj_tool_test",
            name="Tool Test Project",
            workspace_path=str(workspace_dir)
        )
        session.add(proj)
        session.commit()

    registry = ToolRegistry()
    registry.register(ReadFileTool())

    # Turn 1: Model calls filesystem.read
    # Turn 2: Model returns final text after inspecting tool output
    turn_1 = [
        {
            "delta": "",
            "tool_calls": [{
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "filesystem.read",
                    "arguments": json.dumps({"path": str(target_file)})
                }
            }]
        }
    ]
    turn_2 = [
        {"delta": "The file contains: print('Jarvis Active')"}
    ]

    provider = FakeModelProvider([turn_1, turn_2])
    loop = AgentLoop(tool_registry=registry)

    events = []
    async for ev in loop.run(
        provider=provider,
        messages=[{"role": "user", "content": "Read app.py"}],
        session_id="sess_tool_test",
        project_id="proj_tool_test",
        model="qwen3.5-9b"
    ):
        events.append(ev)

    event_types = [e["event"] for e in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "done" in event_types


    # Assert OpenAI tool format was passed to second turn
    second_turn_msgs = provider.received_messages_history[1]
    tool_msg = next((m for m in second_turn_msgs if m.get("role") == "tool"), None)
    assert tool_msg is not None
    assert tool_msg["tool_call_id"] == "call_abc123"
    assert "Jarvis Active" in tool_msg["content"]

    # Verify ToolCall in DB
    with Session(engine) as session:
        tcs = session.exec(select(ToolCall).where(ToolCall.session_id == "sess_tool_test")).all()
        assert len(tcs) == 1
        assert tcs[0].tool_name == "filesystem.read"
        assert tcs[0].status == "success"
        assert "Jarvis Active" in tcs[0].result


@pytest.mark.anyio
async def test_agent_loop_confirmation_required_pauses(agent_test_db):
    engine, tmp_path = agent_test_db

    class HighRiskActionTool(BaseTool):
        name = "system.delete_all"
        description = "Dangerous operation"
        permission_level = PermissionLevel.CONFIRMATION_REQUIRED
        parameters = {"type": "object", "properties": {}}

        async def execute(self, **kwargs):
            return ToolResult(status="success", result="deleted")

    registry = ToolRegistry()
    registry.register(HighRiskActionTool())

    turn_1 = [
        {
            "delta": "",
            "tool_calls": [{
                "id": "call_risk_1",
                "type": "function",
                "function": {
                    "name": "system.delete_all",
                    "arguments": "{}"
                }
            }]
        }
    ]

    provider = FakeModelProvider([turn_1])
    loop = AgentLoop(tool_registry=registry)

    events = []
    async for ev in loop.run(
        provider=provider,
        messages=[{"role": "user", "content": "Delete everything"}],
        session_id="sess_conf_test",
        approved_action_ids=[]  # Not approved yet
    ):
        events.append(ev)

    assert loop.state == AgentState.PENDING_USER_CONFIRMATION
    assert any(e["event"] == "confirmation_required" for e in events)


@pytest.mark.anyio
async def test_agent_loop_image_attachment_interception_and_fallback(agent_test_db):
    engine, tmp_path = agent_test_db

    class MockVisionProvider:
        async def analyze_image(self, image_data, prompt="..."):
            return "A cat sitting on a laptop keyboard."

    class MockFailingVisionProvider:
        async def analyze_image(self, image_data, prompt="..."):
            raise RuntimeError("Vision endpoint offline")

    from app.vision.manager import VisionManager

    # 1. Successful image analysis interception
    img_file = tmp_path / "cat.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n")

    vis_mgr = VisionManager(provider=MockVisionProvider())
    loop = AgentLoop(vision_manager=vis_mgr)
    provider = FakeModelProvider([[{"delta": "I see the cat."}]])

    messages = [
        {
            "role": "user",
            "content": "Look at this picture",
            "attachments": [{"path": str(img_file), "name": "cat.png", "type": "image/png"}]
        }
    ]

    events = []
    async for ev in loop.run(provider=provider, messages=messages, session_id="s_vis"):
        events.append(ev)

    # Verify injected vision description
    assert len(provider.received_messages_history) >= 1
    injected_user_msg = provider.received_messages_history[0][0]["content"]
    assert "Vision Analysis of cat.png" in injected_user_msg
    assert "A cat sitting on a laptop keyboard." in injected_user_msg

    # 2. Graceful fallback when vision analysis fails (Amendment 1)
    failing_vis_mgr = VisionManager(provider=MockFailingVisionProvider())
    failing_loop = AgentLoop(vision_manager=failing_vis_mgr)
    failing_provider = FakeModelProvider([[{"delta": "Acknowledged."}]])

    events_fallback = []
    async for ev in failing_loop.run(provider=failing_provider, messages=messages, session_id="s_vis_fail"):
        events_fallback.append(ev)

    injected_fallback_msg = failing_provider.received_messages_history[0][0]["content"]
    assert "vision analysis is currently unavailable" in injected_fallback_msg
