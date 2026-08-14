import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional
import ollama


from app.config import settings
from app.agent.tools.registry import AVAILABLE_TOOLS, execute_tool
from app.agent.permissions import (
    evaluate_tool_calls_batch,
    PermissionDecision,
    RiskTier
)
from app.agent.model_router import ModelRouter, RoutingDecision
from app.agent.openrouter_client import OpenRouterClient
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


def extract_tool_calls_from_text(content: str) -> tuple[str, list[dict[str, Any]]]:
    """
    Extract embedded tool calls outputted as raw text by models (e.g. Qwen <tool_call> tags or json snippets).
    Returns (cleaned_content, extracted_tool_calls).
    """
    if not content or not isinstance(content, str):
        return content, []

    extracted = []
    tag_pattern = re.compile(r"(?:<tool_call>)?\s*(\{[\s\S]*?\})\s*</tool_call>", re.DOTALL)
    for m in tag_pattern.finditer(content):
        try:
            parsed = json.loads(m.group(1).strip())
            if isinstance(parsed, dict) and ("name" in parsed or "function" in parsed):
                fn_name = parsed.get("name") or parsed.get("function", {}).get("name")
                fn_args = parsed.get("arguments") or parsed.get("args") or parsed.get("function", {}).get("arguments", {})
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

    return content, []


DEFAULT_SYSTEM_PROMPT = (
    "You are Jarvis, a highly capable local AI assistant running on Windows with direct access to tools, memory, and skills.\n"
    "CRITICAL TOOL USAGE RULES:\n"
    "1. When creating new files or scripts, ALWAYS write complete, robust, fully-implemented code with proper functions, docstrings, and logic. Invoke 'write_file(file_path=..., content=...)'.\n"
    "2. When editing or updating code in an existing file, invoke 'patch_file(file_path=..., search_block=..., replacement_block=...)'. If needed, invoke 'read_file' first to see the exact text before patching.\n"
    "3. When searching for words, functions, classes, definitions, or symbols across the codebase/project, ALWAYS invoke 'grep_in_files(pattern=..., path=...)'. Never say a symbol is missing without running grep_in_files first.\n"
    "4. When looking for files or directories by name/pattern/extension, ALWAYS invoke 'find_files(pattern=..., root_dir=...)'.\n"
    "5. When the user asks to search online for real-time web info, live news, or documentation, invoke 'web_search(query=...)'.\n"
    "6. When the user provides a web URL (http/https), invoke 'fetch_url(url=...)'. Never use read_file for web URLs.\n"
    "7. When inspecting or reading a local disk file, invoke 'read_file(file_path=...)'.\n"
    "8. When browsing a directory tree, invoke 'list_directory(path=...)'.\n"
    "9. When running shell commands, terminal tools, or scripts, invoke 'execute_command(command=...)'.\n"
    "10. For system uptime or disk usage, invoke 'get_system_uptime' or 'get_disk_usage'.\n"
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
        ollama_client: ollama.AsyncClient,
        openrouter_client: Optional[OpenRouterClient] = None,
        router: Optional[ModelRouter] = None,
        memory_store: Optional[MemoryStore] = None,
        compactor: Optional[ContextCompactor] = None,
        skills_loader: Optional[SkillsLoader] = None,
        mcp_manager: Optional[MCPManager] = None
    ):
        self.ollama_client = ollama_client
        self.openrouter_client = openrouter_client or OpenRouterClient(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url
        )
        self.router = router or ModelRouter(
            default_mode=settings.default_routing_mode,
            ollama_model=settings.ollama_model,
            openrouter_heavy_model=settings.openrouter_heavy_model
        )
        self.memory_store = memory_store or MemoryStore(db_path=settings.memory_db_path)
        self.compactor = compactor or ContextCompactor(
            max_context_tokens=settings.memory_max_context_tokens,
            tool_pruning_char_threshold=settings.memory_tool_pruning_char_threshold
        )
        self.skills_loader = skills_loader or SkillsLoader()
        self.mcp_manager = mcp_manager or MCPManager()

    async def run(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        requested_mode: Optional[str] = None,
        requested_model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        approved_action_ids: Optional[list[str]] = None,
        max_iterations: int = 5,
        compaction_threshold_override: Optional[int] = None
    ) -> OrchestratorResult:
        active_session_id = session_id or "default"
        self.memory_store.get_or_create_session(active_session_id)

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
                logger.warning("OpenRouter dispatch failed (%s). Gracefully falling back to local Ollama.", e)
                fallback_model = requested_model or settings.ollama_model
                result = await self._run_ollama_loop(
                    session_id=active_session_id,
                    conversation_messages=compacted_msgs,
                    tools=combined_tools,
                    model=fallback_model,
                    system_prompt=composed_system_prompt,
                    approved_action_ids=approved_action_ids,
                    max_iterations=max_iterations
                )
                result.route_reason = f"{decision.reason} [Fallback: OpenRouter failed ({str(e)}), used local Ollama]"
                result.fallback_used = True
                result.compaction_performed = compaction_info
                result.active_skills = active_skill_names
                return result

        # 6. Dispatch: Local Ollama (Normal Mode)
        result = await self._run_ollama_loop(
            session_id=active_session_id,
            conversation_messages=compacted_msgs,
            tools=combined_tools,
            model=decision.model,
            system_prompt=composed_system_prompt,
            approved_action_ids=approved_action_ids,
            max_iterations=max_iterations,
            route_reason=decision.reason
        )
        result.compaction_performed = compaction_info
        result.active_skills = active_skill_names
        return result

    async def _run_ollama_loop(
        self,
        session_id: str,
        conversation_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        system_prompt: str,
        approved_action_ids: Optional[list[str]] = None,
        max_iterations: int = 5,
        route_reason: str = "Local Ollama execution"
    ) -> OrchestratorResult:
        messages: list[dict[str, Any]] = []

        messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation_messages)

        tools_used: list[dict[str, Any]] = []

        for iteration in range(max_iterations):
            logger.info("Agent loop iteration %d/%d for model '%s'", iteration + 1, max_iterations, model)
            
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

            # If Ollama didn't populate tool_calls, check if the model outputted raw <tool_call> text
            if not tool_calls:
                content, extracted_calls = extract_tool_calls_from_text(content)
                if extracted_calls:
                    logger.info("Extracted %d tool call(s) from raw model text stream", len(extracted_calls))
                    tool_calls = extracted_calls

            # If still no tools were invoked, save assistant message and return
            if not tool_calls:
                # If tools were executed but the model returned empty content, synthesize final response without tools schema
                if not content.strip() and tools_used:
                    logger.info("Tools were executed but model returned empty content. Requesting final synthesis without tools parameter.")
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

            # Evaluate permissions in a single batch pass
            batch_permission = evaluate_tool_calls_batch(
                normalized_tool_calls,
                approved_action_ids=approved_action_ids
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
                        tc_dict = {
                            "function": {
                                "name": getattr(func_obj, "name", ""),
                                "arguments": getattr(func_obj, "arguments", {})
                            }
                        }
                        assistant_msg["tool_calls"].append(tc_dict)
                messages.append(assistant_msg)

            # Execute tools (Native or MCP)
            for tc_item in normalized_tool_calls:
                fn_name = tc_item["name"]
                fn_args = tc_item["args"]

                if self.mcp_manager.is_mcp_tool(fn_name):
                    logger.info("Executing MCP tool '%s'", fn_name)
                    tool_output = await self.mcp_manager.call_tool(fn_name, fn_args)
                else:
                    logger.info("Executing Native tool '%s'", fn_name)
                    tool_output = execute_tool(fn_name, fn_args)

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
