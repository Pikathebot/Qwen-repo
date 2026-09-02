import os
import base64
import mimetypes
import logging
from pathlib import Path
from typing import Union, Optional
import httpx

from app.config import settings
from app.vision.base import VisionProvider

logger = logging.getLogger("jarvis.vision.openai_compatible")


class OpenAICompatibleVisionProvider(VisionProvider):
    """
    OpenAI-compatible local multimodal vision provider (Build Plan §18).
    Connects to local endpoints (e.g., llama.cpp server, Ollama, LM Studio) hosting a VISION_MODEL.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ):
        self.base_url = (base_url or settings.llama_base_url).rstrip("/")
        self.model = model or getattr(settings, "vision_model", None) or "Qwen2.5-VL-7B-Instruct"
        self.timeout_seconds = timeout_seconds

    def _encode_image_to_data_uri(self, image_data: Union[bytes, str]) -> str:
        """
        Converts image bytes or file path into a base64 data URI string.
        """
        if isinstance(image_data, (str, Path)):
            path_obj = Path(image_data).resolve()
            if not path_obj.exists() or not path_obj.is_file():
                raise FileNotFoundError(f"Image file not found: '{image_data}'")

            mime_type, _ = mimetypes.guess_type(str(path_obj))
            mime_type = mime_type or "image/jpeg"
            raw_bytes = path_obj.read_bytes()
        elif isinstance(image_data, bytes):
            mime_type = "image/jpeg"
            if image_data.startswith(b"\x89PNG\r\n\x1a\n"):
                mime_type = "image/png"
            elif image_data.startswith(b"GIF8"):
                mime_type = "image/gif"
            elif image_data.startswith(b"RIFF") and b"WEBP" in image_data[:16]:
                mime_type = "image/webp"
            raw_bytes = image_data
        else:
            raise TypeError(f"Unsupported image_data type: {type(image_data)}")

        b64_str = base64.b64encode(raw_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{b64_str}"

    async def analyze_image(
        self,
        image_data: Union[bytes, str],
        prompt: str = "Describe this image in detail for a text-based AI",
    ) -> str:
        data_uri = self._encode_image_to_data_uri(image_data)

        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                data = response.json()

                choices = data.get("choices", [])
                if not choices:
                    return "Vision analysis returned no description."

                message = choices[0].get("message", {})
                content = message.get("content", "")
                return content.strip() or "Vision model returned an empty description."

        except httpx.TimeoutException:
            logger.warning("Vision analysis request timed out after %.1fs", self.timeout_seconds)
            raise TimeoutError(f"Vision analysis request timed out after {self.timeout_seconds} seconds.")
        except httpx.HTTPStatusError as hse:
            logger.error("Vision HTTP error %s: %s", hse.response.status_code, hse.response.text)
            raise RuntimeError(f"Vision provider HTTP error {hse.response.status_code}: {hse.response.text}")
        except Exception as e:
            logger.exception("Failed executing vision analysis: %s", e)
            raise RuntimeError(f"Vision analysis error: {e}")
