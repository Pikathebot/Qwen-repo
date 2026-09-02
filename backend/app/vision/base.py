from abc import ABC, abstractmethod
from typing import Union


class VisionProvider(ABC):
    """
    Abstract interface for multimodal vision analysis providers (Build Plan §18).
    """

    @abstractmethod
    async def analyze_image(
        self,
        image_data: Union[bytes, str],
        prompt: str = "Describe this image in detail for a text-based AI",
    ) -> str:
        """
        Analyzes an image and returns a detailed textual description.
        Accepts raw image bytes or a string filesystem path.
        """
        pass
