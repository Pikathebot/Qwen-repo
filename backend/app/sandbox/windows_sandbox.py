from typing import Optional
from app.sandbox.base import ExecutionBackend, ExecutionResult


class WindowsSandboxBackend(ExecutionBackend):
    """
    Windows Sandbox / AppContainer isolation backend (Stub for Build Plan §12).
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path

    async def execute(
        self,
        command: str,
        cwd: str = ".",
        env: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> ExecutionResult:
        raise NotImplementedError("Windows Sandbox backend is not yet configured.")

    async def cancel(self) -> None:
        raise NotImplementedError("Windows Sandbox backend is not yet configured.")
