import pytest
from pathlib import Path

from app.tools.base import PermissionLevel
from app.tools.vision_tools import VisionAnalyzeImageTool
from app.vision.base import VisionProvider
from app.vision.manager import VisionManager


class MockVisionProvider(VisionProvider):
    async def analyze_image(self, image_data, prompt="..."):
        return f"Mock visual description of '{image_data}' for prompt: '{prompt}'"


@pytest.fixture
def mock_vision_manager():
    return VisionManager(provider=MockVisionProvider())


def test_vision_tool_permission_level():
    """Verify vision analysis tool is LOW_RISK for local image processing."""
    assert VisionAnalyzeImageTool().permission_level == PermissionLevel.LOW_RISK


@pytest.mark.anyio
async def test_vision_tool_analyze_image_success(tmp_path, mock_vision_manager):
    img_file = tmp_path / "app_ui.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00mock_image_bytes")

    tool = VisionAnalyzeImageTool(vision_manager=mock_vision_manager)
    res = await tool.execute(
        image_path=str(img_file),
        prompt="Explain what buttons are in this UI",
        allowed_folders=[tmp_path]
    )

    assert res.status == "success"
    assert "Mock visual description" in res.result
    assert "Explain what buttons" in res.result
    assert "app_ui.png" in res.summary


@pytest.mark.anyio
async def test_vision_tool_missing_file_error(tmp_path, mock_vision_manager):
    tool = VisionAnalyzeImageTool(vision_manager=mock_vision_manager)
    res = await tool.execute(
        image_path=str(tmp_path / "ghost.png"),
        allowed_folders=[tmp_path]
    )
    assert res.status == "error"
    assert "not found" in res.error.lower()


@pytest.mark.anyio
async def test_vision_tool_sandbox_boundary_enforcement(tmp_path, mock_vision_manager):
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    outside_dir = tmp_path / "outside_forbidden"
    outside_dir.mkdir()

    outside_img = outside_dir / "confidential.png"
    outside_img.write_bytes(b"\x89PNG\r\n\x1a\n")

    tool = VisionAnalyzeImageTool(vision_manager=mock_vision_manager)
    res = await tool.execute(
        image_path=str(outside_img),
        allowed_folders=[sandbox_dir]
    )

    assert res.status == "error"
    assert "Access denied" in res.error or "outside the allowed project sandbox" in res.error
