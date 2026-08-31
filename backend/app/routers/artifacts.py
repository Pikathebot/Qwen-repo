import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from app.config import settings
from app.database import get_session
from app.database.models import Artifact, ArtifactVersion, Attachment, Project

logger = logging.getLogger("jarvis.routers.artifacts")

router = APIRouter(prefix="/api", tags=["artifacts", "attachments"])

ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".json", ".yaml", ".yml",
    ".cpp", ".h", ".hpp", ".cs", ".ini", ".csv", ".html", ".css", ".svg",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"
}


# ==========================================
# Pydantic Schemas
# ==========================================

class AttachmentResponse(BaseModel):
    id: str
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    filename: str
    path: str
    size_bytes: int
    content_type: Optional[str] = None
    created_at: datetime


class ArtifactVersionResponse(BaseModel):
    id: str
    artifact_id: str
    version: int
    content: str
    summary: Optional[str] = None
    created_at: datetime


class ArtifactResponse(BaseModel):
    id: str
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    name: str
    type: str
    content: str
    version: int
    created_at: datetime
    updated_at: datetime


class CreateArtifactRequest(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(default="code", description="code/markdown/html/json/csv/python/svg")
    content: str
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    summary: Optional[str] = None


class CreateArtifactVersionRequest(BaseModel):
    content: str
    summary: Optional[str] = None


class UpdateArtifactRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    create_new_version: bool = Field(default=False, description="Whether to snapshot new content as an incremented version")


class ProjectFileItem(BaseModel):
    name: str
    path: str
    size_bytes: int
    is_dir: bool
    updated_at: Optional[float] = None


# ==========================================
# Helpers
# ==========================================

def sanitize_filename(filename: str) -> str:
    """Strip path traversal characters and dangerous special characters."""
    base = os.path.basename(filename).strip()
    # Replace non-alphanumeric (except dot, dash, underscore) with underscore
    sanitized = re.sub(r"[^\w\.\-]", "_", base)
    if not sanitized or sanitized.startswith("."):
        sanitized = f"upload_{uuid.uuid4().hex[:8]}{sanitized}"
    return sanitized


def get_target_files_dir(project_id: Optional[str], db: Session) -> Path:
    """Resolve and ensure the target upload directory exists."""
    workspace_base = Path(settings.workspace_path).resolve()

    if project_id:
        proj = db.get(Project, project_id)
        if proj and proj.workspace_path:
            target_dir = Path(proj.workspace_path).resolve() / "files"
        else:
            target_dir = workspace_base / "projects" / project_id / "files"
    else:
        target_dir = workspace_base / "files"

    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


# ==========================================
# Attachments (User-Uploaded Files) Endpoints
# ==========================================

@router.post("/upload", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
    db: Session = Depends(get_session),
) -> AttachmentResponse:
    """
    Securely uploads a user file attachment into the active project workspace
    or global workspace directory with whitelist and size validation.
    """
    raw_filename = file.filename or "uploaded_file.txt"
    ext = os.path.splitext(raw_filename)[1].lower()

    # 1. Whitelist validation
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' is not permitted. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. Filename sanitization and path traversal prevention
    clean_name = sanitize_filename(raw_filename)
    target_dir = get_target_files_dir(project_id, db)
    dest_path = (target_dir / clean_name).resolve()

    # Verify destination remains inside target_dir
    try:
        dest_path.relative_to(target_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path detected.",
        )

    # If file already exists, create unique name
    if dest_path.exists():
        stem, extension = os.path.splitext(clean_name)
        clean_name = f"{stem}_{uuid.uuid4().hex[:6]}{extension}"
        dest_path = target_dir / clean_name

    # 3. Read and enforce size limit
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    size_bytes = len(content)

    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({size_bytes / (1024*1024):.2f}MB) exceeds maximum limit of {settings.max_upload_size_mb}MB.",
        )

    # Write file to disk
    with open(dest_path, "wb") as f:
        f.write(content)

    # 4. Record attachment in database
    attachment = Attachment(
        id=str(uuid.uuid4()),
        session_id=session_id,
        project_id=project_id,
        filename=clean_name,
        path=str(dest_path),
        size_bytes=size_bytes,
        content_type=file.content_type,
        created_at=datetime.utcnow(),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    logger.info("Uploaded attachment '%s' (%d bytes) to %s", clean_name, size_bytes, dest_path)
    return AttachmentResponse(
        id=attachment.id,
        session_id=attachment.session_id,
        project_id=attachment.project_id,
        filename=attachment.filename,
        path=attachment.path,
        size_bytes=attachment.size_bytes,
        content_type=attachment.content_type,
        created_at=attachment.created_at,
    )


@router.get("/attachments", response_model=list[AttachmentResponse])
def list_attachments(
    session_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_session),
) -> list[AttachmentResponse]:
    """List attachments, optionally filtered by session or project."""
    statement = select(Attachment)
    if session_id:
        statement = statement.where(Attachment.session_id == session_id)
    if project_id:
        statement = statement.where(Attachment.project_id == project_id)
    statement = statement.order_by(col(Attachment.created_at).desc())
    attachments = db.exec(statement).all()
    return [
        AttachmentResponse(
            id=a.id,
            session_id=a.session_id,
            project_id=a.project_id,
            filename=a.filename,
            path=a.path,
            size_bytes=a.size_bytes,
            content_type=a.content_type,
            created_at=a.created_at,
        )
        for a in attachments
    ]


@router.delete("/attachments/{attachment_id}")
def delete_attachment(
    attachment_id: str,
    delete_file: bool = Query(default=True),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Delete an attachment record and optionally remove the file from disk."""
    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attachment '{attachment_id}' not found.",
        )

    file_path = attachment.path
    db.delete(attachment)
    db.commit()

    if delete_file and file_path:
        p = Path(file_path)
        if p.exists() and p.is_file():
            try:
                p.unlink()
            except Exception as e:
                logger.warning("Failed to delete attachment file %s: %s", file_path, e)

    return {"deleted": True, "attachment_id": attachment_id}


# ==========================================
# Artifacts (AI Generated Outputs) Endpoints
# ==========================================

@router.get("/artifacts", response_model=list[ArtifactResponse])
def list_artifacts(
    session_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_session),
) -> list[ArtifactResponse]:
    """List generated artifacts, optionally filtered by session or project."""
    statement = select(Artifact)
    if session_id:
        statement = statement.where(Artifact.session_id == session_id)
    if project_id:
        statement = statement.where(Artifact.project_id == project_id)
    statement = statement.order_by(col(Artifact.updated_at).desc())
    artifacts = db.exec(statement).all()
    return [
        ArtifactResponse(
            id=a.id,
            project_id=a.project_id,
            session_id=a.session_id,
            name=a.name,
            type=a.type,
            content=a.content,
            version=a.version,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in artifacts
    ]


@router.post("/artifacts", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
def create_artifact(
    req: CreateArtifactRequest,
    db: Session = Depends(get_session),
) -> ArtifactResponse:
    """Create a new AI-generated artifact and snapshot version 1."""
    now = datetime.utcnow()
    artifact_id = str(uuid.uuid4())

    artifact = Artifact(
        id=artifact_id,
        project_id=req.project_id,
        session_id=req.session_id,
        name=req.name.strip(),
        type=req.type.strip().lower(),
        content=req.content,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(artifact)

    # Create initial version record
    v1 = ArtifactVersion(
        id=str(uuid.uuid4()),
        artifact_id=artifact_id,
        version=1,
        content=req.content,
        summary=req.summary or "Initial version",
        created_at=now,
    )
    db.add(v1)

    db.commit()
    db.refresh(artifact)
    logger.info("Created artifact '%s' (%s) v1", artifact.name, artifact.id)

    return ArtifactResponse(
        id=artifact.id,
        project_id=artifact.project_id,
        session_id=artifact.session_id,
        name=artifact.name,
        type=artifact.type,
        content=artifact.content,
        version=artifact.version,
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(artifact_id: str, db: Session = Depends(get_session)) -> ArtifactResponse:
    """Retrieve detailed artifact metadata and current active content."""
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_id}' not found.",
        )
    return ArtifactResponse(
        id=artifact.id,
        project_id=artifact.project_id,
        session_id=artifact.session_id,
        name=artifact.name,
        type=artifact.type,
        content=artifact.content,
        version=artifact.version,
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


@router.put("/artifacts/{artifact_id}", response_model=ArtifactResponse)
def update_artifact(
    artifact_id: str,
    req: UpdateArtifactRequest,
    db: Session = Depends(get_session),
) -> ArtifactResponse:
    """Update artifact content or properties, optionally snapshotting an incremented version."""
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_id}' not found.",
        )

    now = datetime.utcnow()
    if req.name is not None:
        artifact.name = req.name.strip()
    if req.type is not None:
        artifact.type = req.type.strip().lower()

    if req.content is not None:
        artifact.content = req.content
        if req.create_new_version:
            artifact.version += 1
            ver = ArtifactVersion(
                id=str(uuid.uuid4()),
                artifact_id=artifact.id,
                version=artifact.version,
                content=req.content,
                summary=req.summary or f"Version {artifact.version}",
                created_at=now,
            )
            db.add(ver)

    artifact.updated_at = now
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    return ArtifactResponse(
        id=artifact.id,
        project_id=artifact.project_id,
        session_id=artifact.session_id,
        name=artifact.name,
        type=artifact.type,
        content=artifact.content,
        version=artifact.version,
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


@router.delete("/artifacts/{artifact_id}")
def delete_artifact(artifact_id: str, db: Session = Depends(get_session)) -> dict[str, Any]:
    """Delete an artifact and cascade all associated version history."""
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_id}' not found.",
        )

    # Delete all versions
    versions = db.exec(select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact_id)).all()
    for v in versions:
        db.delete(v)

    db.delete(artifact)
    db.commit()
    return {"deleted": True, "artifact_id": artifact_id}


@router.get("/artifacts/{artifact_id}/versions", response_model=list[ArtifactVersionResponse])
def list_artifact_versions(
    artifact_id: str,
    db: Session = Depends(get_session),
) -> list[ArtifactVersionResponse]:
    """Retrieve full version history for an artifact ordered by version number."""
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_id}' not found.",
        )

    statement = select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact_id).order_by(col(ArtifactVersion.version).asc())
    versions = db.exec(statement).all()
    return [
        ArtifactVersionResponse(
            id=v.id,
            artifact_id=v.artifact_id,
            version=v.version,
            content=v.content,
            summary=v.summary,
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.post("/artifacts/{artifact_id}/versions", response_model=ArtifactVersionResponse, status_code=status.HTTP_201_CREATED)
def create_artifact_version(
    artifact_id: str,
    req: CreateArtifactVersionRequest,
    db: Session = Depends(get_session),
) -> ArtifactVersionResponse:
    """Create a new version for an artifact, updating the current artifact content."""
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_id}' not found.",
        )

    now = datetime.utcnow()
    # Find next version number
    existing_versions = db.exec(select(ArtifactVersion.version).where(ArtifactVersion.artifact_id == artifact_id)).all()
    next_ver = (max(existing_versions) if existing_versions else artifact.version) + 1

    new_ver = ArtifactVersion(
        id=str(uuid.uuid4()),
        artifact_id=artifact_id,
        version=next_ver,
        content=req.content,
        summary=req.summary or f"Version {next_ver}",
        created_at=now,
    )
    db.add(new_ver)

    artifact.version = next_ver
    artifact.content = req.content
    artifact.updated_at = now
    db.add(artifact)

    db.commit()
    db.refresh(new_ver)
    return ArtifactVersionResponse(
        id=new_ver.id,
        artifact_id=new_ver.artifact_id,
        version=new_ver.version,
        content=new_ver.content,
        summary=new_ver.summary,
        created_at=new_ver.created_at,
    )


# ==========================================
# Project Files Explorer (Section 19 / Amendment 4)
# ==========================================

@router.get("/projects/{project_id}/files", response_model=list[ProjectFileItem])
def list_project_files(
    project_id: str,
    db: Session = Depends(get_session),
) -> list[ProjectFileItem]:
    """
    List files in the project's 'files/' directory for the RightPanel Files tab.
    """
    target_dir = get_target_files_dir(project_id, db)
    items: list[ProjectFileItem] = []

    if not target_dir.exists() or not target_dir.is_dir():
        return items

    try:
        for entry in os.scandir(target_dir):
            stat = entry.stat()
            items.append(
                ProjectFileItem(
                    name=entry.name,
                    path=entry.path,
                    size_bytes=stat.st_size if entry.is_file() else 0,
                    is_dir=entry.is_dir(),
                    updated_at=stat.st_mtime,
                )
            )
    except Exception as e:
        logger.warning("Error scanning project files directory %s: %s", target_dir, e)

    items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
    return items
