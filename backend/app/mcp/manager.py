import logging
import sys
from pathlib import Path
from typing import Any, Optional
from app.mcp.client import MCPClient
from app.mcp.protocol import MCPTool

logger = logging.getLogger("jarvis.mcp.manager")


class MCPManager:
    """
    Manages MCP server connections, tool discovery, schema translation, and tool execution.
    """

    def __init__(self):
        self._servers: dict[str, MCPClient] = {}
        self._tool_to_server: dict[str, str] = {}
        self._cached_tools: dict[str, MCPTool] = {}
        self._auto_register_builtins()

    def _auto_register_builtins(self) -> None:
        """
        Register the built-in system diagnostics MCP server.
        """
        server_script = Path(__file__).resolve().parent / "builtin_servers" / "system_mcp_server.py"
        if server_script.exists():
            python_exe = sys.executable
            self.register_server("system_diagnostics", [python_exe, str(server_script)])

    def register_server(self, name: str, command: list[str]) -> None:
        if name in self._servers:
            logger.info("MCP server '%s' already registered. Replacing.", name)
        self._servers[name] = MCPClient(name=name, command=command)

    async def connect_all(self) -> None:
        """
        Connect to all registered MCP servers and discover their tools.
        """
        for name, client in self._servers.items():
            try:
                await client.connect()
                tools = await client.list_tools()
                for tool in tools:
                    self._cached_tools[tool.name] = tool
                    self._tool_to_server[tool.name] = name
                logger.info("MCP server '%s' connected successfully. %d tool(s) registered.", name, len(tools))
            except Exception as e:
                logger.warning("Failed to connect to MCP server '%s': %s", name, e)

    async def disconnect_all(self) -> None:
        """
        Disconnect from all MCP servers.
        """
        for client in self._servers.values():
            try:
                await client.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting MCP client '%s': %s", client.name, e)
        self._tool_to_server.clear()
        self._cached_tools.clear()

    def is_mcp_tool(self, tool_name: str) -> bool:
        return tool_name in self._tool_to_server

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        server_name = self._tool_to_server.get(tool_name)
        if not server_name or server_name not in self._servers:
            return f"Error: MCP tool '{tool_name}' is not routed to an active server."

        client = self._servers[server_name]
        try:
            result = await client.call_tool(tool_name, arguments)
            return result.text or f"Tool '{tool_name}' executed successfully with no text output."
        except Exception as e:
            return f"Error executing MCP tool '{tool_name}': {str(e)}"

    def get_tool_definitions(self, filter_names: Optional[list[str]] = None) -> list[dict[str, Any]]:
        """
        Translate MCP tools to Ollama/OpenAI standard tool schemas.
        """
        definitions = []
        for name, tool in self._cached_tools.items():
            if filter_names is not None and name not in filter_names:
                continue

            schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema or {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            definitions.append(schema)

        return definitions

    def list_servers(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "connected": client.is_connected,
                "command": client.command,
                "tools": [t for t, s in self._tool_to_server.items() if s == name]
            }
            for name, client in self._servers.items()
        ]
