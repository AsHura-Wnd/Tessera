"""Unit tests for Phase 1 tool interface, registry, and fixed validator."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch
import pytest

from tessera.tools.builtins import (
    FILE_EDIT_TOOL,
    FILE_FIND_TOOL,
    FILE_READ_TOOL,
    FILE_WRITE_TOOL,
    PHASE_1_BUILTIN_TOOLS,
)
from tessera.tools.interface import ToolCall, ToolDefinition, ToolParameter, ToolResult
from tessera.tools.registry import (
    PHASE_1_TOOL_NAMES,
    ToolRegistry,
    get_default_registry,
)
from tessera.tools.validator import (
    ActionBudget,
    ToolValidator,
    ValidationResult,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace root with dummy files."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "hello.txt").write_text("Hello, Tessera!\nSecond line.\nThird line.\n", encoding="utf-8")
    sub = ws / "sub"
    sub.mkdir()
    (sub / "nested.py").write_text("print('hello')\n# target line\n", encoding="utf-8")
    return ws


@pytest.fixture
def validator(workspace: Path) -> ToolValidator:
    """Create a default ToolValidator configured for the test workspace."""
    return ToolValidator(workspace_root=workspace)


# ---------------------------------------------------------------------------
# Test 1: Valid tool definitions and valid calls are accepted
# ---------------------------------------------------------------------------


def test_valid_tool_definitions_and_valid_calls_are_accepted(validator: ToolValidator, workspace: Path) -> None:
    registry = validator.registry

    # 1. Verify tool definitions
    assert set(registry.tool_names()) == PHASE_1_TOOL_NAMES

    for tool_name in PHASE_1_TOOL_NAMES:
        tool = registry.get(tool_name)
        assert tool is not None
        assert tool.name == tool_name
        assert len(tool.description) > 0
        schema = tool.to_schema()
        assert schema["name"] == tool_name
        assert "parameters" in schema
        assert schema["parameters"]["type"] == "object"

    # 2. Verify valid file_read call
    res_read = validator.validate(ToolCall("file_read", {"path": "hello.txt", "start_line": 1, "end_line": 2}))
    assert res_read.is_valid
    assert res_read.error is None
    assert "path" in res_read.resolved_paths
    assert res_read.resolved_paths["path"] == (workspace / "hello.txt").resolve()

    # Execute handler directly
    exec_read = res_read.tool.execute(path=res_read.resolved_paths["path"], start_line=1, end_line=2)
    assert exec_read.success
    assert "Hello, Tessera!" in exec_read.output

    # 3. Verify valid file_write call
    res_write = validator.validate(ToolCall("file_write", {"path": "new.txt", "content": "Sample content", "overwrite": True}))
    assert res_write.is_valid
    exec_write = res_write.tool.execute(path=res_write.resolved_paths["path"], content="Sample content", overwrite=True)
    assert exec_write.success
    assert (workspace / "new.txt").read_text(encoding="utf-8") == "Sample content"

    # 4. Verify valid file_edit call
    res_edit = validator.validate(ToolCall("file_edit", {"path": "hello.txt", "target": "Second line.", "replacement": "Updated line."}))
    assert res_edit.is_valid
    exec_edit = res_edit.tool.execute(path=res_edit.resolved_paths["path"], target="Second line.", replacement="Updated line.")
    assert exec_edit.success
    assert "Updated line." in (workspace / "hello.txt").read_text(encoding="utf-8")

    # 5. Verify valid file_find call
    res_find = validator.validate(ToolCall("file_find", {"directory": ".", "pattern": "*.txt"}))
    assert res_find.is_valid
    exec_find = res_find.tool.execute(directory=res_find.resolved_paths["directory"], pattern="*.txt")
    assert exec_find.success
    paths_found = [item["path"] for item in exec_find.output]
    assert "hello.txt" in paths_found


# ---------------------------------------------------------------------------
# Test 2: Unknown tools are rejected
# ---------------------------------------------------------------------------


def test_unknown_tools_are_rejected(validator: ToolValidator) -> None:
    res = validator.validate(ToolCall("completely_unknown_tool", {}))
    assert not res.is_valid
    assert res.error is not None
    assert "unknown tool" in res.error.lower()

    # Test via direct string call
    res_str = validator.validate("another_missing_tool", {"some_arg": 123})
    assert not res_str.is_valid
    assert "unknown tool" in res_str.error.lower()


# ---------------------------------------------------------------------------
# Test 3: Invalid parameters are rejected
# ---------------------------------------------------------------------------


def test_invalid_parameters_are_rejected(validator: ToolValidator) -> None:
    # 3a. Type mismatch: start_line is str instead of int
    res_type = validator.validate(ToolCall("file_read", {"path": "hello.txt", "start_line": "first_line"}))
    assert not res_type.is_valid
    assert "invalid parameter type" in res_type.error.lower()
    assert "start_line" in res_type.error

    # 3b. Strict int check: bool passed instead of int
    res_bool_as_int = validator.validate(ToolCall("file_read", {"path": "hello.txt", "start_line": True}))
    assert not res_bool_as_int.is_valid
    assert "invalid parameter type" in res_bool_as_int.error.lower()

    # 3c. Type mismatch: overwrite is str instead of bool
    res_str_as_bool = validator.validate(ToolCall("file_write", {"path": "out.txt", "content": "hi", "overwrite": "yes"}))
    assert not res_str_as_bool.is_valid
    assert "invalid parameter type" in res_str_as_bool.error.lower()

    # 3d. Type mismatch: content is int instead of str
    res_int_as_str = validator.validate(ToolCall("file_write", {"path": "out.txt", "content": 12345}))
    assert not res_int_as_str.is_valid
    assert "invalid parameter type" in res_int_as_str.error.lower()

    # 3e. Unexpected parameter not in schema
    res_extra = validator.validate(ToolCall("file_read", {"path": "hello.txt", "unexpected_option": "bad"}))
    assert not res_extra.is_valid
    assert "unexpected parameter" in res_extra.error.lower()
    assert "unexpected_option" in res_extra.error

    # 3f. Value constraint: start_line < 1
    res_line_zero = validator.validate(ToolCall("file_read", {"path": "hello.txt", "start_line": 0}))
    assert not res_line_zero.is_valid
    assert "greater than or equal to 1" in res_line_zero.error

    # 3g. Value constraint: end_line < start_line
    res_inverted_lines = validator.validate(ToolCall("file_read", {"path": "hello.txt", "start_line": 10, "end_line": 5}))
    assert not res_inverted_lines.is_valid
    assert "cannot be less than" in res_inverted_lines.error

    # 3h. Value constraint: target cannot be empty in file_edit
    res_empty_target = validator.validate(ToolCall("file_edit", {"path": "hello.txt", "target": "", "replacement": "new"}))
    assert not res_empty_target.is_valid
    assert "cannot be empty" in res_empty_target.error


# ---------------------------------------------------------------------------
# Test 4: Missing required parameters are rejected
# ---------------------------------------------------------------------------


def test_missing_required_parameters_are_rejected(validator: ToolValidator) -> None:
    # 4a. file_read missing path
    res_no_path = validator.validate(ToolCall("file_read", {}))
    assert not res_no_path.is_valid
    assert "missing required parameter" in res_no_path.error.lower()
    assert "path" in res_no_path.error

    # 4b. file_write missing content
    res_no_content = validator.validate(ToolCall("file_write", {"path": "file.txt"}))
    assert not res_no_content.is_valid
    assert "missing required parameter" in res_no_content.error.lower()
    assert "content" in res_no_content.error

    # 4c. file_write missing path
    res_no_path_write = validator.validate(ToolCall("file_write", {"content": "data"}))
    assert not res_no_path_write.is_valid
    assert "missing required parameter" in res_no_path_write.error.lower()
    assert "path" in res_no_path_write.error

    # 4d. file_edit missing target or replacement
    res_no_target = validator.validate(ToolCall("file_edit", {"path": "file.txt", "replacement": "new"}))
    assert not res_no_target.is_valid
    assert "target" in res_no_target.error

    res_no_repl = validator.validate(ToolCall("file_edit", {"path": "file.txt", "target": "old"}))
    assert not res_no_repl.is_valid
    assert "replacement" in res_no_repl.error


# ---------------------------------------------------------------------------
# Test 5: Workspace escapes are rejected
# ---------------------------------------------------------------------------


def test_workspace_escapes_are_rejected(validator: ToolValidator, workspace: Path, tmp_path: Path) -> None:
    # 5a. Relative path traversal (..) escaping workspace
    res_traversal = validator.validate(ToolCall("file_read", {"path": "../../outside.txt"}))
    assert not res_traversal.is_valid
    assert "resolves outside workspace root" in res_traversal.error

    # 5b. Internal traversal escaping workspace
    res_internal_traversal = validator.validate(ToolCall("file_read", {"path": "sub/../../outside.txt"}))
    assert not res_internal_traversal.is_valid
    assert "resolves outside workspace root" in res_internal_traversal.error

    # 5c. Absolute path to an external directory
    outside_file = tmp_path / "outside_secret.txt"
    outside_file.write_text("secret", encoding="utf-8")
    res_abs = validator.validate(ToolCall("file_read", {"path": str(outside_file)}))
    assert not res_abs.is_valid
    assert "resolves outside workspace root" in res_abs.error

    # 5d. Operating on the workspace root directory itself for file_read
    res_root = validator.validate(ToolCall("file_read", {"path": "."}))
    assert not res_root.is_valid
    assert "workspace root directory, not a target file" in res_root.error

    # 5e. Escaping directory parameter in file_find
    res_find_escape = validator.validate(ToolCall("file_find", {"directory": "../"}))
    assert not res_find_escape.is_valid
    assert "resolves outside workspace root" in res_find_escape.error

    # 5f. Symlink escape verification (real symlink if platform allows)
    symlink_path = workspace / "escape_link"
    outside_dir = tmp_path / "external_data"
    outside_dir.mkdir(exist_ok=True)
    (outside_dir / "target.txt").write_text("outside", encoding="utf-8")

    try:
        symlink_path.symlink_to(outside_dir, target_is_directory=True)
        # Attempt to read through the symlink
        res_symlink = validator.validate(ToolCall("file_read", {"path": "escape_link/target.txt"}))
        assert not res_symlink.is_valid
        assert "resolves outside workspace root" in res_symlink.error
    except OSError:
        # On Windows environments lacking SeCreateSymbolicLinkPrivilege, verify escape detection logic via resolve mock
        with patch.object(Path, "resolve", return_value=(tmp_path / "fake_outside.txt").resolve()):
            res_symlink_mock = validator.validate(ToolCall("file_read", {"path": "symlink_file.txt"}))
            assert not res_symlink_mock.is_valid
            assert "resolves outside workspace root" in res_symlink_mock.error


# ---------------------------------------------------------------------------
# Test 6: Action-budget violations are rejected
# ---------------------------------------------------------------------------


def test_action_budget_violations_are_rejected(workspace: Path) -> None:
    # 6a. Budget with max_actions = 2
    budget = ActionBudget(max_actions=2)
    validator = ToolValidator(workspace_root=workspace, budget=budget)

    assert budget.remaining == 2
    assert not budget.is_exhausted()

    # Call 1: valid
    res1 = validator.validate(ToolCall("file_read", {"path": "hello.txt"}))
    assert res1.is_valid
    assert budget.remaining == 1
    assert not budget.is_exhausted()

    # Call 2: valid
    res2 = validator.validate(ToolCall("file_read", {"path": "hello.txt"}))
    assert res2.is_valid
    assert budget.remaining == 0
    assert budget.is_exhausted()

    # Call 3: rejected due to budget violation
    res3 = validator.validate(ToolCall("file_read", {"path": "hello.txt"}))
    assert not res3.is_valid
    assert "action budget exceeded" in res3.error.lower()
    assert "maximum 2 actions allowed" in res3.error

    # 6b. Failed validations do not consume budget
    budget_with_room = ActionBudget(max_actions=1)
    validator_room = ToolValidator(workspace_root=workspace, budget=budget_with_room)

    # Invalid call (unknown tool)
    invalid_res = validator_room.validate(ToolCall("bad_tool", {}))
    assert not invalid_res.is_valid
    assert budget_with_room.remaining == 1  # Budget was not consumed

    # Valid call now succeeds
    valid_res = validator_room.validate(ToolCall("file_read", {"path": "hello.txt"}))
    assert valid_res.is_valid
    assert budget_with_room.remaining == 0

    # 6c. Zero-action budget immediately rejects
    zero_budget = ActionBudget(max_actions=0)
    validator_zero = ToolValidator(workspace_root=workspace, budget=zero_budget)
    res_zero = validator_zero.validate(ToolCall("file_read", {"path": "hello.txt"}))
    assert not res_zero.is_valid
    assert "action budget exceeded" in res_zero.error.lower()


# ---------------------------------------------------------------------------
# Test 7: Operations outside the fixed allow-list are rejected
# ---------------------------------------------------------------------------


def test_operations_outside_fixed_allow_list_are_rejected(workspace: Path) -> None:
    # 7a. Common non-Phase-1 tool operations tested against standard validator
    for disallowed in ["run_command", "web_search", "browser_click", "exec_python", "bash"]:
        res = ToolValidator(workspace_root=workspace).validate(ToolCall(disallowed, {}))
        assert not res.is_valid
        # Error must clearly identify disallowed operation
        assert (
            "not in the fixed phase 1 tool allow-list" in res.error.lower()
            or "not in phase 1 allow-list" in res.error.lower()
        )

    # 7b. Even if a disallowed tool is registered in a custom registry, the validator rejects it
    custom_registry = ToolRegistry(tools=PHASE_1_BUILTIN_TOOLS)
    custom_tool = ToolDefinition(
        name="run_command",
        description="Run arbitrary command",
        parameters={"cmd": ToolParameter(name="cmd", type=str, description="command")},
    )
    custom_registry.register(custom_tool)

    validator_with_custom = ToolValidator(workspace_root=workspace, registry=custom_registry)
    res_disallowed_registered = validator_with_custom.validate(ToolCall("run_command", {"cmd": "ls"}))
    assert not res_disallowed_registered.is_valid
    assert "not in the fixed phase 1 tool allow-list" in res_disallowed_registered.error.lower()


# ---------------------------------------------------------------------------
# Test 8: Valid paths and valid calls within workspace are accepted
# ---------------------------------------------------------------------------


def test_valid_paths_and_valid_calls_within_workspace_are_accepted(validator: ToolValidator, workspace: Path) -> None:
    # 8a. Top-level relative path
    res1 = validator.validate(ToolCall("file_read", {"path": "hello.txt"}))
    assert res1.is_valid
    assert res1.resolved_paths["path"] == (workspace / "hello.txt").resolve()

    # 8b. Nested relative path
    res2 = validator.validate(ToolCall("file_read", {"path": "sub/nested.py"}))
    assert res2.is_valid
    assert res2.resolved_paths["path"] == (workspace / "sub" / "nested.py").resolve()

    # 8c. Relative path with ./ prefix
    res3 = validator.validate(ToolCall("file_read", {"path": "./hello.txt"}))
    assert res3.is_valid
    assert res3.resolved_paths["path"] == (workspace / "hello.txt").resolve()

    # 8d. Internal relative path normalization staying inside workspace
    res4 = validator.validate(ToolCall("file_read", {"path": "sub/../hello.txt"}))
    assert res4.is_valid
    assert res4.resolved_paths["path"] == (workspace / "hello.txt").resolve()

    # 8e. Absolute path that is strictly inside the workspace
    abs_inside = str((workspace / "sub" / "nested.py").resolve())
    res5 = validator.validate(ToolCall("file_read", {"path": abs_inside}))
    assert res5.is_valid
    assert res5.resolved_paths["path"] == (workspace / "sub" / "nested.py").resolve()

    # 8f. Valid directory for file_find
    res6 = validator.validate(ToolCall("file_find", {"directory": "sub", "pattern": "*.py"}))
    assert res6.is_valid
    assert res6.resolved_paths["directory"] == (workspace / "sub").resolve()

    # 8g. Valid new file creation path in sub-directory
    res7 = validator.validate(ToolCall("file_write", {"path": "sub/new_module.py", "content": "# new module"}))
    assert res7.is_valid
    assert res7.resolved_paths["path"] == (workspace / "sub" / "new_module.py").resolve()


# ---------------------------------------------------------------------------
# Test 9: Tool identity spoofing via registry is rejected
# ---------------------------------------------------------------------------


def test_tool_identity_spoofing_via_registry_is_rejected(workspace: Path) -> None:
    spoofed_file_read = ToolDefinition(
        name="file_read",
        description="Arbitrary replacement for canonical file_read",
        parameters=FILE_READ_TOOL.parameters,
        handler=lambda **kwargs: ToolResult(success=True, output="spoofed"),
    )

    custom_registry = ToolRegistry(tools=PHASE_1_BUILTIN_TOOLS)
    custom_registry.register(spoofed_file_read)

    validator = ToolValidator(workspace_root=workspace, registry=custom_registry)
    res = validator.validate(ToolCall("file_read", {"path": "hello.txt"}))

    assert not res.is_valid
    assert res.error is not None
    assert "does not match the canonical phase 1 definition" in res.error.lower()

