import os
import sys
import uuid
import pytest
import httpx
from pathlib import Path
from app.main import app, skills_loader, mcp_manager
from app.skills.loader import SkillsLoader, Skill
from app.mcp.manager import MCPManager


# --- Unit Tests for Skills Loader ---

def test_skills_loader_discovery():
    loader = SkillsLoader()
    skills = loader.load_skills()
    assert "code_review" in skills
    assert "system_diagnostics" in skills

    review_skill = skills["code_review"]
    assert "review code" in review_skill.triggers
    assert "read_file" in review_skill.tools
    assert len(review_skill.instructions) > 0


def test_skills_trigger_matching():
    loader = SkillsLoader()
    
    # 1. Matches code review
    matches_review = loader.match_skills("Can you do a code review of this file?")
    assert len(matches_review) == 1
    assert matches_review[0].name == "code_review"

    # 2. Matches system diagnostics
    matches_diag = loader.match_skills("Check system diagnostics and hardware stats.")
    assert len(matches_diag) >= 1
    assert any(s.name == "system_diagnostics" for s in matches_diag)

    # 3. No match for unrelated text
    matches_none = loader.match_skills("Tell me a funny joke.")
    assert len(matches_none) == 0


def test_skills_prompt_injection():
    loader = SkillsLoader()
    skills = loader.match_skills("Please inspect code quality.")
    injection = loader.build_skill_prompt_injection(skills)
    assert "Skill Active: code_review" in injection
    assert "Code Review Instructions" in injection


def test_skills_hot_reload(tmp_path):
    # Setup temporary skills folder
    temp_skill_file = tmp_path / "custom_skill.md"
    temp_skill_file.write_text(
        "---\nname: custom_test\ndescription: Custom test skill\ntriggers:\n  - trigger_abc\ntools:\n  - custom_tool\n---\nCustom instructions here.",
        encoding="utf-8"
    )

    loader = SkillsLoader(skills_dir=str(tmp_path))
    skills = loader.load_skills()
    assert "custom_test" in skills
    assert loader.match_skills("trigger_abc")[0].name == "custom_test"


# --- Unit Tests for MCP Manager & Stdio Server ---

@pytest.mark.anyio
async def test_mcp_manager_connection_and_tool_call():
    mgr = MCPManager()
    await mgr.connect_all()

    try:
        servers = mgr.list_servers()
        assert len(servers) >= 1
        assert any(s["name"] == "system_diagnostics" for s in servers)

        # Verify tool definitions
        tools = mgr.get_tool_definitions()
        assert len(tools) >= 2
        tool_names = [t["function"]["name"] for t in tools]
        assert "get_disk_usage" in tool_names
        assert "get_system_uptime" in tool_names

        # Verify tool execution
        assert mgr.is_mcp_tool("get_disk_usage") is True
        disk_result = await mgr.call_tool("get_disk_usage", {"path": "."})
        assert "Disk Usage" in disk_result
        assert "GB" in disk_result

        uptime_result = await mgr.call_tool("get_system_uptime", {})
        assert "System Uptime" in uptime_result

    finally:
        await mgr.disconnect_all()


# --- Integration Tests with FastAPI app ---

@pytest.mark.anyio
async def test_api_get_skills():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/skills")
    
    assert response.status_code == 200
    skills = response.json()
    assert len(skills) >= 2
    names = [s["name"] for s in skills]
    assert "code_review" in names
    assert "system_diagnostics" in names


@pytest.mark.anyio
async def test_api_get_mcp_servers():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/mcp/servers")
    
    assert response.status_code == 200
    servers = response.json()
    assert len(servers) >= 1
    assert any(s["name"] == "system_diagnostics" for s in servers)


@pytest.mark.anyio
async def test_chat_with_dynamic_skills_matching():
    """Verify that a chat query triggering a skill records the active skill name."""
    mock_resp = {
        "message": {
            "role": "assistant",
            "content": "Code review complete."
        }
    }
    class FakeOllama:
        async def chat(self, *args, **kwargs):
            return mock_resp

    from unittest.mock import patch
    with patch("app.main.get_ollama_client", return_value=FakeOllama()):
        payload = {
            "message": "Please review code in docs/PLAN.md and check this code.",
            "session_id": f"test_skill_{uuid.uuid4().hex[:8]}",
            "model": "qwen2.5:0.5b"
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=10.0) as ac:
            response = await ac.post("/chat", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "active_skills" in data
        assert "code_review" in data["active_skills"]
