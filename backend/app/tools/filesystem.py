import os
import json
import uuid
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, select
from app.database.session import engine
from app.database.models import Project, Artifact, ArtifactVersion
from app.tools.base import BaseTool, ToolResult, PermissionLevel, PermissionDeniedError

logger = logging.getLogger("jarvis.tools.filesystem")


def get_project_allowed_folders(project_id: Optional[str] = None) -> list[Path]:
    """
    Resolve allowed base directories for a project.
    Always includes the dedicated workspace project directory and any project-attached local folders.
    """
    workspace_root = Path("workspace").resolve()
    allowed: list[Path] = []

    if project_id:
        proj_dir = (workspace_root / "projects" / project_id).resolve()
        proj_dir.mkdir(parents=True, exist_ok=True)
        allowed.append(proj_dir)

        # Check DB for attached local folders
        try:
            with Session(engine) as session:
                project = session.get(Project, project_id)

                if project:
                    if project.workspace_path:
                        allowed.append(Path(project.workspace_path).resolve())
                    if project.local_folders_json:
                        try:
                            folders = json.loads(project.local_folders_json)
                            if isinstance(folders, list):
                                for f in folders:
                                    if isinstance(f, str) and os.path.exists(f):
                                        allowed.append(Path(f).resolve())
                        except Exception:
                            pass
        except Exception as e:
            logger.debug("Could not query project folders from DB: %s", e)
    else:
        # Default workspace root if no specific project is active
        workspace_root.mkdir(parents=True, exist_ok=True)
        allowed.append(workspace_root)

    return allowed


def validate_path(
    requested_path: str,
    project_id: Optional[str] = None,
    allowed_folders: Optional[list[str | Path]] = None
) -> Path:
    """
    Security Sandbox Guard (Build Plan Section 11 & Amendment 1):
    Resolves canonical filesystem paths (resolving all symlinks and '..' segments)
    and asserts that the target is strictly contained within allowed folders.
    """
    if not requested_path or not str(requested_path).strip():
        raise ValueError("Path argument cannot be empty.")

    # 1. Determine allowed folder roots
    if allowed_folders:
        resolved_allowed = [Path(f).resolve() for f in allowed_folders]
    else:
        resolved_allowed = get_project_allowed_folders(project_id)

    primary_root = resolved_allowed[0] if resolved_allowed else Path("workspace").resolve()

    # 2. Canonicalize path
    raw_path = Path(requested_path)
    if not raw_path.is_absolute():
        candidate = (primary_root / raw_path).resolve()
    else:
        candidate = raw_path.resolve()

    # 3. Verify target is within at least one allowed directory
    is_allowed = False
    for allowed_root in resolved_allowed:
        try:
            if candidate == allowed_root or candidate.is_relative_to(allowed_root):
                is_allowed = True
                break
        except AttributeError:
            try:
                candidate.relative_to(allowed_root)
                is_allowed = True
                break
            except ValueError:
                pass

    if not is_allowed:
        logger.warning(
            "Security violation: path '%s' resolved to '%s' outside sandbox roots (%s)",
            requested_path,
            candidate,
            resolved_allowed
        )
        raise PermissionDeniedError(
            f"Access denied: '{requested_path}' resolves outside the allowed project sandbox."
        )

    return candidate


def validate_directory_path(
    requested_path: str,
    project_id: Optional[str] = None,
    allowed_folders: Optional[list[str | Path]] = None
) -> Path:
    """
    Validates that requested_path resolves within allowed project workspace folders
    and is safe for working directory usage (Amendment 2).
    """
    safe_path = validate_path(requested_path, project_id=project_id, allowed_folders=allowed_folders)
    if safe_path.exists() and not safe_path.is_dir():
        raise PermissionDeniedError(f"Target path '{requested_path}' is a file, expected a directory.")
    return safe_path


def _save_file_version_snapshot(
    safe_path: Path,
    project_id: Optional[str] = None,
    summary: Optional[str] = None
) -> None:
    """
    Build Plan Section 16: Versioning Hook.
    Saves snapshot of existing file before write or edit into the Artifacts/ArtifactVersions DB.
    """
    if not safe_path.exists() or not safe_path.is_file():
        return

    try:
        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            existing_content = f.read()

        file_name = safe_path.name
        with Session(engine) as session:
            # Query existing artifact for this file
            statement = select(Artifact).where(Artifact.name == file_name)
            if project_id:
                statement = statement.where(Artifact.project_id == project_id)
            artifact = session.exec(statement).first()

            if artifact:
                # Add version record for previous state
                art_version = ArtifactVersion(
                    id=str(uuid.uuid4()),
                    artifact_id=artifact.id,
                    version=artifact.version,
                    content=existing_content,
                    summary=summary or f"Version {artifact.version} before file update",
                    created_at=datetime.utcnow()
                )
                session.add(art_version)
                artifact.version += 1
                artifact.updated_at = datetime.utcnow()
                session.add(artifact)
            else:
                # Create initial artifact and version 1
                art_id = str(uuid.uuid4())
                new_artifact = Artifact(
                    id=art_id,
                    project_id=project_id,
                    name=file_name,
                    type="code",
                    content=existing_content,
                    version=1,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(new_artifact)
                art_version = ArtifactVersion(
                    id=str(uuid.uuid4()),
                    artifact_id=art_id,
                    version=1,
                    content=existing_content,
                    summary=summary or "Initial snapshot before edit",
                    created_at=datetime.utcnow()
                )
                session.add(art_version)

            session.commit()
            logger.info("Saved version snapshot for '%s'", file_name)
    except Exception as e:
        logger.warning("Could not record artifact version snapshot for '%s': %s", safe_path, e)


class ReadFileTool(BaseTool):
    """
    Reads file content safely from within the project workspace.
    """
    name = "filesystem.read"
    description = "Read the contents of a file inside the project workspace. Supports optional start_line and end_line parameters."
    permission_level = PermissionLevel.LOW_RISK
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative or absolute path to the file inside the project workspace"
            },
            "start_line": {
                "type": "integer",
                "description": "Optional 1-indexed starting line number"
            },
            "end_line": {
                "type": "integer",
                "description": "Optional 1-indexed ending line number (inclusive)"
            }
        },
        "required": ["path"]
    }

    async def execute(
        self,
        path: str,
        project_id: Optional[str] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_path = validate_path(path, project_id=project_id, allowed_folders=allowed_folders)
            if not safe_path.exists():
                return ToolResult(
                    status="error",
                    error=f"File not found: '{path}'"
                )
            if not safe_path.is_file():
                return ToolResult(
                    status="error",
                    error=f"Path is not a file: '{path}'"
                )

            def _read() -> tuple[str, int, int]:
                with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                total_lines = len(lines)
                s = max(1, start_line) if start_line is not None else 1
                e = min(total_lines, end_line) if end_line is not None else total_lines
                sliced = lines[s - 1 : e]
                return "".join(sliced), total_lines, len(sliced)

            content, total_lines, sliced_count = await asyncio.to_thread(_read)

            summary = f"Read {sliced_count} lines from {path}"
            if start_line or end_line:
                summary += f" (lines {start_line or 1}-{end_line or total_lines} of {total_lines})"

            return ToolResult(
                status="success",
                result=content,
                summary=summary,
                metadata={
                    "path": str(safe_path),
                    "total_lines": total_lines,
                    "sliced_lines": sliced_count
                }
            )
        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Failed to read file: {e}")


class WriteFileTool(BaseTool):
    """
    Writes or overwrites a file inside the project sandbox.
    """
    name = "filesystem.write"
    description = "Create or overwrite a file in the project workspace. Automatically creates parent directories and takes version snapshots."
    permission_level = PermissionLevel.LOW_RISK
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative or absolute path to the target file inside the workspace"
            },
            "content": {
                "type": "string",
                "description": "Text content to write into the file"
            },
            "overwrite": {
                "type": "boolean",
                "description": "Whether to overwrite if file already exists (default true)",
                "default": True
            }
        },
        "required": ["path", "content"]
    }

    def __init__(self, file_version_service: Optional[Any] = None):
        self.file_version_service = file_version_service

    async def execute(
        self,
        path: str,
        content: str,
        overwrite: bool = True,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_path = validate_path(path, project_id=project_id, allowed_folders=allowed_folders)

            if safe_path.exists() and not overwrite:
                return ToolResult(
                    status="error",
                    error=f"File already exists at '{path}' and overwrite is set to False."
                )

            # 1. Versioning Hook
            if safe_path.exists():
                if self.file_version_service:
                    await asyncio.to_thread(
                        self.file_version_service.capture_version,
                        str(safe_path),
                        session_id or "default",
                        "agent"
                    )
                await asyncio.to_thread(_save_file_version_snapshot, safe_path, project_id, "Snapshot before file overwrite")

            # 2. Write file
            def _write():
                safe_path.parent.mkdir(parents=True, exist_ok=True)
                with open(safe_path, "w", encoding="utf-8") as f:
                    f.write(content)

            await asyncio.to_thread(_write)

            summary = f"Wrote {len(content)} characters to {path}"
            return ToolResult(
                status="success",
                result=f"Successfully wrote {len(content)} characters to {path}",
                summary=summary,
                metadata={"path": str(safe_path), "bytes": len(content.encode("utf-8"))}
            )
        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Failed to write file: {e}")


class EditFileTool(BaseTool):
    """
    Performs targeted diff-based search-and-replace in a workspace file (Build Plan Section 16).
    """
    name = "filesystem.edit"
    description = "Edit a file in the project workspace by replacing targeted old text with new text. Avoids full file rewrites."
    permission_level = PermissionLevel.LOW_RISK
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the target file inside the workspace"
            },
            "old_text": {
                "type": "string",
                "description": "Exact text chunk in the file to be replaced"
            },
            "new_text": {
                "type": "string",
                "description": "Replacement text"
            },
            "allow_multiple": {
                "type": "boolean",
                "description": "Whether to replace multiple occurrences if found (default false)",
                "default": False
            }
        },
        "required": ["path", "old_text", "new_text"]
    }

    def __init__(self, file_version_service: Optional[Any] = None):
        self.file_version_service = file_version_service

    async def execute(
        self,
        path: str,
        old_text: str,
        new_text: str,
        allow_multiple: bool = False,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_path = validate_path(path, project_id=project_id, allowed_folders=allowed_folders)

            if not safe_path.exists():
                return ToolResult(status="error", error=f"File not found: '{path}'")
            if not safe_path.is_file():
                return ToolResult(status="error", error=f"Path is not a file: '{path}'")

            def _edit() -> tuple[str, int]:
                with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                count = content.count(old_text)
                if count == 0:
                    raise ValueError(f"Target text was not found in '{path}'. Make sure the old_text matches existing file content exactly.")

                if not allow_multiple and count > 1:
                    raise ValueError(f"Target text matched {count} times in '{path}'. Please include more surrounding context or set allow_multiple=True.")

                # Save version snapshot
                if self.file_version_service:
                    self.file_version_service.capture_version(
                        str(safe_path),
                        session_id or "default",
                        "agent"
                    )
                _save_file_version_snapshot(safe_path, project_id, f"Snapshot before editing '{old_text[:30]}...'")

                replaced = content.replace(old_text, new_text) if allow_multiple else content.replace(old_text, new_text, 1)
                with open(safe_path, "w", encoding="utf-8") as f:
                    f.write(replaced)

                return replaced, count

            _, match_count = await asyncio.to_thread(_edit)

            summary = f"Edited {path} (replaced {match_count} occurrence{'s' if match_count > 1 else ''})"
            return ToolResult(
                status="success",
                result=f"Successfully edited '{path}'. Replaced {match_count} occurrence(s).",
                summary=summary,
                metadata={"path": str(safe_path), "replacements": match_count}
            )
        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except ValueError as ve:
            return ToolResult(status="error", error=str(ve))
        except Exception as e:
            return ToolResult(status="error", error=f"Failed to edit file: {e}")


class CreateDirectoryTool(BaseTool):
    """
    Creates directories safely within the project sandbox.
    """
    name = "filesystem.create_directory"
    description = "Create a directory structure within the project workspace."
    permission_level = PermissionLevel.LOW_RISK
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative or absolute directory path to create"
            }
        },
        "required": ["path"]
    }

    async def execute(
        self,
        path: str,
        project_id: Optional[str] = None,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_path = validate_path(path, project_id=project_id, allowed_folders=allowed_folders)

            def _mkdir():
                safe_path.mkdir(parents=True, exist_ok=True)

            await asyncio.to_thread(_mkdir)
            return ToolResult(
                status="success",
                result=f"Directory created: '{path}'",
                summary=f"Created directory {path}",
                metadata={"path": str(safe_path)}
            )
        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Failed to create directory: {e}")


class ListDirectoryTool(BaseTool):
    """
    Lists directory contents within the project workspace.
    """
    name = "filesystem.list_directory"
    description = "List files and subdirectories within a folder inside the project workspace."
    permission_level = PermissionLevel.LOW_RISK
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative or absolute directory path inside the workspace",
                "default": "."
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum directory traversal depth (default 1)",
                "default": 1
            }
        },
        "required": []
    }

    async def execute(
        self,
        path: str = ".",
        project_id: Optional[str] = None,
        max_depth: int = 1,
        allowed_folders: Optional[list[str | Path]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            safe_path = validate_path(path, project_id=project_id, allowed_folders=allowed_folders)
            if not safe_path.exists():
                return ToolResult(status="error", error=f"Directory not found: '{path}'")
            if not safe_path.is_dir():
                return ToolResult(status="error", error=f"Path is not a directory: '{path}'")

            def _scan() -> list[dict[str, Any]]:
                entries = []
                for root, dirs, files in os.walk(safe_path):
                    rel = os.path.relpath(root, safe_path)
                    depth = 0 if rel == "." else len(Path(rel).parts)
                    if depth > max_depth:
                        continue

                    for d in dirs:
                        entries.append({
                            "name": d,
                            "type": "directory",
                            "path": os.path.join(rel, d) if rel != "." else d
                        })
                    for f in files:
                        full_f = os.path.join(root, f)
                        try:
                            size = os.path.getsize(full_f)
                        except Exception:
                            size = 0
                        entries.append({
                            "name": f,
                            "type": "file",
                            "size_bytes": size,
                            "path": os.path.join(rel, f) if rel != "." else f
                        })
                    if depth >= max_depth:
                        dirs.clear()  # Do not recurse deeper
                return entries

            items = await asyncio.to_thread(_scan)
            summary = f"Found {len(items)} items in '{path}'"
            return ToolResult(
                status="success",
                result=items,
                summary=summary,
                metadata={"path": str(safe_path), "count": len(items)}
            )
        except PermissionDeniedError as pe:
            return ToolResult(status="error", error=str(pe))
        except Exception as e:
            return ToolResult(status="error", error=f"Failed to list directory: {e}")
