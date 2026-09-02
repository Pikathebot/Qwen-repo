from typing import Optional
from app.sandbox.base import ExecutionBackend, ExecutionResult


class DockerBackend(ExecutionBackend):
    """
    Docker container sandbox execution backend (Stub for Build Plan §12).
    """

    def __init__(self, image: str = "python:3.11-slim"):
        self.image = image

    async def execute(
        self,
        command: str,
        cwd: str = ".",
        env: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> ExecutionResult:
        raise NotImplementedError("Docker sandbox backend is not yet configured.")

    async def cancel(self) -> None:
        raise NotImplementedError("Docker sandbox backend is not yet configured.")
