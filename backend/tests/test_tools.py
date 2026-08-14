import os
import uuid
from pathlib import Path
import pytest
import httpx
from app.main import app
from app.agent.tools.read_file import read_file
from app.agent.tools.list_directory import list_directory
from app.agent.tools.registry import execute_tool

TEST_SECRET_FILE = "test_sandbox_secret.txt"
TEST_SECRET_CONTENT = "JARVIS_PHASE1_CONFIRMED_40918"


@pytest.fixture(autouse=True)
def setup_test_files():
    # Setup test file
    with open(TEST_SECRET_FILE, "w", encoding="utf-8") as f:
        f.write(TEST_SECRET_CONTENT)
    yield
    # Teardown test file
    if os.path.exists(TEST_SECRET_FILE):
        os.remove(TEST_SECRET_FILE)


# --- Unit Tests for Tool Functions ---

def test_read_file_success():
    content = read_file(TEST_SECRET_FILE)
    assert content == TEST_SECRET_CONTENT


def test_read_file_not_found():
    result = read_file("non_existent_file_xyz999.txt")
    assert "Error: File not found" in result


def test_read_file_directory():
    result = read_file("docs")
    assert "is a directory" in result


def test_list_directory_success():
    result = list_directory("docs")
    assert "Contents of 'docs':" in result
    assert "PLAN.md" in result


def test_list_directory_not_found():
    result = list_directory("non_existent_dir_999")
    assert "Error: Directory not found" in result


def test_execute_tool_unregistered():
    result = execute_tool("fake_tool", {})
    assert "Error: Tool 'fake_tool' is not registered" in result


# --- Integration Tests with Ollama (qwen2.5:0.5b) ---

@pytest.mark.anyio
@pytest.mark.parametrize("prompt_phrasing", [
    f"Please read the file {TEST_SECRET_FILE} and report its text.",
    f"Please read the contents of {TEST_SECRET_FILE} and tell me the token.",
    f"Inspect {TEST_SECRET_FILE} and report the exact secret code inside it."
])
async def test_tool_calling_read_file_phrasings(prompt_phrasing: str):
    """
    Test Ollama native tool-calling with 3 different phrasings as required by Phase 1.
    """
    payload = {
        "message": prompt_phrasing,
        "session_id": f"test_phrasing_{uuid.uuid4().hex[:8]}",
        "model": "qwen2.5:0.5b"
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=45.0) as ac:
        response = await ac.post("/chat", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "tools_used" in data
    assert len(data["tools_used"]) >= 1
    assert any(t["tool"] in ("read_file", "execute_command") for t in data["tools_used"])
    assert "JARVIS_PHASE1_CONFIRMED_40918" in data["response"] or "JARVIS_PHASE1_CONFIRMED_40918" in str(data["tools_used"])


@pytest.mark.anyio
async def test_tool_calling_list_directory():
    """
    Test Ollama native tool-calling with directory listing.
    """
    payload = {
        "message": "Please list the files in the 'docs' directory using your list_directory tool.",
        "session_id": f"test_listdir_{uuid.uuid4().hex[:8]}",
        "model": "qwen2.5:0.5b"
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=45.0) as ac:
        response = await ac.post("/chat", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "tools_used" in data
    assert len(data["tools_used"]) >= 1
    assert any(t["tool"] == "list_directory" for t in data["tools_used"])
    assert "PLAN.md" in data["response"] or "PLAN.md" in str(data["tools_used"])


@pytest.mark.anyio
async def test_chat_no_tools_needed():
    """
    Test that general conversation queries do not trigger tools unnecessarily.
    """
    payload = {
        "message": "Say hello politely.",
        "session_id": f"test_notools_{uuid.uuid4().hex[:8]}",
        "model": "qwen2.5:0.5b"
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0) as ac:
        response = await ac.post("/chat", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "tools_used" in data
    assert len(data["tools_used"]) == 0
    assert len(data["response"]) > 0
