import pytest
from app.tools.base import PermissionLevel
from app.tools.web_tools import WebSearchTool, WebExtractTool
from app.search.base import SearchProvider, SearchResult
from app.search.manager import SearchManager


class MockSearchProvider(SearchProvider):
    async def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        return [
            SearchResult(title="Result 1", url="https://example.com/1", snippet="Snippet 1"),
            SearchResult(title="Result 2", url="https://example.com/2", snippet="Snippet 2"),
        ]

    async def extract(self, url: str) -> str:
        return f"# Article Title\n\nMain content extracted from {url}"


@pytest.fixture
def mock_search_manager():
    return SearchManager(provider=MockSearchProvider(), enabled=True)


def test_web_tools_permission_levels():
    """Verify web search and extraction tools require user confirmation for network access."""
    assert WebSearchTool().permission_level == PermissionLevel.CONFIRMATION_REQUIRED
    assert WebExtractTool().permission_level == PermissionLevel.CONFIRMATION_REQUIRED


@pytest.mark.anyio
async def test_web_search_tool_execute(mock_search_manager):
    tool = WebSearchTool(search_manager=mock_search_manager)
    res = await tool.execute(query="python tutorials", limit=2)

    assert res.status == "success"
    assert "Result 1" in res.result
    assert "https://example.com/1" in res.result
    assert "Snippet 2" in res.result
    assert res.metadata["count"] == 2


@pytest.mark.anyio
async def test_web_search_tool_empty_query(mock_search_manager):
    tool = WebSearchTool(search_manager=mock_search_manager)
    res = await tool.execute(query="")
    assert res.status == "error"
    assert "cannot be empty" in res.error


@pytest.mark.anyio
async def test_web_extract_tool_execute(mock_search_manager):
    tool = WebExtractTool(search_manager=mock_search_manager)
    res = await tool.execute(url="https://example.com/docs")

    assert res.status == "success"
    assert "Article Title" in res.result
    assert "https://example.com/docs" in res.result


@pytest.mark.anyio
async def test_web_extract_tool_empty_url(mock_search_manager):
    tool = WebExtractTool(search_manager=mock_search_manager)
    res = await tool.execute(url="")
    assert res.status == "error"
    assert "cannot be empty" in res.error


@pytest.mark.anyio
async def test_web_tools_disabled_search_rejection():
    disabled_manager = SearchManager(provider=MockSearchProvider(), enabled=False)
    search_tool = WebSearchTool(search_manager=disabled_manager)
    extract_tool = WebExtractTool(search_manager=disabled_manager)

    search_res = await search_tool.execute(query="test")
    assert search_res.status == "error"
    assert "disabled" in search_res.error.lower()

    extract_res = await extract_tool.execute(url="https://example.com")
    assert extract_res.status == "error"
    assert "disabled" in extract_res.error.lower()
