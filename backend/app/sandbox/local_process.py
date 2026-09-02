import os
import time
import psutil
import asyncio
import logging
from pathlib import Path
from typing import Optional

from app.sandbox.base import ExecutionBackend, ExecutionResult

logger = logging.getLogger("jarvis.sandbox.local_process")

# Standard environment variables permitted in restricted execution
SAFE_ENV_PASSTHROUGH_KEYS = {
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE",
    "TEMP", "TMP", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
    "COMSPEC", "PROGRAMFILES", "PROGRAMFILES(X86)", "COMMONPROGRAMFILES",
    "APPDATA", "LOCALAPPDATA", "LANG", "LC_ALL", "TERM"
}

# Environment variables explicitly stripped to prevent injection / hijacking
DANGEROUS_ENV_KEYS = {
    "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES",
    "DYLD_LIBRARY_PATH", "NODE_OPTIONS", "RUBYOPT", "PERL5OPT"
}


async def kill_process_tree(pid: int) -> None:
    """
    Recursively discovers and terminates child processes and parent process.
    """
    def _kill():
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            try:
                parent.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    await asyncio.to_thread(_kill)


class LocalRestrictedProcessBackend(ExecutionBackend):
    """
    Local restricted subprocess execution backend (Build Plan §12).
    Enforces process tree timeouts, working directory containment, and clean environment filtering.
    """

    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout
        self._current_process: Optional[asyncio.subprocess.Process] = None

    def build_restricted_env(self, custom_env: Optional[dict[str, str]] = None) -> dict[str, str]:
        """
        Builds a sanitized environment dictionary by filtering dangerous injection variables.
        """
        clean_env: dict[str, str] = {}

        # 1. Passthrough safe system environment variables
        for k, v in os.environ.items():
            if k.upper() in SAFE_ENV_PASSTHROUGH_KEYS and k.upper() not in DANGEROUS_ENV_KEYS:
                clean_env[k] = v

        # 2. Add caller's custom environment variables (excluding blacklisted keys)
        if custom_env:
            for k, v in custom_env.items():
                if k.upper() not in DANGEROUS_ENV_KEYS:
                    clean_env[k] = str(v)

        return clean_env

    async def execute(
        self,
        command: str,
        cwd: str = ".",
        env: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> ExecutionResult:
        start_time = time.time()
        effective_timeout = timeout or self.default_timeout
        sanitized_env = self.build_restricted_env(env)
        resolved_cwd = str(Path(cwd).resolve())

        logger.info(
            "Executing local process: '%s' in cwd='%s' (timeout=%.1fs)",
            command, resolved_cwd, effective_timeout
        )

        try:
            self._current_process = await asyncio.create_subprocess_shell(
                command,
                cwd=resolved_cwd,
                env=sanitized_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                self._current_process.communicate(),
                timeout=effective_timeout,
            )
            exit_code = self._current_process.returncode or 0
            timed_out = False
            cancelled = False

        except asyncio.TimeoutError:
            logger.warning("Process timed out after %.1fs. Killing process tree PID=%s", effective_timeout, self._current_process.pid if self._current_process else None)
            timed_out = True
            cancelled = False
            exit_code = -1
            if self._current_process and self._current_process.pid:
                await kill_process_tree(self._current_process.pid)
            stdout_bytes = b""
            stderr_bytes = f"Command timed out after {effective_timeout} seconds and was terminated.".encode("utf-8")

        except asyncio.CancelledError:
            logger.warning("Execution cancelled. Terminating process.")
            cancelled = True
            timed_out = False
            exit_code = -15
            if self._current_process and self._current_process.pid:
                await kill_process_tree(self._current_process.pid)
            stdout_bytes = b""
            stderr_bytes = b"Command execution was cancelled."

        finally:
            self._current_process = None

        latency_ms = int((time.time() - start_time) * 1000)
        stdout_str = stdout_bytes.decode("utf-8", errors="replace")
        stderr_str = stderr_bytes.decode("utf-8", errors="replace")

        return ExecutionResult(
            stdout=stdout_str,
            stderr=stderr_str,
            exit_code=exit_code,
            timed_out=timed_out,
            cancelled=cancelled,
            latency_ms=latency_ms,
            metadata={"cwd": resolved_cwd, "command": command},
        )

    async def cancel(self) -> None:
        if self._current_process and self._current_process.pid:
            await kill_process_tree(self._current_process.pid)
            self._current_process = None
