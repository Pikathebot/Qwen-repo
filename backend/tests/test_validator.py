import pytest
from pydantic import BaseModel, Field
from app.agent.validator import validate_tool_call, CallHistory, ValidationResult
from app.agent.tools.registry import get_tool_schema, WebSearchArgs, FetchUrlArgs


class SampleSchema(BaseModel):
    query: str
    count: int = Field(default=5, ge=1, le=10)


@pytest.mark.anyio
async def test_validate_tool_call_valid():
    res = await validate_tool_call("web_search", {"query": "python news", "max_results": 3}, WebSearchArgs)
    assert res.valid is True
    assert res.tool_name == "web_search"
    assert res.args["query"] == "python news"
    assert res.args["max_results"] == 3
    assert res.error is None
    assert res.repair_attempt == 0


@pytest.mark.anyio
async def test_validate_tool_call_invalid_missing_field():
    # web_search requires 'query'
    res = await validate_tool_call("web_search", {"max_results": 3}, WebSearchArgs, repair_attempt=0)
    assert res.valid is False
    assert res.tool_name == "web_search"
    assert "query" in res.error
    assert res.repair_attempt == 0


@pytest.mark.anyio
async def test_validate_tool_call_invalid_out_of_bounds():
    # max_results exceeds le=10 constraint
    res = await validate_tool_call("web_search", {"query": "test", "max_results": 999}, WebSearchArgs)
    assert res.valid is False
    assert "max_results" in res.error


@pytest.mark.anyio
async def test_validate_tool_call_none_schema_passes():
    res = await validate_tool_call("custom_tool", {"foo": "bar"}, schema=None)
    assert res.valid is True
    assert res.args == {"foo": "bar"}


@pytest.mark.anyio
async def test_validate_tool_call_non_dict_args():
    res = await validate_tool_call("web_search", "not a dict", WebSearchArgs)
    assert res.valid is False
    assert "dictionary" in res.error.lower()


def test_call_history_duplicate_detection():
    history = CallHistory(window=3)
    assert history.is_duplicate("web_search", {"query": "test"}) is False

    # Record first invocation
    history.record("web_search", {"query": "test"})
    # Immediate identical duplicate invocation should be detected
    assert history.is_duplicate("web_search", {"query": "test"}) is True

    # Different query is not duplicate
    assert history.is_duplicate("web_search", {"query": "different"}) is False
    history.record("web_search", {"query": "different"})

    # Now the preceding call is 'different', so 'test' is no longer consecutive duplicate
    assert history.is_duplicate("web_search", {"query": "test"}) is False


def test_call_history_canonicalization_arg_ordering():
    history = CallHistory(window=3)
    args1 = {"a": 1, "b": 2, "c": 3}
    args2 = {"c": 3, "a": 1, "b": 2}

    history.record("my_tool", args1)
    # args2 has different key ordering but same canonical representation
    assert history.is_duplicate("my_tool", args2) is True


def test_call_history_nested_dict_canonicalization():
    history = CallHistory(window=3)
    args1 = {"config": {"retries": 3, "timeout": 30}, "user": "alice"}
    args2 = {"user": "alice", "config": {"timeout": 30, "retries": 3}}

    history.record("my_tool", args1)
    assert history.is_duplicate("my_tool", args2) is True


def test_call_history_window_eviction():
    history = CallHistory(window=2)
    history.record("tool_a", {"x": 1})
    history.record("tool_b", {"x": 2})
    history.record("tool_c", {"x": 3})

    assert len(history.history) == 2
    assert history.history[0][0] == "tool_b"
    assert history.history[1][0] == "tool_c"
