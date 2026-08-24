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
    provider: str  # "lmstudio" | "ollama" | "openrouter"
    model: str
    reason: str


class ModelRouter:
    """
    Determines execution destination: Normal Mode (local LM Studio Bonsai / Ollama Hermes3) vs Heavy Mode (OpenRouter).
    Enforces deterministic evaluation rules and complete local isolation for Normal Mode.
    """

    def __init__(
        self,
        default_mode: str = "auto",
        active_backend: Optional[str] = None,
        lmstudio_model: Optional[str] = None,
        ollama_model: Optional[str] = None,
        openrouter_heavy_model: Optional[str] = None
    ):
        self.default_mode = default_mode
        self._active_backend = active_backend.lower().strip() if active_backend else None
        self.lmstudio_model = lmstudio_model or getattr(settings, "lmstudio_model", "prism-ml/bonsai-27b")
        self.lmstudio_qwen_model = getattr(settings, "lmstudio_qwen_model", "qwen3.8-9b-distill")
        self.ollama_model = ollama_model or settings.ollama_model
        self.openrouter_heavy_model = openrouter_heavy_model or settings.openrouter_heavy_model

    @property
    def active_backend(self) -> str:
        if self._active_backend is not None:
            return self._active_backend
        return getattr(settings, "active_model_backend", "bonsai").lower().strip()

    @active_backend.setter
    def active_backend(self, value: Optional[str]) -> None:
        self._active_backend = value.lower().strip() if value else None

    def _resolve_normal_target(self, requested_model: Optional[str] = None) -> tuple[str, str, str]:
        """
        Determine provider and model for Normal Mode based on active backend and overrides.
        Returns (provider, model, backend_name).
        """
        if requested_model:
            req_lower = requested_model.lower().strip()
            if req_lower in ("qwen3.8:9b", "qwen3.8-9b", "qwen3.8-9b-distill", "qwen3.8", self.lmstudio_qwen_model.lower()):
                return "lmstudio", self.lmstudio_qwen_model, f"LM Studio ({self.lmstudio_qwen_model})"
            elif requested_model == self.lmstudio_model:
                return "lmstudio", requested_model, f"LM Studio ({requested_model})"
            elif requested_model == self.ollama_model or ":" in requested_model:
                return "ollama", requested_model, f"Ollama ({requested_model})"
            else:
                provider = "lmstudio" if self.active_backend == "bonsai" else "ollama"
                return provider, requested_model, f"{provider} ({requested_model})"

        if self.active_backend == "bonsai":
            return "lmstudio", self.lmstudio_model, f"LM Studio ({self.lmstudio_model})"
        else:
            return "ollama", self.ollama_model, f"Ollama ({self.ollama_model})"

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

        # 1. Explicit Mode: HEAVY
        if mode_str == RoutingMode.HEAVY.value:
            target_model = requested_model or self.openrouter_heavy_model
            return RoutingDecision(
                mode="heavy",
                provider="openrouter",
                model=target_model,
                reason="Explicitly requested Heavy Mode via request parameters."
            )

        # 2. Explicit Mode: NORMAL
        if mode_str == RoutingMode.NORMAL.value:
            provider, target_model, label = self._resolve_normal_target(requested_model)
            return RoutingDecision(
                mode="normal",
                provider=provider,
                model=target_model,
                reason=f"Explicitly requested Normal Mode ({label}) via request parameters."
            )

        # 3. AUTO Mode: Check explicit prompt tags
        msg_lower = msg_clean.lower()
        for tag in HEAVY_TAG_PREFIXES:
            if msg_lower.startswith(tag):
                target_model = requested_model or self.openrouter_heavy_model
                return RoutingDecision(
                    mode="heavy",
                    provider="openrouter",
                    model=target_model,
                    reason=f"Matched explicit user heavy-mode trigger tag: '{tag}'."
                )

        # 4. AUTO Mode: Check concrete complexity heuristics
        for pattern in HEAVY_TASK_PATTERNS:
            match = pattern.search(msg_clean)
            if match:
                target_model = requested_model or self.openrouter_heavy_model
                return RoutingDecision(
                    mode="heavy",
                    provider="openrouter",
                    model=target_model,
                    reason=f"Matched complex reasoning task pattern: '{match.group(0)}'."
                )

        # 5. Default fallback for Auto: NORMAL Mode (local LM Studio Bonsai or Ollama rollback)
        provider, target_model, label = self._resolve_normal_target(requested_model)
        return RoutingDecision(
            mode="normal",
            provider=provider,
            model=target_model,
            reason=f"Standard complexity query routed to local {label} (Normal Mode)."
        )
