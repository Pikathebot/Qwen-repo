from app.routers.projects import router as projects_router
from app.routers.artifacts import router as artifacts_router
from app.routers.memories import router as memories_router
from app.routers.persona import router as persona_router
from app.routers.voice import router as voice_router
from app.routers.awareness import router as awareness_router

__all__ = [
    "projects_router",
    "artifacts_router",
    "memories_router",
    "persona_router",
    "voice_router",
    "awareness_router",
]
