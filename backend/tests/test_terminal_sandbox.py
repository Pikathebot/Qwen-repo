import os
import pytest
from pathlib import Path

from app.tools.terminal import TerminalExecuteTool
from app.tools.base import PermissionDeniedError


@pytest.fixture
def terminal_sandbox_env(tmp_path):
    proj_dir = tmp_path / "workspace" / "projects" / "term_proj"
    proj_dir.mkdir(parents=True, exist_ok=True)

    outside_dir = tmp_path / "forbidden_outside"
    outside_dir.mkdir(parents=True, exist_ok=True)

    return {
        "proj_dir": proj_dir,
        "outside_dir": outside_dir,
        "allowed_folders": [proj_dir]
    }


@pytest.mark.anyio
async def test_terminal_execute_success(terminal_sandbox_env):
    tool = TerminalExecuteTool()
    allowed = terminal_sandbox_env["allowed_folders"]
    cwd = str(terminal_sandbox_env["proj_dir"])

    res = await tool.execute(
        command='python -c "print(\'NEXUS_TERMINAL_OK\')"',
        cwd=cwd,
        allowed_folders=allowed,
        timeout_seconds=5.0
    )

    assert res.status == "success"
    assert res.result["exit_code"] == 0
    assert "NEXUS_TERMINAL_OK" in res.result["stdout"]
    assert res.result["timed_out"] is False


@pytest.mark.anyio
async def test_terminal_execute_timeout_and_process_kill(terminal_sandbox_env):
    """Amendment 1: Assert long-running process is killed upon timeout on Windows."""
    tool = TerminalExecuteTool()
    allowed = terminal_sandbox_env["allowed_folders"]
    cwd = str(terminal_sandbox_env["proj_dir"])

    # Sleep 10s with 1.0s timeout
    res = await tool.execute(
        command='python -c "import time; time.sleep(10)"',
        cwd=cwd,
        allowed_folders=allowed,
        timeout_seconds=1.0
    )

    assert res.status == "error"
    assert res.result["timed_out"] is True
    assert res.result["exit_code"] == -1
    assert "timed out" in res.result["stderr"]


@pytest.mark.anyio
async def test_terminal_blocks_outside_cwd(terminal_sandbox_env):
    tool = TerminalExecuteTool()
    allowed = terminal_sandbox_env["allowed_folders"]
    forbidden_cwd = str(terminal_sandbox_env["outside_dir"])

    res = await tool.execute(
        command='python -c "print(\'should_fail\')"',
        cwd=forbidden_cwd,
        allowed_folders=allowed
    )

    assert res.status == "error"
    assert "Access denied" in res.error or "outside the allowed project sandbox" in res.error
