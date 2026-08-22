import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from app.agent.lmstudio_client import LMStudioClient, convert_tool_to_openai_schema
from app.agent.tools.registry import read_file, web_search, write_file


def test_convert_tool_to_openai_schema_callable():
    schema = convert_tool_to_openai_schema(read_file)
    assert schema is not None
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "read_file"
    assert "file_path" in schema["function"]["parameters"]["properties"]
    assert "file_path" in schema["function"]["parameters"]["required"]


def test_convert_tool_to_openai_schema_mcp_dict():
    mcp_dict = {
        "type": "function",
        "function": {
            "name": "system_diagnostics",
            "description": "System diagnostic metrics",
            "parameters": {
                "type": "object",
                "properties": {"detail_level": {"type": "string"}},
                "required": []
            }
        }
    }
    converted = convert_tool_to_openai_schema(mcp_dict)
    assert converted == mcp_dict


@pytest.mark.anyio
async def test_lmstudio_client_is_available():
    client = LMStudioClient(base_url="http://localhost:1234/v1")
    
    # Mock successful /models response
    mock_resp = MagicMock(status_code=200)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        is_avail = await client.is_available()
        assert is_avail is True

    # Mock unreachable server
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")
        is_avail = await client.is_available()
        assert is_avail is False


@pytest.mark.anyio
async def test_lmstudio_client_list_models():
    client = LMStudioClient(base_url="http://localhost:1234/v1")
    mock_resp = MagicMock(
        status_code=200,
        json=lambda: {"data": [{"id": "prism-ml/bonsai-27b"}, {"id": "hermes3:8b"}]}
    )
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        models = await client.list_models()
        assert models == ["prism-ml/bonsai-27b", "hermes3:8b"]


@pytest.mark.anyio
async def test_lmstudio_client_chat_with_tools():
    client = LMStudioClient(base_url="http://localhost:1234/v1")
    mock_api_response = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Searching the web...",
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": '{"query": "quantum computing news"}'
                            }
                        }
                    ]
                }
            }
        ]
    }
    mock_resp = MagicMock(status_code=200, json=lambda: mock_api_response)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.chat(
            messages=[{"role": "user", "content": "Search for quantum news"}],
            model="prism-ml/bonsai-27b",
            tools=[web_search]
        )
        assert result["message"]["content"] == "Searching the web..."
        assert len(result["message"]["tool_calls"]) == 1
        tc = result["message"]["tool_calls"][0]
        assert tc["function"]["name"] == "web_search"
        assert tc["function"]["arguments"] == {"query": "quantum computing news"}


@pytest.mark.anyio
async def test_lmstudio_client_unload_success():
    client = LMStudioClient(base_url="http://localhost:1234/v1")
    
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Unloaded 1 model.", b"")

    with patch("shutil.which", return_value="C:\\Fake\\lms.exe"), \
         patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        unloaded = await client.unload_model("prism-ml/bonsai-27b")
        assert unloaded is True


@pytest.mark.anyio
async def test_lmstudio_client_unload_missing_cli():
    client = LMStudioClient(base_url="http://localhost:1234/v1")

    with patch("shutil.which", return_value=None), \
         patch("os.path.exists", return_value=False):
        unloaded = await client.unload_model("prism-ml/bonsai-27b")
        assert unloaded is False


@pytest.mark.anyio
async def test_lmstudio_client_load_cli_success():
    client = LMStudioClient(base_url="http://localhost:1234/v1")

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Loaded model successfully.", b"")

    with patch("shutil.which", return_value="C:\\Fake\\lms.exe"), \
         patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        loaded = await client.load_model("prism-ml/bonsai-27b")
        assert loaded is True


@pytest.mark.anyio
async def test_lmstudio_client_load_http_fallback():
    client = LMStudioClient(base_url="http://localhost:1234/v1")

    with patch("shutil.which", return_value=None), \
         patch("os.path.exists", return_value=False), \
         patch.object(client, "chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"message": {"content": "pong"}}
        loaded = await client.load_model("prism-ml/bonsai-27b")
        assert loaded is True
        mock_chat.assert_awaited_once()

