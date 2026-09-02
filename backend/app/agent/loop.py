import json
import time
import uuid
import logging
from enum import Enum
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Optional

from sqlmodel import Session, select
from app.database.session import engine
from app.database.models import AgentRun, ToolCall, Message as DBMessage

from app.tools.base import BaseTool, ToolResult, PermissionLevel
from app.tools.registry import ToolRegistry
from app.agent.tool_result_truncator import truncate_tool_result
from app.agent.model_provider import ModelProvider

logger = logging.getLogger("jarvis.agent.loop")


class AgentState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    EXECUTING_TOOL = "executing_tool"
    PENDING_USER_CONFIRMATION = "pending_user_confirmation"
    COMPLETED = "completed"
    ERROR = "error"


class AgentLoop:
    """
    Autonomous multi-turn agent execution loop complying with Build Plan Sections 10, 11, 12, 21.
    Coordinates context building, LLM inference, tool execution, DB persistence, and SSE event streaming.
    """

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        vision_manager: Optional[Any] = None,
        max_iterations: int = 5,
        max_tool_chars: int = 16000
    ):
        self.tool_registry = tool_registry or ToolRegistry()
        self.vision_manager = vision_manager
        self.max_iterations = max_iterations
        self.max_tool_chars = max_tool_chars
        self.state = AgentState.IDLE

    def _create_agent_run(
        self,
        session_id: str,
        project_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """Create and persist an AgentRun record in the database."""
        run_id = str(uuid.uuid4())
        try:
            with Session(engine) as session:
                run = AgentRun(
                    id=run_id,
                    session_id=session_id,
                    project_id=project_id,
                    status=AgentState.RUNNING.value,
                    model=model,
                    started_at=datetime.utcnow()
                )
                session.add(run)
                session.commit()
        except Exception as e:
            logger.warning("Failed to create AgentRun in DB: %s", e)
        return run_id

    def _update_agent_run(
        self,
        run_id: str,
        status: AgentState,
        tool_calls_count: int = 0,
        errors: Optional[list[str]] = None,
        latency_ms: int = 0
    ) -> None:
        """Update the status and metrics of an AgentRun record."""
        try:
            with Session(engine) as session:
                run = session.get(AgentRun, run_id)
                if run:
                    run.status = status.value
                    run.tool_calls_count = tool_calls_count
                    run.latency_ms = latency_ms
                    if errors:
                        run.errors_json = json.dumps(errors)
                    if status in (AgentState.COMPLETED, AgentState.ERROR):
                        run.completed_at = datetime.utcnow()
                    session.add(run)
                    session.commit()
        except Exception as e:
            logger.debug("Failed to update AgentRun %s: %s", run_id, e)

    def _persist_tool_call_start(
        self,
        call_id: str,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> None:
        """Record the invocation of a ToolCall in the database."""
        try:
            with Session(engine) as session:
                tc = ToolCall(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    call_id=call_id,
                    tool_name=tool_name,
                    arguments_json=json.dumps(arguments),
                    status="running",
                    started_at=datetime.utcnow()
                )
                session.add(tc)
                session.commit()
        except Exception as e:
            logger.debug("Failed to record ToolCall start in DB: %s", e)

    def _persist_tool_call_end(
        self,
        call_id: str,
        status: str,
        result_text: str,
        error_message: Optional[str] = None
    ) -> None:
        """Update a ToolCall record with execution results."""
        try:
            with Session(engine) as session:
                statement = select(ToolCall).where(ToolCall.call_id == call_id)
                tc = session.exec(statement).first()
                if tc:
                    tc.status = status
                    tc.result = result_text
                    tc.error_message = error_message
                    tc.completed_at = datetime.utcnow()
                    session.add(tc)
                    session.commit()
        except Exception as e:
            logger.debug("Failed to update ToolCall in DB: %s", e)


    async def run(
        self,
        provider: ModelProvider,
        messages: list[dict[str, Any]],
        session_id: str,
        project_id: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        approved_action_ids: Optional[list[str]] = None,
        chat_mode: str = "WORKSPACE",
        profile: str = "general"
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Execute the agentic loop with streaming events.
        Yields structured SSE event dictionaries.
        """
        start_time = time.time()
        self.state = AgentState.RUNNING
        run_id = self._create_agent_run(session_id=session_id, project_id=project_id, model=model)

        active_messages = [dict(m) for m in messages]
        tool_schemas = tools if tools is not None else self.tool_registry.get_tools_schema()
        tool_calls_executed = 0
        errors_logged: list[str] = []
        approved_ids = set(approved_action_ids or [])

        # Intercept image attachments and inject vision analysis (Build Plan §18 & Amendment 1)
        for msg in active_messages:
            if msg.get("role") == "user":
                attachments = msg.get("attachments") or []
                for att in attachments:
                    file_path = att.get("path") or att.get("file_path") or ""
                    filename = att.get("name") or (file_path.split("/")[-1].split("\\")[-1] if file_path else "image")
                    mime = att.get("mime_type") or att.get("type") or ""
                    if (
                        mime.startswith("image/")
                        or any(file_path.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"])
                    ):
                        image_desc = None
                        if self.vision_manager:
                            try:
                                image_desc = await self.vision_manager.analyze_image(
                                    image_data=file_path,
                                    prompt="Describe this image in detail for a text-based AI"
                                )
                            except Exception as e:
                                logger.warning("Vision analysis failed for '%s': %s", filename, e)
                                image_desc = f"[Image attached: {filename}, but vision analysis is currently unavailable]"
                        else:
                            image_desc = f"[Image attached: {filename}, but vision analysis is currently unavailable]"

                        if image_desc:
                            orig_content = msg.get("content", "")
                            msg["content"] = f"{orig_content}\n\n[Vision Analysis of {filename}]:\n{image_desc}".strip()

        try:
            iteration = 0
            while iteration < self.max_iterations:
                iteration += 1
                logger.info("AgentLoop iteration %d/%d (session_id=%s)", iteration, self.max_iterations, session_id)

                accumulated_text = ""
                extracted_tool_calls: list[dict[str, Any]] = []

                # Yield agent status update
                yield {
                    "event": "agent_status",
                    "data": {
                        "status": "Thinking..." if iteration == 1 else f"Processing step {iteration}...",
                        "iteration": iteration,
                        "run_id": run_id
                    }
                }

                # 1. Stream response from model provider
                async for chunk in provider.stream_chat(
                    messages=active_messages,
                    model=model,
                    tools=tool_schemas,
                    profile=profile
                ):
                    delta = chunk.get("delta") or ""
                    if delta:
                        accumulated_text += delta
                        yield {"event": "token", "data": {"delta": delta}}

                    # If provider returns structured tool call events
                    if chunk.get("tool_calls"):
                        extracted_tool_calls.extend(chunk["tool_calls"])

                # Check if raw text contained embedded tool calls (fallback for models without native JSON calling)
                if not extracted_tool_calls and "<tool_call>" in accumulated_text:
                    from app.agent.orchestrator import extract_tool_calls_from_text
                    cleaned, extracted = extract_tool_calls_from_text(accumulated_text)
                    if extracted:
                        extracted_tool_calls = extracted
                        accumulated_text = cleaned

                # Append assistant response to message history
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": accumulated_text
                }
                if extracted_tool_calls:
                    assistant_msg["tool_calls"] = extracted_tool_calls
                active_messages.append(assistant_msg)

                # 2. If NO tool calls requested -> final answer reached
                if not extracted_tool_calls:
                    self.state = AgentState.COMPLETED
                    total_latency = int((time.time() - start_time) * 1000)
                    self._update_agent_run(
                        run_id=run_id,
                        status=AgentState.COMPLETED,
                        tool_calls_count=tool_calls_executed,
                        latency_ms=total_latency
                    )
                    yield {
                        "event": "done",
                        "data": {
                            "response": accumulated_text,
                            "model": model or provider.name,
                            "provider": provider.name,
                            "session_id": session_id,
                            "run_id": run_id,
                            "tool_calls_count": tool_calls_executed
                        }
                    }
                    return

                # 3. Process tool calls
                for tc in extracted_tool_calls:
                    tc_id = tc.get("id") or f"call_{uuid.uuid4().hex[:8]}"
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    raw_args = fn.get("arguments", {})

                    if isinstance(raw_args, str):
                        try:
                            parsed_args = json.loads(raw_args)
                        except Exception:
                            parsed_args = {"query": raw_args}
                    else:
                        parsed_args = raw_args or {}

                    tool_inst = self.tool_registry.get_tool(tool_name)

                    # State machine check: Permission Level & Confirmation Stub (Amendment 2)
                    if tool_inst and tool_inst.permission_level == PermissionLevel.CONFIRMATION_REQUIRED:
                        if tc_id not in approved_ids:
                            self.state = AgentState.PENDING_USER_CONFIRMATION
                            logger.info("Tool '%s' requires confirmation. Pausing loop.", tool_name)
                            yield {
                                "event": "confirmation_required",
                                "data": {
                                    "pending_confirmations": [{
                                        "id": tc_id,
                                        "tool": tool_name,
                                        "args": parsed_args
                                    }],
                                    "session_id": session_id,
                                    "run_id": run_id
                                }
                            }
                            return

                    # Emit tool call start events
                    self.state = AgentState.EXECUTING_TOOL
                    yield {
                        "event": "tool_call",
                        "data": {
                            "tool": tool_name,
                            "args": parsed_args,
                            "call_id": tc_id
                        }
                    }
                    yield {
                        "event": "agent_status",
                        "data": {
                            "status": f"Executing {tool_name}...",
                            "tool": tool_name
                        }
                    }

                    self._persist_tool_call_start(
                        call_id=tc_id,
                        session_id=session_id,
                        tool_name=tool_name,
                        arguments=parsed_args
                    )

                    # Execute tool asynchronously
                    tool_result = await self.tool_registry.execute_tool(
                        tool_name=tool_name,
                        arguments=parsed_args,
                        project_id=project_id
                    )
                    tool_calls_executed += 1

                    # Truncate bulky tool results to protect KV Cache
                    raw_content = tool_result.to_message_content()
                    truncated_content, was_truncated = truncate_tool_result(
                        raw_content,
                        max_chars=self.max_tool_chars
                    )
                    tool_result.truncated = was_truncated

                    if tool_result.status == "error" and tool_result.error:
                        errors_logged.append(tool_result.error)

                    self._persist_tool_call_end(
                        call_id=tc_id,
                        status=tool_result.status,
                        result_text=truncated_content,
                        error_message=tool_result.error
                    )

                    # Emit tool result SSE event
                    yield {
                        "event": "tool_result",
                        "data": {
                            "tool": tool_name,
                            "status": tool_result.status,
                            "summary": tool_result.summary or ("Success" if tool_result.status == "success" else "Error"),
                            "result": truncated_content,
                            "call_id": tc_id,
                            "latency_ms": tool_result.metadata.get("latency_ms", 0),
                            "truncated": was_truncated
                        }
                    }

                    # Emit file_change SSE event on filesystem / patch mutations (Step 4.3)
                    if tool_result.status == "success" and tool_name in (
                        "filesystem.write", "filesystem.edit", "apply_patch",
                        "replace_range", "insert", "delete_range"
                    ):
                        yield {
                            "event": "file_change",
                            "data": {
                                "path": tool_result.metadata.get("path") or str(parsed_args.get("path") or parsed_args.get("file_path") or ""),
                                "action": tool_name.replace("filesystem.", ""),
                                "diff": tool_result.metadata.get("diff") or tool_result.summary or "",
                                "session_id": session_id,
                            }
                        }

                    # Emit artifact_update SSE event on artifact mutations (Step 4.2)
                    if tool_result.status == "success" and (
                        "artifact" in tool_name or tool_result.metadata.get("artifact_id")
                    ):
                        yield {
                            "event": "artifact_update",
                            "data": {
                                "id": tool_result.metadata.get("artifact_id", ""),
                                "name": tool_result.metadata.get("name") or str(parsed_args.get("name", "")),
                                "type": tool_result.metadata.get("type") or str(parsed_args.get("type", "code")),
                                "version": tool_result.metadata.get("version", 1),
                                "content": tool_result.result if isinstance(tool_result.result, str) else "",
                                "action": "update" if "update" in tool_name or "patch" in tool_name else "create",
                                "session_id": session_id,
                            }
                        }

                    # Append standardized OpenAI tool message (Amendment 2)
                    active_messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": tool_name,
                        "content": truncated_content
                    })

                # Loop continues to next turn to allow model to read tool outputs

            # Max iterations reached
            self.state = AgentState.COMPLETED
            total_latency = int((time.time() - start_time) * 1000)
            self._update_agent_run(
                run_id=run_id,
                status=AgentState.COMPLETED,
                tool_calls_count=tool_calls_executed,
                latency_ms=total_latency,
                errors=errors_logged
            )
            yield {
                "event": "done",
                "data": {
                    "response": accumulated_text or "Agent task reached maximum iteration limit.",
                    "model": model or provider.name,
                    "provider": provider.name,
                    "session_id": session_id,
                    "run_id": run_id,
                    "tool_calls_count": tool_calls_executed
                }
            }

        except Exception as e:
            self.state = AgentState.ERROR
            logger.exception("Fatal error in AgentLoop: %s", e)
            total_latency = int((time.time() - start_time) * 1000)
            self._update_agent_run(
                run_id=run_id,
                status=AgentState.ERROR,
                tool_calls_count=tool_calls_executed,
                errors=[str(e)],
                latency_ms=total_latency
            )
            yield {"event": "error", "data": {"error": f"Agent runtime error: {e}"}}
