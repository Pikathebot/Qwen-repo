import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # Model Runtime Configuration ("llama_cpp" primary, "ollama" fallback)
    model_runtime: str = "llama_cpp"

    # Active Model Backend (Stage B: "bonsai" default, "hermes3" rollback target - retained for backward compat)
    active_model_backend: str = "llama_cpp"

    # llama.cpp Local Configuration (Primary Runtime)
    llamacpp_server_exe: str = "tools/llama-cpp/llama-server.exe"
    llamacpp_main_model_path: str = "models/Qwen3.5-9B-Q4_K_M.gguf"
    llamacpp_fast_model_path: str = "models/Qwen3.5-4B-UD-Q4_K_XL.gguf"
    llamacpp_host: str = "127.0.0.1"
    llamacpp_port: int = 8001
    llamacpp_ctx_size: int = 16384
    llamacpp_gpu_layers: int = 999
    llamacpp_extra_args: list[str] = []       # future: TurboQuant -ctk/-ctv, mmproj, etc.
    llamacpp_startup_timeout_seconds: float = 90.0

    # LM Studio Local Configuration (Deprecated)
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_model: str = "prism-ml/bonsai-27b"
    lmstudio_qwen_model: str = "qwen3.8-9b-distill"

    # Local Ollama Configuration (Fallback Runtime)
    ollama_base_url: str = "http://localhost:11434"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "hermes3:8b"
    ollama_main_model: str = "hermes3:8b"     # fallback family ONLY, never Qwen3.5
    ollama_fast_model: str = "qwen2.5:3b-instruct"
    
    # Server Configuration
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # Cloud Routing & Heavy Mode Settings (Disabled)
    cloud_routing_enabled: bool = False
    heavy_mode_enabled: bool = False
    openrouter_enabled: bool = False
    openrouter_api_key: Optional[str] = None
    openrouter_heavy_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    default_routing_mode: str = "auto"  # "auto" | "normal" | "heavy"

    # Resource Governor V2 Settings
    governor_enabled: bool = True
    governor_poll_interval: float = 1.0
    governor_gpu_threshold: float = 88.0
    governor_vram_threshold: float = 92.0
    governor_cpu_threshold: float = 95.0
    governor_ram_threshold: float = 98.5
    governor_sustained_breach_polls: int = 3
    governor_recovery_polls: int = 2
    governor_startup_grace_seconds: float = 20.0
    governor_queue_timeout_seconds: float = 3.0
    governor_watchlist_path: str = os.path.join(BASE_DIR.parent, "governor_watchlist.json")
    governor_process_poll_interval: float = 2.0
    governor_process_launch_debounce: float = 4.0
    governor_process_recovery_debounce: float = 3.0

    # Memory & Context Compaction Settings
    memory_db_path: str = os.path.join(BASE_DIR, "data", "jarvis_memory.db")
    memory_max_context_tokens: int = 8192  # Compact when exceeding 8k to stay well under 16k context
    memory_tool_pruning_char_threshold: int = 200

    @property
    def database_url(self) -> str:
        db_path = Path(self.memory_db_path).resolve().as_posix()
        return f"sqlite:///{db_path}"


    # Safety & Tool Limits Settings (Stage A)
    max_tool_calls_per_turn: int = 15
    confirmation_timeout_action: str = "deny"

    # Tool-Call Reliability & Rollback Settings (Stage B Addendum)
    reliability_window_size: int = 30
    reliability_floor: float = 0.75  # 75% floor over rolling window of last 30 tool calls

    # TTS & Voice Output Settings
    voice_output_enabled: bool = False
    tts_engine: str = "chatterbox"  # "chatterbox" | "kokoro"
    tts_vram_required_mb: float = 2500.0
    tts_kokoro_vram_required_mb: float = 1200.0
    tts_chunk_size_chars: int = 300
    tts_device: str = "cuda"

    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
MAX_TOOL_CALLS_PER_TURN: int = settings.max_tool_calls_per_turn

