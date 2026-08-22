import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional
import ollama


from app.config import settings, MAX_TOOL_CALLS_PER_TURN
from app.agent.tools.registry import AVAILABLE_TOOLS, execute_tool, get_tool_schema
from app.agent.permissions import (
    evaluate_tool_calls_batch,
    evaluate_tool_permission,
    check_rate_limit,
    RATE_LIMITS,
    PermissionDecision,
    RiskTier,
    ChatMode,
)

from app.agent.validator import validate_tool_call, CallHistory, ValidationResult
from app.agent.model_router import ModelRouter, RoutingDecision
from app.agent.openrouter_client import OpenRouterClient
from app.agent.lmstudio_client import LMStudioClient
from app.agent.reliability_monitor import ReliabilityMonitor
from app.memory.store import MemoryStore

from app.memory.compactor import ContextCompactor
from app.skills.loader import SkillsLoader, Skill
from app.mcp.manager import MCPManager

logger = logging.getLogger("jarvis.agent.orchestrator")


@dataclass
class OrchestratorResult:
    response: str
    model: str
    provider: str = "ollama"  # "ollama" | "openrouter"
    status: str = "completed"  # "completed" | "confirmation_required"
    session_id: str = "default"
    route_reason: str = ""
    fallback_used: bool = False
    compaction_performed: Optional[dict[str, Any]] = None
    active_skills: list[str] = field(default_factory=list)
    tools_used: list[dict[str, Any]] = field(default_factory=list)
    pending_confirmations: list[dict[str, Any]] = field(default_factory=list)


def extract_tool_calls_from_text(content: str, user_prompt: str = "") -> tuple[str, list[dict[str, Any]]]:

    """
    Extract embedded tool calls outputted as raw text by models:
    1. <tool_call> ... </tool_call> tags
    2. Conversational tool announcements: 'use the write_file function: { ... }'
    3. Markdown ```json { ... } ``` or raw JSON blocks matching known tool argument signatures.
    Returns (cleaned_content, extracted_tool_calls).
    """
    if not content or not isinstance(content, str):
        return content, []

    extracted = []

    # 1. Standard <tool_call>...</tool_call> tags
    tag_pattern = re.compile(r"(?:<tool_call>)?\s*(\{[\s\S]*?\})\s*</tool_call>", re.DOTALL)
    for m in tag_pattern.finditer(content):
        try:
            raw_j = m.group(1).strip().replace("True", "true").replace("False", "false")
            parsed = json.loads(raw_j)
            if isinstance(parsed, dict) and ("name" in parsed or "function" in parsed):
                fn_name = parsed.get("name") or parsed.get("function", {}).get("name")
                fn_args = parsed.get("arguments") or parsed.get("args") or parsed.get("parameters") or parsed.get("params") or parsed.get("function", {}).get("arguments", {})
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {"query": fn_args}
                if fn_name:
                    extracted.append({
                        "function": {
                            "name": fn_name,
                            "arguments": fn_args if isinstance(fn_args, dict) else {}
                        }
                    })
        except Exception:
            pass

    if extracted:
        cleaned_content = tag_pattern.sub("", content).strip()
        return cleaned_content, extracted

    # 2. Match conversational tool announcements (e.g. "use the write_file function ... { ... }" or "execute grep_in_files:\n{...}")
    tool_names = {
        "write_file", "patch_file", "find_files", "grep_in_files",
        "read_file", "list_directory", "execute_command", "delete_file",
        "web_search", "fetch_url"
    }
    tool_announcement_regex = re.compile(
        r"(?:use(?: the)?|execute(?: the)?|call(?: the)?|invok(?:e|ing)(?: the)?)\s+`?([a-z_]+)`?(?:\s+tool|\s+function)?[\s\S]*?(```(?:json)?\s*)?(\{[\s\S]*?\})(\s*```)?",
        re.IGNORECASE
    )
    for m in tool_announcement_regex.finditer(content):
        t_name = m.group(1).lower().strip()
        if t_name in tool_names:
            raw_json = m.group(3).strip().replace("True", "true").replace("False", "false")
            try:
                parsed_args = json.loads(raw_json)
                if isinstance(parsed_args, dict):
                    extracted.append({
                        "function": {
                            "name": t_name,
                            "arguments": parsed_args
                        }
                    })
            except Exception:
                pass

    if extracted:
        cleaned_content = tool_announcement_regex.sub("", content).strip()
        return cleaned_content, extracted

    # 3. Match JSON blocks with unambiguous parameter signatures or name/parameters
    json_block_regex = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```|(\{[\s\S]*?\})", re.DOTALL)
    for m in json_block_regex.finditer(content):
        raw_json_str = (m.group(1) or m.group(2) or "").strip().replace("True", "true").replace("False", "false")
        if not raw_json_str.startswith("{") or not raw_json_str.endswith("}"):
            continue
        try:
            parsed = json.loads(raw_json_str)
            if isinstance(parsed, dict):
                if "name" in parsed and ("arguments" in parsed or "args" in parsed or "parameters" in parsed or "params" in parsed):
                    fn_name = parsed["name"]
                    fn_args = parsed.get("arguments") or parsed.get("args") or parsed.get("parameters") or parsed.get("params") or {}
                    extracted.append({"function": {"name": fn_name, "arguments": fn_args}})
                elif "file_path" in parsed and "content" in parsed:
                    extracted.append({"function": {"name": "write_file", "arguments": parsed}})
                elif "file_path" in parsed and "search_block" in parsed:
                    extracted.append({"function": {"name": "patch_file", "arguments": parsed}})
                elif "pattern" in parsed and ("max_matches" in parsed or "case_sensitive" in parsed or "path" in parsed):
                    extracted.append({"function": {"name": "grep_in_files", "arguments": parsed}})
                elif "pattern" in parsed and ("root_dir" in parsed or "*" in str(parsed.get("pattern"))):
                    extracted.append({"function": {"name": "find_files", "arguments": parsed}})
                elif "query" in parsed and ("max_results" in parsed or len(parsed) == 1):
                    extracted.append({"function": {"name": "web_search", "arguments": parsed}})
                elif "url" in parsed and ("max_chars" in parsed or len(parsed) == 1):
                    extracted.append({"function": {"name": "fetch_url", "arguments": parsed}})
                elif "command" in parsed:
                    extracted.append({"function": {"name": "execute_command", "arguments": parsed}})
        except Exception:
            pass


    if extracted:
        cleaned_content = json_block_regex.sub("", content).strip()
        return cleaned_content, extracted

    # 4. Infer write_file if a file path is requested and the model generated a code block in markdown
    if not extracted and ("```" in content):
        combined_text = (user_prompt or "") + "\n" + content
        path_matches = re.findall(r"(?:in|to|at|file|into|create)\s+[`'\"]?([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)[`'\"]?", combined_text, re.IGNORECASE)
        code_block_match = re.search(r"```(?:[a-zA-Z0-9_\-]+)?\n([\s\S]*?)\n```", content)
        if path_matches and code_block_match:
            target_file_path = path_matches[0].strip().replace("\\", "/")
            if any(target_file_path.endswith(ext) for ext in [".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".txt", ".sh", ".bat", ".ps1", ".yml", ".yaml"]):
                code_content = code_block_match.group(1)
                if len(code_content.strip()) > 10:
                    logger.info("Inferred write_file tool call for '%s' from generated code block", target_file_path)
                    extracted.append({
                        "function": {
                            "name": "write_file",
                            "arguments": {
                                "file_path": target_file_path,
                                "content": code_content,
                                "overwrite": True
                            }
                        }
                    })
                    return content, extracted

    return content, []



DEFAULT_SYSTEM_PROMPT = (
    "You are Jarvis, a highly capable local AI assistant running on Windows with direct access to tools, memory, and skills.\n"
    "CRITICAL RULES:\n"
    "1. NEVER output conversational plans or raw JSON code blocks in your text describing tools you want to run. When an action is needed, directly invoke the tool.\n"
    "2. When creating new files or scripts, ALWAYS write complete, fully-implemented code with proper functions, docstrings, and logic. Invoke 'write_file(file_path=..., content=...)'.\n"
    "3. When editing or updating code in an existing file, invoke 'patch_file(file_path=..., search_block=..., replacement_block=...)'. If needed, invoke 'read_file' first to see the exact text before patching.\n"
    "4. When searching for words, functions, classes, definitions, or symbols across the codebase/project, ALWAYS invoke 'grep_in_files(pattern=..., path=...)'. Never say a symbol is missing without running grep_in_files first.\n"
    "5. When looking for files or directories by name/pattern/extension, ALWAYS invoke 'find_files(pattern=..., root_dir=...)'.\n"
    "6. When the user asks to search online for real-time web info, live news, or documentation, invoke 'web_search(query=...)'.\n"
    "7. When the user provides a web URL (http/https), invoke 'fetch_url(url=...)'. Never use read_file for web URLs.\n"
    "8. When inspecting or reading a local disk file, invoke 'read_file(file_path=...)'.\n"
    "9. When browsing a directory tree, invoke 'list_directory(path=...)'.\n"
    "10. When running shell commands, terminal tools, or scripts, invoke 'execute_command(command=...)'.\n"
    "11. Strip surrounding quotation marks from user queries if present.\n"
    "12. Always use clean relative workspace paths (e.g. '.', 'backend/app', 'scripts', 'docs')."
)







class AgentOrchestrator:
    """
    Orchestrates communication with Ollama and OpenRouter, enforcing hardcoded
    safety permissions, complexity routing, memory persistence, context compaction,
    dynamic skills loading, and MCP tool execution.
    """

    def __init__(
        self,
        ollama_client: Optional[ollama.AsyncClient] = None,
        lmstudio_client: Optional[LMStudioClient] = None,
        openrouter_client: Optional[OpenRouterClient] = None,
        router: Optional[ModelRouter] = None,
        memory_store: Optional[MemoryStore] = None,
        compactor: Optional[ContextCompactor] = None,
        skills_loader: Optional[SkillsLoader] = None,
        mcp_manager: Optional[MCPManager] = None,
        reliability_monitor: Optional[ReliabilityMonitor] = None
    ):
        self.ollama_client = ollama_client or ollama.AsyncClient(host=settings.ollama_host)
        self.lmstudio_client = lmstudio_client or LMStudioClient(
            base_url=settings.lmstudio_base_url,
            timeout=90.0
        )
        self.openrouter_client = openrouter_client or OpenRouterClient(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url
        )
        if router is None:
            if ollama_client is not None and lmstudio_client is None:
                resolved_backend = "hermes3"
            elif lmstudio_client is not None and ollama_client is None:
                resolved_backend = "bonsai"
            else:
                resolved_backend = settings.active_model_backend
            self.router = ModelRouter(
                default_mode=settings.default_routing_mode,
                active_backend=resolved_backend,
                lmstudio_model=settings.lmstudio_model,
                ollama_model=settings.ollama_model,
                openrouter_heavy_model=settings.openrouter_heavy_model
            )
        else:
            self.router = router
        self.memory_store = memory_store or MemoryStore(db_path=settings.memory_db_path)
        self.compactor = compactor or ContextCompactor(
            max_context_tokens=settings.memory_max_context_tokens,
            tool_pruning_char_threshold=settings.memory_tool_pruning_char_threshold
        )
        self.skills_loader = skills_loader or SkillsLoader()
        self.mcp_manager = mcp_manager or MCPManager()
        self.reliability_monitor = reliability_monitor or ReliabilityMonitor(memory_store=self.memory_store)

    async def run(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        requested_mode: Optional[str] = None,
        requested_model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        approved_action_ids: Optional[list[str]] = None,
        max_iterations: int = 5,
        compaction_threshold_override: Optional[int] = None,
        chat_mode: Optional[str] = "WORKSPACE"
    ) -> OrchestratorResult:
        active_session_id = session_id or "default"
        session_data = self.memory_store.get_or_create_session(active_session_id, chat_mode=chat_mode)
        effective_mode_str = (chat_mode or session_data.get("chat_mode") or "WORKSPACE").upper()
        resolved_chat_mode = ChatMode.SYSTEM if effective_mode_str == "SYSTEM" else ChatMode.WORKSPACE

        # 1. Evaluate Routing
        decision = self.router.evaluate(
            message=user_message,
            requested_mode=requested_mode,
            requested_model=requested_model
        )
        logger.info("Routing decision: mode='%s', provider='%s', model='%s', reason='%s'",
                    decision.mode, decision.provider, decision.model, decision.reason)

        # 2. Dynamic Skills Matching & Prompt Augmentation
        matched_skills = self.skills_loader.match_skills(user_message)
        active_skill_names = [s.name for s in matched_skills]
        if active_skill_names:
            logger.info("Active dynamic skills matched: %s", active_skill_names)

        skill_prompt_injection = self.skills_loader.build_skill_prompt_injection(matched_skills)
        base_system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        composed_system_prompt = base_system_prompt + skill_prompt_injection

        # 3. Dynamic Tool Aggregation (Base Tools + MCP Tools)
        mcp_tools = self.mcp_manager.get_tool_definitions()
        combined_tools = AVAILABLE_TOOLS + mcp_tools

        # 4. Load History & Evaluate Context Compaction
        history = self.memory_store.get_messages(active_session_id)
        current_turn = {"role": "user", "content": user_message}
        full_conversation = history + [current_turn]

        compacted_msgs, compaction_info = await self.compactor.compact(
            messages=full_conversation,
            client=self.ollama_client,
            model=decision.model,
            threshold_override=compaction_threshold_override
        )

        if compaction_info:
            logger.info("Compaction applied to session '%s': %s", active_session_id, compaction_info)
            self.memory_store.replace_messages(active_session_id, compacted_msgs[:-1])
            self.memory_store.record_compaction(
                session_id=active_session_id,
                strategy=compaction_info["strategy"],
                tokens_before=compaction_info["tokens_before"],
                tokens_after=compaction_info["tokens_after"],
                details=compaction_info.get("details")
            )

        # Save user prompt
        self.memory_store.append_message(active_session_id, role="user", content=user_message)

        # 5. Dispatch: OpenRouter (Heavy Mode)
        if decision.provider == "openrouter":
            try:
                dispatch_messages = [{"role": "system", "content": composed_system_prompt}] + compacted_msgs
                
                openrouter_res = await self.openrouter_client.chat(
                    messages=dispatch_messages,
                    model=decision.model
                )

                content = ""
                choices = openrouter_res.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")

                self.memory_store.append_message(active_session_id, role="assistant", content=content)

                return OrchestratorResult(
                    response=content,
                    model=decision.model,
                    provider="openrouter",
                    status="completed",
                    session_id=active_session_id,
                    route_reason=decision.reason,
                    fallback_used=False,
                    compaction_performed=compaction_info,
                    active_skills=active_skill_names
                )

            except Exception as e:
                logger.warning("OpenRouter dispatch failed (%s). Gracefully falling back to local model.", e)
                if self.router.active_backend == "bonsai":
                    fallback_model = requested_model or settings.lmstudio_model
                    result = await self._run_lmstudio_loop(
                        session_id=active_session_id,
                        conversation_messages=compacted_msgs,
                        tools=combined_tools,
                        model=fallback_model,
                        system_prompt=composed_system_prompt,
                        approved_action_ids=approved_action_ids,
                        max_iterations=max_iterations,
                        chat_mode=resolved_chat_mode
                    )
                    result.route_reason = f"{decision.reason} [Fallback: OpenRouter failed ({str(e)}), used local LM Studio]"
                else:
                    fallback_model = requested_model or settings.ollama_model
                    result = await self._run_ollama_loop(
                        session_id=active_session_id,
                        conversation_messages=compacted_msgs,
                        tools=combined_tools,
                        model=fallback_model,
                        system_prompt=composed_system_prompt,
                        approved_action_ids=approved_action_ids,
                        max_iterations=max_iterations,
                        chat_mode=resolved_chat_mode
                    )
                    result.route_reason = f"{decision.reason} [Fallback: OpenRouter failed ({str(e)}), used local Ollama]"
                result.fallback_used = True
                result.compaction_performed = compaction_info
                result.active_skills = active_skill_names
                return result

        # 6. Dispatch: Local LM Studio (Stage B Normal Mode Default)
        if decision.provider == "lmstudio":
            try:
                result = await self._run_lmstudio_loop(
                    session_id=active_session_id,
                    conversation_messages=compacted_msgs,
                    tools=combined_tools,
                    model=decision.model,
                    system_prompt=composed_system_prompt,
                    approved_action_ids=approved_action_ids,
                    max_iterations=max_iterations,
                    route_reason=decision.reason,
                    chat_mode=resolved_chat_mode
                )
                result.compaction_performed = compaction_info
                result.active_skills = active_skill_names
                return result
            except Exception as e:
                logger.warning("LM Studio dispatch failed (%s). Gracefully falling back to local Ollama.", e)
                fallback_model = settings.ollama_model
                result = await self._run_ollama_loop(
                    session_id=active_session_id,
                    conversation_messages=compacted_msgs,
                    tools=combined_tools,
                    model=fallback_model,
                    system_prompt=composed_system_prompt,
                    approved_action_ids=approved_action_ids,
                    max_iterations=max_iterations,
                    chat_mode=resolved_chat_mode
                )
                result.route_reason = f"{decision.reason} [Fallback: LM Studio failed ({str(e)}), used local Ollama ({fallback_model})]"
                result.fallback_used = True
                result.compaction_performed = compaction_info
                result.active_skills = active_skill_names
                return result

        # 7. Dispatch: Local Ollama (Normal Mode / Rollback Target)
        result = await self._run_ollama_loop(
            session_id=active_session_id,
            conversation_messages=compacted_msgs,
            tools=combined_tools,
            model=decision.model,
            system_prompt=composed_system_prompt,
            approved_action_ids=approved_action_ids,
            max_iterations=max_iterations,
            route_reason=decision.reason,
            chat_mode=resolved_chat_mode
        )
        result.compaction_performed = compaction_info
        result.active_skills = active_skill_names
        return result

    async def _run_lmstudio_loop(
        self,
        session_id: str,
        conversation_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        system_prompt: str,
        approved_action_ids: Optional[list[str]] = None,
        max_iterations: int = 5,
        route_reason: str = "Local LM Studio execution",
        chat_mode: ChatMode = ChatMode.WORKSPACE
    ) -> OrchestratorResult:
        """
        Execute agent loop against LM Studio (OpenAI-compatible) endpoint with
        robust Stage A schema validation, loop breaking, rate limits, and safety gating.
        """
        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        call_history = CallHistory(window=3)
        total_turn_tool_calls = 0
        tool_turn_counts: dict[str, int] = {}
        repair_attempts: dict[str, int] = {}
        model_tier = "tier2"

        messages: list[dict[str, Any]] = []
        messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation_messages)

        tools_used: list[dict[str, Any]] = []

        for iteration in range(max_iterations):
            logger.info("LM Studio loop iteration %d/%d for model '%s' (turn_id=%s)", iteration + 1, max_iterations, model, turn_id)

            chat_response = await self.lmstudio_client.chat(
                model=model,
                messages=messages,
                tools=tools
            )

            message_obj = chat_response.get("message", {})
            content = message_obj.get("content", "") or ""
            tool_calls = message_obj.get("tool_calls")

            # Fallback tool call extraction from text if needed
            if not tool_calls:
                latest_user_prompt = ""
                for msg in reversed(messages):
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        latest_user_prompt = msg.get("content", "")
                        break

                content, extracted_calls = extract_tool_calls_from_text(content, user_prompt=latest_user_prompt)
                if extracted_calls:
                    logger.info("Extracted %d tool call(s) from raw LM Studio text stream", len(extracted_calls))
                    tool_calls = extracted_calls

            if not tool_calls:
                if not content.strip():
                    logger.info("LM Studio returned empty content with tools schema. Requesting text generation without tools parameter.")
                    synth_response = await self.lmstudio_client.chat(
                        model=model,
                        messages=messages
                    )
                    content = synth_response.get("message", {}).get("content", "") or ""

                logger.info("No further tool calls requested. Returning final LM Studio response.")
                self.memory_store.append_message(session_id, role="assistant", content=content)
                return OrchestratorResult(
                    response=content,
                    model=model,
                    provider="lmstudio",
                    status="completed",
                    session_id=session_id,
                    route_reason=route_reason,
                    fallback_used=False,
                    tools_used=tools_used
                )

            logger.info("LM Studio requested %d tool call(s)", len(tool_calls))

            # Normalize tool calls
            normalized_tool_calls = []
            for tc in tool_calls:
                func_data = tc.get("function", {})
                fn_name = func_data.get("name", "")
                fn_args = func_data.get("arguments", {})
                normalized_tool_calls.append({
                    "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                    "name": fn_name,
                    "args": fn_args if isinstance(fn_args, dict) else {}
                })

            # Duplicate / Loop breaker
            duplicate_detected = False
            for tc in normalized_tool_calls:
                if call_history.is_duplicate(tc["name"], tc["args"]):
                    duplicate_detected = True
                    break
            if duplicate_detected:
                loop_msg = "Jarvis attempted the same action twice — stopping to avoid a loop."
                logger.warning("Duplicate tool invocation loop detected in LM Studio turn. Halting turn.")
                self.memory_store.append_message(session_id, role="assistant", content=loop_msg)
                return OrchestratorResult(
                    response=loop_msg,
                    model=model,
                    provider="lmstudio",
                    status="completed",
                    session_id=session_id,
                    route_reason=route_reason,
                    fallback_used=False,
                    tools_used=tools_used
                )

            for tc in normalized_tool_calls:
                call_history.record(tc["name"], tc["args"])

            # 3. Per-Tool Rate Limiting Check (§2)
            rate_limited_tool = None
            for tc in normalized_tool_calls:
                fn_name = tc["name"]
                current_count = tool_turn_counts.get(fn_name, 0)
                if not check_rate_limit(fn_name, current_count):
                    rate_limited_tool = fn_name
                    break

            if rate_limited_tool:
                limit = RATE_LIMITS.get(rate_limited_tool, 0)
                rate_msg = f"Rate limit exceeded: Tool '{rate_limited_tool}' reached the maximum allowed limit of {limit} calls for this turn."
                logger.warning(rate_msg)
                self.memory_store.append_message(session_id, role="assistant", content=rate_msg)
                return OrchestratorResult(
                    response=rate_msg,
                    model=model,
                    provider="lmstudio",
                    status="completed",
                    session_id=session_id,
                    route_reason=route_reason,
                    fallback_used=False,
                    tools_used=tools_used
                )

            # Global per-turn cap
            if total_turn_tool_calls + len(normalized_tool_calls) > MAX_TOOL_CALLS_PER_TURN:
                cap_msg = f"Per-turn tool call limit ({MAX_TOOL_CALLS_PER_TURN}) exceeded. Halting further tool execution for safety."
                logger.warning("Turn tool call cap reached (%d / %d). Halting turn.", total_turn_tool_calls, MAX_TOOL_CALLS_PER_TURN)
                self.memory_store.append_message(session_id, role="assistant", content=cap_msg)
                return OrchestratorResult(
                    response=cap_msg,
                    model=model,
                    provider="lmstudio",
                    status="completed",
                    session_id=session_id,
                    route_reason=route_reason,
                    fallback_used=False,
                    tools_used=tools_used
                )

            # Schema validation & Repair-then-Escalate
            validation_failed_items = []
            validated_tool_calls = []
            escalate_to_heavy = False

            for tc in normalized_tool_calls:
                fn_name = tc["name"]
                fn_args = tc["args"]
                call_id = tc["id"]
                schema = get_tool_schema(fn_name)
                current_attempt = repair_attempts.get(fn_name, 0)

                val_res = await validate_tool_call(
                    tool_name=fn_name,
                    raw_args=fn_args,
                    schema=schema,
                    repair_attempt=current_attempt
                )

                if not val_res.valid:
                    if current_attempt == 0:
                        repair_attempts[fn_name] = 1
                        self.memory_store.record_tool_call_audit(
                            call_id=call_id,
                            turn_id=turn_id,
                            tool_name=fn_name,
                            args=fn_args,
                            model_tier=model_tier,
                            validation_result="invalid_repaired",
                            permission_result="blocked",
                            executed=False,
                            error=val_res.error,
                            repair_attempt=0
                        )
                        validation_failed_items.append((fn_name, fn_args, val_res.error, call_id))
                    else:
                        self.memory_store.record_tool_call_audit(
                            call_id=call_id,
                            turn_id=turn_id,
                            tool_name=fn_name,
                            args=fn_args,
                            model_tier=model_tier,
                            validation_result="invalid_escalated",
                            permission_result="blocked",
                            executed=False,
                            error=val_res.error,
                            repair_attempt=1
                        )
                        self.reliability_monitor.evaluate_and_trigger_rollback(model_tier=model_tier)
                        escalate_to_heavy = True
                        break
                else:
                    validated_tool_calls.append((call_id, fn_name, val_res.args))

            if escalate_to_heavy:
                logger.warning("LM Studio tool call validation failed twice. Escalating remaining turn to Tier 3 (OpenRouter).")
                try:
                    openrouter_res = await self.openrouter_client.chat(
                        messages=messages,
                        model=settings.openrouter_heavy_model
                    )
                    esc_content = ""
                    choices = openrouter_res.get("choices", [])
                    if choices:
                        esc_content = choices[0].get("message", {}).get("content", "")
                    self.memory_store.append_message(session_id, role="assistant", content=esc_content)
                    return OrchestratorResult(
                        response=esc_content,
                        model=settings.openrouter_heavy_model,
                        provider="openrouter",
                        status="completed",
                        session_id=session_id,
                        route_reason=f"{route_reason} [Escalated to Tier 3 OpenRouter due to repeated tool argument validation failures]",
                        fallback_used=False,
                        tools_used=tools_used
                    )
                except Exception as e:
                    logger.error("Tier 3 escalation OpenRouter call failed: %s", e)
                    esc_error_msg = f"Escalation to Tier 3 OpenRouter failed ({e}). Stopping turn."
                    return OrchestratorResult(
                        response=esc_error_msg,
                        model=model,
                        provider="lmstudio",
                        status="completed",
                        session_id=session_id,
                        route_reason=route_reason,
                        fallback_used=False,
                        tools_used=tools_used
                    )

            if validation_failed_items:
                assistant_msg = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": item[3],
                            "type": "function",
                            "function": {"name": item[0], "arguments": json.dumps(item[1]) if isinstance(item[1], dict) else str(item[1])}
                        }
                        for item in validation_failed_items
                    ]
                }
                messages.append(assistant_msg)
                for fn_name, fn_args, err_str, cid in validation_failed_items:
                    repair_msg = f"Schema validation error for '{fn_name}': {err_str}. Please correct the parameters and retry."
                    messages.append({
                        "role": "tool",
                        "tool_call_id": cid,
                        "name": fn_name,
                        "content": repair_msg
                    })
                continue

            # Safety permission checks
            batch_calls = [{"name": name, "arguments": args} for _, name, args in validated_tool_calls]
            batch_permission = evaluate_tool_calls_batch(
                tool_calls=batch_calls,
                chat_mode=chat_mode,
                approved_action_ids=approved_action_ids
            )

            if not batch_permission.all_allowed:
                pending_list = [
                    {
                        "action_id": p.action_id,
                        "tool": p.tool,
                        "args": p.args,
                        "risk_tier": p.risk_tier.value,
                        "reason": p.reason
                    }
                    for p in batch_permission.pending_confirmations
                ]
                
                for call_id, name, args in validated_tool_calls:
                    self.memory_store.record_tool_call_audit(
                        call_id=call_id,
                        turn_id=turn_id,
                        tool_name=name,
                        args=args,
                        model_tier=model_tier,
                        validation_result="valid",
                        permission_result="blocked",
                        executed=False,
                        error="Action requires user confirmation",
                        repair_attempt=repair_attempts.get(name, 0)
                    )

                logger.warning(
                    "Tool execution blocked by safety permission gate. %d action(s) require confirmation. Details: %s",
                    len(pending_list), pending_list
                )
                actions_summary = ", ".join([f"'{p['tool']}' (Risk: {p['risk_tier']})" for p in pending_list])
                confirm_response = f"Confirmation Required: The action requires user approval before executing: {actions_summary}."

                return OrchestratorResult(
                    response=confirm_response,
                    model=model,
                    provider="lmstudio",
                    status="confirmation_required",
                    session_id=session_id,
                    route_reason=route_reason,
                    fallback_used=False,
                    tools_used=tools_used,
                    pending_confirmations=pending_list
                )

            # All tools approved -> append assistant message
            assistant_msg = {
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": cid,
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args) if isinstance(args, dict) else str(args)}
                    }
                    for cid, name, args in validated_tool_calls
                ]
            }
            messages.append(assistant_msg)

            # Execute tools & Record audit log
            for call_id, fn_name, fn_args in validated_tool_calls:
                total_turn_tool_calls += 1
                tool_turn_counts[fn_name] = tool_turn_counts.get(fn_name, 0) + 1

                if self.mcp_manager.is_mcp_tool(fn_name):
                    logger.info("Executing MCP tool '%s'", fn_name)
                    tool_output = await self.mcp_manager.call_tool(fn_name, fn_args)
                else:
                    logger.info("Executing Native tool '%s'", fn_name)
                    tool_output = execute_tool(fn_name, fn_args)

                self.memory_store.record_tool_call_audit(
                    call_id=call_id,
                    turn_id=turn_id,
                    tool_name=fn_name,
                    args=fn_args,
                    model_tier=model_tier,
                    validation_result="valid",
                    permission_result="allowed",
                    executed=True,
                    error=None,
                    repair_attempt=repair_attempts.get(fn_name, 0)
                )
                self.reliability_monitor.evaluate_and_trigger_rollback(model_tier=model_tier)

                tools_used.append({
                    "tool": fn_name,
                    "args": fn_args,
                    "result": tool_output
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": fn_name,
                    "content": tool_output
                })
                self.memory_store.append_message(session_id, role="tool", content=tool_output, name=fn_name)

        logger.warning("Max tool iterations reached (%d). Requesting final summary from LM Studio.", max_iterations)
        final_response = await self.lmstudio_client.chat(
            model=model,
            messages=messages
        )
        final_content = final_response.get("message", {}).get("content", "") or ""
        self.memory_store.append_message(session_id, role="assistant", content=final_content)

        return OrchestratorResult(
            response=final_content,
            model=model,
            provider="lmstudio",
            status="completed",
            session_id=session_id,
            route_reason=route_reason,
            fallback_used=False,
            tools_used=tools_used
        )

    async def _run_ollama_loop(
        self,
        session_id: str,
        conversation_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        system_prompt: str,
        approved_action_ids: Optional[list[str]] = None,
        max_iterations: int = 5,
        route_reason: str = "Local Ollama execution",
        chat_mode: ChatMode = ChatMode.WORKSPACE
    ) -> OrchestratorResult:

        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        call_history = CallHistory(window=3)
        total_turn_tool_calls = 0
        tool_turn_counts: dict[str, int] = {}
        repair_attempts: dict[str, int] = {}
        model_tier = "tier1"

        messages: list[dict[str, Any]] = []
        messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation_messages)

        tools_used: list[dict[str, Any]] = []

        for iteration in range(max_iterations):
            logger.info("Agent loop iteration %d/%d for model '%s' (turn_id=%s)", iteration + 1, max_iterations, model, turn_id)
            
            chat_response = await self.ollama_client.chat(
                model=model,
                messages=messages,
                tools=tools
            )

            message_obj = chat_response.get("message") if isinstance(chat_response, dict) else getattr(chat_response, "message", None)
            content = ""
            tool_calls = None

            if isinstance(message_obj, dict):
                content = message_obj.get("content", "") or ""
                tool_calls = message_obj.get("tool_calls")
            elif message_obj is not None:
                content = getattr(message_obj, "content", "") or ""
                tool_calls = getattr(message_obj, "tool_calls", None)

            # If Ollama didn't populate tool_calls, check if the model outputted raw <tool_call> text or code blocks
            if not tool_calls:
                latest_user_prompt = ""
                for msg in reversed(messages):
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        latest_user_prompt = msg.get("content", "")
                        break
                    elif hasattr(msg, "role") and getattr(msg, "role", "") == "user":
                        latest_user_prompt = getattr(msg, "content", "")
                        break

                content, extracted_calls = extract_tool_calls_from_text(content, user_prompt=latest_user_prompt)
                if extracted_calls:
                    logger.info("Extracted %d tool call(s) from raw model text stream", len(extracted_calls))
                    tool_calls = extracted_calls

            # If still no tools were invoked, save assistant message and return
            if not tool_calls:
                if not content.strip():
                    logger.info("Model returned empty content with tools schema. Requesting text generation without tools parameter.")
                    synth_response = await self.ollama_client.chat(
                        model=model,
                        messages=messages
                    )
                    if isinstance(synth_response, dict):
                        content = synth_response.get("message", {}).get("content", "") or ""
                    else:
                        content = getattr(synth_response.message, "content", "") or ""

                logger.info("No further tool calls requested. Returning final model response.")
                self.memory_store.append_message(session_id, role="assistant", content=content)
                return OrchestratorResult(
                    response=content,
                    model=model,
                    provider="ollama",
                    status="completed",
                    session_id=session_id,
                    route_reason=route_reason,
                    fallback_used=False,
                    tools_used=tools_used
                )

            logger.info("Model requested %d tool call(s)", len(tool_calls))

            # Normalize tool calls
            normalized_tool_calls = []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    func_data = tc.get("function", {})
                    fn_name = func_data.get("name", "")
                    fn_args = func_data.get("arguments", {})
                else:
                    func_obj = getattr(tc, "function", None)
                    fn_name = getattr(func_obj, "name", "")
                    fn_args = getattr(func_obj, "arguments", {})

                if not isinstance(fn_args, dict):
                    fn_args = {}

                normalized_tool_calls.append({"name": fn_name, "args": fn_args})

            # 1. Global Per-Turn Cap Check (§1.5)
            if total_turn_tool_calls + len(normalized_tool_calls) > MAX_TOOL_CALLS_PER_TURN:
                logger.warning("Per-turn tool call limit reached (%d calls max). Halting execution.", MAX_TOOL_CALLS_PER_TURN)
                cap_msg = f"Turn tool call limit exceeded: Jarvis reached the maximum limit of {MAX_TOOL_CALLS_PER_TURN} tool calls for this turn. Stopping execution."
                self.memory_store.append_message(session_id, role="assistant", content=cap_msg)
                return OrchestratorResult(
                    response=cap_msg,
                    model=model,
                    provider="ollama",
                    status="completed",
                    session_id=session_id,
                    route_reason=route_reason,
                    fallback_used=False,
                    tools_used=tools_used
                )

            # 2. Duplicate / Loop Breaker Check (§1.4)
            duplicate_detected = False
            for tc in normalized_tool_calls:
                fn_name = tc["name"]
                fn_args = tc["args"]
                if call_history.is_duplicate(fn_name, fn_args):
                    logger.warning("Duplicate consecutive tool call detected for '%s' with args %s. Halting loop.", fn_name, fn_args)
                    duplicate_detected = True
                    break
                call_history.record(fn_name, fn_args)

            if duplicate_detected:
                loop_msg = "Jarvis attempted the same action twice — stopping to avoid a loop."
                self.memory_store.append_message(session_id, role="assistant", content=loop_msg)
                return OrchestratorResult(
                    response=loop_msg,
                    model=model,
                    provider="ollama",
                    status="completed",
                    session_id=session_id,
                    route_reason=route_reason,
                    fallback_used=False,
                    tools_used=tools_used
                )

            # 3. Per-Tool Rate Limiting Check (§2)
            rate_limited_tool = None
            for tc in normalized_tool_calls:
                fn_name = tc["name"]
                current_count = tool_turn_counts.get(fn_name, 0)
                if not check_rate_limit(fn_name, current_count):
                    rate_limited_tool = fn_name
                    break

            if rate_limited_tool:
                limit = RATE_LIMITS.get(rate_limited_tool, 0)
                rate_msg = f"Rate limit exceeded: Tool '{rate_limited_tool}' reached the maximum allowed limit of {limit} calls for this turn."
                logger.warning(rate_msg)
                self.memory_store.append_message(session_id, role="assistant", content=rate_msg)
                return OrchestratorResult(
                    response=rate_msg,
                    model=model,
                    provider="ollama",
                    status="completed",
                    session_id=session_id,
                    route_reason=route_reason,
                    fallback_used=False,
                    tools_used=tools_used
                )

            # 4. Schema Validation & Repair-then-Escalate (§1.2 & §1.3)
            validation_failed_items = []
            validated_tool_calls = []
            escalate_to_heavy = False

            for tc in normalized_tool_calls:
                fn_name = tc["name"]
                fn_args = tc["args"]
                call_id = f"call_{uuid.uuid4().hex[:12]}"
                schema = get_tool_schema(fn_name)
                current_attempt = repair_attempts.get(fn_name, 0)

                val_res = await validate_tool_call(
                    tool_name=fn_name,
                    raw_args=fn_args,
                    schema=schema,
                    repair_attempt=current_attempt
                )

                if not val_res.valid:
                    if current_attempt == 0:
                        repair_attempts[fn_name] = 1
                        self.memory_store.record_tool_call_audit(
                            call_id=call_id,
                            turn_id=turn_id,
                            tool_name=fn_name,
                            args=fn_args,
                            model_tier=model_tier,
                            validation_result="invalid_repaired",
                            permission_result="blocked",
                            executed=False,
                            error=val_res.error,
                            repair_attempt=0
                        )
                        validation_failed_items.append((fn_name, fn_args, val_res.error))
                    else:
                        self.memory_store.record_tool_call_audit(
                            call_id=call_id,
                            turn_id=turn_id,
                            tool_name=fn_name,
                            args=fn_args,
                            model_tier=model_tier,
                            validation_result="invalid_escalated",
                            permission_result="blocked",
                            executed=False,
                            error=val_res.error,
                            repair_attempt=1
                        )
                        escalate_to_heavy = True
                        break
                else:
                    validated_tool_calls.append((call_id, fn_name, val_res.args))

            if escalate_to_heavy:
                logger.warning("Tool call validation failed twice. Escalating remaining turn to Tier 3 (OpenRouter).")
                try:
                    openrouter_res = await self.openrouter_client.chat(
                        messages=messages,
                        model=settings.openrouter_heavy_model
                    )
                    esc_content = ""
                    choices = openrouter_res.get("choices", [])
                    if choices:
                        esc_content = choices[0].get("message", {}).get("content", "")
                    self.memory_store.append_message(session_id, role="assistant", content=esc_content)
                    return OrchestratorResult(
                        response=esc_content,
                        model=settings.openrouter_heavy_model,
                        provider="openrouter",
                        status="completed",
                        session_id=session_id,
                        route_reason=f"{route_reason} [Escalated to Tier 3 OpenRouter due to repeated tool argument validation failures]",
                        fallback_used=False,
                        tools_used=tools_used
                    )
                except Exception as e:
                    logger.error("Tier 3 escalation OpenRouter call failed: %s", e)
                    esc_error_msg = f"Escalation to Tier 3 OpenRouter failed ({e}). Stopping turn."
                    return OrchestratorResult(
                        response=esc_error_msg,
                        model=model,
                        provider="ollama",
                        status="completed",
                        session_id=session_id,
                        route_reason=route_reason,
                        fallback_used=False,
                        tools_used=tools_used
                    )

            if validation_failed_items:
                if isinstance(message_obj, dict):
                    messages.append(message_obj)
                else:
                    assistant_msg = {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": []
                    }
                    for tc in tool_calls:
                        if isinstance(tc, dict):
                            assistant_msg["tool_calls"].append(tc)
                        else:
                            func_obj = getattr(tc, "function", None)
                            assistant_msg["tool_calls"].append({
                                "function": {
                                    "name": getattr(func_obj, "name", ""),
                                    "arguments": getattr(func_obj, "arguments", {})
                                }
                            })
                    messages.append(assistant_msg)

                for fn_name, fn_args, err_str in validation_failed_items:
                    repair_msg = f"Schema validation error for '{fn_name}': {err_str}. Please correct the parameters and retry."
                    messages.append({
                        "role": "tool",
                        "name": fn_name,
                        "content": repair_msg
                    })
                    self.memory_store.append_message(session_id, role="tool", content=repair_msg, name=fn_name)
                continue

            # 5. Evaluate permissions in a single batch pass
            calls_for_perm = [{"name": name, "args": args} for _, name, args in validated_tool_calls]
            batch_permission = evaluate_tool_calls_batch(
                calls_for_perm,
                approved_action_ids=approved_action_ids,
                chat_mode=chat_mode
            )


            # If any tool requires confirmation and is not approved, block execution
            if not batch_permission.all_allowed:
                pending_list = [
                    {
                        "action_id": p.action_id,
                        "tool": p.tool,
                        "args": p.args,
                        "risk_tier": p.risk_tier.value,
                        "reason": p.reason
                    }
                    for p in batch_permission.pending_confirmations
                ]
                
                for call_id, name, args in validated_tool_calls:
                    self.memory_store.record_tool_call_audit(
                        call_id=call_id,
                        turn_id=turn_id,
                        tool_name=name,
                        args=args,
                        model_tier=model_tier,
                        validation_result="valid",
                        permission_result="blocked",
                        executed=False,
                        error="Action requires user confirmation",
                        repair_attempt=repair_attempts.get(name, 0)
                    )

                logger.warning(
                    "Tool execution blocked by safety permission gate. %d action(s) require confirmation. Details: %s",
                    len(pending_list), pending_list
                )
                actions_summary = ", ".join([f"'{p['tool']}' (Risk: {p['risk_tier']})" for p in pending_list])
                confirm_response = f"Confirmation Required: The action requires user approval before executing: {actions_summary}."

                return OrchestratorResult(
                    response=confirm_response,
                    model=model,
                    provider="ollama",
                    status="confirmation_required",
                    session_id=session_id,
                    route_reason=route_reason,
                    fallback_used=False,
                    tools_used=tools_used,
                    pending_confirmations=pending_list
                )

            # All tools approved / allowed -> append assistant message
            if isinstance(message_obj, dict):
                messages.append(message_obj)
            else:
                assistant_msg = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": []
                }
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        assistant_msg["tool_calls"].append(tc)
                    else:
                        func_obj = getattr(tc, "function", None)
                        assistant_msg["tool_calls"].append({
                            "function": {
                                "name": getattr(func_obj, "name", ""),
                                "arguments": getattr(func_obj, "arguments", {})
                            }
                        })
                messages.append(assistant_msg)

            # 6. Execute tools (Native or MCP) & Record audit log
            for call_id, fn_name, fn_args in validated_tool_calls:
                total_turn_tool_calls += 1
                tool_turn_counts[fn_name] = tool_turn_counts.get(fn_name, 0) + 1

                if self.mcp_manager.is_mcp_tool(fn_name):
                    logger.info("Executing MCP tool '%s'", fn_name)
                    tool_output = await self.mcp_manager.call_tool(fn_name, fn_args)
                else:
                    logger.info("Executing Native tool '%s'", fn_name)
                    tool_output = execute_tool(fn_name, fn_args)

                self.memory_store.record_tool_call_audit(
                    call_id=call_id,
                    turn_id=turn_id,
                    tool_name=fn_name,
                    args=fn_args,
                    model_tier=model_tier,
                    validation_result="valid",
                    permission_result="allowed",
                    executed=True,
                    error=None,
                    repair_attempt=repair_attempts.get(fn_name, 0)
                )

                tools_used.append({
                    "tool": fn_name,
                    "args": fn_args,
                    "result": tool_output
                })

                tool_dict = {
                    "role": "tool",
                    "name": fn_name,
                    "content": tool_output
                }
                messages.append(tool_dict)
                self.memory_store.append_message(session_id, role="tool", content=tool_output, name=fn_name)

        logger.warning("Max tool iterations reached (%d). Requesting final summary.", max_iterations)
        final_response = await self.ollama_client.chat(
            model=model,
            messages=messages
        )
        final_content = ""
        if isinstance(final_response, dict):
            final_content = final_response.get("message", {}).get("content", "")
        else:
            final_content = getattr(final_response.message, "content", "")

        self.memory_store.append_message(session_id, role="assistant", content=final_content)

        return OrchestratorResult(
            response=final_content,
            model=model,
            provider="ollama",
            status="completed",
            session_id=session_id,
            route_reason=route_reason,
            fallback_used=False,
            tools_used=tools_used
        )

