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
    provider: str  # "ollama" | "openrouter"
    model: str
    reason: str


class ModelRouter:
    """
    Determines execution destination: Normal Mode (local Ollama) vs Heavy Mode (OpenRouter).
    Enforces deterministic evaluation rules and complete local isolation for Normal Mode.
    """

    def __init__(
        self,
        default_mode: str = "auto",
        ollama_model: Optional[str] = None,
        openrouter_heavy_model: Optional[str] = None
    ):
        self.default_mode = default_mode
        self.ollama_model = ollama_model or settings.ollama_model
        self.openrouter_heavy_model = openrouter_heavy_model or settings.openrouter_heavy_model

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
            target_model = requested_model or self.ollama_model
            return RoutingDecision(
                mode="normal",
                provider="ollama",
                model=target_model,
                reason="Explicitly requested Normal Mode via request parameters."
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

        # 5. Default fallback for Auto: NORMAL Mode (local Ollama)
        target_model = requested_model or self.ollama_model
        return RoutingDecision(
            mode="normal",
            provider="ollama",
            model=target_model,
            reason="Standard complexity query routed to local Ollama (Normal Mode)."
        )
