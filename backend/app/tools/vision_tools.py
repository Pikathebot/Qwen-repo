import logging
from pathlib import Path
from typing import Any, Optional

from app.tools.base import BaseTool, ToolResult, PermissionLevel, PermissionDeniedError
from app.tools.filesystem import validate_path
from app.vision.manager import VisionManager

logger = logging.getLogger("jarvis.tools.vision")


class VisionAnalyzeImageTool(BaseTool):
    """
    Analyzes an image inside the workspace using a vision model (Build Plan §18).
    """
    name = "vision.analyze_image"
    description = "Analyze and describe an image file located in the workspace using a vision model."
    permission_level = PermissionLevel.LOW_RISK
    parameters = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the image file inside the workspace"
            },
            "prompt": {
                "type": "string",
                "description": "Specific question or instruction for analyzing the image",
                "default": "Describe this image in detail for a text-based AI"
            }
        },
        "required": ["image_path"]
    }

    def __init__(self, vision_manager: Optional[VisionManager] = None):
        self.vision_manager = vision_manager or VisionManager()

    async def execute(
        self,
        image_path: str,
        prompt: str = "Describe this image in detail for a text-based AI",
        project_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            # 1. Path Sandbox Guard: image must be inside allowed project workspace
            safe_path = validate_path(image_path, project_id=project_id, allowed_folders=allowed_folders)

            if not safe_path.exists() or not safe_path.is_file():
                return ToolResult(status="error", error=f"Image file not found: '{image_path}'")

            # 2. Analyze image
            description = await self.vision_manager.analyze_image(
                image_data=str(safe_path),
                prompt=prompt or "Describe this image in detail for a text-based AI"
            )

            summary = f"Analyzed image '{safe_path.name}' ({len(description)} chars)"
            return ToolResult(
                status="success",
                result=description,
                summary=summary,
                metadata={"image_path": str(safe_path), "prompt": prompt}
            )

        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            logger.warning("Vision analysis error on '%s': %s", image_path, e)
            return ToolResult(status="error", error=f"Vision analysis error: {e}")
