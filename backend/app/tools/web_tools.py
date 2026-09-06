import logging
from typing import Any, Optional

from app.tools.base import BaseTool, ToolResult, PermissionLevel, PermissionDeniedError
from app.search.manager import SearchManager

logger = logging.getLogger("jarvis.tools.web")


class WebSearchTool(BaseTool):
    """
    Searches the web for information using a privacy-respecting search engine (Build Plan §17).
    """
    name = "web.search"
    description = "Search the web for current online information, software documentation, and news."
    permission_level = PermissionLevel.CONFIRMATION_REQUIRED
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query keywords"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of search results to return (default 5)",
                "default": 5
            }
        },
        "required": ["query"]
    }

    def __init__(self, search_manager: Optional[SearchManager] = None):
        self.search_manager = search_manager or SearchManager()

    async def execute(
        self,
        query: str,
        limit: int = 5,
        **kwargs: Any
    ) -> ToolResult:
        clean_query = (query or "").strip()
        if not clean_query:
            return ToolResult(status="error", error="Search query cannot be empty.")

        try:
            results = await self.search_manager.search(query=clean_query, limit=limit)
            if not results:
                return ToolResult(
                    status="success",
                    result=f"No search results found for query: '{clean_query}'.",
                    summary="No search results found",
                    metadata={"query": clean_query, "count": 0}
                )

            formatted_cards = []
            for idx, item in enumerate(results, start=1):
                card = f"### [{idx}] {item.title}\n- **URL**: {item.url}\n- **Summary**: {item.snippet}"
                formatted_cards.append(card)

            output = f"## Search Results for: \"{clean_query}\"\n\n" + "\n\n".join(formatted_cards)
            summary = f"Retrieved {len(results)} web search result(s) for '{clean_query}'"

            return ToolResult(
                status="success",
                result=output,
                summary=summary,
                metadata={"query": clean_query, "count": len(results)}
            )

        except PermissionError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            logger.warning("Web search tool error for '%s': %s", clean_query, e)
            return ToolResult(status="error", error=f"Web search error: {e}")


class WebExtractTool(BaseTool):
    """
    Fetches and extracts clean readable text/markdown from a web URL (Build Plan §17).
    """
    name = "web.extract"
    description = "Fetch and extract readable text content from a web page URL."
    permission_level = PermissionLevel.CONFIRMATION_REQUIRED
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The web URL to fetch and extract content from"
            }
        },
        "required": ["url"]
    }

    def __init__(self, search_manager: Optional[SearchManager] = None):
        self.search_manager = search_manager or SearchManager()

    async def execute(
        self,
        url: str,
        **kwargs: Any
    ) -> ToolResult:
        clean_url = (url or "").strip()
        if not clean_url:
            return ToolResult(status="error", error="URL cannot be empty.")

        try:
            content = await self.search_manager.extract(url=clean_url)
            summary = f"Extracted content from '{clean_url}' ({len(content)} chars)"

            return ToolResult(
                status="success",
                result=content,
                summary=summary,
                metadata={"url": clean_url, "length": len(content)}
            )

        except PermissionError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            logger.warning("Web extract tool error for '%s': %s", clean_url, e)
            return ToolResult(status="error", error=f"Web extraction error: {e}")
