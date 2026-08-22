import pytest
import httpx
from unittest.mock import AsyncMock, patch
import ollama
from app.main import app
from app.agent.lmstudio_client import LMStudioClient


@pytest.mark.anyio
async def test_health_check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "active_backend" in data


@pytest.mark.anyio
async def test_chat_with_model():
    """Test /chat with mocked backend to avoid loading models in VRAM during tests."""
    mock_resp = {
        "message": {
            "role": "assistant",
            "content": "OK",
            "tool_calls": None
        }
    }
    with patch.object(ollama.AsyncClient, "chat", new_callable=AsyncMock) as mock_ollama_chat:
        mock_ollama_chat.return_value = mock_resp
        payload = {
            "message": "Respond with 'OK' and nothing else.",
            "model": "qwen2.5:0.5b"
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0) as ac:
            response = await ac.post("/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "OK" in data["response"]
        assert data["model"] == "qwen2.5:0.5b"


@pytest.mark.anyio
async def test_chat_nonexistent_model():
    """Test /chat with an invalid model tag to ensure 404 handling without live loading."""
    with patch.object(ollama.AsyncClient, "chat", new_callable=AsyncMock) as mock_ollama_chat:
        mock_ollama_chat.side_effect = ollama.ResponseError(
            error="model 'non_existent_model_12345:xyz' not found",
            status_code=404
        )
        payload = {
            "message": "Hello",
            "model": "non_existent_model_12345:xyz"
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=10.0) as ac:
            response = await ac.post("/chat", json=payload)
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


@pytest.mark.anyio
async def test_unload_model_endpoint():
    """Test /models/unload endpoint."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/models/unload", json={"model_name": "qwen2.5:0.5b"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
