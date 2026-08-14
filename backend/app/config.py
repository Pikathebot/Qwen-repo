import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # Local Ollama Configuration
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "hermes3:8b"
    
    # Server Configuration
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # Resource Governor Settings
    governor_enabled: bool = True
    governor_poll_interval: float = 1.0
    governor_gpu_threshold: float = 95.0
    governor_vram_threshold: float = 95.0
    governor_cpu_threshold: float = 95.0
    governor_ram_threshold: float = 95.0
    governor_queue_timeout_seconds: float = 3.0

    # OpenRouter Heavy Mode Settings
    openrouter_api_key: Optional[str] = None
    openrouter_heavy_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    default_routing_mode: str = "auto"  # "auto" | "normal" | "heavy"

    # Memory & Context Compaction Settings
    memory_db_path: str = os.path.join(BASE_DIR, "data", "jarvis_memory.db")
    memory_max_context_tokens: int = 16000  # Default within 10,000-20,000 range
    memory_tool_pruning_char_threshold: int = 200

    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
