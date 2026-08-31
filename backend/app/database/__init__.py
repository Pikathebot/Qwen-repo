"""
Database module for Jarvis memory and extended schema.
Exports SQLModel models, database engine, and session dependencies.
"""
from sqlmodel import Session
from app.database.session import engine, get_db, SessionLocal, get_session
from app.database.models import (
    Project,
    Artifact,
    Memory,
    Document,
    DocumentChunk,
    ToolCall,
    AgentRun,
    Session as DBSession,
    Message,
    CompactionEvent,
    ToolCallAudit,
    ReliabilityEvent,
)

__all__ = [
    "engine",
    "get_db",
    "SessionLocal",
    "get_session",
    "Session",

    "Project",
    "Artifact",
    "Memory",
    "Document",
    "DocumentChunk",
    "ToolCall",
    "AgentRun",
    "DBSession",
    "Message",
    "CompactionEvent",
    "ToolCallAudit",
    "ReliabilityEvent",
]
