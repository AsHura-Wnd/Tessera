"""Controlled local process execution tool for Phase 2."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any, Sequence

from tessera.tools.interface import ToolDefinition, ToolParameter, ToolResult


def handle_process_run(
    command: str,
    arguments: Sequence[str] | None = None,
    working_directory: str | Path | None = None,
    timeout: int | float | None = 30,
) -> ToolResult:
    """Execute a local process with explicit arguments, optional working directory, and timeout.

    This primitive enforces:
    - Explicit command and arguments list (no shell=True)
    - Optional working directory validation
    - Real timeout enforcement and process termination
    - Structured capture of exit code, stdout, stderr, and timeout status
    - Completely serializable result shape
    """
    # 1. Validate command parameter
    if not isinstance(command, str) or not command.strip():
        return ToolResult(
            success=False,
            output={
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
            },
            error="Command must be a non-empty string",
        )

    # 2. Validate arguments parameter
    if arguments is None:
        args_list: list[str] = []
    elif isinstance(arguments, (list, tuple)):
        for i, arg in enumerate(arguments):
            if not isinstance(arg, str):
                return ToolResult(
                    success=False,
                    output={
                        "exit_code": None,
                        "stdout": "",
                        "stderr": "",
                        "timed_out": False,
                    },
                    error=f"Argument at index {i} must be a string, got {type(arg).__name__}",
                )
        args_list = list(arguments)
    else:
        return ToolResult(
            success=False,
            output={
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
            },
            error=f"Arguments must be a list of strings, got {type(arguments).__name__}",
        )

    # 3. Validate working directory parameter
    cwd: str | None = None
    if working_directory is not None:
        if not isinstance(working_directory, (str, Path)):
            return ToolResult(
                success=False,
                output={
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                },
                error=f"Working directory must be a string or Path, got {type(working_directory).__name__}",
            )
        wd_str = str(working_directory).strip()
        if not wd_str:
            return ToolResult(
                success=False,
                output={
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                },
                error="Working directory cannot be an empty string",
            )
        resolved_wd = Path(wd_str).resolve()
        if not resolved_wd.exists():
            return ToolResult(
                success=False,
                output={
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                },
                error=f"Working directory does not exist: '{resolved_wd}'",
            )
        if not resolved_wd.is_dir():
            return ToolResult(
                success=False,
                output={
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                },
                error=f"Working directory is not a directory: '{resolved_wd}'",
            )
        cwd = str(resolved_wd)

    # 4. Validate timeout parameter
    if timeout is None:
        effective_timeout: float = 30.0
    elif isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        return ToolResult(
            success=False,
            output={
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
            },
            error=f"Timeout must be a positive number, got {type(timeout).__name__}",
        )
    elif timeout <= 0:
        return ToolResult(
            success=False,
            output={
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
            },
            error=f"Timeout must be greater than 0, got {timeout}",
        )
    else:
        effective_timeout = float(timeout)

    # 5. Spawn child process (explicit shell=False)
    cmd = [command] + args_list
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            shell=False,
        )
    except FileNotFoundError as exc:
        return ToolResult(
            success=False,
            output={
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
            },
            error=f"Executable not found: '{command}' ({exc})",
        )
    except PermissionError as exc:
        return ToolResult(
            success=False,
            output={
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
            },
            error=f"Permission denied executing '{command}': {exc}",
        )
    except OSError as exc:
        return ToolResult(
            success=False,
            output={
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
            },
            error=f"Process execution failed for '{command}': {exc}",
        )

    # 6. Communicate and handle timeout
    try:
        stdout, stderr = proc.communicate(timeout=effective_timeout)
        exit_code = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            proc.kill()
        except (ProcessLookupError, OSError):
            pass
        try:
            stdout, stderr = proc.communicate(timeout=5.0)
        except Exception:
            stdout = ""
            stderr = ""
        exit_code = proc.returncode

    stdout_str = stdout if stdout is not None else ""
    stderr_str = stderr if stderr is not None else ""

    if timed_out:
        return ToolResult(
            success=False,
            output={
                "exit_code": exit_code,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "timed_out": True,
            },
            error=f"Process timed out after {effective_timeout} seconds",
        )

    if exit_code != 0:
        return ToolResult(
            success=False,
            output={
                "exit_code": exit_code,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "timed_out": False,
            },
            error=f"Process exited with non-zero exit code: {exit_code}",
        )

    return ToolResult(
        success=True,
        output={
            "exit_code": 0,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "timed_out": False,
        },
        error=None,
    )


PROCESS_RUN_TOOL = ToolDefinition(
    name="process_run",
    description="Execute a local process with explicit command and argument list.",
    parameters={
        "command": ToolParameter(
            name="command",
            type=str,
            description="The executable command or program to run.",
            required=True,
        ),
        "arguments": ToolParameter(
            name="arguments",
            type=list,
            description="List of string arguments passed directly to the executable.",
            required=False,
            default=None,
        ),
        "working_directory": ToolParameter(
            name="working_directory",
            type=str,
            description="Optional working directory path from which to execute the process.",
            required=False,
            default=None,
            is_path=True,
        ),
        "timeout": ToolParameter(
            name="timeout",
            type=int,
            description="Execution timeout in seconds (default: 30).",
            required=False,
            default=30,
        ),
    },
    handler=handle_process_run,
)
