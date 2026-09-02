import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import httpx

from app.search.base import SearchProvider, SearchResult
from app.search.duckduckgo_provider import DuckDuckGoProvider
from app.search.manager import SearchManager


@pytest.mark.anyio
async def test_duckduckgo_provider_search_empty_query():
    provider = DuckDuckGoProvider()
    results = await provider.search("")
    assert results == []
    results_whitespace = await provider.search("   ")
    assert results_whitespace == []


@pytest.mark.anyio
async def test_duckduckgo_provider_search_mocked():
    sample_raw = [
        {"title": "Python 3.13 Overview", "href": "https://python.org/3.13", "body": "Python 3.13 features nogil."},
        {"title": "FastAPI Guide", "href": "https://fastapi.tiangolo.com", "body": "FastAPI modern async framework."}
    ]

    provider = DuckDuckGoProvider()

    mock_instance = MagicMock()
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.text.return_value = sample_raw

    try:
        patch_target = "ddgs.DDGS"
        import ddgs  # noqa: F401
    except ImportError:
        patch_target = "duckduckgo_search.DDGS"

    with patch(patch_target, return_value=mock_instance):
        results = await provider.search("python features", limit=2)
        assert len(results) == 2
        assert results[0].title == "Python 3.13 Overview"
        assert results[0].url == "https://python.org/3.13"
        assert results[0].snippet == "Python 3.13 features nogil."


@pytest.mark.anyio
async def test_duckduckgo_provider_extract_html_cleaning():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title><script>alert('bad')</script></head>
    <body>
        <nav><a href="/">Nav</a></nav>
        <article>
            <h1>FastAPI Overview</h1>
            <p>FastAPI is high performance and easy to learn.</p>
        </article>
        <footer><p>Footer content</p></footer>
    </body>
    </html>
    """

    provider = DuckDuckGoProvider()

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
    mock_resp.text = html_content

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        extracted = await provider.extract("https://example.com/fastapi")

        assert "FastAPI Overview" in extracted
        assert "FastAPI is high performance" in extracted
        assert "alert('bad')" not in extracted


@pytest.mark.anyio
async def test_duckduckgo_provider_extract_timeout_and_error():
    provider = DuckDuckGoProvider()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Read timeout")
        res = await provider.extract("https://example.com/slow")
        assert "Error: Request timed out" in res


@pytest.mark.anyio
async def test_search_manager_disabled_by_config():
    manager = SearchManager(enabled=False)
    assert manager.is_enabled is False

    with pytest.raises(PermissionError, match="Web search is disabled"):
        await manager.search("python")

    with pytest.raises(PermissionError, match="Web search is disabled"):
        await manager.extract("https://example.com")


@pytest.mark.anyio
async def test_search_manager_enabled_dispatch_and_switching():
    class CustomSearchProvider(SearchProvider):
        async def search(self, query: str, limit: int = 5) -> list[SearchResult]:
            return [SearchResult(title="Custom Title", url="https://custom.com", snippet="Custom snippet")]

        async def extract(self, url: str) -> str:
            return f"Custom extracted text from {url}"

    custom = CustomSearchProvider()
    manager = SearchManager(provider=custom, enabled=True)
    assert manager.get_provider() is custom

    res = await manager.search("test")
    assert len(res) == 1
    assert res[0].title == "Custom Title"

    extracted = await manager.extract("https://custom.com/page")
    assert "Custom extracted text" in extracted

    # Test provider switching
    ddg = DuckDuckGoProvider()
    manager.set_provider(ddg)
    assert manager.get_provider() is ddg
