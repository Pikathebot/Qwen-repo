import asyncio
import os
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.runtime_process_manager import (
    RuntimeProcessManager,
    reset_runtime_process_manager,
    resolve_repo_path,
)


@pytest.fixture(autouse=True)
def clean_pm():
    reset_runtime_process_manager()
    yield
    reset_runtime_process_manager()


def test_resolve_repo_path():
    p_rel = resolve_repo_path("models/test.gguf")
    assert p_rel.is_absolute()
    assert str(p_rel).endswith("models\\test.gguf") or str(p_rel).endswith("models/test.gguf")


@pytest.mark.anyio
async def test_ensure_running_noops_when_healthy():
    pm = RuntimeProcessManager()
    with patch.object(pm, "health_check", return_value=True), \
         patch("subprocess.Popen") as mock_spawn:
        res = await pm.ensure_running(model_kind="main")
        assert res is True
        mock_spawn.assert_not_called()
        assert pm.is_externally_managed is True


@pytest.mark.anyio
async def test_ensure_running_recheck_keeps_externally_managed_false_for_jarvis_spawned():
    pm = RuntimeProcessManager()
    mock_proc = MagicMock()
    mock_proc.poll = MagicMock(return_value=None)
    mock_proc.pid = 8888
    pm._process = mock_proc
    pm._current_model_kind = "main"
    pm._externally_managed = False

    with patch.object(pm, "health_check", return_value=True), \
         patch("subprocess.Popen") as mock_spawn:
        res = await pm.ensure_running(model_kind="main")
        assert res is True
        mock_spawn.assert_not_called()
        # Must stay False because Jarvis spawned it
        assert pm.is_externally_managed is False



@pytest.mark.anyio
async def test_ensure_running_spawns_when_unhealthy():
    pm = RuntimeProcessManager(startup_timeout=5.0)

    mock_proc = MagicMock()
    mock_proc.poll = MagicMock(return_value=None)
    mock_proc.stdout = None
    mock_proc.stderr = None
    mock_proc.pid = 9999

    health_states = [False, False, True]

    async def mock_health(timeout=None):
        if health_states:
            return health_states.pop(0)
        return True

    with patch.object(pm, "health_check", side_effect=mock_health), \
         patch("subprocess.Popen") as mock_spawn:
        mock_spawn.return_value = mock_proc
        res = await pm.ensure_running(model_kind="main")

        assert res is True
        mock_spawn.assert_called_once()
        args, kwargs = mock_spawn.call_args
        cmd = args[0]
        assert "--model" in cmd
        assert "--alias" in cmd
        assert "main" in cmd
        assert "--ctx-size" in cmd


@pytest.mark.anyio
async def test_stop_terminates_and_kills_on_timeout():
    pm = RuntimeProcessManager()
    mock_proc = MagicMock()
    mock_proc.poll = MagicMock(return_value=None)
    mock_proc.pid = 1234
    mock_proc.terminate = MagicMock()
    mock_proc.kill = MagicMock()
    mock_proc.wait = MagicMock(return_value=0)
    pm._process = mock_proc
    pm._externally_managed = False

    res = await pm.stop()
    assert res is True
    mock_proc.terminate.assert_called_once()
    mock_proc.kill.assert_called_once()
    assert pm._process is None


@pytest.mark.anyio
async def test_externally_managed_server_is_never_killed():
    pm = RuntimeProcessManager()
    pm._externally_managed = True
    pm._process = None

    res = await pm.stop()
    assert res is True
    assert pm._process is None


@pytest.mark.anyio
async def test_stop_does_not_sweep_unrelated_processes_by_default():
    pm = RuntimeProcessManager()
    pm._process = None

    unrelated_proc = MagicMock()
    unrelated_proc.info = {"pid": 55555, "name": "llama-server.exe"}
    unrelated_proc.terminate = MagicMock()

    with patch("psutil.process_iter", return_value=[unrelated_proc]) as mock_iter:
        res = await pm.stop(sweep_all=False)
        assert res is True
        mock_iter.assert_not_called()
        unrelated_proc.terminate.assert_not_called()


@pytest.mark.anyio
async def test_stop_sweeps_all_when_explicitly_requested():
    pm = RuntimeProcessManager()
    pm._process = None

    unrelated_proc = MagicMock()
    unrelated_proc.info = {"pid": 55555, "name": "llama-server.exe"}
    unrelated_proc.terminate = MagicMock()
    unrelated_proc.wait = MagicMock(return_value=0)

    with patch("psutil.process_iter", return_value=[unrelated_proc]) as mock_iter:
        res = await pm.stop(sweep_all=True)
        assert res is True
        mock_iter.assert_called_once()
        unrelated_proc.terminate.assert_called_once()



@pytest.mark.anyio
async def test_switch_model_restarts_with_new_model():
    pm = RuntimeProcessManager()
    pm._current_model_kind = "main"
    pm._process = MagicMock(returncode=None)

    with patch.object(pm, "_stop_internal", new_callable=AsyncMock) as mock_stop, \
         patch.object(pm, "ensure_running", new_callable=AsyncMock) as mock_ensure:
        mock_stop.return_value = True
        mock_ensure.return_value = True

        res = await pm.switch_model("fast")
        assert res is True
        mock_stop.assert_awaited_once()
        mock_ensure.assert_awaited_once_with("fast")


def test_static_audit_no_lms_cli_usage_in_backend_app():
    """
    Static analysis check verifying no active module in backend/app
    references 'lms' CLI subprocess or shutil.which for LM Studio,
    except for the deprecated lmstudio_client.py.
    """
    app_dir = Path(__file__).resolve().parent.parent / "app"
    forbidden_terms = ["shutil.which('lms')", 'shutil.which("lms")', "lms unload", "lms load"]

    for py_file in app_dir.rglob("*.py"):
        if py_file.name == "lmstudio_client.py":
            continue
        code = py_file.read_text(encoding="utf-8", errors="ignore")
        for term in forbidden_terms:
            assert term not in code, f"Forbidden LM Studio CLI pattern '{term}' found in {py_file}"
