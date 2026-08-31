import json
import logging
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.config import settings
from app.memory.token_counter import TokenCounter
from app.memory.store import MemoryStore

logger = logging.getLogger("jarvis.memory.context_manager")


class ContextPackage(BaseModel):
    """
    Structured context package output by ContextManager.
    Passed directly to LLM inference runtime and frontend observability panels.
    """
    system_prompt: str
    messages: list[dict[str, Any]]
    total_tokens: int
    retrieved_chunks_used: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks_dropped: list[dict[str, Any]] = Field(default_factory=list)
    budget_report: dict[str, Any] = Field(default_factory=dict)


class ContextManager:
    """
    Context Manager Engine complying with Build Plan Sections 4, 5, and 29.
    Enforces strict Tier-Based Token Budgeting to guarantee 8GB VRAM KV Cache safety.
    """

    def __init__(
        self,
        memory_store: Optional[MemoryStore] = None,
        token_counter: Optional[TokenCounter] = None,
        reserved_output_tokens: Optional[int] = None,
        max_attachment_tokens: Optional[int] = None,
    ):
        self.memory_store = memory_store or MemoryStore()
        self.token_counter = token_counter or TokenCounter()
        self.reserved_output_tokens = (
            reserved_output_tokens
            if reserved_output_tokens is not None
            else settings.context_reserved_output_tokens
        )
        self.max_attachment_tokens = (
            max_attachment_tokens
            if max_attachment_tokens is not None
            else settings.context_tier2_max_attachment_tokens
        )

    # File extensions we are willing to read and inject as text into context
    _TEXT_EXTS = {
        ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".json", ".yaml", ".yml",
        ".cpp", ".c", ".h", ".hpp", ".cs", ".ini", ".csv", ".html", ".css",
        ".svg", ".sh", ".rs", ".go", ".java", ".rb", ".php", ".toml", ".cfg",
        ".log", ".xml", ".env", ".gitignore"
    }
    _MAX_FILE_READ_BYTES = 16_000  # 16KB hard read cap per file

    def _read_attachment_content(self, att: Any) -> tuple[str, str]:
        """
        Given an attachment dict (or object), return (filename, text_content).
        Falls back to reading from disk via the 'path' field when 'content' is absent.
        Returns ("", "") if nothing readable is found.
        """
        import os
        from pathlib import Path

        fname = (
            getattr(att, "filename", None)
            or (att.get("filename") if isinstance(att, dict) else None)
            or "attached_file"
        )
        # 1. Prefer inline content if present (rare — future-proofing)
        content = (
            getattr(att, "content", None)
            or (att.get("content") if isinstance(att, dict) else None)
            or ""
        )
        if content:
            return fname, content

        # 2. Fall back: read from disk via path
        fpath = (
            getattr(att, "path", None)
            or (att.get("path") if isinstance(att, dict) else None)
            or ""
        )
        if not fpath:
            return fname, ""

        ext = os.path.splitext(fname)[1].lower()
        if ext not in self._TEXT_EXTS:
            # Binary/non-text: give the model the path so it can use a tool to read it
            return fname, f"[Binary or unsupported file type. Path on disk: {fpath}]"

        try:
            p = Path(fpath)
            if not p.exists() or not p.is_file():
                return fname, f"[File not found on disk at: {fpath}]"
            raw = p.read_text(encoding="utf-8", errors="replace")
            if len(raw) > self._MAX_FILE_READ_BYTES:
                raw = raw[: self._MAX_FILE_READ_BYTES] + "\n\n... [File truncated at 16KB. Use filesystem.read tool for the full content.]"
            return fname, raw
        except Exception as e:
            logger.warning("Could not read attachment '%s' from disk: %s", fpath, e)
            return fname, f"[Could not read file: {e}]"

    def _format_attachment_text(self, attachments: list[Any]) -> str:
        """
        Extract attachment text and enforce Amendment 1 attachment size safeguard.
        Reads file content from disk when inline 'content' field is absent.
        """
        if not attachments:
            return ""

        parts = []
        for att in attachments:
            fname, content = self._read_attachment_content(att)
            if content:
                parts.append(f"--- Attachment: {fname} ---\n{content}")

        combined_text = "\n\n".join(parts)
        if not combined_text:
            return ""

        token_cost = self.token_counter.count(combined_text)
        if token_cost > self.max_attachment_tokens:
            logger.warning(
                "Attachment payload (%d tokens) exceeded Tier 2 cap (%d tokens). Truncating attachment.",
                token_cost,
                self.max_attachment_tokens
            )
            max_chars = int(self.max_attachment_tokens * self.token_counter.chars_per_token)
            truncated_text = combined_text[:max_chars]
            combined_text = (
                f"{truncated_text}\n\n"
                "[Attachment truncated due to size. The full document has been indexed and is available via workspace search.]"
            )

        return combined_text

    def _format_rag_chunk(self, chunk: dict[str, Any]) -> str:
        """Format an individual RAG chunk into a concise Markdown code block."""
        file_path = chunk.get("file_path") or chunk.get("file_name") or "unknown"
        start_line = chunk.get("start_line")
        end_line = chunk.get("end_line")
        symbol = chunk.get("symbol_name")
        content = (chunk.get("content") or "").strip()

        loc_str = f"L{start_line}-L{end_line}" if start_line and end_line else ""
        sym_str = f" ({symbol})" if symbol else ""
        header = f"--- Context: {file_path} {loc_str}{sym_str} ---"
        return f"{header}\n{content}"

    def build_context(
        self,
        session_id: Optional[str] = None,
        user_message: str = "",
        system_prompt: Optional[str] = None,
        project_id: Optional[str] = None,
        project_instructions: Optional[str] = None,
        attachments: Optional[list[Any]] = None,
        retrieved_chunks: Optional[list[dict[str, Any]]] = None,
        chat_mode: str = "WORKSPACE",
        max_context_tokens: Optional[int] = None,
    ) -> ContextPackage:
        """
        Main entrypoint: Assembles strict tier-budgeted context package.
        
        Tiers:
        - Tier 1 (Reserved): System prompt + project instructions
        - Tier 2 (Reserved): User prompt + attachments (with size safeguard)
        - Tier 3 (Dynamic): Retrieved RAG chunks
        - Tier 4 (Dynamic): Recent message history
        - Tier 5 (Fallback): Compaction rolling summary if history overflows
        """
        # 1. Budget Resolution (Amendment 2: Model context window resolution)
        total_window = max_context_tokens or settings.llama_ctx_size_main
        reserved_output = self.reserved_output_tokens
        input_budget = max(0, total_window - reserved_output)
        remaining_budget = input_budget


        logger.debug(
            "ContextManager starting budget calculation: total_window=%d, reserved_output=%d, input_budget=%d",
            total_window,
            reserved_output,
            input_budget
        )

        # -------------------------------------------------------------
        # Tier 1: System Prompt + Project Instructions (ALWAYS RESERVED)
        # -------------------------------------------------------------
        base_system = system_prompt or "You are Jarvis, an expert local AI software engineering assistant."
        tier1_parts = [base_system.strip()]

        if project_instructions and project_instructions.strip():
            tier1_parts.append(f"--- Project Instructions ---\n{project_instructions.strip()}")

        tier1_text = "\n\n".join(tier1_parts)
        tier1_tokens = self.token_counter.count(tier1_text) + 4  # system framing
        remaining_budget -= tier1_tokens

        # -------------------------------------------------------------
        # Tier 2: User Prompt + Attached Files (ALWAYS RESERVED with Safeguard)
        # -------------------------------------------------------------
        attachment_text = self._format_attachment_text(attachments or [])
        tier2_user_content_parts = []
        if attachment_text:
            tier2_user_content_parts.append(attachment_text)
        if user_message and user_message.strip():
            tier2_user_content_parts.append(user_message.strip())

        tier2_full_user_text = "\n\n".join(tier2_user_content_parts) if tier2_user_content_parts else user_message
        tier2_tokens = self.token_counter.count(tier2_full_user_text) + 4
        remaining_budget -= tier2_tokens

        # -------------------------------------------------------------
        # Tier 3: Retrieved RAG Chunks (DYNAMIC)
        # -------------------------------------------------------------
        chunks_used: list[dict[str, Any]] = []
        chunks_dropped: list[dict[str, Any]] = []
        tier3_formatted_blocks: list[str] = []
        tier3_tokens = 0

        # RAG is active in WORKSPACE mode only
        if (chat_mode or "").upper() == "WORKSPACE" and retrieved_chunks:
            max_chunks = settings.context_tier3_max_chunks
            candidate_chunks = retrieved_chunks[:max_chunks]

            for chunk in candidate_chunks:
                block_str = self._format_rag_chunk(chunk)
                block_cost = self.token_counter.count(block_str) + 2

                # Leave at least 500 tokens for recent messages (Tier 4) if budget allows
                if remaining_budget - block_cost >= 500 or (remaining_budget - block_cost >= 0 and not session_id):
                    chunks_used.append(chunk)
                    tier3_formatted_blocks.append(block_str)
                    tier3_tokens += block_cost
                    remaining_budget -= block_cost
                else:
                    chunks_dropped.append(chunk)
        elif retrieved_chunks:
            # Dropped because chat_mode is SYSTEM
            chunks_dropped.extend(retrieved_chunks)

        # -------------------------------------------------------------
        # Tier 4 & 5: Message History & Compaction Summary (DYNAMIC)
        # -------------------------------------------------------------
        history_messages: list[dict[str, Any]] = []
        tier4_tokens = 0
        summary_included = False

        if session_id:
            try:
                # Fetch recent messages
                limit = settings.context_tier4_max_messages
                stored_messages = self.memory_store.get_messages(session_id, limit=limit)
                
                # Check for rolling compaction summary
                compaction_summary = None
                if settings.context_include_summary:
                    try:
                        compactions = self.memory_store.get_compaction_events(session_id)
                        if compactions:
                            last_ev = compactions[-1]
                            det = last_ev.get("details")
                            if isinstance(det, dict):
                                compaction_summary = det.get("summary")
                            elif isinstance(det, str):
                                try:
                                    parsed = json.loads(det)
                                    if isinstance(parsed, dict):
                                        compaction_summary = parsed.get("summary") or det
                                    else:
                                        compaction_summary = det
                                except Exception:
                                    compaction_summary = det
                    except Exception as comp_err:
                        logger.debug("No compaction summary found: %s", comp_err)


                # Fit recent messages starting from newest backwards
                included_stored: list[dict[str, Any]] = []
                for msg in reversed(stored_messages):
                    msg_dict = {
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    }
                    if "tool_calls" in msg and msg["tool_calls"]:
                        msg_dict["tool_calls"] = msg["tool_calls"]

                    msg_cost = self.token_counter.count_messages([msg_dict])
                    if remaining_budget - msg_cost >= 0:
                        included_stored.insert(0, msg_dict)
                        tier4_tokens += msg_cost
                        remaining_budget -= msg_cost
                    else:
                        break

                # If older messages were truncated and we have a compaction summary, prepend it
                if compaction_summary and (len(included_stored) < len(stored_messages) or not included_stored):
                    summary_msg = {
                        "role": "system",
                        "content": f"--- Prior Conversation Summary ---\n{compaction_summary}"
                    }
                    summary_cost = self.token_counter.count_messages([summary_msg])

                    # If remaining budget is too tight for summary, drop oldest included message to make room
                    while included_stored and remaining_budget < summary_cost:
                        popped = included_stored.pop(0)
                        popped_cost = self.token_counter.count_messages([popped])
                        tier4_tokens -= popped_cost
                        remaining_budget += popped_cost

                    if remaining_budget >= summary_cost:
                        history_messages.append(summary_msg)
                        tier4_tokens += summary_cost
                        remaining_budget -= summary_cost
                        summary_included = True

                history_messages.extend(included_stored)


            except Exception as hist_err:
                logger.warning("Error fetching session message history: %s", hist_err)

        # -------------------------------------------------------------
        # Final Message Assembly
        # -------------------------------------------------------------
        final_system_prompt_parts = [tier1_text]
        if tier3_formatted_blocks:
            final_system_prompt_parts.append(
                "--- Relevant Workspace Context & Code ---\n" +
                "\n\n".join(tier3_formatted_blocks)
            )

        assembled_system_prompt = "\n\n".join(final_system_prompt_parts)

        # Messages list for OpenAI / llama.cpp format
        final_messages: list[dict[str, Any]] = [
            {"role": "system", "content": assembled_system_prompt}
        ]

        final_messages.extend(history_messages)

        # Append current turn user prompt (if provided)
        if tier2_full_user_text:
            final_messages.append({
                "role": "user",
                "content": tier2_full_user_text
            })

        total_input_tokens = self.token_counter.count_messages(final_messages)

        budget_report = {
            "total_context_window": total_window,
            "reserved_output_tokens": reserved_output,
            "available_input_budget": input_budget,
            "tier1_system_tokens": tier1_tokens,
            "tier2_user_tokens": tier2_tokens,
            "tier3_rag_tokens": tier3_tokens,
            "tier4_history_tokens": tier4_tokens,
            "tier5_summary_included": summary_included,
            "total_input_tokens_used": total_input_tokens,
            "remaining_unallocated_tokens": max(0, remaining_budget),
            "chunks_used_count": len(chunks_used),
            "chunks_dropped_count": len(chunks_dropped),
            "chat_mode": chat_mode,
        }

        logger.info(
            "Context assembled: %d tokens (Tier1: %d, Tier2: %d, Tier3: %d, Tier4: %d) | Chunks: %d used, %d dropped",
            total_input_tokens,
            tier1_tokens,
            tier2_tokens,
            tier3_tokens,
            tier4_tokens,
            len(chunks_used),
            len(chunks_dropped)
        )

        return ContextPackage(
            system_prompt=assembled_system_prompt,
            messages=final_messages,
            total_tokens=total_input_tokens,
            retrieved_chunks_used=chunks_used,
            retrieved_chunks_dropped=chunks_dropped,
            budget_report=budget_report
        )
