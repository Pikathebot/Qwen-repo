import pytest
import httpx
from app.main import app, governor
from app.governor.resource_governor import ResourceGovernor, SystemMetrics


def test_governor_telemetry_collection():
    """Verify live hardware telemetry collection."""
    gov = ResourceGovernor(enabled=True)
    metrics = gov.collect_metrics()
    
    assert metrics.cpu_percent >= 0.0
    assert metrics.ram_percent > 0.0
    assert metrics.ram_total_mb > 0.0
    assert metrics.ram_used_mb > 0.0
    assert isinstance(metrics.gpu_available, bool)
    if metrics.gpu_available:
        assert metrics.vram_total_mb > 0.0
        assert metrics.gpu_util_percent >= 0.0


def test_governor_threshold_breach_detection():
    """Verify governor throttles when thresholds are breached."""
    gov = ResourceGovernor(
        enabled=True,
        cpu_threshold=0.1,  # Ultra-low threshold guarantees breach
        gpu_threshold=0.1,
    )
    metrics = gov.collect_metrics()
    assert metrics.throttled is True
    assert len(metrics.throttle_reasons) > 0


def test_governor_disabled_mode():
    """Verify disabled governor never throttles."""
    gov = ResourceGovernor(
        enabled=False,
        cpu_threshold=0.1,
        gpu_threshold=0.1,
    )
    metrics = gov.collect_metrics()
    assert metrics.throttled is False
    assert len(metrics.throttle_reasons) == 0


@pytest.mark.anyio
async def test_governor_adaptive_wait():
    gov = ResourceGovernor(
        enabled=True,
        cpu_threshold=100.0,
        gpu_threshold=100.0,
        ram_threshold=100.0,
        vram_threshold=100.0
    )
    await gov.start()
    try:
        is_healthy, reason = await gov.wait_until_healthy(timeout_seconds=0.5)
        assert is_healthy is True
        assert reason is None
    finally:
        await gov.stop()


@pytest.mark.anyio
async def test_governor_status_endpoint():
    """Verify GET /governor/status returns telemetry and threshold configuration."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/governor/status")
    
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert "throttled" in data
    assert "metrics" in data
    assert "thresholds" in data
    assert "cpu_percent" in data["metrics"]
    assert "ram_percent" in data["metrics"]
    assert "gpu_available" in data["metrics"]


@pytest.mark.anyio
async def test_chat_blocked_and_recovered_with_governor():
    """
    Artificially trigger governor throttle, verify /chat returns HTTP 429,
    then restore thresholds and verify /chat resumes normal execution.
    """
    orig_cpu = governor.cpu_threshold
    orig_gpu = governor.gpu_threshold

    try:
        # 1. Artificially lower threshold to 0.01% to force throttle state
        governor.cpu_threshold = 0.01
        governor.gpu_threshold = 0.01
        governor._current_metrics = governor.collect_metrics()

        payload = {
            "message": "Say 'hello'",
            "model": "qwen2.5:0.5b"
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=10.0) as ac:
            res_blocked = await ac.post("/chat", json=payload)
        
        # Verify request is rejected with 429
        assert res_blocked.status_code == 429
        assert "Resource Governor active" in res_blocked.json()["detail"]

        # 2. Restore healthy thresholds
        governor.cpu_threshold = orig_cpu
        governor.gpu_threshold = orig_gpu
        governor._current_metrics = governor.collect_metrics()

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0) as ac:
            res_recovered = await ac.post("/chat", json=payload)
        
        # Verify request successfully recovers and executes
        assert res_recovered.status_code == 200
        assert res_recovered.json()["status"] == "completed"

    finally:
        governor.cpu_threshold = orig_cpu
        governor.gpu_threshold = orig_gpu
        governor._current_metrics = governor.collect_metrics()


@pytest.mark.anyio
async def test_governor_auto_unload_callback():
    """Verify governor triggers auto-unload callback on sustained throttle."""
    unloaded_called = []

    async def mock_unload():
        unloaded_called.append(True)

    gov = ResourceGovernor(
        enabled=True,
        cpu_threshold=0.01,  # Force throttle
        gpu_threshold=0.01,
        poll_interval=0.1,
        auto_unload_on_throttle=True,
        on_throttle_unload=mock_unload
    )

    await gov.start()
    try:
        import asyncio
        await asyncio.sleep(0.35)
        assert len(unloaded_called) >= 1
    finally:
        await gov.stop()

