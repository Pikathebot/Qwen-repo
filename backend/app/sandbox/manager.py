import logging
from typing import Optional

from app.sandbox.base import ExecutionBackend, ExecutionResult
from app.sandbox.local_process import LocalRestrictedProcessBackend

logger = logging.getLogger("jarvis.sandbox.manager")


class SandboxManager:
    """
    Central manager and router for sandbox execution backends (Build Plan §12).
    Dispatches execution requests to the active configured backend.
    """

    def __init__(self, backend: Optional[ExecutionBackend] = None):
        self._backend: ExecutionBackend = backend or LocalRestrictedProcessBackend()

    def get_backend(self) -> ExecutionBackend:
        return self._backend

    def set_backend(self, backend: ExecutionBackend) -> None:
        if not isinstance(backend, ExecutionBackend):
            raise TypeError(f"Expected ExecutionBackend instance, got {type(backend)}")
        logger.info("Switched active sandbox backend to %s", backend.__class__.__name__)
        self._backend = backend

    async def execute(
        self,
        command: str,
        cwd: str = ".",
        env: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> ExecutionResult:
        """
        Executes command through the active sandbox backend.
        """
        return await self._backend.execute(
            command=command,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )

    async def cancel(self) -> None:
        """
        Cancels running process on the active sandbox backend.
        """
        await self._backend.cancel()
