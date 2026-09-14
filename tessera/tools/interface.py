"""Tool interface and parameter definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class ToolParameter:
    """Specification for a single tool parameter."""

    name: str
    type: type
    description: str
    required: bool = True
    default: Any = None
    is_path: bool = False


@dataclass(frozen=True)
class ToolResult:
    """Outcome of a tool execution."""

    success: bool
    output: Any = None
    error: str | None = None


@dataclass(frozen=True)
class ToolDefinition:
    """Definition of an executable tool."""

    name: str
    description: str
    parameters: Mapping[str, ToolParameter] = field(default_factory=dict)
    handler: Callable[..., ToolResult] | None = None

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool handler with provided arguments."""
        if self.handler is None:
            return ToolResult(
                success=False,
                error=f"Tool '{self.name}' has no registered execution handler",
            )
        return self.handler(**kwargs)

    def to_schema(self) -> dict[str, Any]:
        """Convert parameter specifications to JSON schema format."""
        properties: dict[str, Any] = {}
        required: list[str] = []

        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array",
        }

        for param in self.parameters.values():
            type_name = type_map.get(param.type, "string")
            properties[param.name] = {
                "type": type_name,
                "description": param.description,
            }
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


@dataclass(frozen=True)
class ToolCall:
    """Structured representation of a proposed tool call."""

    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
