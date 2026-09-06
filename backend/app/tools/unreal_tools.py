import os
import glob
import json
import logging
import asyncio
from pathlib import Path
from typing import Any, Optional

from app.tools.base import BaseTool, ToolResult, PermissionLevel, PermissionDeniedError
from app.tools.filesystem import validate_directory_path, validate_path
from app.sandbox.manager import SandboxManager

logger = logging.getLogger("jarvis.tools.unreal")


class UnrealDetectProjectTool(BaseTool):
    """
    Detects and inspects Unreal Engine .uproject manifests inside workspace (Build Plan §14).
    """
    name = "unreal.detect_project"
    description = "Detect and inspect an Unreal Engine project (.uproject) inside the workspace."
    permission_level = PermissionLevel.LOW_RISK
    parameters = {
        "type": "object",
        "properties": {
            "search_path": {
                "type": "string",
                "description": "Directory or .uproject path inside workspace to inspect (defaults to workspace root)",
                "default": "."
            }
        }
    }

    async def execute(
        self,
        search_path: str = ".",
        project_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_target = validate_path(search_path, project_id=project_id, allowed_folders=allowed_folders)

            # 1. Locate .uproject file
            if safe_target.is_file() and safe_target.suffix.lower() == ".uproject":
                uproject_files = [safe_target]
            elif safe_target.is_dir():
                uproject_files = list(safe_target.glob("*.uproject"))
                if not uproject_files:
                    # Recursive search up to 2 levels deep
                    uproject_files = list(safe_target.glob("*/*.uproject"))
            else:
                return ToolResult(status="error", error=f"Target path does not exist: '{search_path}'")

            if not uproject_files:
                return ToolResult(
                    status="error",
                    error=f"No Unreal Engine (.uproject) file found in '{search_path}'.",
                    metadata={"path": str(safe_target)}
                )

            target_uproject = uproject_files[0]
            project_dir = target_uproject.parent

            # 2. Parse .uproject JSON
            content = await asyncio.to_thread(target_uproject.read_text, encoding="utf-8", errors="replace")
            try:
                data = json.loads(content)
            except Exception as e:
                return ToolResult(
                    status="error",
                    error=f"Failed parsing .uproject JSON in '{target_uproject.name}': {e}",
                    metadata={"file": str(target_uproject)}
                )

            engine_version = data.get("EngineAssociation", "Unknown")
            modules = data.get("Modules", [])
            plugins = data.get("Plugins", [])
            description = data.get("Description", "")
            category = data.get("Category", "")

            # 3. Check for Source and Plugins folders
            has_source = (project_dir / "Source").exists()
            has_plugins = (project_dir / "Plugins").exists()
            has_config = (project_dir / "Config").exists()

            result = {
                "project_name": target_uproject.stem,
                "uproject_path": str(target_uproject),
                "project_directory": str(project_dir),
                "engine_version": str(engine_version),
                "description": description,
                "category": category,
                "modules_count": len(modules),
                "modules": modules,
                "plugins_count": len(plugins),
                "plugins": plugins,
                "has_source": has_source,
                "has_plugins": has_plugins,
                "has_config": has_config,
            }

            summary = f"Detected Unreal Project: '{target_uproject.stem}' (Engine {engine_version}, {len(modules)} module(s))"
            return ToolResult(
                status="success",
                result=result,
                summary=summary,
                metadata={"uproject_path": str(target_uproject), "engine_version": str(engine_version)}
            )

        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            logger.exception("Error detecting Unreal project: %s", e)
            return ToolResult(status="error", error=f"Unreal project detection error: {e}")


class UnrealReadLogsTool(BaseTool):
    """
    Reads and tails recent log entries from the project's Saved/Logs/ directory (Build Plan §14).
    """
    name = "unreal.read_logs"
    description = "Read recent log entries from the Unreal Engine project Saved/Logs directory."
    permission_level = PermissionLevel.LOW_RISK
    parameters = {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Path to Unreal project root directory or .uproject file",
                "default": "."
            },
            "lines_count": {
                "type": "integer",
                "description": "Number of tail log lines to retrieve (default 100)",
                "default": 100
            }
        }
    }

    async def execute(
        self,
        project_path: str = ".",
        lines_count: int = 100,
        project_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_target = validate_path(project_path, project_id=project_id, allowed_folders=allowed_folders)

            proj_dir = safe_target if safe_target.is_dir() else safe_target.parent
            logs_dir = proj_dir / "Saved" / "Logs"

            if not logs_dir.exists() or not logs_dir.is_dir():
                return ToolResult(
                    status="error",
                    error=f"Unreal logs directory not found at '{logs_dir}'. Run or cook the project first to generate logs.",
                    metadata={"logs_dir": str(logs_dir)}
                )

            # Find newest .log file
            log_files = list(logs_dir.glob("*.log"))
            if not log_files:
                return ToolResult(
                    status="error",
                    error=f"No .log files found in '{logs_dir}'.",
                    metadata={"logs_dir": str(logs_dir)}
                )

            newest_log = max(log_files, key=lambda p: p.stat().st_mtime)

            def _read_tail() -> tuple[str, int]:
                with open(newest_log, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                tail_lines = lines[-max(1, lines_count):]
                return "".join(tail_lines), len(lines)

            content, total_lines = await asyncio.to_thread(_read_tail)

            summary = f"Read last {min(lines_count, total_lines)} lines from '{newest_log.name}'"
            return ToolResult(
                status="success",
                result=content,
                summary=summary,
                metadata={
                    "log_file": str(newest_log),
                    "total_lines": total_lines,
                    "retrieved_lines": min(lines_count, total_lines),
                }
            )

        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Unreal log reading error: {e}")


class UnrealBuildTool(BaseTool):
    """
    Constructs and executes Unreal Engine build commands via SandboxManager (Build Plan §14).
    """
    name = "unreal.build"
    description = "Trigger Unreal Engine build via UnrealBuildTool or RunUAT (Requires Confirmation)."
    permission_level = PermissionLevel.CONFIRMATION_REQUIRED
    parameters = {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Path to the .uproject file or Unreal project root directory"
            },
            "target": {
                "type": "string",
                "description": "Build target (e.g. Editor, Game, Client, Server)",
                "default": "Editor"
            },
            "config": {
                "type": "string",
                "description": "Build configuration (Development, Shipping, DebugGame)",
                "default": "Development"
            },
            "platform": {
                "type": "string",
                "description": "Target platform (Win64, Linux, Mac, Android)",
                "default": "Win64"
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Maximum build timeout in seconds (default 600.0)",
                "default": 600.0
            }
        },
        "required": ["project_path"]
    }

    def __init__(self, sandbox_manager: Optional[SandboxManager] = None):
        self.sandbox_manager = sandbox_manager or SandboxManager()

    def _resolve_build_command(
        self,
        uproject_file: Path,
        target: str = "Editor",
        config: str = "Development",
        platform: str = "Win64"
    ) -> str:
        """
        Dynamically locates engine root and constructs appropriate build command.
        """
        project_name = uproject_file.stem
        target_name = f"{project_name}{target}" if target != "Game" else project_name

        # Check standard UE_ROOT environment variable or common install directories
        ue_root = os.environ.get("UE_ROOT") or os.environ.get("UNREAL_ENGINE_ROOT")
        if not ue_root:
            candidates = [
                r"C:\Program Files\Epic Games\UE_5.4",
                r"C:\Program Files\Epic Games\UE_5.3",
                r"C:\Program Files\Epic Games\UE_5.2",
                r"C:\Program Files\Epic Games\UE_5.1",
                r"C:\Program Files\Epic Games\UE_5.0",
            ]
            for c in candidates:
                if os.path.exists(c):
                    ue_root = c
                    break

        if ue_root:
            ubt_path = Path(ue_root) / "Engine" / "Binaries" / "DotNET" / "UnrealBuildTool" / "UnrealBuildTool.exe"
            if ubt_path.exists():
                return f'"{ubt_path}" {target_name} {platform} {config} "{uproject_file}" -waitmutex'

            uat_path = Path(ue_root) / "Engine" / "Build" / "BatchFiles" / "RunUAT.bat"
            if uat_path.exists():
                return f'"{uat_path}" BuildCookRun -project="{uproject_file}" -target={target_name} -platform={platform} -clientconfig={config} -build'

        # Fallback to generic UBT invocation in PATH
        return f'UnrealBuildTool.exe {target_name} {platform} {config} "{uproject_file}" -waitmutex'

    async def execute(
        self,
        project_path: str,
        target: str = "Editor",
        config: str = "Development",
        platform: str = "Win64",
        timeout_seconds: Optional[float] = 600.0,
        project_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_target = validate_path(project_path, project_id=project_id, allowed_folders=allowed_folders)

            # Locate .uproject
            if safe_target.is_file() and safe_target.suffix.lower() == ".uproject":
                uproject_file = safe_target
            elif safe_target.is_dir():
                candidates = list(safe_target.glob("*.uproject"))
                if not candidates:
                    return ToolResult(status="error", error=f"No .uproject file found in directory '{project_path}'.")
                uproject_file = candidates[0]
            else:
                return ToolResult(status="error", error=f"Project path '{project_path}' does not exist.")

            cmd = self._resolve_build_command(
                uproject_file=uproject_file,
                target=target,
                config=config,
                platform=platform
            )

            logger.info("Executing Unreal build command: %s (cwd=%s)", cmd, uproject_file.parent)

            exec_res = await self.sandbox_manager.execute(
                command=cmd,
                cwd=str(uproject_file.parent),
                timeout=timeout_seconds or 600.0
            )

            status = "success" if exec_res.exit_code == 0 else "error"
            summary = f"Unreal build {status} (exit code {exec_res.exit_code}, {exec_res.latency_ms}ms)"
            if exec_res.timed_out:
                summary = f"Unreal build timed out after {timeout_seconds}s"

            return ToolResult(
                status=status,
                result={
                    "command": cmd,
                    "exit_code": exec_res.exit_code,
                    "stdout": exec_res.stdout,
                    "stderr": exec_res.stderr,
                    "timed_out": exec_res.timed_out,
                },
                summary=summary,
                metadata={
                    "uproject": str(uproject_file),
                    "exit_code": exec_res.exit_code,
                    "timed_out": exec_res.timed_out,
                    "latency_ms": exec_res.latency_ms
                }
            )

        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Unreal build dispatch error: {e}")
