import asyncio
import json
import logging
import os
import sys
from typing import Any, Optional
from app.mcp.protocol import MCPTool, MCPToolCallResult

logger = logging.getLogger("jarvis.mcp.client")


class MCPClient:
    """
    Asynchronous Model Context Protocol (MCP) client communicating via JSON-RPC 2.0 over stdio.
    """

    def __init__(self, name: str, command: list[str], env: Optional[dict[str, str]] = None):
        self.name = name
        self.command = command
        self.env = env or os.environ.copy()
        self._process: Optional[asyncio.subprocess.Process] = None
        self._req_id = 0
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def connect(self) -> None:
        """
        Spawn MCP server subprocess and perform JSON-RPC handshake.
        """
        if self.is_connected:
            return

        logger.info("Connecting to MCP server '%s' via %s", self.name, self.command)
        self._process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env
        )

        # 1. Send initialize request
        init_response = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "JarvisAssistant", "version": "1.0.0"}
        })
        logger.info("MCP server '%s' initialized: %s", self.name, init_response)

        # 2. Send initialized notification
        await self._send_notification("notifications/initialized", {})

    async def disconnect(self) -> None:
        """
        Cleanly terminate the MCP server subprocess.
        """
        if not self._process:
            return

        logger.info("Disconnecting from MCP server '%s'", self.name)
        try:
            if self._process.stdin:
                self._process.stdin.close()
                await self._process.stdin.wait_closed()
            self._process.terminate()
            await asyncio.wait_for(self._process.wait(), timeout=3.0)
        except Exception as e:
            logger.warning("Force killing MCP server '%s': %s", self.name, e)
            try:
                self._process.kill()
            except Exception:
                pass
        finally:
            self._process = None

    async def list_tools(self) -> list[MCPTool]:
        """
        Query available tools from the MCP server.
        """
        response = await self._send_request("tools/list", {})
        tools_data = response.get("tools", []) if isinstance(response, dict) else []
        
        tools = []
        for t in tools_data:
            tools.append(MCPTool(
                name=t.get("name", ""),
                description=t.get("description", ""),
                inputSchema=t.get("inputSchema", {})
            ))
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolCallResult:
        """
        Invoke a specific tool on the MCP server.
        """
        response = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })

        content = response.get("content", []) if isinstance(response, dict) else []
        is_error = response.get("isError", False) if isinstance(response, dict) else False

        return MCPToolCallResult(content=content, isError=is_error)

    async def _send_request(self, method: str, params: dict[str, Any]) -> Any:
        async with self._lock:
            if not self.is_connected or not self._process or not self._process.stdin or not self._process.stdout:
                raise RuntimeError(f"MCP server '{self.name}' is not connected.")

            self._req_id += 1
            request_payload = {
                "jsonrpc": "2.0",
                "id": self._req_id,
                "method": method,
                "params": params
            }

            raw_request = json.dumps(request_payload) + "\n"
            self._process.stdin.write(raw_request.encode("utf-8"))
            await self._process.stdin.drain()

            raw_line = await self._process.stdout.readline()
            if not raw_line:
                raise RuntimeError(f"MCP server '{self.name}' closed connection unexpectedly.")

            try:
                response = json.loads(raw_line.decode("utf-8"))
            except Exception as e:
                raise RuntimeError(f"Invalid JSON response from MCP server '{self.name}': {raw_line.decode('utf-8')}")

            if "error" in response:
                err = response["error"]
                raise RuntimeError(f"MCP server error ({err.get('code')}): {err.get('message')}")

            return response.get("result")

    async def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        async with self._lock:
            if not self.is_connected or not self._process or not self._process.stdin:
                return

            notification = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params
            }
            raw = json.dumps(notification) + "\n"
            self._process.stdin.write(raw.encode("utf-8"))
            await self._process.stdin.drain()
