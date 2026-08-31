import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from app.config import settings

logger = logging.getLogger("jarvis.agent.router")


class RoutingMode(str, Enum):
    AUTO = "auto"
    NORMAL = "normal"
    HEAVY = "heavy"


# Patterns indicating coding or tool-heavy tasks requiring the MAIN model
CODING_AND_TOOL_PATTERNS = [
    re.compile(r"\b(def |class |import |function|async |return |const |let |var |struct |impl )\b"),
    re.compile(r"\b(write_file|patch_file|read_file|grep_in_files|find_files|execute_command)\b"),
    re.compile(r"\b(refactor|debug|compile|pytest|unittest|traceback|syntaxerror|exception)\b", re.IGNORECASE),
    re.compile(r"\b(codebase|repository|script|algorithm|regex|api endpoint|backend|frontend)\b", re.IGNORECASE),
]

# Concrete regex patterns indicating high task complexity
HEAVY_TASK_PATTERNS = [
    re.compile(r"\b(system\s+design|architect(?:ure|ural)?\s+design|distributed\s+systems?)\b", re.IGNORECASE),
    re.compile(r"\b(microservices?\s+architecture|high-availability\s+architecture)\b", re.IGNORECASE),
    re.compile(r"\b(formal\s+verification|mathematical\s+proof|theorem\s+proving)\b", re.IGNORECASE),
    re.compile(r"\b(full\s+codebase\s+refactor(?:ing)?|architectural\s+refactoring)\b", re.IGNORECASE),
]

# Explicit user prompt prefix tags
HEAVY_TAG_PREFIXES = (
    "[heavy]",
    "/heavy",
    "heavy mode:",
    "deep reason:",
    "deep reasoning:",
    "think step by step in detail:",
)


@dataclass
class RoutingDecision:
    mode: str  # "normal" | "heavy"
    provider: str  # "llama_cpp" | "ollama" | "openrouter"
    model: str
    reason: str


class ModelRouter:
    """
    Routes execution to local primary runtime (llama.cpp Qwen3.5 9B / 4B)
    or fallback runtime (Ollama Hermes3 / Qwen2.5).
    Cloud routing (OpenRouter / Heavy Mode) is disabled by default.
    """

    def __init__(
        self,
        default_mode: str = "auto",
        active_runtime: Optional[str] = None,
        llamacpp_main_model: Optional[str] = None,
        llamacpp_fast_model: Optional[str] = None,
        ollama_main_model: Optional[str] = None,
        ollama_fast_model: Optional[str] = None,
        openrouter_heavy_model: Optional[str] = None,
        # Backward compatibility kwargs
        active_backend: Optional[str] = None,
        lmstudio_model: Optional[str] = None,
        ollama_model: Optional[str] = None,
    ):
        self.default_mode = default_mode
        eff_runtime = active_runtime or active_backend
        self._active_runtime = eff_runtime.lower().strip() if eff_runtime else None
        self.llamacpp_main_model = llamacpp_main_model or lmstudio_model or getattr(settings, "llamacpp_main_model_path", "models/Qwen3.5-9B-Q4_K_M.gguf")
        self.llamacpp_fast_model = llamacpp_fast_model or getattr(settings, "llamacpp_fast_model_path", "models/Qwen3.5-4B-Q4_K_M.gguf")
        self.ollama_main_model = ollama_main_model or ollama_model or getattr(settings, "ollama_main_model", settings.ollama_model)
        self.ollama_fast_model = ollama_fast_model or getattr(settings, "ollama_fast_model", "qwen2.5:3b-instruct")
        self.openrouter_heavy_model = openrouter_heavy_model or settings.openrouter_heavy_model

    @property
    def active_runtime(self) -> str:
        if self._active_runtime is not None:
            return self._active_runtime
        if hasattr(settings, "active_model_backend") and getattr(settings, "active_model_backend") in ("bonsai", "hermes3", "lmstudio"):
            return getattr(settings, "active_model_backend").lower().strip()
        return getattr(settings, "model_runtime", "llama_cpp").lower().strip()

    @active_runtime.setter
    def active_runtime(self, value: Optional[str]) -> None:
        self._active_runtime = value.lower().strip() if value else None

    # Backward compatibility alias
    @property
    def active_backend(self) -> str:
        return self.active_runtime

    @active_backend.setter
    def active_backend(self, value: Optional[str]) -> None:
        self.active_runtime = value

    def _resolve_local_target(self, requested_model: Optional[str] = None, prefer_fast: bool = False) -> tuple[str, str, str]:
        """
        Determine local provider and model target based on configured runtime and overrides.
        Returns (provider, model, label).
        """
        runtime = self.active_runtime

        if runtime in ("bonsai", "lmstudio"):
            provider = "lmstudio"
            model = requested_model or getattr(settings, "lmstudio_model", "prism-ml/bonsai-27b")
            return provider, model, f"LM Studio ({model})"

        elif runtime == "llama_cpp":
            provider = "llama_cpp"
            if requested_model:
                req_lower = requested_model.lower().strip()
                if req_lower in ("fast", "4b", "qwen3.5-4b"):
                    return provider, "fast", "llama.cpp (Qwen3.5-4B Fast)"
                elif req_lower in ("main", "9b", "qwen3.5-9b", "default"):
                    return provider, "main", "llama.cpp (Qwen3.5-9B Main)"
                else:
                    return provider, requested_model, f"llama.cpp ({requested_model})"
            
            if prefer_fast:
                return provider, "fast", "llama.cpp (Qwen3.5-4B Fast)"
            return provider, "main", "llama.cpp (Qwen3.5-9B Main)"

        elif runtime in ("hermes3", "ollama"):
            provider = "ollama"
            if requested_model:
                return provider, requested_model, f"Ollama ({requested_model})"
            if runtime == "hermes3":
                return provider, self.ollama_main_model, f"Ollama ({self.ollama_main_model})"
            if prefer_fast:
                return provider, self.ollama_fast_model, f"Ollama ({self.ollama_fast_model})"
            return provider, self.ollama_main_model, f"Ollama ({self.ollama_main_model})"

    def evaluate(
        self,
        message: str,
        requested_mode: Optional[str] = None,
        requested_model: Optional[str] = None
    ) -> RoutingDecision:
        """
        Evaluate user message and request parameters to produce a deterministic RoutingDecision.
        """
        mode_str = (requested_mode or self.default_mode).lower().strip()
        msg_clean = message.strip()
        cloud_enabled = getattr(settings, "cloud_routing_enabled", False) and getattr(settings, "openrouter_enabled", False)

        # 1. Explicit Mode: HEAVY
        if mode_str == RoutingMode.HEAVY.value:
            if cloud_enabled:
                target_model = requested_model or self.openrouter_heavy_model
                return RoutingDecision(
                    mode="heavy",
                    provider="openrouter",
                    model=target_model,
                    reason="Explicitly requested Heavy Mode (Cloud OpenRouter) via request parameters."
                )
            else:
                provider, model, label = self._resolve_local_target(requested_model, prefer_fast=False)
                return RoutingDecision(
                    mode="normal",
                    provider=provider,
                    model=model,
                    reason=f"Heavy Mode requested but cloud routing is disabled by config; routed to local {label}."
                )

        # 2. Explicit Mode: NORMAL
        if mode_str == RoutingMode.NORMAL.value:
            provider, model, label = self._resolve_local_target(requested_model, prefer_fast=False)
            return RoutingDecision(
                mode="normal",
                provider=provider,
                model=model,
                reason=f"Explicitly requested Normal Mode ({label}) via request parameters."
            )

        # 3. AUTO Mode: Check prompt tags
        msg_lower = msg_clean.lower()
        for tag in HEAVY_TAG_PREFIXES:
            if msg_lower.startswith(tag):
                if cloud_enabled:
                    target_model = requested_model or self.openrouter_heavy_model
                    return RoutingDecision(
                        mode="heavy",
                        provider="openrouter",
                        model=target_model,
                        reason=f"Matched explicit user heavy-mode trigger tag: '{tag}'."
                    )
                else:
                    provider, model, label = self._resolve_local_target(requested_model, prefer_fast=False)
                    return RoutingDecision(
                        mode="normal",
                        provider=provider,
                        model=model,
                        reason=f"Matched heavy trigger tag '{tag}', but cloud routing is disabled; routed to local {label}."
                    )

        # 4. AUTO Mode: Check heavy complexity heuristics
        for pattern in HEAVY_TASK_PATTERNS:
            match = pattern.search(msg_clean)
            if match:
                if cloud_enabled:
                    target_model = requested_model or self.openrouter_heavy_model
                    return RoutingDecision(
                        mode="heavy",
                        provider="openrouter",
                        model=target_model,
                        reason=f"Matched complex reasoning task pattern: '{match.group(0)}'."
                    )
                else:
                    provider, model, label = self._resolve_local_target(requested_model, prefer_fast=False)
                    return RoutingDecision(
                        mode="normal",
                        provider=provider,
                        model=model,
                        reason=f"Matched complex task pattern '{match.group(0)}' (local {label})."
                    )

        # 5. Default AUTO Mode: Check coding/tools vs fast query
        is_coding_task = any(p.search(msg_clean) for p in CODING_AND_TOOL_PATTERNS)
        prefer_fast = not is_coding_task and len(msg_clean.split()) <= 15 and not any(kw in msg_lower for kw in ["tool", "file", "search", "run", "execute", "create", "write"])

        provider, model, label = self._resolve_local_target(requested_model, prefer_fast=prefer_fast)
        return RoutingDecision(
            mode="normal",
            provider=provider,
            model=model,
            reason=f"Local execution routed to {label}."
        )
