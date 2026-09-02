import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union
from app.config import settings

logger = logging.getLogger("jarvis.agent.router")


class RoutingMode(str, Enum):
    AUTO = "auto"
    NORMAL = "normal"
    HEAVY = "heavy"


class TaskType(str, Enum):
    """
    Task classification for deterministic model routing (Build Plan Section 22).
    - simple_chat, summarization, background_memory, compaction -> FAST_MODEL (Qwen3.5-4B)
    - deep_reasoning, coding, complex_tool_use -> MAIN_MODEL (Qwen3.5-9B)
    """
    SIMPLE_CHAT = "simple_chat"
    SUMMARIZATION = "summarization"
    BACKGROUND_MEMORY = "background_memory"
    COMPACTION = "compaction"
    DEEP_REASONING = "deep_reasoning"
    CODING = "coding"
    COMPLEX_TOOL_USE = "complex_tool_use"
    VISION = "vision"
    WEB_EXTRACTION = "web_extraction"


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

        return "llama_cpp", "main", "llama.cpp (Default Main)"

    def route_task(
        self,
        task_type: Union[TaskType, str],
        message: str = "",
        requested_mode: Optional[str] = None,
        requested_model: Optional[str] = None,
    ) -> RoutingDecision:
        """
        Deterministic routing based on TaskType (Build Plan Section 22):
        - simple_chat, summarization, background_memory, compaction -> FAST_MODEL
        - deep_reasoning, coding, complex_tool_use -> MAIN_MODEL
        """
        task_str = task_type.value if isinstance(task_type, TaskType) else str(task_type).lower().strip()

        # 1. Vision Task Type -> Route to VISION_MODEL
        if task_str in (TaskType.VISION.value, "vision"):
            vision_target = requested_model or getattr(settings, "vision_model", None) or "Qwen2.5-VL-7B-Instruct"
            provider = "llama_cpp" if self.active_runtime == "llama_cpp" else "ollama"
            decision = RoutingDecision(
                mode="normal",
                provider=provider,
                model=vision_target,
                reason=f"Task '{task_str}' routed deterministically to VISION_MODEL ({vision_target})."
            )
            logger.info("[ModelRouter] %s", decision.reason)
            return decision

        fast_tasks = {
            TaskType.SIMPLE_CHAT.value,
            TaskType.SUMMARIZATION.value,
            TaskType.BACKGROUND_MEMORY.value,
            TaskType.COMPACTION.value,
            TaskType.WEB_EXTRACTION.value,
            "simple_chat",
            "summarization",
            "background_memory",
            "compaction",
            "web_extraction",
        }

        prefer_fast = task_str in fast_tasks
        provider, model, label = self._resolve_local_target(requested_model, prefer_fast=prefer_fast)
        tier_label = "FAST_MODEL" if prefer_fast else "MAIN_MODEL"

        decision = RoutingDecision(
            mode="normal",
            provider=provider,
            model=model,
            reason=f"Task '{task_str}' routed deterministically to {tier_label} ({label})."
        )

        logger.info(
            "[ModelRouter] Deterministic route: task_type='%s' -> target='%s' via '%s' (Reason: %s)",
            task_str, decision.model, decision.provider, decision.reason
        )
        return decision

    def evaluate(
        self,
        message: str,
        requested_mode: Optional[str] = None,
        requested_model: Optional[str] = None,
        task_type: Optional[Union[TaskType, str]] = None,
    ) -> RoutingDecision:
        """
        Evaluate user message and request parameters to produce a deterministic RoutingDecision.
        Maintains complete backward compatibility with Phase 4 agent loop callers.
        """
        if task_type:
            return self.route_task(task_type, message, requested_mode, requested_model)

        mode_str = (requested_mode or self.default_mode).lower().strip()
        msg_clean = message.strip()
        cloud_enabled = getattr(settings, "cloud_routing_enabled", False) and getattr(settings, "openrouter_enabled", False)

        # 1. Explicit Mode: HEAVY
        if mode_str == RoutingMode.HEAVY.value:
            if cloud_enabled:
                target_model = requested_model or self.openrouter_heavy_model
                decision = RoutingDecision(
                    mode="heavy",
                    provider="openrouter",
                    model=target_model,
                    reason="Explicitly requested Heavy Mode (Cloud OpenRouter) via request parameters."
                )
                logger.info("[ModelRouter] %s", decision.reason)
                return decision
            else:
                provider, model, label = self._resolve_local_target(requested_model, prefer_fast=False)
                decision = RoutingDecision(
                    mode="normal",
                    provider=provider,
                    model=model,
                    reason=f"Heavy Mode requested but cloud routing is disabled by config; routed to local {label}."
                )
                logger.info("[ModelRouter] %s", decision.reason)
                return decision

        # 2. Explicit Mode: NORMAL
        if mode_str == RoutingMode.NORMAL.value:
            provider, model, label = self._resolve_local_target(requested_model, prefer_fast=False)
            decision = RoutingDecision(
                mode="normal",
                provider=provider,
                model=model,
                reason=f"Explicitly requested Normal Mode ({label}) via request parameters."
            )
            logger.info("[ModelRouter] %s", decision.reason)
            return decision

        # 3. AUTO Mode: Check prompt tags
        msg_lower = msg_clean.lower()
        for tag in HEAVY_TAG_PREFIXES:
            if msg_lower.startswith(tag):
                if cloud_enabled:
                    target_model = requested_model or self.openrouter_heavy_model
                    decision = RoutingDecision(
                        mode="heavy",
                        provider="openrouter",
                        model=target_model,
                        reason=f"Matched explicit user heavy-mode trigger tag: '{tag}'."
                    )
                    logger.info("[ModelRouter] %s", decision.reason)
                    return decision
                else:
                    provider, model, label = self._resolve_local_target(requested_model, prefer_fast=False)
                    decision = RoutingDecision(
                        mode="normal",
                        provider=provider,
                        model=model,
                        reason=f"Matched heavy trigger tag '{tag}', but cloud routing is disabled; routed to local {label}."
                    )
                    logger.info("[ModelRouter] %s", decision.reason)
                    return decision

        # 4. AUTO Mode: Check heavy complexity heuristics
        for pattern in HEAVY_TASK_PATTERNS:
            match = pattern.search(msg_clean)
            if match:
                if cloud_enabled:
                    target_model = requested_model or self.openrouter_heavy_model
                    decision = RoutingDecision(
                        mode="heavy",
                        provider="openrouter",
                        model=target_model,
                        reason=f"Matched complex reasoning task pattern: '{match.group(0)}'."
                    )
                    logger.info("[ModelRouter] %s", decision.reason)
                    return decision
                else:
                    provider, model, label = self._resolve_local_target(requested_model, prefer_fast=False)
                    decision = RoutingDecision(
                        mode="normal",
                        provider=provider,
                        model=model,
                        reason=f"Matched complex task pattern '{match.group(0)}' (local {label})."
                    )
                    logger.info("[ModelRouter] %s", decision.reason)
                    return decision

        # 5. Default AUTO Mode: Check coding/tools vs fast query
        is_coding_task = any(p.search(msg_clean) for p in CODING_AND_TOOL_PATTERNS)
        prefer_fast = not is_coding_task and len(msg_clean.split()) <= 15 and not any(kw in msg_lower for kw in ["tool", "file", "search", "run", "execute", "create", "write"])

        provider, model, label = self._resolve_local_target(requested_model, prefer_fast=prefer_fast)
        decision = RoutingDecision(
            mode="normal",
            provider=provider,
            model=model,
            reason=f"Local execution routed to {label}."
        )
        logger.info("[ModelRouter] %s", decision.reason)
        return decision
