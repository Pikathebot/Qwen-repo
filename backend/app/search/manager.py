import logging
from typing import Optional

from app.config import settings
from app.search.base import SearchProvider, SearchResult
from app.search.duckduckgo_provider import DuckDuckGoProvider

logger = logging.getLogger("jarvis.search.manager")


class SearchManager:
    """
    Central search manager managing search providers and enforcing configuration gates (Build Plan §17).
    """

    def __init__(
        self,
        provider: Optional[SearchProvider] = None,
        enabled: Optional[bool] = None,
    ):
        self._provider: SearchProvider = provider or DuckDuckGoProvider()
        self._enabled: bool = enabled if enabled is not None else getattr(settings, "web_search_enabled", False)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @is_enabled.setter
    def is_enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    def get_provider(self) -> SearchProvider:
        return self._provider

    def set_provider(self, provider: SearchProvider) -> None:
        if not isinstance(provider, SearchProvider):
            raise TypeError(f"Expected SearchProvider instance, got {type(provider)}")
        logger.info("Switched active SearchProvider to %s", provider.__class__.__name__)
        self._provider = provider

    async def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        if not self._enabled:
            raise PermissionError("Web search is disabled in configuration.")
        return await self._provider.search(query=query, limit=limit)

    async def extract(self, url: str) -> str:
        if not self._enabled:
            raise PermissionError("Web search is disabled in configuration.")
        return await self._provider.extract(url=url)
