import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.routines.models import Routine, RoutineKind

logger = logging.getLogger("jarvis.routers.routines")

router = APIRouter(prefix="/api/routines", tags=["routines"])


def get_scheduler():
    from app.main import routine_scheduler

    return routine_scheduler


class RoutineCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    time: str = Field(description="24-hour local time, HH:MM")
    kind: str = Field(default="briefing", description="briefing | message")
    message: str = Field(default="", max_length=500)
    days: list[int] = Field(default_factory=list, description="0=Mon .. 6=Sun; empty = every day")
    enabled: bool = True


class RoutineUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    time: Optional[str] = None
    kind: Optional[str] = None
    message: Optional[str] = Field(default=None, max_length=500)
    days: Optional[list[int]] = None
    enabled: Optional[bool] = None


def _validate_time(value: str) -> str:
    parts = value.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "time must be HH:MM")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "time must be a valid 24-hour HH:MM")
    return f"{hour:02d}:{minute:02d}"


def _validate_kind(value: str) -> RoutineKind:
    try:
        return RoutineKind(value)
    except ValueError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"kind must be one of: {', '.join(k.value for k in RoutineKind)}",
        )


@router.get("", response_model=dict)
async def list_routines() -> dict[str, Any]:
    scheduler = get_scheduler()
    return {
        "routines": [r.to_dict() for r in scheduler.list()],
        "scheduler": scheduler.status(),
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_routine(req: RoutineCreateRequest) -> dict[str, Any]:
    kind = _validate_kind(req.kind)
    if kind == RoutineKind.MESSAGE and not req.message.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "message is required for kind=message")

    routine = Routine(
        name=req.name.strip(),
        time=_validate_time(req.time),
        kind=kind,
        message=req.message.strip(),
        days=sorted({d for d in req.days if 0 <= d <= 6}),
        enabled=req.enabled,
    )
    get_scheduler().create(routine)
    return routine.to_dict()


@router.patch("/{routine_id}", response_model=dict)
async def update_routine(routine_id: str, req: RoutineUpdateRequest) -> dict[str, Any]:
    scheduler = get_scheduler()
    fields: dict[str, Any] = {}
    if req.name is not None:
        fields["name"] = req.name.strip()
    if req.time is not None:
        fields["time"] = _validate_time(req.time)
    if req.kind is not None:
        fields["kind"] = _validate_kind(req.kind)
    if req.message is not None:
        fields["message"] = req.message.strip()
    if req.days is not None:
        fields["days"] = sorted({d for d in req.days if 0 <= d <= 6})
    if req.enabled is not None:
        fields["enabled"] = req.enabled

    routine = scheduler.update(routine_id, **fields)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No routine with id '{routine_id}'.")
    return routine.to_dict()


@router.delete("/{routine_id}", response_model=dict)
async def delete_routine(routine_id: str) -> dict[str, Any]:
    if not get_scheduler().delete(routine_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No routine with id '{routine_id}'.")
    return {"deleted": True, "id": routine_id}


@router.post("/{routine_id}/run", response_model=dict)
async def run_routine_now(routine_id: str) -> dict[str, Any]:
    """Fire a routine immediately, e.g. to preview what it will say."""
    scheduler = get_scheduler()
    routine = scheduler.get(routine_id)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No routine with id '{routine_id}'.")
    observation = scheduler.fire(routine)
    return observation.to_dict()
