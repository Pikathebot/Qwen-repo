import os
from pathlib import Path
from sqlmodel import Session, create_engine
from app.config import settings

# Ensure database parent directory exists
db_file = Path(settings.memory_db_path)
db_file.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False
)


def get_db():
    """FastAPI dependency for obtaining a SQLModel database session."""
    with Session(engine) as session:
        yield session
