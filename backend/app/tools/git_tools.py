import sys
import logging
import shlex
from pathlib import Path
from typing import Any, Optional

from app.tools.base import BaseTool, ToolResult, PermissionLevel, PermissionDeniedError
from app.tools.filesystem import validate_directory_path
from app.sandbox.manager import SandboxManager

logger = logging.getLogger("jarvis.tools.git")


def quote_arg(arg: str) -> str:
    """
    Safely quotes command line arguments for cross-platform subprocess shell execution.
    On Windows (cmd.exe), wraps in double quotes. On POSIX, uses shlex.quote.
    """
    if sys.platform == "win32":
        escaped = arg.replace('"', '""')
        return f'"{escaped}"'
    return shlex.quote(arg)


class BaseGitTool(BaseTool):
    """
    Base class for workspace-gated Git tools (Build Plan §11).
    """

    def __init__(self, sandbox_manager: Optional[SandboxManager] = None):
        self.sandbox_manager = sandbox_manager or SandboxManager()

    def _resolve_safe_cwd(
        self,
        cwd: str,
        project_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
    ) -> Path:
        safe_cwd = validate_directory_path(cwd, project_id=project_id, allowed_folders=allowed_folders)
        if not safe_cwd.exists() or not safe_cwd.is_dir():
            raise FileNotFoundError(f"Working directory does not exist: '{cwd}'")
        return safe_cwd


class GitStatusTool(BaseGitTool):
    """
    Retrieves porcelain git status in the project workspace (Build Plan §11).
    """
    name = "git.status"
    description = "Check git status in the project workspace (porcelain format)."
    permission_level = PermissionLevel.LOW_RISK
    parameters = {
        "type": "object",
        "properties": {
            "cwd": {
                "type": "string",
                "description": "Path to git repository working directory (defaults to workspace root)",
                "default": "."
            }
        }
    }

    async def execute(
        self,
        cwd: str = ".",
        project_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_cwd = self._resolve_safe_cwd(cwd, project_id, allowed_folders)
            res = await self.sandbox_manager.execute("git status --porcelain", cwd=str(safe_cwd))

            if res.exit_code != 0:
                return ToolResult(
                    status="error",
                    error=f"Git status failed (code {res.exit_code}): {res.stderr.strip() or res.stdout.strip()}",
                    metadata={"exit_code": res.exit_code, "cwd": str(safe_cwd)}
                )

            output = res.stdout.strip()
            summary = "Git working tree clean" if not output else f"{len(output.splitlines())} modified/untracked file(s)"
            return ToolResult(
                status="success",
                result=output or "Working tree clean. Nothing to commit.",
                summary=summary,
                metadata={"cwd": str(safe_cwd), "raw_status": output}
            )
        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Git status error: {e}")


class GitDiffTool(BaseGitTool):
    """
    Shows git diff for unstaged or staged changes in the workspace (Build Plan §11).
    """
    name = "git.diff"
    description = "View git diff for working tree or staged changes in the project workspace."
    permission_level = PermissionLevel.LOW_RISK
    parameters = {
        "type": "object",
        "properties": {
            "cwd": {
                "type": "string",
                "description": "Path to git repository working directory",
                "default": "."
            },
            "file_path": {
                "type": "string",
                "description": "Optional specific file path to diff"
            },
            "staged": {
                "type": "boolean",
                "description": "Whether to view staged changes (--staged)",
                "default": False
            }
        }
    }

    async def execute(
        self,
        cwd: str = ".",
        file_path: Optional[str] = None,
        staged: bool = False,
        project_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_cwd = self._resolve_safe_cwd(cwd, project_id, allowed_folders)
            cmd = "git diff --staged" if staged else "git diff"
            if file_path and file_path.strip():
                cmd += f" -- {quote_arg(file_path.strip())}"

            res = await self.sandbox_manager.execute(cmd, cwd=str(safe_cwd))

            if res.exit_code != 0:
                return ToolResult(
                    status="error",
                    error=f"Git diff failed (code {res.exit_code}): {res.stderr.strip() or res.stdout.strip()}",
                    metadata={"exit_code": res.exit_code, "cwd": str(safe_cwd)}
                )

            output = res.stdout.strip()
            summary = "No diff changes" if not output else f"Git diff ({len(output.splitlines())} lines)"
            return ToolResult(
                status="success",
                result=output or "No diff detected.",
                summary=summary,
                metadata={"cwd": str(safe_cwd), "staged": staged}
            )
        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Git diff error: {e}")


class GitLogTool(BaseGitTool):
    """
    Retrieves commit history in the workspace (Build Plan §11).
    """
    name = "git.log"
    description = "View commit history in the project workspace."
    permission_level = PermissionLevel.LOW_RISK
    parameters = {
        "type": "object",
        "properties": {
            "cwd": {
                "type": "string",
                "description": "Path to git repository working directory",
                "default": "."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of commits to retrieve (default 10)",
                "default": 10
            },
            "file_path": {
                "type": "string",
                "description": "Optional file path to filter history for"
            }
        }
    }

    async def execute(
        self,
        cwd: str = ".",
        limit: int = 10,
        file_path: Optional[str] = None,
        project_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_cwd = self._resolve_safe_cwd(cwd, project_id, allowed_folders)
            safe_limit = max(1, min(limit, 100))
            cmd = f"git log -n {safe_limit} --oneline"
            if file_path and file_path.strip():
                cmd += f" -- {quote_arg(file_path.strip())}"

            res = await self.sandbox_manager.execute(cmd, cwd=str(safe_cwd))

            if res.exit_code != 0:
                return ToolResult(
                    status="error",
                    error=f"Git log failed (code {res.exit_code}): {res.stderr.strip() or res.stdout.strip()}",
                    metadata={"exit_code": res.exit_code, "cwd": str(safe_cwd)}
                )

            output = res.stdout.strip()
            count = len(output.splitlines()) if output else 0
            summary = f"Retrieved {count} commit(s)"
            return ToolResult(
                status="success",
                result=output or "No commits found in branch history.",
                summary=summary,
                metadata={"cwd": str(safe_cwd), "count": count}
            )
        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Git log error: {e}")


class GitCheckoutTool(BaseGitTool):
    """
    Switches branches or restores working tree files (Build Plan §11).
    """
    name = "git.checkout"
    description = "Switch git branches or restore files in the workspace."
    permission_level = PermissionLevel.CONFIRMATION_REQUIRED
    parameters = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Branch name or file path to checkout/restore"
            },
            "cwd": {
                "type": "string",
                "description": "Path to git repository working directory",
                "default": "."
            }
        },
        "required": ["target"]
    }

    async def execute(
        self,
        target: str,
        cwd: str = ".",
        project_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            if not target or not target.strip():
                return ToolResult(status="error", error="Checkout target argument cannot be empty.")

            safe_cwd = self._resolve_safe_cwd(cwd, project_id, allowed_folders)
            cmd = f"git checkout {quote_arg(target.strip())}"
            res = await self.sandbox_manager.execute(cmd, cwd=str(safe_cwd))

            if res.exit_code != 0:
                return ToolResult(
                    status="error",
                    error=f"Git checkout failed (code {res.exit_code}): {res.stderr.strip() or res.stdout.strip()}",
                    metadata={"exit_code": res.exit_code, "cwd": str(safe_cwd)}
                )

            summary = f"Checked out '{target}' successfully"
            return ToolResult(
                status="success",
                result=res.stderr.strip() or res.stdout.strip() or summary,
                summary=summary,
                metadata={"cwd": str(safe_cwd), "target": target}
            )
        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Git checkout error: {e}")


class GitCommitTool(BaseGitTool):
    """
    Stages all changes and creates a new git commit (Build Plan §11).
    """
    name = "git.commit"
    description = "Stage all modified files and create a git commit in the workspace."
    permission_level = PermissionLevel.CONFIRMATION_REQUIRED
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Git commit message"
            },
            "cwd": {
                "type": "string",
                "description": "Path to git repository working directory",
                "default": "."
            }
        },
        "required": ["message"]
    }

    async def execute(
        self,
        message: str,
        cwd: str = ".",
        project_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            clean_msg = message.strip() if message else ""
            if not clean_msg:
                return ToolResult(status="error", error="Git commit message cannot be empty.")

            safe_cwd = self._resolve_safe_cwd(cwd, project_id, allowed_folders)

            # 1. Stage changes
            add_res = await self.sandbox_manager.execute("git add -A", cwd=str(safe_cwd))
            if add_res.exit_code != 0:
                return ToolResult(
                    status="error",
                    error=f"Git staging (git add -A) failed: {add_res.stderr.strip() or add_res.stdout.strip()}",
                    metadata={"exit_code": add_res.exit_code, "cwd": str(safe_cwd)}
                )

            # 2. Check if anything is staged to prevent empty commits
            diff_check = await self.sandbox_manager.execute("git diff --staged --name-only", cwd=str(safe_cwd))
            if diff_check.exit_code == 0 and not diff_check.stdout.strip():
                return ToolResult(
                    status="error",
                    error="Nothing to commit (working tree clean). Empty commits are prohibited.",
                    metadata={"cwd": str(safe_cwd)}
                )

            # 3. Create commit
            commit_cmd = f"git commit -m {quote_arg(clean_msg)}"
            res = await self.sandbox_manager.execute(commit_cmd, cwd=str(safe_cwd))

            if res.exit_code != 0:
                return ToolResult(
                    status="error",
                    error=f"Git commit failed (code {res.exit_code}): {res.stderr.strip() or res.stdout.strip()}",
                    metadata={"exit_code": res.exit_code, "cwd": str(safe_cwd)}
                )

            output = res.stdout.strip() or res.stderr.strip()
            summary = f"Committed: '{clean_msg[:50]}...'" if len(clean_msg) > 50 else f"Committed: '{clean_msg}'"
            return ToolResult(
                status="success",
                result=output,
                summary=summary,
                metadata={"cwd": str(safe_cwd), "message": clean_msg}
            )
        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Git commit error: {e}")
