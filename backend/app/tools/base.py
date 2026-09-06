from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class PermissionLevel(str, Enum):
    LOW_RISK = "LOW_RISK"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    HIGH_RISK = "HIGH_RISK"


class PermissionDeniedError(Exception):
    """Raised when a tool tries to access files or perform operations outside allowed sandbox boundaries."""
    pass


class ToolResult(BaseModel):
    """
    Standardized execution result produced by any BaseTool instance.
    """
    status: str = "success"  # "success" or "error"
    result: Any = None
    error: Optional[str] = None
    summary: Optional[str] = None
    truncated: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_message_content(self) -> str:
        """Convert result to a clean string suitable for LLM context injection."""
        if self.status == "error":
            return f"Error: {self.error or 'Unknown tool execution error'}"
        if isinstance(self.result, str):
            return self.result
        if self.result is None:
            return "Execution completed successfully with no output."
        import json
        try:
            return json.dumps(self.result, indent=2)
        except Exception:
            return str(self.result)


class BaseTool(ABC):
    """
    Abstract Base Class for all Jarvis executable tools complying with Build Plan Section 11.
    """
    name: str
    description: str
    parameters: dict[str, Any]
    permission_level: PermissionLevel = PermissionLevel.LOW_RISK

    def get_schema(self) -> dict[str, Any]:
        """
        Produce OpenAI-compatible function calling tool schema for the LLM.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    @abstractmethod
    async def execute(self, project_id: Optional[str] = None, **kwargs: Any) -> ToolResult:
        """
        Execute tool logic asynchronously. Must be thread-safe and non-blocking.
        """
        pass
