"""Phase-appropriate tool authorization for Tessera."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from tessera.tools.builtins import PHASE_1_BUILTIN_TOOLS
from tessera.tools.interface import ToolDefinition
from tessera.tools.process import PROCESS_RUN_TOOL
from tessera.tools.registry import PHASE_1_TOOL_NAMES

CANONICAL_PHASE_1_TOOLS: dict[str, ToolDefinition] = {
    tool.name: tool for tool in PHASE_1_BUILTIN_TOOLS
}
CANONICAL_PHASE_2_TOOLS: dict[str, ToolDefinition] = {
    PROCESS_RUN_TOOL.name: PROCESS_RUN_TOOL,
}
CANONICAL_ALL_TOOLS: dict[str, ToolDefinition] = {
    **CANONICAL_PHASE_1_TOOLS,
    **CANONICAL_PHASE_2_TOOLS,
}


class ExecutionPhase(str, Enum):
    """Operational phase boundary defining tool authorization scope."""

    PHASE_1 = "phase_1"
    PHASE_2 = "phase_2"


PHASE_2_TOOL_NAMES: frozenset[str] = frozenset({
    "process_run",
})


@dataclass(frozen=True)
class AuthorizationResult:
    """Outcome of tool authorization check."""

    is_authorized: bool
    error: str | None = None
    phase: ExecutionPhase | None = None

    def __bool__(self) -> bool:
        return self.is_authorized


class ToolAuthorizer:
    """Explicit static capability authorizer for Tessera tool execution.

    The authorized capability set is determined strictly by the ExecutionPhase.
    External callers cannot inject arbitrary allowed tool names or canonical tool mappings.
    """

    def __init__(self, phase: ExecutionPhase = ExecutionPhase.PHASE_1) -> None:
        if not isinstance(phase, ExecutionPhase):
            raise TypeError(
                f"phase must be an instance of ExecutionPhase, got {type(phase).__name__}"
            )
        self._phase = phase
        if phase == ExecutionPhase.PHASE_1:
            self._allowed_tools: frozenset[str] = PHASE_1_TOOL_NAMES
            self._canonical_tools: Mapping[str, ToolDefinition] = CANONICAL_PHASE_1_TOOLS
        elif phase == ExecutionPhase.PHASE_2:
            self._allowed_tools = frozenset(PHASE_1_TOOL_NAMES | PHASE_2_TOOL_NAMES)
            self._canonical_tools = CANONICAL_ALL_TOOLS
        else:
            raise ValueError(f"Unsupported execution phase: {phase}")

    @property
    def phase(self) -> ExecutionPhase:
        """The execution phase governing this authorizer."""
        return self._phase

    @property
    def allowed_tools(self) -> frozenset[str]:
        """Fixed set of tool names authorized for this phase."""
        return self._allowed_tools

    @property
    def canonical_tools(self) -> Mapping[str, ToolDefinition]:
        """Fixed mapping of canonical tool definitions for this phase."""
        return self._canonical_tools

    def authorize(
        self,
        tool_name: str,
        tool: ToolDefinition | None = None,
    ) -> AuthorizationResult:
        """Check whether a tool is authorized to execute in this phase."""
        if tool_name not in self._allowed_tools:
            if tool_name in PHASE_2_TOOL_NAMES and self._phase == ExecutionPhase.PHASE_1:
                return AuthorizationResult(
                    is_authorized=False,
                    error=f"Operation '{tool_name}' is a Phase 2 tool and is not authorized in Phase 1",
                    phase=self._phase,
                )
            return AuthorizationResult(
                is_authorized=False,
                error=f"Operation '{tool_name}' is not authorized in {self._phase.value}",
                phase=self._phase,
            )

        # Canonical tool identity verification during authorization
        if tool is not None:
            if tool.name != tool_name:
                return AuthorizationResult(
                    is_authorized=False,
                    error=f"Tool identity mismatch: call requested '{tool_name}' but tool object is '{tool.name}'",
                    phase=self._phase,
                )
            expected = self._canonical_tools.get(tool_name)
            if expected is not None and tool is not expected:
                return AuthorizationResult(
                    is_authorized=False,
                    error=f"Tool object for '{tool_name}' does not match canonical definition",
                    phase=self._phase,
                )

        return AuthorizationResult(
            is_authorized=True,
            phase=self._phase,
        )


def get_phase_1_authorizer() -> ToolAuthorizer:
    """Create an authorizer permitting only the fixed Phase 1 tool capability set."""
    return ToolAuthorizer(phase=ExecutionPhase.PHASE_1)


def get_phase_2_authorizer() -> ToolAuthorizer:
    """Create an authorizer permitting only the fixed Phase 2 tool capability set."""
    return ToolAuthorizer(phase=ExecutionPhase.PHASE_2)
