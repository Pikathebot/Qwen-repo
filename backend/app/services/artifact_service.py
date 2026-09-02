import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Any

from sqlmodel import Session as DbSession, select, col
from app.database.session import engine
from app.database.models import Artifact, ArtifactVersion

logger = logging.getLogger("jarvis.services.artifact")


class ArtifactService:
    """
    Manages AI-generated artifact creation, versioning, rollback, and retrieval (Build Plan §15).
    """

    def __init__(self, db_engine: Optional[Any] = None):
        self.engine = db_engine or engine

    def create_artifact(
        self,
        name: str,
        type: str,
        content: str,
        conversation_id: Optional[str] = None,
        project_id: Optional[str] = None,
        language: Optional[str] = None,
        summary: Optional[str] = None,
        created_by: str = "agent",
    ) -> Artifact:
        """
        Creates a new artifact and initializes ArtifactVersion (Version 1).
        """
        now = datetime.now(timezone.utc)
        artifact_id = str(uuid.uuid4())
        session_id = conversation_id

        artifact = Artifact(
            id=artifact_id,
            name=name.strip(),
            type=type.strip().lower(),
            content=content,
            version=1,
            language=language,
            session_id=session_id,
            conversation_id=conversation_id,
            project_id=project_id,
            created_at=now,
            updated_at=now,
        )

        v1 = ArtifactVersion(
            id=str(uuid.uuid4()),
            artifact_id=artifact_id,
            version=1,
            content=content,
            summary=summary or "Initial version",
            created_by=created_by,
            created_at=now,
        )

        with DbSession(self.engine) as session:
            session.add(artifact)
            session.add(v1)
            session.commit()
            session.refresh(artifact)

        logger.info("Created artifact '%s' (%s) v1", artifact.name, artifact.id)
        return artifact

    def update_artifact(
        self,
        artifact_id: str,
        content: Optional[str] = None,
        name: Optional[str] = None,
        type: Optional[str] = None,
        language: Optional[str] = None,
        summary: Optional[str] = None,
        created_by: str = "agent",
    ) -> Artifact:
        """
        Updates artifact content. Automatically saves previous content snapshot into
        ArtifactVersion table before overwriting and increments the version counter.
        """
        with DbSession(self.engine) as session:
            artifact = session.get(Artifact, artifact_id)
            if not artifact:
                raise KeyError(f"Artifact '{artifact_id}' not found.")

            now = datetime.now(timezone.utc)

            if content is not None and content != artifact.content:
                # 1. Increment version and update content
                artifact.version += 1
                artifact.content = content

                # 2. Record new version snapshot
                new_version_record = ArtifactVersion(
                    id=str(uuid.uuid4()),
                    artifact_id=artifact.id,
                    version=artifact.version,
                    content=content,
                    summary=summary or f"Version {artifact.version}",
                    created_by=created_by,
                    created_at=now,
                )
                session.add(new_version_record)

            if name is not None:
                artifact.name = name.strip()
            if type is not None:
                artifact.type = type.strip().lower()
            if language is not None:
                artifact.language = language

            artifact.updated_at = now
            session.add(artifact)
            session.commit()
            session.refresh(artifact)

        logger.info("Updated artifact '%s' to version %d", artifact.name, artifact.version)
        return artifact

    def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """Retrieves a single artifact by its ID."""
        with DbSession(self.engine) as session:
            return session.get(Artifact, artifact_id)

    def list_artifacts(
        self,
        conversation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        type: Optional[str] = None,
    ) -> list[Artifact]:
        """
        Lists artifacts filtered by conversation_id, project_id, or artifact type.
        """
        active_conv_id = conversation_id or session_id
        with DbSession(self.engine) as session:
            statement = select(Artifact)
            if active_conv_id:
                statement = statement.where(
                    (Artifact.conversation_id == active_conv_id) | (Artifact.session_id == active_conv_id)
                )
            if project_id:
                statement = statement.where(Artifact.project_id == project_id)
            if type:
                statement = statement.where(Artifact.type == type.strip().lower())

            statement = statement.order_by(col(Artifact.updated_at).desc())
            return list(session.exec(statement).all())

    def list_versions(self, artifact_id: str) -> list[ArtifactVersion]:
        """Retrieves full version history for an artifact ordered by version number."""
        with DbSession(self.engine) as session:
            artifact = session.get(Artifact, artifact_id)
            if not artifact:
                raise KeyError(f"Artifact '{artifact_id}' not found.")

            statement = (
                select(ArtifactVersion)
                .where(ArtifactVersion.artifact_id == artifact_id)
                .order_by(col(ArtifactVersion.version).asc())
            )
            return list(session.exec(statement).all())

    def get_version(self, artifact_id: str, version: int) -> Optional[ArtifactVersion]:
        """Retrieves a specific version record for an artifact."""
        with DbSession(self.engine) as session:
            statement = (
                select(ArtifactVersion)
                .where(ArtifactVersion.artifact_id == artifact_id)
                .where(ArtifactVersion.version == version)
            )
            return session.exec(statement).first()

    def restore_version(
        self,
        artifact_id: str,
        version: int,
        created_by: str = "user",
    ) -> Artifact:
        """
        Restores an artifact to the content of a specific historical version.
        Snapshots current state before rolling back, then increments the active version.
        """
        with DbSession(self.engine) as session:
            artifact = session.get(Artifact, artifact_id)
            if not artifact:
                raise KeyError(f"Artifact '{artifact_id}' not found.")

            target_version = self.get_version(artifact_id, version)
            if not target_version:
                raise ValueError(f"Version {version} not found for artifact '{artifact_id}'.")

            now = datetime.now(timezone.utc)

            # 1. Increment version and apply restored content
            artifact.version += 1
            artifact.content = target_version.content
            artifact.updated_at = now

            # 2. Record restored version record
            restored_record = ArtifactVersion(
                id=str(uuid.uuid4()),
                artifact_id=artifact.id,
                version=artifact.version,
                content=target_version.content,
                summary=f"Restored from version {version}",
                created_by=created_by,
                created_at=now,
            )
            session.add(restored_record)

            session.add(artifact)
            session.commit()
            session.refresh(artifact)

        logger.info("Restored artifact '%s' to content from version %d (new active version: %d)",
                    artifact.name, version, artifact.version)
        return artifact

    def delete_artifact(self, artifact_id: str) -> bool:
        """Deletes an artifact and cascades deletion to all associated versions."""
        with DbSession(self.engine) as session:
            artifact = session.get(Artifact, artifact_id)
            if not artifact:
                return False

            versions = session.exec(
                select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact_id)
            ).all()
            for v in versions:
                session.delete(v)

            session.delete(artifact)
            session.commit()

        logger.info("Deleted artifact '%s' and %d version records", artifact_id, len(versions))
        return True
