import asyncio
import json
import time
import pytest
from unittest.mock import MagicMock, patch
from app.governor.process_watcher import (
    ProcessWatcher,
    WatchedProcess,
    DEFAULT_WATCHLIST,
    load_watchlist,
)
from app.governor.resource_governor import (
    ResourceGovernor,
    ActivityType,
    GovernorStatus,
)


def test_watched_process_matching():
    """Verify exact and contains process matching (case-insensitive)."""
    # Exact
    p1 = WatchedProcess(match="UnrealEditor.exe", match_type="exact", label="Unreal Engine")
    assert p1.matches("unrealeditor.exe") is True
    assert p1.matches("UNREALEDITOR.EXE") is True
    assert p1.matches("OtherApp.exe") is False
    assert p1.matches("MyUnrealEditor.exe") is False

    # Contains
    p2 = WatchedProcess(match="cyberpunk", match_type="contains", label="Cyberpunk 2077")
    assert p2.matches("Cyberpunk2077.exe") is True
    assert p2.matches("CYBERPUNK.exe") is True
    assert p2.matches("launcher.exe") is False


def test_load_watchlist_merging(tmp_path):
    """Verify custom watchlist JSON merges with DEFAULT_WATCHLIST."""
    custom_json = tmp_path / "test_watchlist.json"
    custom_json.write_text(
        json.dumps([
            {"match": "custom_game.exe", "match_type": "exact", "label": "Custom Game"}
        ]),
        encoding="utf-8"
    )

    merged = load_watchlist(config_path=custom_json)
    assert len(merged) == len(DEFAULT_WATCHLIST) + 1
    assert any(w.label == "Custom Game" for w in merged)
    assert any(w.label == "Blender" for w in merged)


@pytest.mark.anyio
async def test_process_watcher_launch_and_recovery_debounce():
    """Verify launch and recovery debounce delays before confirming external app presence."""
    governor = ResourceGovernor(enabled=True)
    watcher = ProcessWatcher(
        watchlist=[WatchedProcess(match="test_game.exe", label="Test Game")],
        poll_interval=0.05,
        launch_debounce_seconds=0.15,
        recovery_debounce_seconds=0.15,
    )

    mock_scans = [
        # Poll 1 (t=0.05): App appears
        [WatchedProcess(match="test_game.exe", label="Test Game")],
        # Poll 2 (t=0.10): App still present (0.05s elapsed < 0.15s launch debounce)
        [WatchedProcess(match="test_game.exe", label="Test Game")],
        # Poll 3 (t=0.15): App still present -> launch debounce satisfied!
        [WatchedProcess(match="test_game.exe", label="Test Game")],
        # Poll 4 (t=0.20): App still present
        [WatchedProcess(match="test_game.exe", label="Test Game")],
        # Poll 5 (t=0.25): App disappears
        [],
        # Poll 6 (t=0.30): App missing (0.05s elapsed < 0.15s recovery debounce)
        [],
        # Poll 7 (t=0.35): App missing -> recovery debounce satisfied!
        [],
    ]

    scan_idx = 0

    def fake_scan():
        nonlocal scan_idx
        if scan_idx < len(mock_scans):
            res = mock_scans[scan_idx]
            scan_idx += 1
            return res
        return []

    watcher.scan = fake_scan

    await watcher.start(governor)
    try:
        # Wait enough time for scan sequence to unfold
        await asyncio.sleep(0.45)
        
        # After sequence completes, app is confirmed closed -> Governor should be IDLE
        assert governor.status == GovernorStatus.IDLE
        assert len(governor._external_apps_active) == 0
    finally:
        await watcher.stop()


@pytest.mark.anyio
async def test_mid_inference_external_app_deferral():
    """
    Verify that if a heavy external app launches while Jarvis is actively inferencing,
    the auto-unload is deferred until inference completes.
    """
    unloaded_called = []

    async def mock_unload():
        unloaded_called.append(True)

    gov = ResourceGovernor(
        enabled=True,
        auto_unload_on_throttle=True,
        on_throttle_unload=mock_unload
    )

    # 1. Start active inference turn
    act_id = gov.begin_activity(ActivityType.INFERENCING, label="long_query")
    assert gov.is_busy is True
    assert gov.status == GovernorStatus.RUNNING

    # 2. External app launches mid-inference
    gov.report_external_app("Helldivers 2", present=True)
    assert gov.status == GovernorStatus.PAUSED
    assert "Helldivers 2" in gov._pending_external_app_unloads
    # Auto-unload must NOT fire while busy
    assert len(unloaded_called) == 0

    # 3. Complete inference turn
    gov.end_activity(act_id)
    assert gov.is_busy is False

    # Wait brief moment for deferred unload async task
    await asyncio.sleep(0.05)
    
    # Auto-unload should have fired now that Jarvis is idle
    assert len(unloaded_called) == 1
    assert gov.model_unloaded is True
    assert gov.status == GovernorStatus.PAUSED


def test_lazy_reload_on_app_close():
    """Verify closing watched app clears pause without proactively loading model."""
    gov = ResourceGovernor(enabled=True)
    gov.report_external_app("Cyberpunk 2077", present=True)
    assert gov.status == GovernorStatus.PAUSED

    # App closes
    gov.report_external_app("Cyberpunk 2077", present=False)
    assert gov.status == GovernorStatus.IDLE
    # Model stays in lazy state until next query
    assert gov.is_busy is False

