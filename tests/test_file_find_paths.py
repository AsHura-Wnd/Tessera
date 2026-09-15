"""Focused regression and interface tests for ExecutionContext and file_find workspace-relative paths.

Covers all required verification items:
A. ExecutionContext is frozen and contains exactly workspace_root.
B. ToolDefinition.execute(context=...) forwards workspace_root only to handlers that explicitly declare it.
C. Tools without workspace_root continue receiving their existing arguments unchanged.
D. Tool schema does not expose workspace_root.
E. Canonical ToolDefinition identity remains unchanged.
F. AgentLoop supplies the ExecutionContext during actual tool execution.
G. file_find(directory="logs/") returns "logs/auth_01.log".
H. A file_find result can be passed directly to file_read.
I. Deep directory paths remain workspace-relative (e.g. "storage/backups/2026/").
J. Existing file_find search semantics/security remain intact.
K. Direct handle_file_find(...) without workspace_root still behaves sensibly using its backward-compatible fallback.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import os
from pathlib import Path
import sys
from typing import Any, Sequence

import pytest

from tessera.agent.loop import AgentLoop, RunResult, RunStatus
from tessera.models.provider import ModelProvider, ProviderResult
from tessera.tools.authorization import CANONICAL_PHASE_1_TOOLS
from tessera.tools.builtins import (
    FILE_EDIT_TOOL,
    FILE_FIND_TOOL,
    FILE_READ_TOOL,
    FILE_WRITE_TOOL,
    handle_file_edit,
    handle_file_find,
    handle_file_read,
    handle_file_write,
)
from tessera.tools.interface import (
    ExecutionContext,
    ToolCall,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)
from tessera.tools.process import PROCESS_RUN_TOOL
from tessera.tools.registry import ToolRegistry, get_default_registry
from tessera.tools.validator import ToolValidator


class ScriptedModelProvider(ModelProvider):
    """Deterministic mock provider returning a canned sequence of ProviderResults."""

    def __init__(self, responses: Sequence[ProviderResult]) -> None:
        self.responses = list(responses)

    def generate(
        self,
        prompt: str,
        tools: Sequence[Any] | None = None,
        context: Sequence[Any] | None = None,
    ) -> ProviderResult:
        if not self.responses:
            raise RuntimeError("ScriptedModelProvider exhausted responses")
        return self.responses.pop(0)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def validator(workspace: Path) -> ToolValidator:
    return ToolValidator(workspace_root=workspace)


# ---------------------------------------------------------------------------
# Test A: ExecutionContext is frozen and contains exactly workspace_root
# ---------------------------------------------------------------------------
def test_execution_context_is_frozen_and_contains_exactly_workspace_root(workspace: Path) -> None:
    ctx = ExecutionContext(workspace_root=workspace)
    assert ctx.workspace_root == workspace
    assert isinstance(ctx.workspace_root, Path)

    # Contains exactly workspace_root
    ctx_fields = [f.name for f in fields(ExecutionContext)]
    assert ctx_fields == ["workspace_root"]

    # Frozen: cannot mutate or add attributes
    with pytest.raises(FrozenInstanceError):
        ctx.workspace_root = Path("/other")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        ctx.extra = "value"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Test B: ToolDefinition.execute(context=...) forwards workspace_root only to handlers that declare it
# ---------------------------------------------------------------------------
def test_tool_definition_execute_forwards_workspace_root_only_to_declaring_handlers(workspace: Path) -> None:
    received: dict[str, Any] = {}

    def declaring_handler(query: str, workspace_root: Path | None = None) -> ToolResult:
        received["query"] = query
        received["workspace_root"] = workspace_root
        return ToolResult(success=True, output=f"found:{query}")

    tool = ToolDefinition(
        name="declaring_tool",
        description="A tool that declares workspace_root",
        parameters={"query": ToolParameter(name="query", type=str, description="query string")},
        handler=declaring_handler,
    )

    ctx = ExecutionContext(workspace_root=workspace)

    # 1. Calling with context supplies workspace_root
    res = tool.execute(context=ctx, query="test_query")
    assert res.success is True
    assert received["query"] == "test_query"
    assert received["workspace_root"] == workspace

    # 2. Calling without context leaves workspace_root None
    received.clear()
    res_no_ctx = tool.execute(query="test_no_ctx")
    assert res_no_ctx.success is True
    assert received["query"] == "test_no_ctx"
    assert received["workspace_root"] is None


# ---------------------------------------------------------------------------
# Test C: Tools without workspace_root continue receiving their existing arguments unchanged
# ---------------------------------------------------------------------------
def test_tools_without_workspace_root_receive_arguments_unchanged(workspace: Path) -> None:
    test_file = workspace / "greeting.txt"
    test_file.write_text("Hello, world!", encoding="utf-8")

    ctx = ExecutionContext(workspace_root=workspace)

    # FILE_READ_TOOL does not declare workspace_root
    res_read = FILE_READ_TOOL.execute(context=ctx, path=test_file)
    assert res_read.success is True
    assert res_read.output == "Hello, world!"

    # FILE_WRITE_TOOL does not declare workspace_root
    out_file = workspace / "written.txt"
    res_write = FILE_WRITE_TOOL.execute(context=ctx, path=out_file, content="new data", overwrite=True)
    assert res_write.success is True
    assert out_file.read_text(encoding="utf-8") == "new data"

    # FILE_EDIT_TOOL does not declare workspace_root
    res_edit = FILE_EDIT_TOOL.execute(context=ctx, path=out_file, target="new", replacement="edited")
    assert res_edit.success is True
    assert out_file.read_text(encoding="utf-8") == "edited data"

    # PROCESS_RUN_TOOL does not declare workspace_root
    res_proc = PROCESS_RUN_TOOL.execute(context=ctx, command=sys.executable, arguments=["-c", "print('ok')"])
    assert res_proc.success is True
    assert res_proc.output["exit_code"] == 0


# ---------------------------------------------------------------------------
# Test D: Tool schema does not expose workspace_root
# ---------------------------------------------------------------------------
def test_tool_schema_does_not_expose_workspace_root() -> None:
    schema = FILE_FIND_TOOL.to_schema()
    props = schema["parameters"]["properties"]
    assert "workspace_root" not in props
    assert "context" not in props
    assert set(props.keys()) == {"pattern", "directory", "content_pattern"}


# ---------------------------------------------------------------------------
# Test E: Canonical ToolDefinition identity remains unchanged
# ---------------------------------------------------------------------------
def test_canonical_tool_definition_identity_remains_unchanged() -> None:
    default_reg = get_default_registry()
    assert default_reg.get("file_find") is FILE_FIND_TOOL
    assert default_reg.get("file_read") is FILE_READ_TOOL
    assert default_reg.get("file_write") is FILE_WRITE_TOOL
    assert default_reg.get("file_edit") is FILE_EDIT_TOOL

    assert CANONICAL_PHASE_1_TOOLS["file_find"] is FILE_FIND_TOOL
    assert CANONICAL_PHASE_1_TOOLS["file_read"] is FILE_READ_TOOL


# ---------------------------------------------------------------------------
# Test F: AgentLoop supplies ExecutionContext during actual tool execution
# ---------------------------------------------------------------------------
def test_agent_loop_supplies_execution_context_during_tool_execution(workspace: Path) -> None:
    logs_dir = workspace / "logs"
    logs_dir.mkdir()
    (logs_dir / "auth_01.log").write_text("token=secret123\n", encoding="utf-8")

    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call(
            tool_name="file_find",
            arguments={"directory": "logs", "pattern": "*.log"},
        ),
        ProviderResult.create_text(text="Discovery complete."),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        max_steps=5,
    )

    result = loop.run(goal="Find logs")
    assert result.status == RunStatus.TEXT
    assert result.last_tool_result is not None
    assert result.last_tool_result.success is True
    paths = [m["path"] for m in result.last_tool_result.output]
    assert paths == ["logs/auth_01.log"]


# ---------------------------------------------------------------------------
# Test G: file_find(directory="logs/") returns "logs/auth_01.log"
# ---------------------------------------------------------------------------
def test_file_find_with_directory_includes_directory_prefix(
    workspace: Path,
    validator: ToolValidator,
) -> None:
    logs_dir = workspace / "logs"
    logs_dir.mkdir()
    (logs_dir / "auth_01.log").write_text("session 1", encoding="utf-8")
    (logs_dir / "auth_02.log").write_text("session 2", encoding="utf-8")

    ctx = ExecutionContext(workspace_root=workspace)

    # 1. Direct handler call with trailing slash
    res_trailing = handle_file_find(directory="logs/", pattern="*", workspace_root=workspace)
    assert res_trailing.success is True
    paths_trailing = sorted([m["path"] for m in res_trailing.output])
    assert paths_trailing == ["logs/auth_01.log", "logs/auth_02.log"]

    # 2. Direct handler call without trailing slash
    res_no_slash = handle_file_find(directory="logs", pattern="*", workspace_root=workspace)
    assert res_no_slash.success is True
    paths_no_slash = sorted([m["path"] for m in res_no_slash.output])
    assert paths_no_slash == ["logs/auth_01.log", "logs/auth_02.log"]

    # 3. Via ToolValidator + ToolDefinition.execute(context=ctx)
    call = ToolCall("file_find", {"directory": "logs/", "pattern": "*"})
    val_res = validator.validate(call)
    assert val_res.is_valid is True
    exec_args = dict(call.arguments)
    exec_args.update(val_res.resolved_paths)
    exec_res = val_res.tool.execute(context=ctx, **exec_args)
    assert exec_res.success is True
    paths_exec = sorted([m["path"] for m in exec_res.output])
    assert paths_exec == ["logs/auth_01.log", "logs/auth_02.log"]


# ---------------------------------------------------------------------------
# Test H: A file_find result can be passed directly to file_read
# ---------------------------------------------------------------------------
def test_file_find_result_can_be_passed_directly_to_file_read(
    workspace: Path,
    validator: ToolValidator,
) -> None:
    logs_dir = workspace / "logs"
    logs_dir.mkdir()
    (logs_dir / "auth_01.log").write_text("CRITICAL_AUTH_FAILURE\n", encoding="utf-8")

    ctx = ExecutionContext(workspace_root=workspace)

    # 1. Discover via file_find
    find_call = ToolCall("file_find", {"directory": "logs", "pattern": "*.log"})
    val_find = validator.validate(find_call)
    assert val_find.is_valid is True
    find_args = dict(find_call.arguments)
    find_args.update(val_find.resolved_paths)
    res_find = val_find.tool.execute(context=ctx, **find_args)
    assert res_find.success is True
    assert len(res_find.output) == 1
    returned_path = res_find.output[0]["path"]
    assert returned_path == "logs/auth_01.log"

    # 2. Pass directly to file_read
    read_call = ToolCall("file_read", {"path": returned_path})
    val_read = validator.validate(read_call)
    assert val_read.is_valid is True
    read_args = dict(read_call.arguments)
    read_args.update(val_read.resolved_paths)
    res_read = val_read.tool.execute(context=ctx, **read_args)
    assert res_read.success is True
    assert res_read.output == "CRITICAL_AUTH_FAILURE\n"


# ---------------------------------------------------------------------------
# Test I: Deep directory paths remain workspace-relative
# ---------------------------------------------------------------------------
def test_file_find_with_deep_directory_includes_complete_prefix(
    workspace: Path,
    validator: ToolValidator,
) -> None:
    backup_dir = workspace / "storage" / "backups" / "2026"
    backup_dir.mkdir(parents=True)
    (backup_dir / "database.sqlite").write_text("SQLite data", encoding="utf-8")
    (backup_dir / "metadata.json").write_text('{"ver": 1}', encoding="utf-8")

    ctx = ExecutionContext(workspace_root=workspace)

    # 1. Direct handler call
    res = handle_file_find(directory="storage/backups/2026/", pattern="*", workspace_root=workspace)
    assert res.success is True
    paths = sorted([m["path"] for m in res.output])
    assert paths == [
        "storage/backups/2026/database.sqlite",
        "storage/backups/2026/metadata.json",
    ]

    # 2. Validated execution with context
    call = ToolCall("file_find", {"directory": "storage/backups/2026", "pattern": "*.sqlite"})
    val_res = validator.validate(call)
    assert val_res.is_valid is True
    exec_args = dict(call.arguments)
    exec_args.update(val_res.resolved_paths)
    exec_res = val_res.tool.execute(context=ctx, **exec_args)
    assert exec_res.success is True
    assert len(exec_res.output) == 1
    assert exec_res.output[0]["path"] == "storage/backups/2026/database.sqlite"


# ---------------------------------------------------------------------------
# Test J: Existing file_find search semantics and security remain intact
# ---------------------------------------------------------------------------
def test_file_find_search_semantics_and_security(
    workspace: Path,
    validator: ToolValidator,
) -> None:
    ctx = ExecutionContext(workspace_root=workspace)

    (workspace / "a.py").write_text("# match_token inside\n", encoding="utf-8")
    (workspace / "b.py").write_text("# non_matching\n", encoding="utf-8")

    # Regex search
    res = handle_file_find(
        directory=".",
        pattern="*.py",
        content_pattern="match_token",
        workspace_root=workspace,
    )
    assert res.success is True
    assert len(res.output) == 1
    assert res.output[0]["path"] == "a.py"
    assert res.output[0]["matches"][0]["line"] == "# match_token inside"

    # Traversal security check via validator
    escape_call = ToolCall("file_find", {"directory": "../outside", "pattern": "*"})
    val_escape = validator.validate(escape_call)
    assert val_escape.is_valid is False

    # Direct handler call attempting to escape workspace_root
    res_escape = handle_file_find(directory="../outside", pattern="*", workspace_root=workspace)
    assert res_escape.success is False
    assert "resolves outside workspace root" in (res_escape.error or "")


# ---------------------------------------------------------------------------
# Test K: Direct handle_file_find(...) without workspace_root falls back to cwd
# ---------------------------------------------------------------------------
def test_direct_handle_file_find_without_workspace_root_fallback(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Change working directory to workspace
    monkeypatch.chdir(workspace)

    (workspace / "test_file.txt").write_text("content", encoding="utf-8")
    (workspace / "sub").mkdir()
    (workspace / "sub" / "child.txt").write_text("child", encoding="utf-8")

    # Direct call with directory omitted and workspace_root=None
    res = handle_file_find(pattern="*.txt")
    assert res.success is True
    paths = sorted([m["path"] for m in res.output])
    assert paths == ["sub/child.txt", "test_file.txt"]

    # Direct call with relative subdirectory and workspace_root=None
    res_sub = handle_file_find(directory="sub", pattern="*.txt")
    assert res_sub.success is True
    assert len(res_sub.output) == 1
    assert res_sub.output[0]["path"] == "sub/child.txt"


# ---------------------------------------------------------------------------
# End-to-end regression tests reproducing FIND-04 and DO-05
# ---------------------------------------------------------------------------
def test_regression_reproduce_find04_resolution(
    workspace: Path,
) -> None:
    """Reproduces the exact FIND-04 sequence and verifies complete success."""
    logs_dir = workspace / "logs"
    logs_dir.mkdir()
    (logs_dir / "auth_01.log").write_text("INFO: Session 1 OK\n", encoding="utf-8")
    (logs_dir / "auth_02.log").write_text("WARNING: Retrying\n", encoding="utf-8")
    (logs_dir / "auth_03.log").write_text(
        "ERROR: CRITICAL_AUTH_FAILURE invalid root signature\nALERT: Terminated\n",
        encoding="utf-8",
    )
    (logs_dir / "auth_04.log").write_text("INFO: Healthcheck OK\n", encoding="utf-8")

    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call("file_find", {"directory": "logs", "pattern": "*.log"}),
        ProviderResult.create_tool_call("file_read", {"path": "logs/auth_01.log"}),
        ProviderResult.create_tool_call("file_read", {"path": "logs/auth_02.log"}),
        ProviderResult.create_tool_call("file_read", {"path": "logs/auth_03.log"}),
        ProviderResult.create_tool_call(
            "file_write",
            {"path": "culprit.txt", "content": "auth_03.log\n", "overwrite": True},
        ),
        ProviderResult.create_text(text="Found culprit: auth_03.log"),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        max_steps=10,
    )

    result = loop.run(goal="Find culprit log")
    assert result.status == RunStatus.TEXT
    assert (workspace / "culprit.txt").read_text(encoding="utf-8") == "auth_03.log\n"


def test_regression_reproduce_do05_resolution(
    workspace: Path,
) -> None:
    """Reproduces the exact DO-05 sequence and verifies complete success."""
    migrations_dir = workspace / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "migration_v1.log").write_text("Migration v1\n", encoding="utf-8")
    (migrations_dir / "migration_v2_final.log").write_text(
        "AUTH_TOKEN=tok_sec_9876543210_xyz\n",
        encoding="utf-8",
    )

    config_dir = workspace / "config"
    config_dir.mkdir()
    config_file = config_dir / "security.json"
    config_file.write_text('{"db_token": "UNCONFIGURED"}\n', encoding="utf-8")

    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call("file_find", {"directory": "migrations", "pattern": "migration_*.log"}),
        ProviderResult.create_tool_call("file_read", {"path": "migrations/migration_v2_final.log"}),
        ProviderResult.create_tool_call(
            "file_edit",
            {
                "path": "config/security.json",
                "target": '"db_token": "UNCONFIGURED"',
                "replacement": '"db_token": "tok_sec_9876543210_xyz"',
            },
        ),
        ProviderResult.create_text(text="Updated token in security.json"),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        max_steps=10,
    )

    result = loop.run(goal="Update security token")
    assert result.status == RunStatus.TEXT
    assert '"db_token": "tok_sec_9876543210_xyz"' in config_file.read_text(encoding="utf-8")
