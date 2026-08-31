import logging
from typing import Optional
from app.config import settings
from app.agent.model_provider import ModelProvider
from app.agent.llamacpp_provider import LlamaCppProvider
from app.agent.ollama_provider import OllamaProvider
from app.agent.runtime_process_manager import get_runtime_process_manager

logger = logging.getLogger("jarvis.agent.factory")

_cached_providers: dict[str, ModelProvider] = {}


def get_model_provider(runtime: Optional[str] = None) -> ModelProvider:
    """
    Returns a cached ModelProvider singleton based on the configured or requested runtime.
    - 'llama_cpp' -> LlamaCppProvider
    - 'ollama'    -> OllamaProvider
    """
    target_runtime = (runtime or settings.model_runtime).strip().lower()
    if target_runtime in ("lmstudio", "bonsai"):
        target_runtime = "llama_cpp"
    elif target_runtime == "hermes3":
        target_runtime = "ollama"

    if target_runtime in _cached_providers:
        return _cached_providers[target_runtime]

    if target_runtime == "llama_cpp":
        pm = get_runtime_process_manager()
        provider = LlamaCppProvider(
            base_url=f"http://{settings.llamacpp_host}:{settings.llamacpp_port}",
            process_manager=pm
        )
        _cached_providers[target_runtime] = provider
        logger.info("Initialized primary ModelProvider: LlamaCppProvider (port %s)", settings.llamacpp_port)
        return provider

    elif target_runtime == "ollama":
        provider = OllamaProvider(
            base_url=getattr(settings, "ollama_base_url", settings.ollama_host),
            default_model=settings.ollama_main_model
        )
        _cached_providers[target_runtime] = provider
        logger.info("Initialized fallback ModelProvider: OllamaProvider")
        return provider

    else:
        raise ValueError(
            f"Unknown model runtime '{target_runtime}'. Expected 'llama_cpp' (primary) or 'ollama' (fallback)."
        )


def reset_provider_cache() -> None:
    """Clear cached provider instances for testing or reconfiguration."""
    global _cached_providers
    _cached_providers.clear()
