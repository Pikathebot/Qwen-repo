import pytest
import httpx
from app.main import app

@pytest.mark.anyio
async def test_health_check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ollama_connected"] is True
    assert "qwen2.5:0.5b" in data["available_models"]

@pytest.mark.anyio
async def test_chat_with_model():
    """Test /chat using the lightweight test model (qwen2.5:0.5b)."""
    payload = {
        "message": "Respond with 'OK' and nothing else.",
        "model": "qwen2.5:0.5b"
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0) as ac:
        response = await ac.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert len(data["response"]) > 0
    assert data["model"] == "qwen2.5:0.5b"

@pytest.mark.anyio
async def test_chat_nonexistent_model():
    """Test /chat with an invalid model tag to ensure 404 handling."""
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
