import time
import pytest
import httpx
from app.config import settings
from app.memory.store import MemoryStore
from app.agent.reliability_monitor import ReliabilityMonitor
from app.agent.model_router import ModelRouter
from app.main import app


@pytest.fixture
def temp_memory_store(tmp_path):
    db_file = tmp_path / "test_reliability.db"
    return MemoryStore(db_path=str(db_file))


def test_cold_start_guard_no_evaluation_before_30_calls(temp_memory_store, monkeypatch):
    """Verify that fewer than 30 samples is treated as cold-start and will NOT trigger rollback."""
    monkeypatch.setattr(settings, "active_model_backend", "bonsai")
    monitor = ReliabilityMonitor(memory_store=temp_memory_store, window_size=30, floor=0.75)

    # Insert 10 calls: 4 clean successes, 6 failures (40% rate)
    for i in range(4):
        temp_memory_store.record_tool_call_audit(
            call_id=f"clean_{i}",
            turn_id="turn_1",
            tool_name="web_search",
            args={"query": "test"},
            model_tier="tier2",
            validation_result="valid",
            permission_result="allowed",
            executed=True,
            repair_attempt=0,
            timestamp=1000 + i
        )
    for i in range(6):
        temp_memory_store.record_tool_call_audit(
            call_id=f"fail_{i}",
            turn_id="turn_1",
            tool_name="write_file",
            args={},
            model_tier="tier2",
            validation_result="invalid_escalated",
            permission_result="blocked",
            executed=False,
            error="Validation failed",
            repair_attempt=1,
            timestamp=1010 + i
        )

    status = monitor.get_status(model_tier="tier2")
    assert status["cold_start"] is True
    assert status["total_samples"] == 10
    assert status["floor_breached"] is False

    # Evaluation should not trigger rollback
    event = monitor.evaluate_and_trigger_rollback(model_tier="tier2")
    assert event is None
    assert settings.active_model_backend == "bonsai"


def test_success_definition_clean_and_repaired_both_count(temp_memory_store, monkeypatch):
    """Verify 2.1 metric: first-attempt clean + auto-repaired calls both count as successes."""
    monkeypatch.setattr(settings, "active_model_backend", "bonsai")
    monitor = ReliabilityMonitor(memory_store=temp_memory_store, window_size=30, floor=0.75)

    # 20 first-attempt clean calls
    for i in range(20):
        temp_memory_store.record_tool_call_audit(
            call_id=f"clean_{i}",
            turn_id="turn_1",
            tool_name="web_search",
            args={"query": "test"},
            model_tier="tier2",
            validation_result="valid",
            permission_result="allowed",
            executed=True,
            repair_attempt=0,
            timestamp=1000 + i
        )

    # 5 auto-repaired calls (attempt 1 valid)
    for i in range(5):
        temp_memory_store.record_tool_call_audit(
            call_id=f"repaired_{i}",
            turn_id="turn_1",
            tool_name="patch_file",
            args={"file_path": "a.py"},
            model_tier="tier2",
            validation_result="valid",
            permission_result="allowed",
            executed=True,
            repair_attempt=1,
            timestamp=1020 + i
        )

    # 5 failed calls (invalid_escalated)
    for i in range(5):
        temp_memory_store.record_tool_call_audit(
            call_id=f"fail_{i}",
            turn_id="turn_1",
            tool_name="write_file",
            args={},
            model_tier="tier2",
            validation_result="invalid_escalated",
            permission_result="blocked",
            executed=False,
            error="Missing required args",
            repair_attempt=1,
            timestamp=1030 + i
        )

    status = monitor.get_status(model_tier="tier2")
    assert status["cold_start"] is False
    assert status["total_samples"] == 30
    assert status["clean_success_count"] == 20
    assert status["repaired_success_count"] == 5
    assert status["success_count"] == 25
    assert status["failure_count"] == 5
    assert status["reliability_rate"] == 0.8333  # 25/30 = 83.33% >= 75%
    assert status["floor_breached"] is False

    event = monitor.evaluate_and_trigger_rollback(model_tier="tier2")
    assert event is None
    assert settings.active_model_backend == "bonsai"


def test_sliding_window_excludes_older_calls(temp_memory_store, monkeypatch):
    """Verify that older calls outside the 30-call window are correctly excluded."""
    monkeypatch.setattr(settings, "active_model_backend", "bonsai")
    monitor = ReliabilityMonitor(memory_store=temp_memory_store, window_size=30, floor=0.75)

    # 15 ancient failures (timestamps 100-114)
    for i in range(15):
        temp_memory_store.record_tool_call_audit(
            call_id=f"ancient_fail_{i}",
            turn_id="turn_old",
            tool_name="write_file",
            args={},
            model_tier="tier2",
            validation_result="invalid_escalated",
            permission_result="blocked",
            executed=False,
            error="Old error",
            repair_attempt=1,
            timestamp=100 + i
        )

    # 30 recent clean successes (timestamps 200-229)
    for i in range(30):
        temp_memory_store.record_tool_call_audit(
            call_id=f"recent_clean_{i}",
            turn_id="turn_new",
            tool_name="web_search",
            args={"query": "test"},
            model_tier="tier2",
            validation_result="valid",
            permission_result="allowed",
            executed=True,
            repair_attempt=0,
            timestamp=200 + i
        )

    status = monitor.get_status(model_tier="tier2")
    assert status["total_samples"] == 30
    assert status["clean_success_count"] == 30
    assert status["failure_count"] == 0
    assert status["reliability_rate"] == 1.0
    assert status["floor_breached"] is False


def test_floor_breach_triggers_loud_alert_and_automatic_rollback(temp_memory_store, monkeypatch, caplog):
    """Verify that dropping below 75% in rolling window logs alert and flips active_model_backend to hermes3."""
    monkeypatch.setattr(settings, "active_model_backend", "bonsai")
    monitor = ReliabilityMonitor(memory_store=temp_memory_store, window_size=30, floor=0.75)

    # 20 clean successes + 10 failures = 20/30 = 66.67% < 75% floor
    for i in range(20):
        temp_memory_store.record_tool_call_audit(
            call_id=f"clean_{i}",
            turn_id="turn_1",
            tool_name="web_search",
            args={"query": "test"},
            model_tier="tier2",
            validation_result="valid",
            permission_result="allowed",
            executed=True,
            repair_attempt=0,
            timestamp=1000 + i
        )

    for i in range(10):
        temp_memory_store.record_tool_call_audit(
            call_id=f"fail_{i}",
            turn_id="turn_1",
            tool_name="patch_file",
            args={},
            model_tier="tier2",
            validation_result="invalid_escalated",
            permission_result="blocked",
            executed=False,
            error=f"Unrepairable syntax error {i}",
            repair_attempt=1,
            timestamp=1020 + i
        )

    with caplog.at_level("WARNING", logger="jarvis.agent.reliability"):
        event = monitor.evaluate_and_trigger_rollback(model_tier="tier2")

    assert event is not None
    assert event["event_type"] == "ROLLBACK_TRIGGERED"
    assert event["backend_from"] == "bonsai"
    assert event["backend_to"] == "hermes3"
    assert event["failed_calls_count"] == 10
    assert event["reliability_rate"] == 0.6667

    # Flag must flip immediately
    assert settings.active_model_backend == "hermes3"

    # Loud warning log check
    assert any("CRITICAL ALERT: Tool-call reliability rate dropped below floor" in r.getMessage() for r in caplog.records) or "CRITICAL ALERT" in caplog.text




    # History audit verification
    history = monitor.get_history()
    assert len(history) >= 1
    assert history[0]["event_type"] == "ROLLBACK_TRIGGERED"


def test_immediate_next_inference_routes_to_hermes3_without_restart(temp_memory_store, monkeypatch):
    """Verify that after rollback, the very next inference request routes to Ollama hermes3:8b."""
    monkeypatch.setattr(settings, "active_model_backend", "bonsai")
    router = ModelRouter(default_mode="auto")

    # Before rollback: routes locally. "bonsai" is a legacy runtime name from the LM Studio era;
    # provider_factory has mapped it to LlamaCppProvider for a long time, and the router now
    # agrees instead of pairing that runtime with an LM Studio model id -- which used to reach
    # llama-server as a file path and kill it. What matters to this test is only that the request
    # routes locally here and to Ollama after the rollback below.
    d1 = router.evaluate("What is 2+2?")
    assert d1.mode == "normal"
    assert d1.provider == "llama_cpp"
    assert d1.model in ("main", "fast")

    # Trigger rollback
    monitor = ReliabilityMonitor(memory_store=temp_memory_store, window_size=30, floor=0.75)
    for i in range(20):
        temp_memory_store.record_tool_call_audit(
            call_id=f"clean_{i}", turn_id="turn_1", tool_name="web_search",
            args={}, model_tier="tier2", validation_result="valid", permission_result="allowed",
            executed=True, repair_attempt=0, timestamp=1000 + i
        )
    for i in range(10):
        temp_memory_store.record_tool_call_audit(
            call_id=f"fail_{i}", turn_id="turn_1", tool_name="write_file",
            args={}, model_tier="tier2", validation_result="invalid_escalated", permission_result="blocked",
            executed=False, error="Syntax error", repair_attempt=1, timestamp=1020 + i
        )

    monitor.evaluate_and_trigger_rollback(model_tier="tier2")
    assert settings.active_model_backend == "hermes3"

    # Very next inference without restart must route to Ollama hermes3:8b
    d2 = router.evaluate("What is 2+2?")
    assert d2.mode == "normal"
    assert d2.provider == "ollama"
    assert d2.model == "hermes3:8b"


def test_no_auto_revert_and_manual_switch(temp_memory_store, monkeypatch):
    """Verify that once rolled back to hermes3, no auto-revert happens, and manual switch is required."""
    monkeypatch.setattr(settings, "active_model_backend", "hermes3")
    monitor = ReliabilityMonitor(memory_store=temp_memory_store, window_size=30, floor=0.75)

    # Insert 30 clean calls while on hermes3
    for i in range(30):
        temp_memory_store.record_tool_call_audit(
            call_id=f"clean_{i}", turn_id="turn_1", tool_name="web_search",
            args={}, model_tier="tier2", validation_result="valid", permission_result="allowed",
            executed=True, repair_attempt=0, timestamp=2000 + i
        )

    # evaluate_and_trigger_rollback should be a no-op when active_model_backend is not bonsai
    event = monitor.evaluate_and_trigger_rollback(model_tier="tier2")
    assert event is None
    assert settings.active_model_backend == "hermes3"

    # Manual switch back to bonsai
    res = monitor.switch_backend("bonsai", reason="Pika resolved Bonsai prompt tuning")
    assert res["success"] is True
    assert res["active_backend"] == "bonsai"
    assert settings.active_model_backend == "bonsai"


def test_manual_switch_clears_window_for_fresh_cold_start(temp_memory_store, monkeypatch):
    """Verify that switching back to Bonsai starts a fresh epoch, avoiding inheriting pre-rollback failures."""
    monkeypatch.setattr(settings, "active_model_backend", "bonsai")
    monitor = ReliabilityMonitor(memory_store=temp_memory_store, window_size=30, floor=0.75)

    # 1. Simulate 30 calls with 10 failures at timestamp 1000-1030 triggering rollback
    for i in range(20):
        temp_memory_store.record_tool_call_audit(
            call_id=f"clean_{i}", turn_id="turn_1", tool_name="web_search",
            args={}, model_tier="tier2", validation_result="valid", permission_result="allowed",
            executed=True, repair_attempt=0, timestamp=1000 + i
        )
    for i in range(10):
        temp_memory_store.record_tool_call_audit(
            call_id=f"fail_{i}", turn_id="turn_1", tool_name="write_file",
            args={}, model_tier="tier2", validation_result="invalid_escalated", permission_result="blocked",
            executed=False, error="Syntax error", repair_attempt=1, timestamp=1020 + i
        )

    # Breaches and rolls back
    ev = monitor.evaluate_and_trigger_rollback(model_tier="tier2")
    assert ev is not None
    assert settings.active_model_backend == "hermes3"

    # 2. Pika reviews and switches back to Bonsai at timestamp 2000
    time_switch = 2000.0
    temp_memory_store.record_reliability_event(
        event_type="MANUAL_SWITCH",
        backend_from="hermes3",
        backend_to="bonsai",
        reliability_rate=1.0,
        window_size=30,
        failed_calls=[],
        details="Manual switch to bonsai post-review",
        timestamp=time_switch
    )
    settings.active_model_backend = "bonsai"

    # 3. Verify that old failures are excluded and fresh cold-start is active
    status = monitor.get_status(model_tier="tier2")
    assert status["total_samples"] == 0
    assert status["cold_start"] is True
    assert status["floor_breached"] is False

    # 4. Log 5 new calls in the new epoch (timestamp 2001-2005)
    for i in range(5):
        temp_memory_store.record_tool_call_audit(
            call_id=f"new_epoch_call_{i}", turn_id="turn_2", tool_name="web_search",
            args={}, model_tier="tier2", validation_result="valid", permission_result="allowed",
            executed=True, repair_attempt=0, timestamp=2001 + i
        )

    status_post = monitor.get_status(model_tier="tier2")
    assert status_post["total_samples"] == 5
    assert status_post["cold_start"] is True
    assert status_post["clean_success_count"] == 5

    # Evaluation should not trigger rollback
    assert monitor.evaluate_and_trigger_rollback(model_tier="tier2") is None
    assert settings.active_model_backend == "bonsai"


def test_switch_backend_full_flow_persists_across_monitor_restarts(temp_memory_store, monkeypatch):
    """Verify that calling switch_backend() writes the epoch event to SQLite, and a new ReliabilityMonitor instance (simulating restart) inherits the epoch."""
    monkeypatch.setattr(settings, "active_model_backend", "bonsai")
    monitor1 = ReliabilityMonitor(memory_store=temp_memory_store, window_size=30, floor=0.75)

    # 1. Fill 30 calls with 10 failures to trigger rollback
    for i in range(20):
        temp_memory_store.record_tool_call_audit(
            call_id=f"clean_{i}", turn_id="turn_1", tool_name="web_search",
            args={}, model_tier="tier2", validation_result="valid", permission_result="allowed",
            executed=True, repair_attempt=0, timestamp=1000 + i
        )
    for i in range(10):
        temp_memory_store.record_tool_call_audit(
            call_id=f"fail_{i}", turn_id="turn_1", tool_name="write_file",
            args={}, model_tier="tier2", validation_result="invalid_escalated", permission_result="blocked",
            executed=False, error="Syntax error", repair_attempt=1, timestamp=1020 + i
        )

    # Rollback fires
    monitor1.evaluate_and_trigger_rollback(model_tier="tier2")
    assert settings.active_model_backend == "hermes3"

    # 2. Call switch_backend() directly on monitor1
    time.sleep(0.01)
    switch_res = monitor1.switch_backend("bonsai", reason="Pika prompt review completed")
    assert switch_res["success"] is True
    assert switch_res["active_backend"] == "bonsai"
    assert settings.active_model_backend == "bonsai"
    switch_ts = switch_res["event"]["timestamp"]

    # 3. Simulate process restart by instantiating a brand-new monitor instance
    monitor_restarted = ReliabilityMonitor(memory_store=temp_memory_store, window_size=30, floor=0.75)

    # 4. Verify the restarted monitor queries the DB and discovers the exact activation epoch
    epoch_ts = monitor_restarted.get_latest_backend_activation_timestamp("bonsai")
    assert epoch_ts == switch_ts

    status = monitor_restarted.get_status(model_tier="tier2")
    assert status["total_samples"] == 0
    assert status["cold_start"] is True
    assert status["evaluation_epoch_since"] == switch_ts
    assert status["floor_breached"] is False

    # 5. Log 2 fresh calls in the new epoch and verify they are counted
    for i in range(2):
        temp_memory_store.record_tool_call_audit(
            call_id=f"post_restart_call_{i}", turn_id="turn_new", tool_name="web_search",
            args={"query": f"test_{i}"}, model_tier="tier2", validation_result="valid",
            permission_result="allowed", executed=True, repair_attempt=0, timestamp=switch_ts + 1 + i
        )

    status_updated = monitor_restarted.get_status(model_tier="tier2")
    assert status_updated["total_samples"] == 2
    assert status_updated["clean_success_count"] == 2
    assert status_updated["cold_start"] is True




@pytest.mark.anyio
async def test_api_reliability_endpoints(monkeypatch):
    """Verify /reliability/status, /reliability/history, and /reliability/switch-backend endpoints."""
    monkeypatch.setattr(settings, "active_model_backend", "bonsai")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. GET /reliability/status
        status_resp = await client.get("/reliability/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert "reliability_rate" in status_data
        assert "window_size" in status_data
        assert "cold_start" in status_data
        assert status_data["floor"] == 0.75

        # 2. POST /reliability/switch-backend
        switch_resp = await client.post("/reliability/switch-backend", json={"backend": "hermes3", "reason": "test manual switch"})
        assert switch_resp.status_code == 200
        switch_data = switch_resp.json()
        assert switch_data["success"] is True
        assert switch_data["active_backend"] == "hermes3"
        assert settings.active_model_backend == "hermes3"

        # 3. GET /reliability/history
        hist_resp = await client.get("/reliability/history")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        assert isinstance(hist_data, list)
        assert len(hist_data) >= 1
        assert hist_data[0]["event_type"] == "MANUAL_SWITCH"
