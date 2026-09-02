import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import httpx

from app.vision.base import VisionProvider
from app.vision.openai_compatible import OpenAICompatibleVisionProvider
from app.vision.manager import VisionManager


def test_vision_provider_base64_encoding_file(tmp_path):
    img_file = tmp_path / "diagram.png"
    # Write mock PNG header bytes
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    provider = OpenAICompatibleVisionProvider()
    data_uri = provider._encode_image_to_data_uri(str(img_file))

    assert data_uri.startswith("data:image/png;base64,")
    assert len(data_uri) > len("data:image/png;base64,")


def test_vision_provider_base64_encoding_bytes():
    mock_jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    provider = OpenAICompatibleVisionProvider()
    data_uri = provider._encode_image_to_data_uri(mock_jpeg_bytes)

    assert data_uri.startswith("data:image/jpeg;base64,")


@pytest.mark.anyio
async def test_vision_provider_openai_compatible_dispatch_mocked(tmp_path):
    img_file = tmp_path / "screenshot.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIFmock_data")

    provider = OpenAICompatibleVisionProvider(
        base_url="http://127.0.0.1:8001/v1",
        model="Qwen2.5-VL-7B-Instruct"
    )

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "The image displays a modern software architecture diagram with a gateway."
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        desc = await provider.analyze_image(str(img_file), prompt="Describe this diagram")

        assert "software architecture diagram" in desc
        assert mock_post.called
        call_args = mock_post.call_args
        endpoint = call_args[0][0]
        assert endpoint == "http://127.0.0.1:8001/v1/chat/completions"
        payload = call_args[1]["json"]
        assert payload["model"] == "Qwen2.5-VL-7B-Instruct"
        assert len(payload["messages"][0]["content"]) == 2


@pytest.mark.anyio
async def test_vision_provider_timeout_handling(tmp_path):
    img_file = tmp_path / "photo.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n")

    provider = OpenAICompatibleVisionProvider(timeout_seconds=0.5)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timed out")
        with pytest.raises(TimeoutError, match="timed out"):
            await provider.analyze_image(str(img_file))


@pytest.mark.anyio
async def test_vision_manager_analyze_and_switching(tmp_path):
    class MockVisionProvider(VisionProvider):
        async def analyze_image(self, image_data, prompt="..."):
            return f"Mock description for {len(image_data)} items"

    mock_p = MockVisionProvider()
    manager = VisionManager(provider=mock_p)
    assert manager.get_provider() is mock_p

    res = await manager.analyze_image(b"fake_bytes", prompt="Analyze")
    assert "Mock description" in res

    # Missing file check
    with pytest.raises(FileNotFoundError, match="Image file not found"):
        await manager.analyze_image(str(tmp_path / "non_existent.png"))
