"""Tests for Phase 2 controlled local process execution (process_run)."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from tessera.tools.interface import ToolCall, ToolResult
from tessera.tools.process import PROCESS_RUN_TOOL, handle_process_run
from tessera.tools.registry import ToolRegistry, get_default_registry
from tessera.tools.validator import ToolValidator


def test_process_run_success():
    """1. Successful command execution returns success=True, exit_code=0, and captured output."""
    result: ToolResult = handle_process_run(
        command=sys.executable,
        arguments=["-c", "print('hello from process_run')"],
    )
    assert result.success is True
    assert result.error is None
    assert isinstance(result.output, dict)
    assert result.output["exit_code"] == 0
    assert result.output["stdout"].strip() == "hello from process_run"
    assert result.output["stderr"] == ""
    assert result.output["timed_out"] is False


def test_process_run_stdout_capture():
    """2. Stdout capture correctly captures multi-line and raw standard output."""
    script = "import sys; sys.stdout.write('line1\\nline2\\n')"
    result: ToolResult = handle_process_run(
        command=sys.executable,
        arguments=["-c", script],
    )
    assert result.success is True
    assert result.output["exit_code"] == 0
    assert result.output["stdout"] == "line1\nline2\n"


def test_process_run_stderr_capture():
    """3. Stderr capture correctly captures standard error without hiding it."""
    script = "import sys; sys.stderr.write('warning: test error\\n')"
    result: ToolResult = handle_process_run(
        command=sys.executable,
        arguments=["-c", script],
    )
    assert result.success is True
    assert result.output["exit_code"] == 0
    assert result.output["stderr"] == "warning: test error\n"


def test_process_run_nonzero_exit():
    """4. Non-zero exit code is recorded, returns success=True, and is observable with exit_code/stderr."""
    script = "import sys; sys.stderr.write('fatal abort\\n'); sys.exit(42)"
    result: ToolResult = handle_process_run(
        command=sys.executable,
        arguments=["-c", script],
    )
    assert result.success is True
    assert result.output["exit_code"] == 42
    assert result.output["stderr"] == "fatal abort\n"
    assert result.output["timed_out"] is False
    assert result.error is None


def test_process_run_invalid_command_creation_failure():
    """5. Invalid command or non-existent binary returns success=False with clear error."""
    result: ToolResult = handle_process_run(
        command="non_existent_executable_tessera_987654",
        arguments=["--version"],
    )
    assert result.success is False
    assert result.output["exit_code"] is None
    assert result.output["timed_out"] is False
    assert result.error is not None
    assert "not found" in result.error.lower() or "failed" in result.error.lower()


def test_process_run_working_directory(tmp_path: Path):
    """6. Supplied working directory is verified and used as execution context."""
    sub_dir = tmp_path / "custom_workdir"
    sub_dir.mkdir()
    marker = sub_dir / "target_marker.txt"
    marker.write_text("found_marker", encoding="utf-8")

    # When executed with working_directory, relative file access resolves inside it
    script = "import os; print(os.path.exists('target_marker.txt'))"
    result: ToolResult = handle_process_run(
        command=sys.executable,
        arguments=["-c", script],
        working_directory=sub_dir,
    )
    assert result.success is True
    assert result.output["stdout"].strip() == "True"

    # Non-existent working directory fails cleanly
    bad_dir = tmp_path / "non_existent_directory"
    bad_result: ToolResult = handle_process_run(
        command=sys.executable,
        arguments=["-c", "print('should not run')"],
        working_directory=bad_dir,
    )
    assert bad_result.success is False
    assert "does not exist" in (bad_result.error or "")

    # Non-directory file supplied as working directory fails cleanly
    bad_file = tmp_path / "a_file.txt"
    bad_file.write_text("content", encoding="utf-8")
    file_as_dir_result: ToolResult = handle_process_run(
        command=sys.executable,
        arguments=["-c", "print('should not run')"],
        working_directory=bad_file,
    )
    assert file_as_dir_result.success is False
    assert "not a directory" in (file_as_dir_result.error or "")


def test_process_run_timeout():
    """7. Real timeout termination: process is killed, timed_out=True, success=False."""
    script = "import time; time.sleep(10)"
    result: ToolResult = handle_process_run(
        command=sys.executable,
        arguments=["-c", script],
        timeout=0.5,
    )
    assert result.success is False
    assert result.output["timed_out"] is True
    assert "timed out" in (result.error or "").lower()


def test_process_run_arguments_with_spaces_and_special_characters(tmp_path: Path):
    """8. Arguments with spaces and shell characters are passed directly without shell interpretation."""
    redirect_target = tmp_path / "redirect_leak.txt"
    script = "import sys; print(f'COUNT={len(sys.argv[1:])}'); print(f'ARGS={sys.argv[1:]}')"
    special_args = [
        "argument with spaces",
        "arg1&arg2;arg3|arg4",
        f">{redirect_target}",
        "\"quoted string\"",
    ]

    result: ToolResult = handle_process_run(
        command=sys.executable,
        arguments=["-c", script] + special_args,
        working_directory=tmp_path,
    )
    assert result.success is True
    assert result.output["exit_code"] == 0
    stdout = result.output["stdout"]
    assert "COUNT=4" in stdout
    # Ensure redirect character was NOT interpreted by a shell (file must not have been created)
    assert not redirect_target.exists()


def test_process_run_no_shell_execution_behavior():
    """9. Confirms no shell=True behavior: shell builtins and pipes fail as executables."""
    # Attempting to run a pipeline or shell operator as the executable name fails
    result: ToolResult = handle_process_run(
        command="echo hello && echo world",
        arguments=[],
    )
    assert result.success is False
    assert result.output["exit_code"] is None
    assert result.error is not None


def test_process_run_result_serializable():
    """10. ToolResult output dictionary is completely JSON-serializable."""
    # Test on success
    res_success = handle_process_run(
        command=sys.executable,
        arguments=["-c", "print('serializable')"],
    )
    serialized_success = json.dumps({
        "success": res_success.success,
        "output": res_success.output,
        "error": res_success.error,
    })
    assert "serializable" in serialized_success
    parsed = json.loads(serialized_success)
    assert parsed["success"] is True
    assert parsed["output"]["exit_code"] == 0
    assert parsed["output"]["timed_out"] is False

    # Test on failure
    res_fail = handle_process_run(
        command="invalid_command_xyz",
    )
    serialized_fail = json.dumps({
        "success": res_fail.success,
        "output": res_fail.output,
        "error": res_fail.error,
    })
    parsed_fail = json.loads(serialized_fail)
    assert parsed_fail["success"] is False
    assert parsed_fail["output"]["exit_code"] is None
    assert parsed_fail["output"]["timed_out"] is False


def test_process_run_tool_definition_and_schema():
    """11. PROCESS_RUN_TOOL conforms to ToolDefinition and produces valid schema."""
    assert PROCESS_RUN_TOOL.name == "process_run"
    assert "command" in PROCESS_RUN_TOOL.parameters
    assert "arguments" in PROCESS_RUN_TOOL.parameters
    assert "working_directory" in PROCESS_RUN_TOOL.parameters
    assert "timeout" in PROCESS_RUN_TOOL.parameters

    assert PROCESS_RUN_TOOL.parameters["command"].required is True
    assert PROCESS_RUN_TOOL.parameters["arguments"].required is False
    assert PROCESS_RUN_TOOL.parameters["working_directory"].required is False
    assert PROCESS_RUN_TOOL.parameters["timeout"].required is False

    schema = PROCESS_RUN_TOOL.to_schema()
    assert schema["name"] == "process_run"
    assert schema["parameters"]["type"] == "object"
    assert "command" in schema["parameters"]["properties"]
    assert "arguments" in schema["parameters"]["properties"]
    assert "working_directory" in schema["parameters"]["properties"]
    assert "timeout" in schema["parameters"]["properties"]
    assert schema["parameters"]["required"] == ["command"]

    # Test execution via ToolDefinition.execute()
    exec_result = PROCESS_RUN_TOOL.execute(
        command=sys.executable,
        arguments=["-c", "print('via execute')"],
    )
    assert exec_result.success is True
    assert exec_result.output["stdout"].strip() == "via execute"


def test_process_run_registration_in_registry():
    """12. PROCESS_RUN_TOOL can be registered in ToolRegistry according to existing architecture."""
    registry = get_default_registry()
    assert not registry.has("process_run")

    registry.register(PROCESS_RUN_TOOL)
    assert registry.has("process_run")
    assert registry.get("process_run") is PROCESS_RUN_TOOL
    assert "process_run" in registry.tool_names()


def test_phase_1_validator_rejects_process_run_seam_check(tmp_path: Path):
    """13. Phase 1 ToolValidator strictly rejects process_run, preserving Phase 1 security boundary."""
    registry = ToolRegistry(tools=[PROCESS_RUN_TOOL])
    validator = ToolValidator(workspace_root=tmp_path, registry=registry)

    call = ToolCall(
        tool_name="process_run",
        arguments={"command": sys.executable, "arguments": ["--version"]},
    )
    val_result = validator.validate(call)
    assert val_result.is_valid is False
    assert "Operation 'process_run' is not in the fixed Phase 1 tool allow-list" in (val_result.error or "")


def test_process_run_input_validation_guards():
    """14. Parameter validation rejects empty command, invalid argument types, and invalid timeouts."""
    # Empty command
    r1 = handle_process_run(command="   ")
    assert r1.success is False
    assert "Command must be a non-empty string" in (r1.error or "")

    # Non-string command
    r2 = handle_process_run(command=123)  # type: ignore
    assert r2.success is False
    assert "Command must be a non-empty string" in (r2.error or "")

    # Invalid arguments type
    r3 = handle_process_run(command=sys.executable, arguments="not a list")  # type: ignore
    assert r3.success is False
    assert "Arguments must be a list of strings" in (r3.error or "")

    # Non-string argument element
    r4 = handle_process_run(command=sys.executable, arguments=[1, 2, 3])  # type: ignore
    assert r4.success is False
    assert "Argument at index 0 must be a string" in (r4.error or "")

    # Invalid timeout type
    r5 = handle_process_run(command=sys.executable, timeout="not a number")  # type: ignore
    assert r5.success is False
    assert "Timeout must be a positive number" in (r5.error or "")

    # Negative timeout
    r6 = handle_process_run(command=sys.executable, timeout=-5)
    assert r6.success is False
    assert "Timeout must be greater than 0" in (r6.error or "")


def test_process_run_omitted_working_directory_uses_workspace_root(tmp_path: Path):
    """15. Omitted working_directory uses workspace_root as process cwd."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    marker = ws / "in_workspace.txt"
    marker.write_text("ws_marker_content", encoding="utf-8")

    script = "import os; print(os.path.exists('in_workspace.txt'))"
    result = handle_process_run(
        command=sys.executable,
        arguments=["-c", script],
        working_directory=None,
        workspace_root=ws,
    )
    assert result.success is True
    assert result.output["exit_code"] == 0
    assert result.output["stdout"].strip() == "True"


def test_process_run_relative_working_directory_resolves_beneath_workspace_root(tmp_path: Path):
    """16. Relative working_directory resolves beneath workspace_root."""
    ws = tmp_path / "workspace"
    sub = ws / "sub"
    sub.mkdir(parents=True)
    marker = sub / "in_sub.txt"
    marker.write_text("sub_marker", encoding="utf-8")

    script = "import os; print(os.path.exists('in_sub.txt'))"
    result = handle_process_run(
        command=sys.executable,
        arguments=["-c", script],
        working_directory="sub",
        workspace_root=ws,
    )
    assert result.success is True
    assert result.output["exit_code"] == 0
    assert result.output["stdout"].strip() == "True"

    # Traversal escaping workspace_root is rejected
    escape_result = handle_process_run(
        command=sys.executable,
        arguments=["-c", "print('should not run')"],
        working_directory="../outside",
        workspace_root=ws,
    )
    assert escape_result.success is False
    assert "resolves outside workspace root" in (escape_result.error or "")


def test_process_run_direct_standalone_invocation_retains_cwd_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """17. Direct standalone invocation without workspace_root retains cwd fallback."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "standalone_marker.txt").write_text("marker", encoding="utf-8")

    script = "import os; print(os.path.exists('standalone_marker.txt'))"
    result = handle_process_run(
        command=sys.executable,
        arguments=["-c", script],
        working_directory=None,
        workspace_root=None,
    )
    assert result.success is True
    assert result.output["exit_code"] == 0
    assert result.output["stdout"].strip() == "True"


def test_process_run_execution_context_integration(tmp_path: Path):
    """18. ToolDefinition.execute(context=...) supplies workspace_root to handle_process_run."""
    from tessera.tools.interface import ExecutionContext

    ws = tmp_path / "ws_ctx"
    ws.mkdir()
    (ws / "ctx_marker.txt").write_text("ctx_ok", encoding="utf-8")

    ctx = ExecutionContext(workspace_root=ws)
    script = "import os; print(os.path.exists('ctx_marker.txt'))"

    # Omitting working_directory in execute() forwards workspace_root from context
    res = PROCESS_RUN_TOOL.execute(
        context=ctx,
        command=sys.executable,
        arguments=["-c", script],
    )
    assert res.success is True
    assert res.output["exit_code"] == 0
    assert res.output["stdout"].strip() == "True"

