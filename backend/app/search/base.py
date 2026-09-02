from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchResult:
    """
    Standardized search result container across all search providers (Build Plan §17).
    """
    title: str
    url: str
    snippet: str
    content: Optional[str] = None


class SearchProvider(ABC):
    """
    Abstract interface for search and web extraction providers.
    """

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        """
        Executes a web search query and returns a list of SearchResults.
        """
        pass

    @abstractmethod
    async def extract(self, url: str) -> str:
        """
        Extracts clean readable text or markdown from the target web URL.
        """
        pass
