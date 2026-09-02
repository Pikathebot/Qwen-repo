"""
Backward-compatibility adapter and re-exports for context compactor.
"""
from app.memory.context_compactor import (
    CompactionSummary,
    ContextCompactor,
    estimate_tokens,
    estimate_messages_tokens,
    prune_tool_outputs,
    summarize_older_turns,
    should_compact,
    compact,
)

__all__ = [
    "CompactionSummary",
    "ContextCompactor",
    "estimate_tokens",
    "estimate_messages_tokens",
    "prune_tool_outputs",
    "summarize_older_turns",
    "should_compact",
    "compact",
]
