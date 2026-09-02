import os
import pytest
from pathlib import Path

from app.sandbox.base import ExecutionBackend, ExecutionResult
from app.sandbox.local_process import LocalRestrictedProcessBackend
from app.sandbox.docker import DockerBackend
from app.sandbox.windows_sandbox import WindowsSandboxBackend
from app.sandbox.manager import SandboxManager
from app.tools.terminal import TerminalExecuteTool


@pytest.mark.anyio
async def test_local_process_backend_success(tmp_path):
    backend = LocalRestrictedProcessBackend(default_timeout=5.0)
    result = await backend.execute(
        command='python -c "print(\'SANDBOX_SUCCESS\')"',
        cwd=str(tmp_path),
        timeout=5.0
    )

    assert result.exit_code == 0
    assert "SANDBOX_SUCCESS" in result.stdout
    assert result.timed_out is False
    assert result.cancelled is False


@pytest.mark.anyio
async def test_local_process_backend_timeout_and_process_kill(tmp_path):
    backend = LocalRestrictedProcessBackend(default_timeout=1.0)
    result = await backend.execute(
        command='python -c "import time; time.sleep(10)"',
        cwd=str(tmp_path),
        timeout=1.0
    )

    assert result.exit_code == -1
    assert result.timed_out is True
    assert "timed out" in result.stderr


def test_local_process_backend_env_sanitization():
    backend = LocalRestrictedProcessBackend()
    custom_env = {
        "MY_VAR": "safe_value",
        "LD_PRELOAD": "/evil/hack.so",
        "NODE_OPTIONS": "--inspect",
    }
    sanitized = backend.build_restricted_env(custom_env)

    assert sanitized["MY_VAR"] == "safe_value"
    assert "LD_PRELOAD" not in sanitized
    assert "NODE_OPTIONS" not in sanitized
    assert "PATH" in sanitized


@pytest.mark.anyio
async def test_docker_backend_not_implemented():
    backend = DockerBackend()
    with pytest.raises(NotImplementedError, match="Docker sandbox backend"):
        await backend.execute("ls")
    with pytest.raises(NotImplementedError, match="Docker sandbox backend"):
        await backend.cancel()


@pytest.mark.anyio
async def test_windows_sandbox_backend_not_implemented():
    backend = WindowsSandboxBackend()
    with pytest.raises(NotImplementedError, match="Windows Sandbox backend"):
        await backend.execute("dir")
    with pytest.raises(NotImplementedError, match="Windows Sandbox backend"):
        await backend.cancel()


@pytest.mark.anyio
async def test_sandbox_manager_dispatch(tmp_path):
    manager = SandboxManager()
    assert isinstance(manager.get_backend(), LocalRestrictedProcessBackend)

    result = await manager.execute('python -c "print(\'MGR_DISPATCH\')"', cwd=str(tmp_path))
    assert result.exit_code == 0
    assert "MGR_DISPATCH" in result.stdout

    # Test backend switching
    class MockBackend(ExecutionBackend):
        async def execute(self, command, cwd=".", env=None, timeout=None):
            return ExecutionResult(stdout="mocked_out", exit_code=0)
        async def cancel(self):
            pass

    mock_b = MockBackend()
    manager.set_backend(mock_b)
    assert manager.get_backend() is mock_b

    mock_res = await manager.execute("any_command")
    assert mock_res.stdout == "mocked_out"


@pytest.mark.anyio
async def test_terminal_tool_delegates_to_sandbox_manager(tmp_path):
    manager = SandboxManager()
    tool = TerminalExecuteTool(sandbox_manager=manager)

    res = await tool.execute(
        command='python -c "print(\'TERMINAL_DELEGATE_OK\')"',
        cwd=str(tmp_path),
        allowed_folders=[tmp_path]
    )

    assert res.status == "success"
    assert res.result["exit_code"] == 0
    assert "TERMINAL_DELEGATE_OK" in res.result["stdout"]


@pytest.mark.anyio
async def test_sandbox_manager_cancel_dispatch():
    manager = SandboxManager()
    # Cancel when no active process runs should complete cleanly without error
    await manager.cancel()


@pytest.mark.anyio
async def test_local_process_backend_cancel_execution():
    backend = LocalRestrictedProcessBackend()
    await backend.cancel()
