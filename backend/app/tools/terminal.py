import time
import logging
from pathlib import Path
from typing import Any, Optional

from app.config import settings
from app.tools.base import BaseTool, ToolResult, PermissionLevel, PermissionDeniedError
from app.tools.filesystem import validate_directory_path, validate_path
from app.agent.tool_result_truncator import truncate_tool_result
from app.sandbox.manager import SandboxManager
from app.sandbox.local_process import kill_process_tree

logger = logging.getLogger("jarvis.tools.terminal")


class TerminalExecuteTool(BaseTool):
    """
    Executes terminal commands safely inside the project workspace sandbox with hard timeouts.
    Uses pluggable SandboxManager backend (Build Plan §12).
    """
    name = "terminal.execute"
    description = "Execute a shell command inside the project workspace directory. Captures stdout and stderr with strict timeout."
    permission_level = PermissionLevel.CONFIRMATION_REQUIRED
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command line to execute"
            },
            "cwd": {
                "type": "string",
                "description": "Working directory path inside the project workspace (defaults to workspace root)",
                "default": "."
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Maximum execution duration before process is killed (defaults to system setting)",
            }
        },
        "required": ["command"]
    }

    def __init__(self, sandbox_manager: Optional[SandboxManager] = None):
        self.sandbox_manager = sandbox_manager or SandboxManager()

    async def execute(
        self,
        command: str,
        cwd: str = ".",
        project_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        start_time = time.time()
        try:
            # 1. Path Sandbox Guard: working directory must be strictly inside the sandbox
            safe_cwd = validate_directory_path(cwd, project_id=project_id, allowed_folders=allowed_folders)
            if not safe_cwd.exists() or not safe_cwd.is_dir():
                return ToolResult(status="error", error=f"Working directory does not exist or is not a directory: '{cwd}'")

            effective_timeout = timeout_seconds or settings.terminal_timeout_seconds

            logger.info("Executing terminal command: '%s' in cwd='%s' (timeout=%.1fs)", command, safe_cwd, effective_timeout)

            # 2. Dispatch to SandboxManager
            exec_res = await self.sandbox_manager.execute(
                command=command,
                cwd=str(safe_cwd),
                timeout=effective_timeout,
            )

            # 3. Truncate outputs to protect KV Cache
            trunc_stdout, std_truncated = truncate_tool_result(exec_res.stdout)
            trunc_stderr, err_truncated = truncate_tool_result(exec_res.stderr)

            latency_ms = int((time.time() - start_time) * 1000)

            result_payload = {
                "command": command,
                "exit_code": exec_res.exit_code,
                "stdout": trunc_stdout,
                "stderr": trunc_stderr,
                "timed_out": exec_res.timed_out,
            }

            status = "success" if exec_res.exit_code == 0 and not exec_res.timed_out else "error"
            summary = f"Command exited with code {exec_res.exit_code} ({latency_ms}ms)"
            if exec_res.timed_out:
                summary = f"Command timed out after {effective_timeout}s"

            return ToolResult(
                status=status,
                result=result_payload,
                summary=summary,
                truncated=std_truncated or err_truncated,
                metadata={
                    "exit_code": exec_res.exit_code,
                    "latency_ms": latency_ms,
                    "cwd": str(safe_cwd),
                    "timed_out": exec_res.timed_out
                }
            )

        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                status="error",
                error=f"Terminal execution error: {e}",
                metadata={"latency_ms": latency_ms}
            )
