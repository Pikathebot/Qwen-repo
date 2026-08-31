import logging
from typing import Tuple

logger = logging.getLogger("jarvis.agent.tool_result_truncator")

DEFAULT_MAX_CHARS = 16000  # ≈ 4000 tokens
TRUNCATION_NOTICE = "\n\n... [Content truncated due to size. Use read_file with line ranges to inspect specific sections.]"


def truncate_tool_result(
    result_text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    notice: str = TRUNCATION_NOTICE
) -> Tuple[str, bool]:
    """
    Safely truncates bulky tool output before feeding into ContextManager to protect KV Cache.
    Returns (truncated_text, was_truncated).
    """
    if not result_text or not isinstance(result_text, str):
        return str(result_text or ""), False

    if len(result_text) <= max_chars:
        return result_text, False

    logger.warning(
        "Tool result exceeded character threshold (%d > %d). Truncating output.",
        len(result_text),
        max_chars
    )
    truncated = result_text[:max_chars] + notice
    return truncated, True
