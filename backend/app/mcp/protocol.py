from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MCPTool:
    name: str
    description: str
    inputSchema: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolCallResult:
    content: list[dict[str, Any]] = field(default_factory=list)
    isError: bool = False

    @property
    def text(self) -> str:
        texts = [c.get("text", "") for c in self.content if c.get("type") == "text"]
        return "\n".join(texts)
