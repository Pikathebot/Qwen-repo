import pytest
from unittest.mock import MagicMock, patch
import httpx

from app.agent.tools.web_search import web_search
from app.agent.tools.fetch_url import fetch_url
from app.agent.tools.registry import execute_tool, AVAILABLE_TOOLS, TOOL_FUNCTIONS
from app.agent.permissions import (
    RiskTier,
    evaluate_url_risk,
    evaluate_tool_permission,
    BASE_TOOL_RISK_MAP
)


def test_web_search_empty():
    res = web_search("")
    assert "Error: Search query cannot be empty" in res


def test_web_search_mocked():
    sample_results = [
        {"title": "Python 3.13 Overview", "href": "https://python.org/3.13", "body": "Python 3.13 features nogil and JIT."},
        {"title": "FastAPI Guide", "href": "https://fastapi.tiangolo.com", "body": "FastAPI framework, high performance."}
    ]

    mock_instance = MagicMock()
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.text.return_value = sample_results

    try:
        patch_target = "ddgs.DDGS"
        import ddgs  # noqa: F401
    except ImportError:
        patch_target = "duckduckgo_search.DDGS"

    with patch(patch_target, return_value=mock_instance):
        res = web_search("python features", max_results=2)
        assert "Search Results for: \"python features\"" in res
        assert "Python 3.13 Overview" in res
        assert "https://python.org/3.13" in res
        assert "Python 3.13 features nogil and JIT." in res
        assert "FastAPI Guide" in res



def test_fetch_url_empty():
    res = fetch_url("")
    assert "Error: URL cannot be empty" in res


def test_fetch_url_html_cleaning():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title><script>alert('malicious')</script></head>
    <body>
        <nav><a href="/home">Home</a></nav>
        <article>
            <h1>Welcome to FastAPI</h1>
            <p>FastAPI is a modern, fast web framework for building APIs.</p>
        </article>
        <footer><p>Copyright 2026</p></footer>
    </body>
    </html>
    """

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html; charset=utf-8"}
    mock_response.text = html_content

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        res = fetch_url("https://example.com/fastapi")
        assert "Welcome to FastAPI" in res
        assert "FastAPI is a modern, fast web framework" in res
        assert "alert('malicious')" not in res


def test_fetch_url_truncation():
    long_text = "A" * 2000
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/plain"}
    mock_response.text = long_text

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        res = fetch_url("https://example.com/long", max_chars=500)
        assert "Content truncated at 500 characters" in res


def test_evaluate_url_risk_ssrf():
    # Public URLs must be LOW_RISK
    assert evaluate_url_risk("https://google.com") == RiskTier.LOW_RISK
    assert evaluate_url_risk("https://docs.python.org/3/") == RiskTier.LOW_RISK
    assert evaluate_url_risk("http://github.com") == RiskTier.LOW_RISK

    # Loopback / Localhost must be CONFIRMATION_REQUIRED
    assert evaluate_url_risk("http://localhost:8000") == RiskTier.CONFIRMATION_REQUIRED
    assert evaluate_url_risk("http://127.0.0.1:11434") == RiskTier.CONFIRMATION_REQUIRED
    assert evaluate_url_risk("http://0.0.0.0:80") == RiskTier.CONFIRMATION_REQUIRED

    # Private RFC 1918 subnets must be CONFIRMATION_REQUIRED
    assert evaluate_url_risk("http://192.168.1.1/admin") == RiskTier.CONFIRMATION_REQUIRED
    assert evaluate_url_risk("http://10.0.0.5:9000") == RiskTier.CONFIRMATION_REQUIRED
    assert evaluate_url_risk("http://172.16.0.10") == RiskTier.CONFIRMATION_REQUIRED

    # Dangerous non-http protocols must be HIGH_RISK
    assert evaluate_url_risk("file:///C:/Windows/System32/cmd.exe") == RiskTier.HIGH_RISK
    assert evaluate_url_risk("ftp://ftp.example.com") == RiskTier.HIGH_RISK


def test_permission_decision_integration():
    # web_search is auto-approved LOW_RISK
    dec_search = evaluate_tool_permission("web_search", {"query": "latest news"})
    assert dec_search.allowed is True
    assert dec_search.risk_tier == RiskTier.LOW_RISK

    # fetch_url on public URL is auto-approved LOW_RISK
    dec_public = evaluate_tool_permission("fetch_url", {"url": "https://fastapi.tiangolo.com"})
    assert dec_public.allowed is True
    assert dec_public.risk_tier == RiskTier.LOW_RISK

    # fetch_url on internal IP blocks and requests confirmation
    dec_internal = evaluate_tool_permission("fetch_url", {"url": "http://192.168.1.1/router"})
    assert dec_internal.allowed is False
    assert dec_internal.risk_tier == RiskTier.CONFIRMATION_REQUIRED


def test_registry_registration():
    assert "web_search" in TOOL_FUNCTIONS
    assert "fetch_url" in TOOL_FUNCTIONS
    assert web_search in AVAILABLE_TOOLS
    assert fetch_url in AVAILABLE_TOOLS

    # Test execution via execute_tool
    res = execute_tool("web_search", {"query": ""})
    assert "Error: Search query cannot be empty" in res
