import uuid
import difflib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any

from sqlmodel import Session as DbSession, select, col
from app.database.session import engine
from app.database.models import FileVersion

logger = logging.getLogger("jarvis.services.file_version")


class FileVersionService:
    """
    Manages filesystem snapshots, rollback history, and diff generation (Build Plan §16).
    """

    def __init__(self, db_engine: Optional[Any] = None):
        self.engine = db_engine or engine

    def capture_version(
        self,
        file_path: str,
        session_id: str,
        created_by: str = "agent",
    ) -> Optional[FileVersion]:
        """
        Captures a snapshot of the current file on disk before modification.
        Saves record into file_versions table with auto-incremented version_number.
        """
        path_obj = Path(file_path)
        if not path_obj.exists() or not path_obj.is_file():
            return None

        try:
            content = path_obj.read_text(encoding="utf-8", errors="replace")
            resolved_path_str = str(path_obj.resolve())

            with DbSession(self.engine) as session:
                # Find current maximum version for this file/session
                statement = (
                    select(FileVersion.version_number)
                    .where(FileVersion.file_path == resolved_path_str)
                    .where(FileVersion.session_id == session_id)
                    .order_by(col(FileVersion.version_number).desc())
                )
                latest_ver = session.exec(statement).first()
                next_ver = (latest_ver or 0) + 1

                file_ver = FileVersion(
                    id=str(uuid.uuid4()),
                    file_path=resolved_path_str,
                    session_id=session_id,
                    content=content,
                    version_number=next_ver,
                    created_by=created_by,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(file_ver)
                session.commit()
                session.refresh(file_ver)

                logger.info(
                    "Captured file version %d for '%s' (session_id=%s)",
                    file_ver.version_number, resolved_path_str, session_id
                )
                return file_ver

        except Exception as e:
            logger.warning("Failed capturing version for file '%s': %s", file_path, e)
            return None

    def get_versions(
        self,
        file_path: str,
        session_id: Optional[str] = None
    ) -> list[FileVersion]:
        """
        Retrieves all version snapshots for a given file path.
        """
        resolved_path_str = str(Path(file_path).resolve())
        with DbSession(self.engine) as session:
            statement = select(FileVersion).where(FileVersion.file_path == resolved_path_str)
            if session_id:
                statement = statement.where(FileVersion.session_id == session_id)
            statement = statement.order_by(col(FileVersion.version_number).asc())
            return list(session.exec(statement).all())

    def restore_version(
        self,
        file_path: str,
        version_id: str,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Restores a file on disk to the content stored in a specific FileVersion record.
        Captures a snapshot of the current state before rolling back.
        """
        with DbSession(self.engine) as session:
            file_ver = session.get(FileVersion, version_id)
            if not file_ver:
                logger.error("FileVersion '%s' not found.", version_id)
                return False

            target_path = Path(file_path)
            try:
                # 1. Snapshot current content before rollback
                if target_path.exists():
                    self.capture_version(
                        file_path=str(target_path),
                        session_id=session_id or file_ver.session_id,
                        created_by="restore_rollback"
                    )

                # 2. Write restored content
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(file_ver.content, encoding="utf-8")
                logger.info("Restored file '%s' to version %d (ID: %s)", file_path, file_ver.version_number, version_id)
                return True

            except Exception as e:
                logger.exception("Error restoring file version for '%s': %s", file_path, e)
                return False

    def generate_diff(
        self,
        old_content: str,
        new_content: str,
        file_path: str = "file.txt"
    ) -> str:
        """
        Generates a standard unified diff string between old and new content.
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=""
        )
        return "\n".join(line.rstrip("\r\n") for line in diff)
