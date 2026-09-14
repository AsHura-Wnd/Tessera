"""Fixed tool validator and action budget for Phase 1 tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from tessera.tools.authorization import (
    CANONICAL_ALL_TOOLS,
    CANONICAL_PHASE_1_TOOLS,
    PHASE_2_TOOL_NAMES,
)
from tessera.tools.builtins import PHASE_1_BUILTIN_TOOLS
from tessera.tools.interface import ToolCall, ToolDefinition
from tessera.tools.registry import (
    PHASE_1_TOOL_NAMES,
    ToolRegistry,
    get_default_registry,
    get_phase_2_registry,
)



class ActionBudget:
    """Minimal, fixed per-task action budget tracking allowable tool actions."""

    def __init__(self, max_actions: int) -> None:
        if max_actions < 0:
            raise ValueError("max_actions must be a non-negative integer")
        self.max_actions = max_actions
        self.used_actions = 0

    @property
    def remaining(self) -> int:
        """Return the number of remaining actions in the budget."""
        return max(0, self.max_actions - self.used_actions)

    def is_exhausted(self) -> bool:
        """Check if the action budget has been fully consumed."""
        return self.used_actions >= self.max_actions

    def record_action(self) -> None:
        """Record the consumption of one action from the budget."""
        self.used_actions += 1


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of tool call validation."""

    is_valid: bool
    error: str | None = None
    tool: ToolDefinition | None = None
    resolved_paths: Mapping[str, Path] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.is_valid


class ToolValidator:
    """Fixed Phase 1 validator for tool calls.

    Strictly enforces:
    - Rejection of unknown tool names
    - Rejection of operations outside the fixed Phase 1 tool allow-list
    - Rejection of missing required parameters
    - Rejection of unexpected parameters
    - Rejection of invalid parameter types and value constraints
    - Rejection of paths resolving outside workspace root (traversals & symlink escapes)
    - Rejection of calls exceeding the per-task action budget
    """

    @property
    def phase_name(self) -> str:
        """Name of the operational phase enforced by this validator."""
        return "Phase 1"

    @property
    def allowed_tool_names(self) -> frozenset[str]:
        """Fixed allow-list of tool names permitted in Phase 1."""
        return PHASE_1_TOOL_NAMES

    @property
    def canonical_tools(self) -> Mapping[str, ToolDefinition]:
        """Fixed canonical tool definitions for Phase 1."""
        return CANONICAL_PHASE_1_TOOLS

    def __init__(
        self,
        workspace_root: str | Path,
        registry: ToolRegistry | None = None,
        budget: ActionBudget | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.registry = registry or get_default_registry()
        self.budget = budget

    def validate(
        self,
        tool_call_or_name: ToolCall | str,
        arguments: Mapping[str, Any] | None = None,
        consume_budget: bool = True,
    ) -> ValidationResult:
        """Validate a tool call against the fixed rules and schemas."""
        if isinstance(tool_call_or_name, ToolCall):
            tool_name = tool_call_or_name.tool_name
            args = dict(tool_call_or_name.arguments)
        else:
            tool_name = str(tool_call_or_name)
            args = dict(arguments or {})

        # 1. Budget constraint check
        if self.budget is not None and self.budget.is_exhausted():
            return ValidationResult(
                is_valid=False,
                error=(
                    f"Action budget exceeded: maximum {self.budget.max_actions} actions allowed "
                    f"({self.budget.used_actions} used)"
                ),
            )

        # 2. Allow-list and Registry checks
        is_known = self.registry.has(tool_name)
        is_allowed = tool_name in self.allowed_tool_names

        if not is_known and not is_allowed:
            return ValidationResult(
                is_valid=False,
                error=f"Unknown tool '{tool_name}' (operation not in {self.phase_name} allow-list)",
            )
        if is_known and not is_allowed:
            return ValidationResult(
                is_valid=False,
                error=f"Operation '{tool_name}' is not in the fixed {self.phase_name} tool allow-list",
            )
        if is_allowed and not is_known:
            return ValidationResult(
                is_valid=False,
                error=f"Unknown tool '{tool_name}' (tool definition missing from registry)",
            )

        tool = self.registry.get(tool_name)
        assert tool is not None

        # Verify tool identity against canonical definition
        canonical_tool = self.canonical_tools.get(tool_name)
        if canonical_tool is not None and tool is not canonical_tool:
            return ValidationResult(
                is_valid=False,
                error=f"Tool '{tool_name}' does not match the canonical {self.phase_name} definition",
            )

        # 3. Schema: check for missing required parameters
        for param_name, param in tool.parameters.items():
            if param.required and param_name not in args:
                return ValidationResult(
                    is_valid=False,
                    error=f"Missing required parameter '{param_name}' for tool '{tool_name}'",
                )

        # 4. Schema: check for unexpected parameters
        for arg_name in args:
            if arg_name not in tool.parameters:
                return ValidationResult(
                    is_valid=False,
                    error=f"Unexpected parameter '{arg_name}' for tool '{tool_name}'",
                )

        # 5. Schema: validate types and path boundaries
        resolved_paths: dict[str, Path] = {}

        for arg_name, arg_val in args.items():
            param = tool.parameters[arg_name]

            # Optional parameter with None value is allowed
            if not param.required and arg_val is None:
                continue

            # Strict type validation (explicitly separating bool from int)
            if param.type is int:
                if not isinstance(arg_val, int) or isinstance(arg_val, bool):
                    return ValidationResult(
                        is_valid=False,
                        error=f"Invalid parameter type for '{arg_name}': expected int, got {type(arg_val).__name__}",
                    )
            elif param.type is bool:
                if not isinstance(arg_val, bool):
                    return ValidationResult(
                        is_valid=False,
                        error=f"Invalid parameter type for '{arg_name}': expected bool, got {type(arg_val).__name__}",
                    )
            elif param.type is str:
                if not isinstance(arg_val, str):
                    return ValidationResult(
                        is_valid=False,
                        error=f"Invalid parameter type for '{arg_name}': expected str, got {type(arg_val).__name__}",
                    )
            elif not isinstance(arg_val, param.type):
                return ValidationResult(
                    is_valid=False,
                    error=f"Invalid parameter type for '{arg_name}': expected {param.type.__name__}, got {type(arg_val).__name__}",
                )

            # Workspace boundary validation for path parameters
            if param.is_path:
                is_in_ws, resolved_p, err = self._validate_workspace_path(
                    path_value=arg_val,
                    param_name=arg_name,
                    allow_root_dir=(tool_name in ("file_find", "process_run")),
                )
                if not is_in_ws or resolved_p is None:
                    return ValidationResult(is_valid=False, error=err)
                resolved_paths[arg_name] = resolved_p

        # 6. Resolve defaults for omitted optional path parameters
        for param_name, param in tool.parameters.items():
            if (
                (param_name not in args or args[param_name] is None)
                and param.is_path
                and param.default is not None
            ):
                is_in_ws, resolved_p, err = self._validate_workspace_path(
                    path_value=param.default,
                    param_name=param_name,
                    allow_root_dir=(tool_name in ("file_find", "process_run")),
                )
                if not is_in_ws or resolved_p is None:
                    return ValidationResult(is_valid=False, error=err)
                resolved_paths[param_name] = resolved_p

        # 7. Specific value constraint validation
        if tool_name == "file_read":
            start_line = args.get("start_line")
            end_line = args.get("end_line")
            if start_line is not None and start_line < 1:
                return ValidationResult(
                    is_valid=False,
                    error="Parameter 'start_line' must be greater than or equal to 1",
                )
            if end_line is not None and end_line < 1:
                return ValidationResult(
                    is_valid=False,
                    error="Parameter 'end_line' must be greater than or equal to 1",
                )
            if start_line is not None and end_line is not None and end_line < start_line:
                return ValidationResult(
                    is_valid=False,
                    error=f"Parameter 'end_line' ({end_line}) cannot be less than 'start_line' ({start_line})",
                )

        elif tool_name == "file_edit":
            target = args.get("target")
            if target is not None and len(target) == 0:
                return ValidationResult(
                    is_valid=False,
                    error="Parameter 'target' cannot be empty for file_edit",
                )

        elif tool_name == "process_run":
            timeout = args.get("timeout")
            if timeout is not None and timeout <= 0:
                return ValidationResult(
                    is_valid=False,
                    error=f"Parameter 'timeout' ({timeout}) must be greater than 0",
                )

        # 7. Consume action from budget if requested and validation passed
        if consume_budget and self.budget is not None:
            self.budget.record_action()

        return ValidationResult(
            is_valid=True,
            tool=tool,
            resolved_paths=resolved_paths,
        )

    def _validate_workspace_path(
        self,
        path_value: Any,
        param_name: str,
        allow_root_dir: bool = False,
    ) -> tuple[bool, Path | None, str | None]:
        """Verify that a path resolves strictly inside workspace_root."""
        if not isinstance(path_value, (str, Path)):
            return False, None, f"Path parameter '{param_name}' must be a string or Path"

        path_str = str(path_value).strip()
        if not path_str:
            return False, None, f"Path parameter '{param_name}' cannot be empty"

        raw_path = Path(path_str)

        # Resolve candidate
        if raw_path.is_absolute():
            candidate = raw_path.resolve()
        else:
            candidate = (self.workspace_root / raw_path).resolve()

        # Check containment within workspace
        try:
            candidate.relative_to(self.workspace_root)
        except ValueError:
            return False, None, f"Path '{path_str}' resolves outside workspace root '{self.workspace_root}'"

        # Prevent operating directly on the workspace root directory itself for file read/write/edit
        if candidate == self.workspace_root and not allow_root_dir:
            return (
                False,
                None,
                f"Path '{path_str}' points to the workspace root directory, not a target file",
            )

        return True, candidate, None


class Phase2ToolValidator(ToolValidator):
    """Phase 2 validator for tool calls.

    Permits Phase 1 tools plus explicitly declared Phase 2 tools (e.g. process_run).
    Shares the exact same deterministic boundary, schema, and path validation logic.
    """

    @property
    def phase_name(self) -> str:
        """Name of the operational phase enforced by this validator."""
        return "Phase 2"

    @property
    def allowed_tool_names(self) -> frozenset[str]:
        """Fixed allow-list of tool names permitted in Phase 2."""
        return frozenset(PHASE_1_TOOL_NAMES | PHASE_2_TOOL_NAMES)

    @property
    def canonical_tools(self) -> Mapping[str, ToolDefinition]:
        """Fixed canonical tool definitions for Phase 2."""
        return CANONICAL_ALL_TOOLS

    def __init__(
        self,
        workspace_root: str | Path,
        registry: ToolRegistry | None = None,
        budget: ActionBudget | None = None,
    ) -> None:
        super().__init__(
            workspace_root=workspace_root,
            registry=registry or get_phase_2_registry(),
            budget=budget,
        )

