import logging
from contextlib import asynccontextmanager
from typing import Any, Optional
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, status
from pydantic import BaseModel, Field
import ollama

from app.config import settings
from app.agent.orchestrator import AgentOrchestrator
from app.agent.model_router import ModelRouter
from app.agent.openrouter_client import OpenRouterClient
from app.agent.lmstudio_client import LMStudioClient
from app.agent.reliability_monitor import ReliabilityMonitor
from app.governor.resource_governor import (
    ResourceGovernor,
    SystemMetrics,
    ActivityType,
    GovernorStatus,
    GovernorEvent,
)
from app.governor.process_watcher import ProcessWatcher
from app.memory.store import MemoryStore
from app.memory.compactor import ContextCompactor
from app.skills.loader import SkillsLoader
from app.mcp.manager import MCPManager
from app.voice.wake_word import WakeWordDetector
from app.voice.transcriber import AudioTranscriber
from app.voice.synthesizer import VoiceSynthesizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("jarvis")

# Initialize global subsystems
async def auto_unload_models() -> bool:
    """Automatically evicts active models from GPU VRAM across both Ollama and LM Studio when host enters heavy load."""
    success = True
    # 1. Evict from Ollama
    ollama_client = get_ollama_client()
    try:
        ps_res = await ollama_client.ps()
        models = ps_res.get("models", []) if isinstance(ps_res, dict) else getattr(ps_res, "models", [])
        for m in models:
            name = m.get("name") if isinstance(m, dict) else getattr(m, "model", getattr(m, "name", str(m)))
            if name:
                await ollama_client.generate(model=name, prompt="", keep_alive=0)
        await ollama_client.generate(model=settings.ollama_model, prompt="", keep_alive=0)
        logger.info("Governor auto-unload: Ollama model(s) evicted from VRAM.")
    except Exception as e:
        logger.debug("Ollama auto-unload error: %s", e)

    # 2. Evict from LM Studio via official CLI
    lmstudio_client = get_lmstudio_client()
    try:
        lm_res = await lmstudio_client.unload_model(settings.lmstudio_model)
        if not lm_res:
            success = False
    except Exception as e:
        logger.warning("LM Studio auto-unload error: %s", e)
        success = False

    return success


governor = ResourceGovernor(
    enabled=settings.governor_enabled,
    poll_interval=settings.governor_poll_interval,
    gpu_threshold=settings.governor_gpu_threshold,
    vram_threshold=settings.governor_vram_threshold,
    cpu_threshold=settings.governor_cpu_threshold,
    ram_threshold=settings.governor_ram_threshold,
    sustained_breach_polls=settings.governor_sustained_breach_polls,
    recovery_polls=settings.governor_recovery_polls,
    startup_grace_seconds=settings.governor_startup_grace_seconds,
    auto_unload_on_throttle=True,
    on_throttle_unload=auto_unload_models
)
process_watcher = ProcessWatcher(
    config_path=settings.governor_watchlist_path,
    poll_interval=settings.governor_process_poll_interval,
    launch_debounce_seconds=settings.governor_process_launch_debounce,
    recovery_debounce_seconds=settings.governor_process_recovery_debounce,
)
memory_store = MemoryStore(db_path=settings.memory_db_path)
reliability_monitor = ReliabilityMonitor(memory_store=memory_store)
compactor = ContextCompactor(
    max_context_tokens=settings.memory_max_context_tokens,
    tool_pruning_char_threshold=settings.memory_tool_pruning_char_threshold
)
skills_loader = SkillsLoader()
mcp_manager = MCPManager()
wake_detector = WakeWordDetector()
transcriber = AudioTranscriber()
synthesizer = VoiceSynthesizer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to start/stop Resource Governor, Process Watcher, MCP servers, and Voice engine."""
    logger.info("Starting up Jarvis Assistant backend services...")
    if settings.governor_enabled:
        await governor.start()
        await process_watcher.start(governor)
    
    # Connect MCP servers
    try:
        await mcp_manager.connect_all()
    except Exception as e:
        logger.warning("Error connecting MCP servers: %s", e)

    # Start wake word listener
    wake_detector.start_listening()

    yield
    
    logger.info("Shutting down Jarvis Assistant backend services...")
    wake_detector.stop_listening()
    if settings.governor_enabled:
        await process_watcher.stop()
        await governor.stop()
    
    # Disconnect MCP servers
    try:
        await mcp_manager.disconnect_all()
    except Exception as e:
        logger.warning("Error disconnecting MCP servers: %s", e)


from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(
    title="Local Jarvis Assistant API",
    description="FastAPI backend for local Jarvis Assistant with Voice Wake-Word, MCP Integration, Dynamic Skills, Memory, Governor, and Permissions",
    version="0.8.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UI_DIR = Path(__file__).resolve().parent.parent.parent / "desktop" / "ui"
if UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")



def get_ollama_client() -> ollama.AsyncClient:
    return ollama.AsyncClient(host=settings.ollama_host)


def get_lmstudio_client() -> LMStudioClient:
    return LMStudioClient(
        base_url=settings.lmstudio_base_url,
        timeout=180.0
    )


def get_openrouter_client() -> OpenRouterClient:
    return OpenRouterClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url
    )


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User prompt or message")
    session_id: Optional[str] = Field(default="default", description="Conversation session ID")
    model: Optional[str] = Field(
        default=None,
        description="Override model to use for this request (defaults to configured model)"
    )
    mode: Optional[str] = Field(
        default=None,
        description="Routing mode: 'auto' (default), 'normal' (local Bonsai/Hermes), or 'heavy' (OpenRouter)"
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Optional system prompt to guide model behavior"
    )
    approved_action_ids: Optional[list[str]] = Field(
        default=None,
        description="List of action ID tokens explicitly approved by the user"
    )
    chat_mode: Optional[str] = Field(
        default="WORKSPACE",
        description="Chat mode: 'WORKSPACE' (default) or 'SYSTEM'"
    )



class ChatResponse(BaseModel):
    response: str
    model: str
    provider: str = Field(default="lmstudio", description="'lmstudio', 'ollama', or 'openrouter'")
    status: str = Field(default="completed", description="'completed' or 'confirmation_required'")
    session_id: str = Field(default="default", description="Active session ID")
    route_reason: str = Field(default="", description="Reason for model and provider selection")
    fallback_used: bool = Field(default=False, description="True if fallback to local model occurred")
    compaction_performed: Optional[dict[str, Any]] = Field(default=None, description="Compaction audit details if triggered")
    active_skills: list[str] = Field(default_factory=list, description="List of dynamically matched skill names")
    tools_used: list[dict[str, Any]] = Field(default_factory=list)
    pending_confirmations: list[dict[str, Any]] = Field(default_factory=list)


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to synthesize for speech")


class TranscribeRequest(BaseModel):
    text: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    active_backend: str
    configured_model: str
    lmstudio_base_url: str
    lmstudio_connected: bool
    lmstudio_model: str
    ollama_host: str
    ollama_connected: bool
    ollama_model: str
    available_models: list[str]
    governor_throttled: bool
    openrouter_configured: bool
    active_sessions_count: int
    active_mcp_servers_count: int
    available_skills_count: int
    voice_enabled: bool


class GovernorPauseRequest(BaseModel):
    reason: str = "manual override"


class GovernorResumeOverrideRequest(BaseModel):
    duration_seconds: Optional[float] = None


class GovernorStatusResponse(BaseModel):
    enabled: bool
    status: str
    throttled: bool
    raw_throttled: bool = False
    throttle_reasons: list[str] = []
    is_manual_override: bool = False
    manual_override_active: bool = False
    pending_reload: bool = False
    active_activities: list[str] = []
    model_unloaded: bool = False
    metrics: dict[str, Any]
    thresholds: dict[str, float]


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint verifying backend status, LM Studio, Ollama, governor, MCP, skills, and voice."""
    # 1. Check Ollama
    ollama_connected = False
    available_models: list[str] = []
    ollama_client = get_ollama_client()

    try:
        models_response = await ollama_client.list()
        models_list = models_response.get("models", []) if isinstance(models_response, dict) else getattr(models_response, "models", [])
        for m in models_list:
            name = m.get("name") if isinstance(m, dict) else getattr(m, "model", getattr(m, "name", str(m)))
            if name:
                available_models.append(name)
        ollama_connected = True
    except Exception as e:
        logger.warning("Failed to connect to Ollama at %s: %s", settings.ollama_host, e)

    # 2. Check LM Studio
    lmstudio_client = get_lmstudio_client()
    lmstudio_connected = await lmstudio_client.is_available()
    if lmstudio_connected:
        lm_models = await lmstudio_client.list_models()
        for lmm in lm_models:
            if lmm not in available_models:
                available_models.append(lmm)

    active_backend = getattr(settings, "active_model_backend", "bonsai").lower().strip()
    configured_model = settings.lmstudio_model if active_backend == "bonsai" else settings.ollama_model
    primary_connected = lmstudio_connected if active_backend == "bonsai" else ollama_connected

    throttled, _ = await governor.is_throttled()
    openrouter_client = get_openrouter_client()
    sessions = memory_store.list_sessions()
    mcp_servers = mcp_manager.list_servers()
    skills = skills_loader.list_skills()

    return HealthResponse(
        status="ok" if primary_connected and not throttled else "degraded",
        active_backend=active_backend,
        configured_model=configured_model,
        lmstudio_base_url=settings.lmstudio_base_url,
        lmstudio_connected=lmstudio_connected,
        lmstudio_model=settings.lmstudio_model,
        ollama_host=settings.ollama_host,
        ollama_connected=ollama_connected,
        ollama_model=settings.ollama_model,
        available_models=available_models,
        governor_throttled=throttled,
        openrouter_configured=openrouter_client.is_configured,
        active_sessions_count=len(sessions),
        active_mcp_servers_count=len([s for s in mcp_servers if s["connected"]]),
        available_skills_count=len(skills),
        voice_enabled=wake_detector.is_listening
    )


@app.get("/governor/status", response_model=GovernorStatusResponse)
async def governor_status():
    """Returns real-time telemetry metrics and resource governor status."""
    metrics = await governor.get_metrics()
    return GovernorStatusResponse(
        enabled=governor.enabled,
        status=governor.status.value,
        throttled=metrics.throttled,
        raw_throttled=metrics.raw_throttled,
        throttle_reasons=metrics.throttle_reasons,
        is_manual_override=governor.is_manual_override,
        manual_override_active=governor.manual_override_active,
        pending_reload=governor.pending_reload,
        active_activities=governor.active_activity_types,
        model_unloaded=governor.model_unloaded,
        metrics={
            "cpu_percent": metrics.cpu_percent,
            "ram_percent": metrics.ram_percent,
            "ram_used_mb": metrics.ram_used_mb,
            "ram_total_mb": metrics.ram_total_mb,
            "gpu_available": metrics.gpu_available,
            "gpu_name": metrics.gpu_name,
            "gpu_util_percent": metrics.gpu_util_percent,
            "vram_util_percent": metrics.vram_util_percent,
            "vram_used_mb": metrics.vram_used_mb,
            "vram_total_mb": metrics.vram_total_mb,
            "vram_free_mb": metrics.vram_free_mb,
            "gpu_temp_c": metrics.gpu_temp_c,
            "timestamp": metrics.timestamp,
        },
        thresholds={
            "gpu_threshold": governor.gpu_threshold,
            "vram_threshold": governor.vram_threshold,
            "cpu_threshold": governor.cpu_threshold,
            "ram_threshold": governor.ram_threshold,
        }
    )


@app.post("/governor/pause")
async def governor_pause(req: Optional[GovernorPauseRequest] = None):
    """Forces governor into PAUSED state. Blocks request execution."""
    reason = req.reason if req and req.reason else "manual override"
    governor.force_pause(reason=reason)
    return {"status": "ok", "governor_status": governor.status.value, "reason": reason}


@app.post("/governor/resume")
async def governor_resume():
    """Clears manual pause and override states, restoring automated governance."""
    governor.force_resume()
    return {"status": "ok", "governor_status": governor.status.value}


@app.post("/governor/resume-override")
async def governor_resume_override(req: Optional[GovernorResumeOverrideRequest] = None):
    """Forces governor to report healthy/NORMAL regardless of load for a duration."""
    duration = req.duration_seconds if req else None
    governor.force_resume_ignore_metrics(duration_seconds=duration)
    return {"status": "ok", "governor_status": governor.status.value, "duration_seconds": duration}


@app.get("/governor/history")
async def governor_history(limit: int = 20):
    """Returns recent status transition events (most recent first)."""
    events = governor.get_history(limit=limit)
    return [
        {
            "timestamp": e.timestamp,
            "from_status": e.from_status,
            "to_status": e.to_status,
            "raw_reasons": e.raw_reasons,
            "active_activities": e.active_activities,
            "metrics_snapshot": {
                "cpu_percent": e.metrics_snapshot.cpu_percent,
                "ram_percent": e.metrics_snapshot.ram_percent,
                "gpu_util_percent": e.metrics_snapshot.gpu_util_percent,
                "vram_util_percent": e.metrics_snapshot.vram_util_percent,
            } if e.metrics_snapshot else None
        }
        for e in events
    ]


@app.get("/sessions")
async def list_sessions():
    """List all stored conversation sessions."""
    return memory_store.list_sessions()


@app.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Retrieve full message history for a specific session."""
    return memory_store.get_messages(session_id)


@app.get("/sessions/{session_id}/compactions")
async def get_session_compactions(session_id: str):
    """Retrieve compaction audit events for a session."""
    return memory_store.get_compaction_events(session_id)


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session and all its stored messages."""
    deleted = memory_store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {"deleted": True, "session_id": session_id}


@app.get("/skills")
async def list_skills():
    """List all discovered markdown skills and their trigger keywords."""
    return skills_loader.list_skills()


@app.post("/skills/reload")
async def reload_skills():
    """Hot-reload markdown skills from disk."""
    skills = skills_loader.load_skills()
    return {"reloaded": True, "count": len(skills), "skills": list(skills.keys())}


@app.get("/mcp/servers")
async def list_mcp_servers():
    """List registered MCP servers and their active tool schemas."""
    return mcp_manager.list_servers()


# --- Tool Reliability & Rollback Endpoints (Stage B Addendum) ---

class SwitchBackendRequest(BaseModel):
    backend: str = Field(..., description="Target model backend ('bonsai' or 'hermes3')")
    reason: Optional[str] = Field(default="manual override", description="Reason for switching backend")


@app.get("/reliability/status")
async def get_reliability_status(model_tier: str = "tier2"):
    """Returns real-time tool-call reliability metrics over the rolling window."""
    return reliability_monitor.get_status(model_tier=model_tier)


@app.get("/reliability/history")
async def get_reliability_history(limit: int = 50):
    """Returns recent tool-call reliability alerts and rollback events."""
    return reliability_monitor.get_history(limit=limit)


@app.post("/reliability/switch-backend")
async def switch_model_backend(req: SwitchBackendRequest):
    """Manually switch active model backend (e.g. re-enable Bonsai after manual review)."""
    try:
        result = reliability_monitor.switch_backend(target_backend=req.backend, reason=req.reason or "manual override")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



# --- Voice Endpoints ---

@app.get("/voice/status")
async def voice_status():
    """Returns voice and wake-word detector status."""
    return {
        "wake_word_active": wake_detector.is_listening,
        "wake_words": wake_detector.wake_words,
        "synthesizer_voice": synthesizer.voice_name
    }


@app.post("/voice/speak")
async def voice_speak(req: SpeakRequest):
    """Sanitize and prepare text for speech synthesis."""
    result = synthesizer.synthesize(req.text)
    return result


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "en-GB-RyanNeural"


@app.post("/voice/tts")
async def voice_neural_tts(req: TTSRequest):
    """Generates ultra-realistic humanlike neural audio (MP3) for spoken responses."""
    audio_bytes = await synthesizer.generate_neural_audio_bytes(req.text, voice=req.voice)
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="Failed to synthesize neural audio.")
    from fastapi.responses import Response
    return Response(content=audio_bytes, media_type="audio/mpeg")


@app.get("/voice/voices")
async def voice_list_neural():
    """List available studio-grade humanlike voices."""
    from app.voice.synthesizer import AVAILABLE_NEURAL_VOICES
    return {
        "current": synthesizer.voice_name,
        "available": AVAILABLE_NEURAL_VOICES
    }


@app.post("/voice/transcribe")
async def voice_transcribe(file: Optional[UploadFile] = File(None)):
    """Transcribe audio upload bytes into text."""
    if file:
        data = await file.read()
        fmt = file.filename.split(".")[-1] if file.filename else "wav"
        res = transcriber.transcribe_audio_bytes(data, format=fmt)
        return res
    return {"success": False, "text": "", "error": "No audio file provided"}


class UnloadModelRequest(BaseModel):
    model_name: Optional[str] = None


@app.post("/models/unload")
async def unload_models(req: Optional[UnloadModelRequest] = None):
    """Immediately evicts loaded models from GPU VRAM across both Ollama and LM Studio."""
    ollama_client = get_ollama_client()
    lmstudio_client = get_lmstudio_client()
    unloaded_models = []
    target_model = req.model_name if req and req.model_name else None

    # 1. Unload from Ollama
    try:
        if target_model:
            await ollama_client.generate(model=target_model, prompt="", keep_alive=0)
            unloaded_models.append(target_model)
        else:
            try:
                ps_res = await ollama_client.ps()
                models = ps_res.get("models", []) if isinstance(ps_res, dict) else getattr(ps_res, "models", [])
                for m in models:
                    name = m.get("name") if isinstance(m, dict) else getattr(m, "model", getattr(m, "name", str(m)))
                    if name:
                        await ollama_client.generate(model=name, prompt="", keep_alive=0)
                        unloaded_models.append(name)
            except Exception:
                pass

            if settings.ollama_model not in unloaded_models:
                try:
                    await ollama_client.generate(model=settings.ollama_model, prompt="", keep_alive=0)
                    unloaded_models.append(settings.ollama_model)
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Error unloading model from Ollama: %s", e)

    # 2. Unload from LM Studio
    try:
        target_lm = target_model or settings.lmstudio_model
        await lmstudio_client.unload_model(target_lm)
        unloaded_models.append(f"lmstudio:{target_lm}")
    except Exception as e:
        logger.warning("Error unloading model from LM Studio: %s", e)

    logger.info("Unloaded models from VRAM: %s", unloaded_models)
    return {
        "success": True,
        "unloaded_models": unloaded_models,
        "message": "Model(s) successfully signaled for GPU VRAM eviction."
    }


class LoadModelRequest(BaseModel):
    model_name: Optional[str] = None
    backend: Optional[str] = None  # "bonsai" (lmstudio) or "hermes3" (ollama)


@app.post("/models/load")
async def load_model_endpoint(req: Optional[LoadModelRequest] = None):
    """Loads/warms up a model into GPU VRAM wrapped with governor.activity(ActivityType.MODEL_LOADING)."""
    target_backend = (req.backend if req and req.backend else getattr(settings, "active_model_backend", "bonsai")).lower().strip()
    target_model = (
        req.model_name
        if req and req.model_name
        else (settings.lmstudio_model if target_backend == "bonsai" else settings.ollama_model)
    )

    async with governor.activity(ActivityType.MODEL_LOADING, label=target_model):
        if target_backend == "bonsai":
            lmstudio_client = get_lmstudio_client()
            success = await lmstudio_client.load_model(target_model)
        else:
            ollama_client = get_ollama_client()
            try:
                await ollama_client.generate(model=target_model, prompt="", keep_alive="10m")
                success = True
            except Exception as e:
                logger.warning("Ollama load/warmup error: %s", e)
                success = False

    return {
        "success": success,
        "model": target_model,
        "backend": target_backend,
        "message": f"Model '{target_model}' loaded successfully." if success else f"Failed to load '{target_model}'."
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint with Voice Wake-Word, MCP Integration, Dynamic Skills Loading,
    SQLite Memory, Model Routing (LM Studio Bonsai default vs Ollama Hermes rollback),
    Resource Governor gating, and Safety Permissions.
    """
    # Check for wake word in message
    detected, wake_word, cleaned_query = wake_detector.detect_in_text(request.message)
    active_message = cleaned_query if detected and cleaned_query else request.message

    # 1. Resource Governor Check (with adaptive queueing wait)
    if settings.governor_enabled:
        is_healthy, reason = await governor.wait_until_healthy(
            timeout_seconds=settings.governor_queue_timeout_seconds
        )
        if not is_healthy:
            logger.warning("Rejecting chat request due to high system load: %s", reason)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Resource Governor active: Request paused/rejected due to heavy system load ({reason}). Please retry once resource load subsides."
            )

    # 2. Agent Orchestration with LM Studio, Ollama, OpenRouter, Memory, Skills, and MCP Tools
    ollama_client = get_ollama_client()
    lmstudio_client = get_lmstudio_client()
    openrouter_client = get_openrouter_client()
    orchestrator = AgentOrchestrator(
        ollama_client=ollama_client,
        lmstudio_client=lmstudio_client,
        openrouter_client=openrouter_client,
        memory_store=memory_store,
        compactor=compactor,
        skills_loader=skills_loader,
        mcp_manager=mcp_manager,
        reliability_monitor=reliability_monitor
    )

    try:
        async with governor.activity(ActivityType.INFERENCING, label=request.session_id or "chat_turn"):
            result = await orchestrator.run(
                user_message=active_message,
                session_id=request.session_id,
                requested_mode=request.mode,
                requested_model=request.model,
                system_prompt=request.system_prompt,
                approved_action_ids=request.approved_action_ids,
                chat_mode=request.chat_mode
            )

        return ChatResponse(
            response=result.response,
            model=result.model,
            provider=result.provider,
            status=result.status,
            session_id=result.session_id,
            route_reason=result.route_reason,
            fallback_used=result.fallback_used,
            compaction_performed=result.compaction_performed,
            active_skills=result.active_skills,
            tools_used=result.tools_used,
            pending_confirmations=result.pending_confirmations
        )

    except ollama.ResponseError as e:
        logger.error("Ollama ResponseError: %s (status_code=%s)", e.error, e.status_code)
        if e.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model not found in Ollama. Pull it with `ollama pull <model_name>`."
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ollama error: {e.error}"
        )
    except Exception as e:
        logger.error("Unexpected error in chat endpoint: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat execution error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True
    )
