import logging
import re
from typing import Optional
import httpx

logger = logging.getLogger("jarvis.agent.tools.fetch_url")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

UNWANTED_TAGS = [
    "script", "style", "noscript", "header", "footer", 
    "nav", "aside", "svg", "form", "iframe", "button", "dialog"
]


def fetch_url(url: str, max_chars: int = 8000) -> str:
    """
    Fetch the content of a web page URL and return its main article text converted to clean markdown.
    Automatically strips ads, headers, scripts, and footers, and limits length to fit the LLM context window.

    Args:
        url: The web URL to fetch (e.g. 'https://docs.python.org/3/whatsnew/3.12.html').
        max_chars: Maximum character budget to return (default 8000, maximum 25000).
    """
    clean_url = str(url or "").strip()
    if not clean_url:
        return "Error: URL cannot be empty."

    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    limit = max(500, min(int(max_chars), 25000))

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        with httpx.Client(follow_redirects=True, timeout=15.0, headers=headers) as client:
            response = client.get(clean_url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()

            # If plain text, json, or markdown
            if "text/plain" in content_type or "application/json" in content_type or "text/markdown" in content_type:
                text = response.text
            else:
                # Parse HTML
                from bs4 import BeautifulSoup
                import html2text

                soup = BeautifulSoup(response.text, "html.parser")

                # Remove non-content tags
                for tag in soup(UNWANTED_TAGS):
                    tag.decompose()

                # Extract main content container if available
                main_element = soup.find("article") or soup.find("main") or soup.find("body") or soup

                converter = html2text.HTML2Text()
                converter.ignore_links = False
                converter.ignore_images = True
                converter.body_width = 0
                converter.single_line_break = False

                text = converter.handle(str(main_element))

            # Normalize excess blank lines
            cleaned_text = re.sub(r"\n{3,}", "\n\n", text).strip()

            if not cleaned_text:
                return f"Notice: Web page at '{clean_url}' returned empty or non-extractable content."

            if len(cleaned_text) > limit:
                truncated = cleaned_text[:limit]
                return f"## Content from: {clean_url}\n\n{truncated}\n\n... [Content truncated at {limit} characters to conserve context tokens]."

            return f"## Content from: {clean_url}\n\n{cleaned_text}"

    except httpx.TimeoutException:
        logger.warning("Timeout fetching URL: %s", clean_url)
        return f"Error: Request timed out while attempting to load '{clean_url}'."
    except httpx.HTTPStatusError as hse:
        logger.warning("HTTP status %s for URL: %s", hse.response.status_code, clean_url)
        return f"Error: HTTP {hse.response.status_code} ({hse.response.reason_phrase}) when fetching '{clean_url}'."
    except Exception as e:
        logger.error("Error fetching URL '%s': %s", clean_url, e)
        return f"Error fetching web page '{clean_url}': {str(e)}"
