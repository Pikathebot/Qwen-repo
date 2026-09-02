import logging
from typing import Union, Optional
from pathlib import Path

from app.vision.base import VisionProvider
from app.vision.openai_compatible import OpenAICompatibleVisionProvider

logger = logging.getLogger("jarvis.vision.manager")


class VisionManager:
    """
    Central vision manager routing image analysis requests to active VisionProvider (Build Plan §18).
    """

    def __init__(self, provider: Optional[VisionProvider] = None):
        self._provider: VisionProvider = provider or OpenAICompatibleVisionProvider()

    def get_provider(self) -> VisionProvider:
        return self._provider

    def set_provider(self, provider: VisionProvider) -> None:
        if not isinstance(provider, VisionProvider):
            raise TypeError(f"Expected VisionProvider instance, got {type(provider)}")
        logger.info("Switched active VisionProvider to %s", provider.__class__.__name__)
        self._provider = provider

    async def analyze_image(
        self,
        image_data: Union[bytes, str],
        prompt: str = "Describe this image in detail for a text-based AI",
    ) -> str:
        if isinstance(image_data, (str, Path)):
            path_obj = Path(image_data).resolve()
            if not path_obj.exists() or not path_obj.is_file():
                raise FileNotFoundError(f"Image file not found: '{image_data}'")

        return await self._provider.analyze_image(image_data=image_data, prompt=prompt)
