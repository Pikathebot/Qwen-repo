import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class ExecutionResult:
    """
    Standardized execution output for any sandbox execution backend.
    """
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    cancelled: bool = False
    latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionBackend(ABC):
    """
    Abstract interface for pluggable command execution backends (Build Plan §12).
    """

    @abstractmethod
    async def execute(
        self,
        command: str,
        cwd: str = ".",
        env: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> ExecutionResult:
        """
        Executes a command asynchronously inside the sandbox environment.
        """
        pass

    @abstractmethod
    async def cancel(self) -> None:
        """
        Cancels any ongoing execution and terminates process tree.
        """
        pass
