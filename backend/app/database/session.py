import os
from pathlib import Path
from typing import Generator
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine
from app.config import settings

# Ensure database parent directory exists
db_file = Path(settings.memory_db_path)
db_file.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session
)


def get_session() -> Session:
    """Factory function returning a new SQLModel Session."""
    return SessionLocal()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a request-scoped SQLModel database session."""
    with SessionLocal() as session:
        yield session

