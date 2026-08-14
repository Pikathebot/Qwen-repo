import logging
from typing import Any, Optional
import httpx

logger = logging.getLogger("jarvis.agent.openrouter")


class OpenRouterClient:
    """
    Asynchronous client for OpenRouter API completions.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        timeout: float = 60.0
    ) -> dict[str, Any]:
        """
        Send a chat completion request to OpenRouter.
        """
        if not self.is_configured:
            raise ValueError("OPENROUTER_API_KEY is not configured in environment/.env.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/jarvis-assistant",
            "X-Title": "Local Jarvis Assistant",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        url = f"{self.base_url}/chat/completions"
        logger.info("Dispatching request to OpenRouter model '%s'", model)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException:
                logger.error("OpenRouter request timed out after %.1fs", timeout)
                raise RuntimeError(f"OpenRouter request timed out after {timeout} seconds.")
            except Exception as e:
                logger.error("OpenRouter connection error: %s", e)
                raise RuntimeError(f"OpenRouter connection error: {str(e)}")

        if response.status_code == 401:
            raise RuntimeError("OpenRouter authentication failed: Invalid or missing API key.")
        elif response.status_code == 429:
            raise RuntimeError("OpenRouter rate limit reached (HTTP 429).")
        elif response.status_code != 200:
            raise RuntimeError(f"OpenRouter error (HTTP {response.status_code}): {response.text}")

        data = response.json()
        return data
