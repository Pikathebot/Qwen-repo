import re
import asyncio
import logging
from typing import Optional
import httpx

from app.search.base import SearchProvider, SearchResult

logger = logging.getLogger("jarvis.search.duckduckgo")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

UNWANTED_HTML_TAGS = [
    "script", "style", "noscript", "header", "footer",
    "nav", "aside", "svg", "form", "iframe", "button", "dialog"
]


class DuckDuckGoProvider(SearchProvider):
    """
    Privacy-respecting local search provider using DuckDuckGo (Build Plan §17).
    No external API keys required.
    """

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout_seconds = timeout_seconds

    async def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        clean_query = (query or "").strip()
        if not clean_query:
            return []

        safe_limit = max(1, min(limit, 10))

        def _sync_ddg_search() -> list[dict]:
            try:
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS

                with DDGS() as ddgs:
                    return list(ddgs.text(clean_query, max_results=safe_limit))
            except Exception as e:
                logger.warning("DuckDuckGo search error for query '%s': %s", clean_query, e)
                return []

        try:
            raw_results = await asyncio.wait_for(
                asyncio.to_thread(_sync_ddg_search),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning("DuckDuckGo search timed out after %.1fs for '%s'", self.timeout_seconds, clean_query)
            return []
        except Exception as e:
            logger.error("Failed executing DuckDuckGo search: %s", e)
            return []

        results: list[SearchResult] = []
        for item in raw_results:
            title = item.get("title") or "Untitled"
            url = item.get("href") or item.get("link") or ""
            snippet = item.get("body") or item.get("snippet") or ""
            if url:
                results.append(SearchResult(title=title.strip(), url=url.strip(), snippet=snippet.strip()))

        return results

    async def extract(self, url: str) -> str:
        clean_url = (url or "").strip()
        if not clean_url:
            return "Error: URL cannot be empty."

        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = "https://" + clean_url

        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=self.timeout_seconds, headers=headers) as client:
                response = await client.get(clean_url)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "").lower()

                if "text/plain" in content_type or "application/json" in content_type or "text/markdown" in content_type:
                    raw_text = response.text
                else:
                    from bs4 import BeautifulSoup
                    import html2text

                    soup = BeautifulSoup(response.text, "html.parser")
                    for tag in soup(UNWANTED_HTML_TAGS):
                        tag.decompose()

                    main_element = soup.find("article") or soup.find("main") or soup.find("body") or soup
                    converter = html2text.HTML2Text()
                    converter.ignore_links = False
                    converter.ignore_images = True
                    converter.body_width = 0
                    converter.single_line_break = False
                    raw_text = converter.handle(str(main_element))

                cleaned = re.sub(r"\n{3,}", "\n\n", raw_text).strip()
                return cleaned or f"Notice: Web page at '{clean_url}' returned empty or non-extractable content."

        except httpx.TimeoutException:
            logger.warning("Timeout fetching URL '%s'", clean_url)
            return f"Error: Request timed out while attempting to load '{clean_url}'."
        except httpx.HTTPStatusError as hse:
            logger.warning("HTTP %s for URL '%s'", hse.response.status_code, clean_url)
            return f"Error: HTTP {hse.response.status_code} ({hse.response.reason_phrase}) when fetching '{clean_url}'."
        except Exception as e:
            logger.error("Error fetching URL '%s': %s", clean_url, e)
            return f"Error fetching web page '{clean_url}': {str(e)}"
