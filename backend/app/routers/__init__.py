from app.routers.projects import router as projects_router
from app.routers.artifacts import router as artifacts_router
from app.routers.memories import router as memories_router

__all__ = ["projects_router", "artifacts_router", "memories_router"]
