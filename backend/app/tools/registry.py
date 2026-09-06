import time
import logging
from typing import Any, Optional
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger("jarvis.tools.registry")


class ToolRegistry:
    """
    Central registry for discovering, validating, and executing Jarvis tools.
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a BaseTool instance."""
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Expected BaseTool instance, got {type(tool)}")
        self._tools[tool.name] = tool
        logger.info("Registered tool: '%s' (permission: %s)", tool.name, tool.permission_level)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieve a registered tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """Return all registered tool instances."""
        return list(self._tools.values())

    def get_tools_schema(self, include_functional: bool = False) -> list[dict[str, Any]]:
        """
        Generate array of OpenAI-compatible tool specifications to provide to the LLM.
        Optionally merges BaseTool instances with functional agent tools.
        """
        schemas = [tool.get_schema() for tool in self._tools.values()]
        if include_functional:
            existing_names = {tool.name for tool in self._tools.values()}
            try:
                from app.agent.tools.registry import AVAILABLE_TOOLS, get_tool_schema
                for fn in AVAILABLE_TOOLS:
                    fn_name = getattr(fn, "__name__", "")
                    if fn_name and fn_name not in existing_names:
                        schemas.append(get_tool_schema(fn))
                        existing_names.add(fn_name)
            except Exception as e:
                logger.warning("Could not merge functional tool schemas: %s", e)
        return schemas

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        project_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None
    ) -> ToolResult:
        """
        Safely dispatches tool execution across BaseTool objects and functional agent tools,
        tracking latency and error status.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            # Fallback to functional agent tool registry
            try:
                from app.agent.tools.registry import TOOL_FUNCTIONS, execute_tool as exec_func_tool
                if tool_name in TOOL_FUNCTIONS:
                    start_time = time.time()
                    ctx = dict(context or {})
                    if project_id and "project_id" not in ctx:
                        ctx["project_id"] = project_id
                    res_str = exec_func_tool(tool_name, arguments, context=ctx)
                    latency_ms = int((time.time() - start_time) * 1000)
                    is_err = str(res_str).startswith("Error:")
                    return ToolResult(
                        status="error" if is_err else "success",
                        data=None if is_err else res_str,
                        error=res_str if is_err else None,
                        metadata={"latency_ms": latency_ms, "tool_name": tool_name}
                    )
            except Exception as e:
                logger.exception("Fallback functional tool execution failed for '%s': %s", tool_name, e)

            logger.warning("Attempted to execute unregistered tool: '%s'", tool_name)
            return ToolResult(
                status="error",
                error=f"Unrecognized tool: '{tool_name}' is not registered in the system.",
                metadata={"tool_name": tool_name}
            )

        start_time = time.time()
        try:
            logger.info("Executing tool '%s' with args=%s (project_id=%s)", tool_name, arguments, project_id)
            result = await tool.execute(project_id=project_id, **arguments)
            latency_ms = int((time.time() - start_time) * 1000)
            result.metadata["latency_ms"] = latency_ms
            result.metadata["tool_name"] = tool_name
            return result
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.exception("Error executing tool '%s': %s", tool_name, e)
            return ToolResult(
                status="error",
                error=str(e),
                metadata={"latency_ms": latency_ms, "tool_name": tool_name}
            )
