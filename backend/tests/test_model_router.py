from unittest.mock import AsyncMock, patch
import pytest
import httpx
from app.main import app
from app.agent.model_router import ModelRouter, RoutingMode, RoutingDecision
from app.agent.openrouter_client import OpenRouterClient
from app.agent.lmstudio_client import LMStudioClient
from app.agent.orchestrator import AgentOrchestrator


# --- Unit Tests for ModelRouter (Stage B) ---

def test_router_bonsai_default():
    """Verify that when active_backend is 'bonsai', Normal Mode routes to LM Studio with Bonsai 27B."""
    router = ModelRouter(
        default_mode="auto",
        active_backend="bonsai",
        lmstudio_model="prism-ml/bonsai-27b",
        ollama_model="hermes3:8b",
        openrouter_heavy_model="heavy-model"
    )
    decision = router.evaluate("What is the current time?")
    assert decision.mode == "normal"
    assert decision.provider == "lmstudio"
    assert decision.model == "prism-ml/bonsai-27b"


def test_router_hermes3_rollback():
    """Verify that when active_backend is switched to 'hermes3', Normal Mode routes to Ollama."""
    router = ModelRouter(
        default_mode="auto",
        active_backend="hermes3",
        lmstudio_model="prism-ml/bonsai-27b",
        ollama_model="hermes3:8b",
        openrouter_heavy_model="heavy-model"
    )
    decision = router.evaluate("What is the current time?")
    assert decision.mode == "normal"
    assert decision.provider == "ollama"
    assert decision.model == "hermes3:8b"


def test_router_explicit_heavy_mode():
    router = ModelRouter(
        default_mode="auto",
        active_backend="bonsai",
        lmstudio_model="prism-ml/bonsai-27b",
        ollama_model="hermes3:8b",
        openrouter_heavy_model="heavy-model"
    )
    decision = router.evaluate("Hello", requested_mode="heavy")
    assert decision.mode == "heavy"
    assert decision.provider == "openrouter"
    assert decision.model == "heavy-model"


def test_router_explicit_normal_mode():
    router = ModelRouter(
        default_mode="auto",
        active_backend="bonsai",
        lmstudio_model="prism-ml/bonsai-27b",
        ollama_model="hermes3:8b",
        openrouter_heavy_model="heavy-model"
    )
    decision = router.evaluate("Design a distributed system architecture", requested_mode="normal")
    assert decision.mode == "normal"
    assert decision.provider == "lmstudio"
    assert decision.model == "prism-ml/bonsai-27b"


def test_router_heavy_tag_trigger():
    router = ModelRouter(
        default_mode="auto",
        active_backend="bonsai",
        lmstudio_model="prism-ml/bonsai-27b",
        ollama_model="hermes3:8b",
        openrouter_heavy_model="heavy-model"
    )
    decision = router.evaluate("[heavy] please explain this complex quantum equation.")
    assert decision.mode == "heavy"
    assert decision.provider == "openrouter"


def test_router_heavy_task_pattern():
    router = ModelRouter(
        default_mode="auto",
        active_backend="bonsai",
        lmstudio_model="prism-ml/bonsai-27b",
        ollama_model="hermes3:8b",
        openrouter_heavy_model="heavy-model"
    )
    decision = router.evaluate("Help me create a system design for a high-availability microservice architecture.")
    assert decision.mode == "heavy"
    assert decision.provider == "openrouter"


def test_router_custom_model_override():
    router = ModelRouter(
        default_mode="auto",
        active_backend="bonsai",
        lmstudio_model="prism-ml/bonsai-27b",
        ollama_model="hermes3:8b",
        openrouter_heavy_model="heavy-model"
    )
    decision = router.evaluate("Hello", requested_mode="heavy", requested_model="custom/model-x")
    assert decision.model == "custom/model-x"


def test_openrouter_client_unconfigured_error():
    client = OpenRouterClient(api_key=None)
    assert client.is_configured is False
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY is not configured"):
        import asyncio
        asyncio.run(client.chat(messages=[], model="test"))


# --- Integration Tests with FastAPI app ---

@pytest.mark.anyio
async def test_chat_lmstudio_normal_mode_mocked():
    """Verify that Normal Mode runs via LM Studio by default."""
    mock_lmstudio_response = {
        "message": {
            "role": "assistant",
            "content": "Hello from Bonsai 27B running locally in LM Studio.",
            "tool_calls": None
        },
        "raw": {}
    }

    with patch.object(LMStudioClient, "chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_lmstudio_response

        payload = {
            "message": "Hello Jarvis",
            "mode": "normal"
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0) as ac:
            response = await ac.post("/chat", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "lmstudio"
        assert "Bonsai 27B" in data["response"]
        assert data["fallback_used"] is False


@pytest.mark.anyio
async def test_chat_lmstudio_fallback_to_ollama_on_error():
    """Verify that if LM Studio fails, it gracefully falls back to local Ollama."""
    with patch.object(LMStudioClient, "chat", new_callable=AsyncMock) as mock_lm_chat:
        mock_lm_chat.side_effect = RuntimeError("LM Studio connection refused.")

        payload = {
            "message": "Hello, answer with 'TEST_OK'",
            "mode": "normal"
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0) as ac:
            response = await ac.post("/chat", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "ollama"
        assert data["fallback_used"] is True
        assert "Fallback: LM Studio failed" in data["route_reason"]


@pytest.mark.anyio
async def test_chat_heavy_mode_mocked_success():
    """Verify Heavy Mode dispatch to OpenRouter."""
    mock_openrouter_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "This is a detailed heavy reasoning response generated by OpenRouter."
                }
            }
        ]
    }

    with patch.object(OpenRouterClient, "chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_openrouter_response

        payload = {
            "message": "Architect a fault-tolerant distributed consensus engine.",
            "mode": "heavy"
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0) as ac:
            response = await ac.post("/chat", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "openrouter"
        assert "OpenRouter" in data["response"]
        assert data["fallback_used"] is False
        mock_chat.assert_awaited_once()


def test_router_dynamic_backend_flip_without_reinstantiation(monkeypatch):
    """Verify that flipping settings.active_model_backend dynamically updates routing decisions without reinstantiating router."""
    from app.config import settings
    monkeypatch.setattr(settings, "active_model_backend", "bonsai")

    router = ModelRouter()
    d1 = router.evaluate("Hello")
    assert d1.provider == "lmstudio"
    assert d1.model == "prism-ml/bonsai-27b"

    # Flip backend dynamically
    monkeypatch.setattr(settings, "active_model_backend", "hermes3")
    d2 = router.evaluate("Hello")
    assert d2.provider == "ollama"
    assert d2.model == "hermes3:8b"

