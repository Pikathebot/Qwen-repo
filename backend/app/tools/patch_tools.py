import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from app.tools.base import BaseTool, ToolResult, PermissionLevel, PermissionDeniedError
from app.tools.filesystem import validate_path
from app.services.patch_validator import PatchValidator
from app.services.file_version_service import FileVersionService

logger = logging.getLogger("jarvis.tools.patch")


class ApplyPatchTool(BaseTool):
    """
    Applies a unified diff patch to a file in the project workspace (Build Plan §16).
    """
    name = "apply_patch"
    description = "Apply a unified diff patch to a file in the workspace. Validates context lines and line numbers before applying changes."
    permission_level = PermissionLevel.CONFIRMATION_REQUIRED
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the target file inside the workspace"
            },
            "patch": {
                "type": "string",
                "description": "Unified diff patch content"
            }
        },
        "required": ["file_path", "patch"]
    }

    def __init__(
        self,
        patch_validator: Optional[PatchValidator] = None,
        file_version_service: Optional[FileVersionService] = None,
    ):
        self.patch_validator = patch_validator or PatchValidator()
        self.file_version_service = file_version_service or FileVersionService()

    async def execute(
        self,
        file_path: str,
        patch: str,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_path = validate_path(file_path, project_id=project_id, allowed_folders=allowed_folders)

            if not safe_path.exists():
                return ToolResult(status="error", error=f"File not found: '{file_path}'")
            if not safe_path.is_file():
                return ToolResult(status="error", error=f"Path is not a file: '{file_path}'")

            # 1. Read existing content
            content = await asyncio.to_thread(safe_path.read_text, encoding="utf-8", errors="replace")

            # 2. Validate patch with tolerant validator
            validation = self.patch_validator.validate_patch(content, patch)
            if not validation.valid:
                errors_str = "\n".join(validation.errors)
                return ToolResult(
                    status="error",
                    error=f"Patch validation failed:\n{errors_str}",
                    metadata={"validation_errors": validation.errors}
                )

            # 3. Capture file version snapshot before modifying
            active_session_id = session_id or "default"
            await asyncio.to_thread(
                self.file_version_service.capture_version,
                str(safe_path),
                active_session_id,
                "agent"
            )

            # 4. Apply patch and save
            new_content, summary = self.patch_validator.apply_unified_diff(content, patch)
            await asyncio.to_thread(safe_path.write_text, new_content, encoding="utf-8")

            logger.info("Applied patch to '%s': %s", safe_path, summary)
            return ToolResult(
                status="success",
                result=f"Patch applied successfully to '{file_path}'. {summary}",
                summary=summary,
                metadata={
                    "path": str(safe_path),
                    "bytes": len(new_content.encode("utf-8")),
                    "warnings": validation.warnings,
                }
            )

        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            logger.exception("Failed to apply patch to '%s': %s", file_path, e)
            return ToolResult(status="error", error=f"Failed to apply patch: {e}")


class ReplaceRangeTool(BaseTool):
    """
    Replaces a specific line range in a workspace file (Build Plan §16).
    """
    name = "replace_range"
    description = "Replace a specific line range in a workspace file with new content."
    permission_level = PermissionLevel.CONFIRMATION_REQUIRED
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the target file inside the workspace"
            },
            "start_line": {
                "type": "integer",
                "description": "1-indexed starting line number of the range to replace"
            },
            "end_line": {
                "type": "integer",
                "description": "1-indexed ending line number of the range to replace (inclusive)"
            },
            "new_content": {
                "type": "string",
                "description": "Replacement text to insert in place of the specified range"
            }
        },
        "required": ["file_path", "start_line", "end_line", "new_content"]
    }

    def __init__(self, file_version_service: Optional[FileVersionService] = None):
        self.file_version_service = file_version_service or FileVersionService()

    async def execute(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        new_content: str,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_path = validate_path(file_path, project_id=project_id, allowed_folders=allowed_folders)

            if not safe_path.exists() or not safe_path.is_file():
                return ToolResult(status="error", error=f"File not found: '{file_path}'")

            content = await asyncio.to_thread(safe_path.read_text, encoding="utf-8", errors="replace")
            lines = content.splitlines(keepends=False)
            total_lines = len(lines)

            if start_line < 1 or start_line > total_lines:
                return ToolResult(
                    status="error",
                    error=f"Invalid start_line {start_line}. File has {total_lines} lines (valid range: 1-{total_lines})."
                )
            if end_line < start_line or end_line > total_lines:
                return ToolResult(
                    status="error",
                    error=f"Invalid end_line {end_line}. Must be between start_line ({start_line}) and total lines ({total_lines})."
                )

            # 1. Snapshot version before modification
            active_session_id = session_id or "default"
            await asyncio.to_thread(
                self.file_version_service.capture_version,
                str(safe_path),
                active_session_id,
                "agent"
            )

            # 2. Replace range
            replacement_lines = new_content.splitlines(keepends=False) if new_content else []
            lines[start_line - 1 : end_line] = replacement_lines

            updated_text = "\n".join(lines)
            if content.endswith("\n"):
                updated_text += "\n"

            await asyncio.to_thread(safe_path.write_text, updated_text, encoding="utf-8")

            summary = f"Replaced lines {start_line}-{end_line} in '{file_path}' with {len(replacement_lines)} line(s)"
            return ToolResult(
                status="success",
                result=summary,
                summary=summary,
                metadata={"path": str(safe_path), "total_lines": len(lines)}
            )

        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Failed replacing line range: {e}")


class InsertTool(BaseTool):
    """
    Inserts content at a specific line number in a workspace file (Build Plan §16).
    """
    name = "insert"
    description = "Insert content at a specific line number in a workspace file."
    permission_level = PermissionLevel.CONFIRMATION_REQUIRED
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the target file inside the workspace"
            },
            "line_number": {
                "type": "integer",
                "description": "1-indexed line number at which to insert content (1 to insert at the top)"
            },
            "content": {
                "type": "string",
                "description": "Content to insert"
            }
        },
        "required": ["file_path", "line_number", "content"]
    }

    def __init__(self, file_version_service: Optional[FileVersionService] = None):
        self.file_version_service = file_version_service or FileVersionService()

    async def execute(
        self,
        file_path: str,
        line_number: int,
        content: str,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_path = validate_path(file_path, project_id=project_id, allowed_folders=allowed_folders)

            if not safe_path.exists() or not safe_path.is_file():
                return ToolResult(status="error", error=f"File not found: '{file_path}'")

            file_content = await asyncio.to_thread(safe_path.read_text, encoding="utf-8", errors="replace")
            lines = file_content.splitlines(keepends=False)
            total_lines = len(lines)

            # Valid insertion index: 1 up to total_lines + 1 (appending at end)
            if line_number < 1 or line_number > total_lines + 1:
                return ToolResult(
                    status="error",
                    error=f"Invalid line_number {line_number}. File has {total_lines} lines (valid range: 1-{total_lines + 1})."
                )

            # 1. Snapshot version before modification
            active_session_id = session_id or "default"
            await asyncio.to_thread(
                self.file_version_service.capture_version,
                str(safe_path),
                active_session_id,
                "agent"
            )

            # 2. Insert content lines
            insert_lines = content.splitlines(keepends=False) if content else []
            insert_idx = line_number - 1
            lines[insert_idx:insert_idx] = insert_lines

            updated_text = "\n".join(lines)
            if file_content.endswith("\n"):
                updated_text += "\n"

            await asyncio.to_thread(safe_path.write_text, updated_text, encoding="utf-8")

            summary = f"Inserted {len(insert_lines)} line(s) at line {line_number} in '{file_path}'"
            return ToolResult(
                status="success",
                result=summary,
                summary=summary,
                metadata={"path": str(safe_path), "total_lines": len(lines)}
            )

        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Failed inserting content: {e}")


class DeleteRangeTool(BaseTool):
    """
    Deletes a specific line range from a workspace file (Build Plan §16).
    """
    name = "delete_range"
    description = "Delete a specific line range from a workspace file."
    permission_level = PermissionLevel.CONFIRMATION_REQUIRED
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the target file inside the workspace"
            },
            "start_line": {
                "type": "integer",
                "description": "1-indexed starting line number of the range to delete"
            },
            "end_line": {
                "type": "integer",
                "description": "1-indexed ending line number of the range to delete (inclusive)"
            }
        },
        "required": ["file_path", "start_line", "end_line"]
    }

    def __init__(self, file_version_service: Optional[FileVersionService] = None):
        self.file_version_service = file_version_service or FileVersionService()

    async def execute(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_path = validate_path(file_path, project_id=project_id, allowed_folders=allowed_folders)

            if not safe_path.exists() or not safe_path.is_file():
                return ToolResult(status="error", error=f"File not found: '{file_path}'")

            content = await asyncio.to_thread(safe_path.read_text, encoding="utf-8", errors="replace")
            lines = content.splitlines(keepends=False)
            total_lines = len(lines)

            if start_line < 1 or start_line > total_lines:
                return ToolResult(
                    status="error",
                    error=f"Invalid start_line {start_line}. File has {total_lines} lines (valid range: 1-{total_lines})."
                )
            if end_line < start_line or end_line > total_lines:
                return ToolResult(
                    status="error",
                    error=f"Invalid end_line {end_line}. Must be between start_line ({start_line}) and total lines ({total_lines})."
                )

            # 1. Snapshot version before modification
            active_session_id = session_id or "default"
            await asyncio.to_thread(
                self.file_version_service.capture_version,
                str(safe_path),
                active_session_id,
                "agent"
            )

            # 2. Delete range
            del lines[start_line - 1 : end_line]

            updated_text = "\n".join(lines)
            if content.endswith("\n"):
                updated_text += "\n"

            await asyncio.to_thread(safe_path.write_text, updated_text, encoding="utf-8")

            deleted_count = end_line - start_line + 1
            summary = f"Deleted lines {start_line}-{end_line} ({deleted_count} lines) from '{file_path}'"
            return ToolResult(
                status="success",
                result=summary,
                summary=summary,
                metadata={"path": str(safe_path), "total_lines": len(lines)}
            )

        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Failed deleting line range: {e}")
