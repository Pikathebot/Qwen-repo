import copy
import logging
from typing import Any, Optional
import ollama

logger = logging.getLogger("jarvis.memory.compactor")


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using fast chars/4 heuristic.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    """
    Estimate total token count across a list of message dictionaries.
    """
    total = 0
    for msg in messages:
        total += 4  # overhead per message
        content = msg.get("content", "") or ""
        total += estimate_tokens(content)
        if msg.get("name"):
            total += estimate_tokens(msg["name"])
        if msg.get("tool_calls"):
            total += estimate_tokens(str(msg["tool_calls"]))
    return total


def prune_tool_outputs(
    messages: list[dict[str, Any]],
    char_threshold: int = 200
) -> tuple[list[dict[str, Any]], int]:
    """
    Stage 1 Compaction: Prune bulky tool outputs in older messages.
    """
    pruned_messages = []
    pruned_count = 0

    # Don't prune the very last message if it's a recent tool response
    total_msgs = len(messages)
    for idx, msg in enumerate(messages):
        msg_copy = copy.deepcopy(msg)
        is_recent = (idx >= total_msgs - 2)

        if not is_recent and msg_copy.get("role") == "tool":
            content = msg_copy.get("content", "") or ""
            if len(content) > char_threshold:
                preview = content[:60].replace("\n", " ")
                msg_copy["content"] = f"{preview}... [Tool output pruned: {len(content)} chars]"
                pruned_count += 1

        pruned_messages.append(msg_copy)

    return pruned_messages, pruned_count


async def summarize_older_turns(
    messages: list[dict[str, Any]],
    client: ollama.AsyncClient,
    model: str,
    keep_recent_count: int = 4
) -> list[dict[str, Any]]:
    """
    Stage 2 Compaction: Summarize the older segment of the conversation into concise facts.
    """
    if len(messages) <= keep_recent_count:
        return messages

    split_index = max(1, len(messages) - keep_recent_count)
    older_segment = messages[:split_index]
    recent_segment = messages[split_index:]

    # Format text for summarization
    formatted_lines = []
    for m in older_segment:
        role = m.get("role", "unknown").upper()
        content = m.get("content", "")
        formatted_lines.append(f"{role}: {content}")

    transcript = "\n".join(formatted_lines)
    summary_prompt = (
        "You are an expert memory compactor. Below is an earlier segment of a conversation. "
        "Extract and summarize the key facts, user preferences, decisions, and file names "
        "into concise bullet points:\n\n"
        f"{transcript}\n\n"
        "Bullet Points of Key Facts:"
    )

    try:
        summary_res = await client.chat(
            model=model,
            messages=[{"role": "user", "content": summary_prompt}]
        )
        summary_content = ""
        if isinstance(summary_res, dict):
            summary_content = summary_res.get("message", {}).get("content", "")
        else:
            summary_content = getattr(summary_res.message, "content", "")

        summary_msg = {
            "role": "system",
            "content": f"[Previous Conversation Context & Summary]\n{summary_content}",
            "is_summary": True
        }

        return [summary_msg] + recent_segment

    except Exception as e:
        logger.error("Failed to generate LLM summary for compaction: %s", e)
        # Fallback: Keep oldest system message + recent segment
        return recent_segment


class ContextCompactor:
    """
    Evaluates conversation token limits and applies progressive compaction.
    """

    def __init__(
        self,
        max_context_tokens: int = 16000,
        tool_pruning_char_threshold: int = 200
    ):
        self.max_context_tokens = max_context_tokens
        self.tool_pruning_char_threshold = tool_pruning_char_threshold

    async def compact(
        self,
        messages: list[dict[str, Any]],
        client: ollama.AsyncClient,
        model: str,
        threshold_override: Optional[int] = None
    ) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
        """
        Progressively compact message history if estimated tokens exceed threshold.
        """
        threshold = threshold_override or self.max_context_tokens
        tokens_before = estimate_messages_tokens(messages)

        if tokens_before <= threshold:
            return messages, None

        logger.info(
            "Context compaction triggered: %d tokens exceeds threshold (%d)",
            tokens_before, threshold
        )

        # Stage 1: Prune bulky tool outputs
        pruned_msgs, pruned_count = prune_tool_outputs(
            messages,
            char_threshold=self.tool_pruning_char_threshold
        )
        tokens_stage1 = estimate_messages_tokens(pruned_msgs)

        if tokens_stage1 <= threshold and pruned_count > 0:
            logger.info("Stage 1 compaction (tool pruning) resolved token load: %d -> %d", tokens_before, tokens_stage1)
            return pruned_msgs, {
                "strategy": "tool_pruning",
                "tokens_before": tokens_before,
                "tokens_after": tokens_stage1,
                "details": f"Pruned {pruned_count} bulky tool outputs"
            }

        # Stage 2: LLM Summarization of older turns
        summarized_msgs = await summarize_older_turns(
            pruned_msgs,
            client=client,
            model=model
        )
        tokens_stage2 = estimate_messages_tokens(summarized_msgs)

        logger.info("Stage 2 compaction (summarization) completed: %d -> %d", tokens_before, tokens_stage2)
        return summarized_msgs, {
            "strategy": "summarization",
            "tokens_before": tokens_before,
            "tokens_after": tokens_stage2,
            "details": f"Summarized earlier conversation history ({tokens_before} -> {tokens_stage2} tokens)"
        }
