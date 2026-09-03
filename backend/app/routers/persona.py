import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.persona import persona_manager
from app.voice.synthesizer import AVAILABLE_NEURAL_VOICES

logger = logging.getLogger("jarvis.routers.persona")

router = APIRouter(prefix="/api/persona", tags=["persona"])


class SetPersonaRequest(BaseModel):
    persona_id: str = Field(..., description="Persona id: 'jarvis', 'assistant' or 'operator'")


class PersonaOverridesRequest(BaseModel):
    address_term: Optional[str] = Field(
        default=None, description="How Jarvis addresses you, e.g. 'sir'. Empty string disables it."
    )
    voice_id: Optional[str] = Field(default=None, description="Neural voice key for spoken replies")
    greeting: Optional[str] = Field(default=None, description="Spoken greeting on wake")
    max_speech_sentences: Optional[int] = Field(
        default=None, ge=0, le=20, description="Cap on spoken sentences; 0 means no cap"
    )


class SpeechPreviewRequest(BaseModel):
    text: str = Field(..., description="Screen text to shape into its spoken form")


@router.get("", response_model=dict)
@router.get("/", response_model=dict)
async def get_persona() -> dict[str, Any]:
    """Active persona, its overrides, and the personas available to switch to."""
    payload = persona_manager.status()
    payload["available_voices"] = AVAILABLE_NEURAL_VOICES
    return payload


@router.post("", response_model=dict)
@router.post("/", response_model=dict)
async def set_persona(req: SetPersonaRequest) -> dict[str, Any]:
    """Switch the active persona. Persists across restarts."""
    try:
        persona_manager.set_active(req.persona_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return persona_manager.status()


@router.patch("/overrides", response_model=dict)
async def set_overrides(req: PersonaOverridesRequest) -> dict[str, Any]:
    """Override presentation details of the active persona (address, voice, verbosity)."""
    persona_manager.set_overrides(req.model_dump(exclude_none=True))
    return persona_manager.status()


@router.delete("/overrides", response_model=dict)
async def clear_overrides() -> dict[str, Any]:
    """Drop all overrides and return to the persona's defaults."""
    persona_manager.clear_overrides()
    return persona_manager.status()


@router.post("/speech-preview", response_model=dict)
async def speech_preview(req: SpeechPreviewRequest) -> dict[str, Any]:
    """Show what the active persona would actually say out loud for a given reply."""
    active = persona_manager.get_active()
    spoken = active.shape_for_speech(req.text)
    return {
        "persona_id": persona_manager.active_id,
        "voice_id": active.voice_id,
        "screen_text": req.text,
        "spoken_text": spoken,
        "spoken_chars": len(spoken),
    }
