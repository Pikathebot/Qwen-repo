import logging
import time
from typing import Any, Optional
from app.config import settings
from app.memory.store import MemoryStore

logger = logging.getLogger("jarvis.agent.reliability")


class ReliabilityMonitor:
    """
    Monitors tool-call reliability rate over a rolling window (default: last 30 tool calls).
    Triggers loud alerts and automated rollback from 'bonsai' to 'hermes3' if reliability
    falls below the 75% floor after cold-start.
    """

    def __init__(
        self,
        memory_store: Optional[MemoryStore] = None,
        window_size: Optional[int] = None,
        floor: Optional[float] = None
    ):
        self.memory_store = memory_store or MemoryStore(db_path=settings.memory_db_path)
        self.window_size = window_size or getattr(settings, "reliability_window_size", 30)
        self.floor = floor if floor is not None else getattr(settings, "reliability_floor", 0.75)

    def get_latest_backend_activation_timestamp(self, backend: str = "bonsai") -> Optional[float]:
        """
        Returns the timestamp when the backend was last manually enabled/switched to, if any.
        Ensures a fresh evaluation epoch and cold-start window post-review.
        Note: Returns None if no prior switch is on record (evaluating since inception, safe for fresh install).
        """
        events = self.memory_store.get_reliability_events(limit=50)
        for ev in events:
            if ev.get("event_type") == "MANUAL_SWITCH" and ev.get("backend_to") == backend:
                return ev.get("timestamp")
        return None

    def get_status(self, model_tier: str = "tier2") -> dict[str, Any]:
        """
        Get current rolling window reliability metrics and cold-start state.
        """
        active_backend = getattr(settings, "active_model_backend", "bonsai").lower().strip()
        since_ts = self.get_latest_backend_activation_timestamp(active_backend)
        stats = self.memory_store.calculate_rolling_reliability(
            window_size=self.window_size,
            model_tier=model_tier,
            floor=self.floor,
            since_timestamp=since_ts
        )
        stats["active_model_backend"] = active_backend
        stats["evaluation_epoch_since"] = since_ts
        return stats

    def evaluate_and_trigger_rollback(
        self,
        model_tier: str = "tier2"
    ) -> Optional[dict[str, Any]]:
        """
        Evaluate tool reliability over the rolling window and execute rollback if floor is breached.
        Enforces cold-start guard (no evaluation before 30 samples).
        """
        current_backend = getattr(settings, "active_model_backend", "bonsai").lower().strip()

        # If already rolled back or on hermes3, do not trigger auto-rollback or auto-revert
        if current_backend != "bonsai":
            return None

        since_ts = self.get_latest_backend_activation_timestamp(current_backend)
        stats = self.memory_store.calculate_rolling_reliability(
            window_size=self.window_size,
            model_tier=model_tier,
            floor=self.floor,
            since_timestamp=since_ts
        )

        # Cold start guard: Do not evaluate against a partial window
        if stats["cold_start"]:
            logger.debug(
                "Reliability monitor: Cold start active (%d/%d samples). Skipping rollback evaluation.",
                stats["total_samples"], self.window_size
            )
            return None

        if stats["floor_breached"]:
            now = time.time()
            failed_summary = [
                {
                    "call_id": c.get("call_id"),
                    "turn_id": c.get("turn_id"),
                    "tool_name": c.get("tool_name"),
                    "error": c.get("error"),
                    "validation_result": c.get("validation_result"),
                    "repair_attempt": c.get("repair_attempt")
                }
                for c in stats["failed_calls"]
            ]

            # 1. Log alert-level event with loud warning
            alert_msg = (
                "CRITICAL ALERT: Tool-call reliability rate dropped below floor! "
                f"Current Rate: {stats['reliability_rate'] * 100.0:.2f}% (Floor: {self.floor * 100.0:.2f}%, Window: {self.window_size}, Samples: {stats['total_samples']}, Timestamp: {now:.3f}). "
                "Triggering automatic rollback from 'bonsai' to 'hermes3'. "
                f"Failed calls causing breach: {failed_summary}"
            )
            logger.warning(alert_msg)
            logging.getLogger().warning(alert_msg)


            # 2. Automatically flip active_model_backend config flag from 'bonsai' to 'hermes3'
            settings.active_model_backend = "hermes3"

            # 3. Record rollback event in audit store
            event = self.memory_store.record_reliability_event(
                event_type="ROLLBACK_TRIGGERED",
                backend_from="bonsai",
                backend_to="hermes3",
                reliability_rate=stats["reliability_rate"],
                window_size=self.window_size,
                failed_calls=failed_summary,
                details=(
                    f"Rolling tool reliability rate ({stats['reliability_rate']:.2%}) dropped below "
                    f"configured floor ({self.floor:.2%}) over last {self.window_size} calls. "
                    f"Automatic rollback to Ollama hermes3:8b initiated."
                ),
                timestamp=now
            )
            return event

        return None

    def switch_backend(
        self,
        target_backend: str,
        reason: str = "manual switch"
    ) -> dict[str, Any]:
        """
        Manually switch active model backend (e.g. to re-enable Bonsai after manual review).
        """
        normalized = target_backend.lower().strip()
        if normalized not in ("bonsai", "hermes3"):
            raise ValueError(f"Invalid model backend '{target_backend}'. Must be 'bonsai' or 'hermes3'.")

        current = getattr(settings, "active_model_backend", "bonsai").lower().strip()
        settings.active_model_backend = normalized

        event = self.memory_store.record_reliability_event(
            event_type="MANUAL_SWITCH",
            backend_from=current,
            backend_to=normalized,
            reliability_rate=1.0,
            window_size=self.window_size,
            failed_calls=[],
            details=f"Manual backend switch to '{normalized}' requested (reason: {reason})."
        )
        logger.info("Active model backend manually switched from '%s' to '%s' (reason: %s)", current, normalized, reason)
        return {
            "success": True,
            "previous_backend": current,
            "active_backend": normalized,
            "event": event
        }

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent rollback and reliability events."""
        return self.memory_store.get_reliability_events(limit=limit)
