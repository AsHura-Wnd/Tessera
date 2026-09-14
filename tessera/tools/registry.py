"""Fixed tool registry for Phase 1 tools."""

from __future__ import annotations

from typing import Iterable

from tessera.tools.builtins import PHASE_1_BUILTIN_TOOLS
from tessera.tools.interface import ToolDefinition

PHASE_1_TOOL_NAMES: frozenset[str] = frozenset({
    "file_read",
    "file_write",
    "file_edit",
    "file_find",
})


class ToolRegistry:
    """Registry maintaining available tool definitions."""

    def __init__(self, tools: Iterable[ToolDefinition] | None = None) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        if tools is not None:
            for tool in tools:
                self.register(tool)

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        """Retrieve a tool definition by name."""
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def list_tools(self) -> list[ToolDefinition]:
        """Return list of all registered tools."""
        return list(self._tools.values())

    def tool_names(self) -> set[str]:
        """Return set of registered tool names."""
        return set(self._tools.keys())


def get_default_registry() -> ToolRegistry:
    """Create a default ToolRegistry pre-populated with Phase 1 built-in tools."""
    return ToolRegistry(tools=PHASE_1_BUILTIN_TOOLS)


def get_phase_2_registry() -> ToolRegistry:
    """Create a ToolRegistry pre-populated with Phase 1 and Phase 2 built-in tools."""
    from tessera.tools.process import PROCESS_RUN_TOOL

    return ToolRegistry(tools=(*PHASE_1_BUILTIN_TOOLS, PROCESS_RUN_TOOL))
