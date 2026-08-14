import logging
from typing import Optional

logger = logging.getLogger("jarvis.agent.tools.web_search")


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo for live information, current documentation, latest news, or facts.
    Returns structured markdown with titles, URLs, and concise snippets.

    Args:
        query: The search query string (e.g. 'Python 3.13 release date', 'FastAPI background tasks').
        max_results: Maximum number of top results to retrieve (default 5, maximum 10).
    """
    clean_query = str(query or "").strip()
    if not clean_query:
        return "Error: Search query cannot be empty."

    # Clamp max_results between 1 and 10 to protect context window tokens
    limit = max(1, min(int(max_results), 10))

    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(clean_query, max_results=limit))


        if not raw_results:
            return f"No search results found for query: '{clean_query}'."

        formatted_cards = []
        for idx, item in enumerate(raw_results, start=1):
            title = item.get("title", "Untitled").strip()
            href = item.get("href", "").strip()
            snippet = item.get("body", "").strip()

            card = f"### [{idx}] {title}\n- **URL**: {href}\n- **Summary**: {snippet}"
            formatted_cards.append(card)

        output = f"## Search Results for: \"{clean_query}\"\n\n" + "\n\n".join(formatted_cards)
        return output

    except ImportError:
        logger.error("duckduckgo_search library is not installed.")
        return "Error: 'duckduckgo_search' package is missing. Please install it with 'pip install duckduckgo_search'."
    except Exception as e:
        logger.warning("Web search failed for '%s': %s", clean_query, e)
        return f"Error during web search for '{clean_query}': {str(e)}"
