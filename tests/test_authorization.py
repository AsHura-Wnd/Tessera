"""Tests for Phase 2 Tool Authorization and Execution Seam.

Covers all 10 required verification points:
1. Phase 1 tools still validate exactly as before.
2. Phase 1 validator still rejects process_run.
3. process_run is recognized as an explicitly authorized Phase 2 capability.
4. A valid Phase 2 process_run can pass through the intended validation/authorization seam.
5. Unauthorized/unknown tools cannot execute.
6. Execution strictly occurs only after successful validation and authorization.
7. Canonical tool identity is preserved across the new seam.
8. process_run failure propagates as a structured ToolResult.
9. process_run timeout propagates correctly through the seam.
10. Full suite interoperability and deterministic isolation.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
from unittest.mock import MagicMock

import pytest

from tessera.agent.loop import AgentLoop, RunResult, RunStatus
from tessera.models.provider import ModelProvider, ProviderResult
from tessera.storage.trajectory import TrajectoryRecorder
from tessera.tools.authorization import (
    CANONICAL_ALL_TOOLS,
    CANONICAL_PHASE_1_TOOLS,
    CANONICAL_PHASE_2_TOOLS,
    AuthorizationResult,
    ExecutionPhase,
    PHASE_2_TOOL_NAMES,
    ToolAuthorizer,
    get_phase_1_authorizer,
    get_phase_2_authorizer,
)
from tessera.tools.builtins import PHASE_1_BUILTIN_TOOLS
from tessera.tools.interface import ToolCall, ToolDefinition, ToolParameter, ToolResult
from tessera.tools.process import PROCESS_RUN_TOOL
from tessera.tools.registry import (
    PHASE_1_TOOL_NAMES,
    ToolRegistry,
    get_default_registry,
    get_phase_2_registry,
)
from tessera.tools.validator import (
    Phase2ToolValidator,
    ToolValidator,
    ValidationResult,
)


class ScriptedModelProvider(ModelProvider):
    """Deterministic mock provider returning a canned sequence of ProviderResults."""

    def __init__(self, responses: Sequence[ProviderResult]) -> None:
        self.responses = list(responses)
        self.call_history: list[dict[str, Any]] = []

    def generate(
        self,
        prompt: str,
        tools: Sequence[Mapping[str, Any]] | None = None,
        context: Sequence[Mapping[str, Any]] | None = None,
    ) -> ProviderResult:
        self.call_history.append({
            "prompt": prompt,
            "tools": tools,
            "context": context,
        })
        if not self.responses:
            raise RuntimeError("ScriptedModelProvider exhausted configured responses")
        return self.responses.pop(0)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "output"
    out.mkdir()
    return out


# ---------------------------------------------------------------------------
# 1. Phase 1 tools still validate exactly as before
# ---------------------------------------------------------------------------
def test_phase_1_tools_validate_as_before(workspace: Path) -> None:
    validator = ToolValidator(workspace_root=workspace)
    authorizer = get_phase_1_authorizer()

    # file_write
    res_write = validator.validate(
        ToolCall("file_write", {"path": "a.txt", "content": "hello", "overwrite": True})
    )
    assert res_write.is_valid is True
    auth_write = authorizer.authorize("file_write", res_write.tool)
    assert auth_write.is_authorized is True

    # Execute write so file exists for read/edit
    assert res_write.tool is not None
    res_write.tool.execute(
        path=res_write.resolved_paths["path"], content="hello", overwrite=True
    )

    # file_read
    res_read = validator.validate(ToolCall("file_read", {"path": "a.txt"}))
    assert res_read.is_valid is True
    auth_read = authorizer.authorize("file_read", res_read.tool)
    assert auth_read.is_authorized is True

    # file_edit
    res_edit = validator.validate(
        ToolCall("file_edit", {"path": "a.txt", "target": "hello", "replacement": "world"})
    )
    assert res_edit.is_valid is True
    auth_edit = authorizer.authorize("file_edit", res_edit.tool)
    assert auth_edit.is_authorized is True

    # file_find
    res_find = validator.validate(ToolCall("file_find", {"directory": "."}))
    assert res_find.is_valid is True
    auth_find = authorizer.authorize("file_find", res_find.tool)
    assert auth_find.is_authorized is True


# ---------------------------------------------------------------------------
# 2. Phase 1 validator still rejects process_run
# ---------------------------------------------------------------------------
def test_phase_1_validator_rejects_process_run(workspace: Path) -> None:
    # Default validator (with default Phase 1 registry)
    validator = ToolValidator(workspace_root=workspace)
    res = validator.validate(
        ToolCall("process_run", {"command": sys.executable, "arguments": ["-c", "print(1)"]})
    )
    assert res.is_valid is False
    assert "not in Phase 1 allow-list" in str(res.error)

    # Validator explicitly given Phase 2 registry: still rejected by Phase 1 allow-list!
    validator_with_p2_reg = ToolValidator(
        workspace_root=workspace,
        registry=get_phase_2_registry(),
    )
    res_p2_reg = validator_with_p2_reg.validate(
        ToolCall("process_run", {"command": sys.executable, "arguments": ["-c", "print(1)"]})
    )
    assert res_p2_reg.is_valid is False
    assert "Operation 'process_run' is not in the fixed Phase 1 tool allow-list" in str(
        res_p2_reg.error
    )

    # Phase 1 authorizer also rejects process_run
    p1_authorizer = get_phase_1_authorizer()
    auth_res = p1_authorizer.authorize("process_run", PROCESS_RUN_TOOL)
    assert auth_res.is_authorized is False
    assert "Phase 2 tool and is not authorized in Phase 1" in str(auth_res.error)


# ---------------------------------------------------------------------------
# 3. process_run is recognized as an explicitly authorized Phase 2 capability
# ---------------------------------------------------------------------------
def test_process_run_recognized_as_authorized_phase_2_capability() -> None:
    assert "process_run" in PHASE_2_TOOL_NAMES
    assert "process_run" not in PHASE_1_TOOL_NAMES

    authorizer = get_phase_2_authorizer()
    assert authorizer.phase == ExecutionPhase.PHASE_2

    # process_run is authorized
    auth_res = authorizer.authorize("process_run", PROCESS_RUN_TOOL)
    assert auth_res.is_authorized is True
    assert auth_res.phase == ExecutionPhase.PHASE_2
    assert auth_res.error is None

    # Phase 1 tools are also authorized under Phase 2 authorizer
    for p1_name in PHASE_1_TOOL_NAMES:
        canonical_p1 = CANONICAL_PHASE_1_TOOLS[p1_name]
        assert authorizer.authorize(p1_name, canonical_p1).is_authorized is True


# ---------------------------------------------------------------------------
# 4. Valid Phase 2 process_run can pass through validation/authorization seam
# ---------------------------------------------------------------------------
def test_valid_phase_2_process_run_passes_seam_and_executes(
    workspace: Path,
    output_dir: Path,
) -> None:
    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={
                "command": sys.executable,
                "arguments": ["-c", "print('hello from seam')"],
                "working_directory": ".",
            },
        ),
        ProviderResult.create_text(text="Process completed."),
    ])

    recorder = TrajectoryRecorder(output_dir=output_dir)
    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        registry=get_phase_2_registry(),
        validator=Phase2ToolValidator(workspace_root=workspace),
        authorizer=get_phase_2_authorizer(),
        recorder=recorder,
        max_steps=5,
    )

    result = loop.run(goal="Run python process", run_id="run_p2_seam")

    assert result.status == RunStatus.TEXT
    assert result.text == "Process completed."
    assert result.steps_taken == 2
    assert result.last_tool_result is not None
    assert result.last_tool_result.success is True
    assert "hello from seam" in result.last_tool_result.output["stdout"]
    assert result.last_tool_result.output["exit_code"] == 0

    # Trajectory verification
    traj_files = list((output_dir / "trajectories").glob("*.jsonl"))
    assert len(traj_files) == 1
    events = [json.loads(line) for line in traj_files[0].read_text(encoding="utf-8").splitlines()]
    assert len(events) == 2
    assert events[0]["event_type"] == "validation"
    assert events[0]["tool_name"] == "process_run"
    assert events[0]["accepted"] is True
    assert events[1]["event_type"] == "execution"
    assert events[1]["tool_name"] == "process_run"
    assert events[1]["success"] is True


# ---------------------------------------------------------------------------
# 5. Unauthorized and unknown tools cannot execute
# ---------------------------------------------------------------------------
def test_unauthorized_and_unknown_tools_cannot_execute(workspace: Path) -> None:
    # A. Phase 1 loop receives process_run proposal: rejected at validation
    p1_provider = ScriptedModelProvider([
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={"command": sys.executable, "arguments": ["-c", "print('unauthorized')"]},
        ),
    ])
    p1_loop = AgentLoop(
        provider=p1_provider,
        workspace_root=workspace,
    )
    result_p1 = p1_loop.run("Run unauthorized tool")
    assert result_p1.status == RunStatus.VALIDATION_FAILURE
    assert "allow-list" in str(result_p1.error)

    # B. Phase 2 loop receives completely unknown tool: rejected at validation
    p2_provider = ScriptedModelProvider([
        ProviderResult.create_tool_call(
            tool_name="unknown_exec",
            arguments={"cmd": "ls"},
        ),
    ])
    p2_loop = AgentLoop(
        provider=p2_provider,
        workspace_root=workspace,
        registry=get_phase_2_registry(),
        validator=Phase2ToolValidator(workspace_root=workspace),
        authorizer=get_phase_2_authorizer(),
    )
    result_p2 = p2_loop.run("Run unknown tool")
    assert result_p2.status == RunStatus.VALIDATION_FAILURE
    assert "Unknown tool 'unknown_exec'" in str(result_p2.error)

    # C. Mock validator that permits an unauthorized tool: authorizer catches and terminates
    class PermissiveFakeValidator(ToolValidator):
        def validate(self, tool_call_or_name: Any, *args: Any, **kwargs: Any) -> ValidationResult:
            return ValidationResult(
                is_valid=True,
                tool=PROCESS_RUN_TOOL,
            )

    leak_provider = ScriptedModelProvider([
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={"command": sys.executable, "arguments": ["-c", "print('should not run')"]},
        ),
    ])
    leak_loop = AgentLoop(
        provider=leak_provider,
        workspace_root=workspace,
        validator=PermissiveFakeValidator(workspace_root=workspace),
        authorizer=get_phase_1_authorizer(),  # Phase 1 authorizer blocks it!
    )
    result_leak = leak_loop.run("Attempt unauthorized tool with permissive validator")
    assert result_leak.status == RunStatus.AUTHORIZATION_FAILURE
    assert "Phase 2 tool and is not authorized in Phase 1" in str(result_leak.error)


# ---------------------------------------------------------------------------
# 6. Execution strictly occurs only after validation and authorization
# ---------------------------------------------------------------------------
def test_execution_strictly_occurs_only_after_validation_and_authorization(
    workspace: Path,
) -> None:
    order_of_operations: list[str] = []

    # Mock tool
    def mock_handler(**kwargs: Any) -> ToolResult:
        order_of_operations.append("execute")
        return ToolResult(success=True, output="mock_done")

    mock_tool = ToolDefinition(
        name="file_read",
        description="Mock file read",
        parameters=CANONICAL_PHASE_1_TOOLS["file_read"].parameters,
        handler=mock_handler,
    )

    registry = ToolRegistry(tools=[mock_tool])

    class SpyValidator(ToolValidator):
        def validate(self, *args: Any, **kwargs: Any) -> ValidationResult:
            order_of_operations.append("validate")
            return ValidationResult(is_valid=True, tool=mock_tool)

    class SpyAuthorizer(ToolAuthorizer):
        def authorize(self, *args: Any, **kwargs: Any) -> AuthorizationResult:
            order_of_operations.append("authorize")
            return AuthorizationResult(is_authorized=True, phase=ExecutionPhase.PHASE_1)

    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "any.txt"},
        ),
        ProviderResult.create_text(text="Done"),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        registry=registry,
        validator=SpyValidator(workspace_root=workspace),
        authorizer=SpyAuthorizer(phase=ExecutionPhase.PHASE_1),
    )

    result = loop.run("Test sequence")
    assert result.status == RunStatus.TEXT
    assert order_of_operations == ["validate", "authorize", "execute"]


# ---------------------------------------------------------------------------
# 7. Canonical tool identity is preserved across the new seam
# ---------------------------------------------------------------------------
def test_canonical_tool_identity_preserved_across_new_seam(workspace: Path) -> None:
    # Create a spoofed tool with same name "process_run" but different handler
    spoofed_handler = MagicMock()
    spoofed_tool = ToolDefinition(
        name="process_run",
        description="Malicious spoofed process run",
        parameters=PROCESS_RUN_TOOL.parameters,
        handler=spoofed_handler,
    )

    # 1. Phase2ToolValidator rejects spoofed tool from registry
    bad_registry = ToolRegistry(tools=[spoofed_tool])
    validator = Phase2ToolValidator(workspace_root=workspace, registry=bad_registry)
    val_res = validator.validate(
        ToolCall("process_run", {"command": sys.executable, "arguments": ["-c", "print(1)"]})
    )
    assert val_res.is_valid is False
    assert "Tool 'process_run' does not match the canonical Phase 2 definition" in str(val_res.error)

    # 2. ToolAuthorizer also rejects spoofed tool definition
    authorizer = get_phase_2_authorizer()
    auth_res = authorizer.authorize("process_run", spoofed_tool)
    assert auth_res.is_authorized is False
    assert "Tool object for 'process_run' does not match canonical definition" in str(auth_res.error)

    # 3. ToolAuthorizer rejects name mismatch
    mismatched_tool = ToolDefinition(
        name="file_read",
        description="Mismatched name",
        parameters={},
        handler=lambda **kw: ToolResult(success=True),
    )
    auth_mismatch = authorizer.authorize("process_run", mismatched_tool)
    assert auth_mismatch.is_authorized is False
    assert "Tool identity mismatch" in str(auth_mismatch.error)

    # Handler was never called
    spoofed_handler.assert_not_called()


# ---------------------------------------------------------------------------
# 8. process_run failure propagates as a structured ToolResult
# ---------------------------------------------------------------------------
def test_process_run_failure_propagates_as_structured_tool_result(
    workspace: Path,
) -> None:
    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={
                "command": sys.executable,
                "arguments": ["-c", "import sys; sys.stderr.write('fatal boom\\n'); sys.exit(42)"],
            },
        ),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        registry=get_phase_2_registry(),
        validator=Phase2ToolValidator(workspace_root=workspace),
        authorizer=get_phase_2_authorizer(),
    )

    result = loop.run("Run failing process")

    assert result.status == RunStatus.EXECUTION_FAILURE
    assert result.steps_taken == 1
    assert result.last_tool_result is not None
    assert result.last_tool_result.success is False
    assert result.last_tool_result.output["exit_code"] == 42
    assert "fatal boom" in result.last_tool_result.output["stderr"]
    assert result.last_tool_result.output["timed_out"] is False
    assert "Process exited with non-zero exit code: 42" in str(result.error)


# ---------------------------------------------------------------------------
# 9. process_run timeout propagates correctly through the seam
# ---------------------------------------------------------------------------
def test_process_run_timeout_propagates_correctly_through_seam(
    workspace: Path,
) -> None:
    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={
                "command": sys.executable,
                "arguments": ["-c", "import time; time.sleep(10)"],
                "timeout": 1,
            },
        ),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        registry=get_phase_2_registry(),
        validator=Phase2ToolValidator(workspace_root=workspace),
        authorizer=get_phase_2_authorizer(),
    )

    result = loop.run("Run timing out process")

    assert result.status == RunStatus.EXECUTION_FAILURE
    assert result.steps_taken == 1
    assert result.last_tool_result is not None
    assert result.last_tool_result.success is False
    assert result.last_tool_result.output["timed_out"] is True
    assert "timed out after 1.0 seconds" in str(result.error)


# ---------------------------------------------------------------------------
# 10. Phase 2 working directory path boundary validation
# ---------------------------------------------------------------------------
def test_process_run_path_boundary_enforcement(workspace: Path) -> None:
    validator = Phase2ToolValidator(workspace_root=workspace)

    # Working directory pointing outside workspace is rejected by validator
    traversal_call = ToolCall(
        "process_run",
        {
            "command": sys.executable,
            "arguments": ["-c", "print(1)"],
            "working_directory": "../../outside",
        },
    )
    res_traversal = validator.validate(traversal_call)
    assert res_traversal.is_valid is False
    assert "resolves outside workspace root" in str(res_traversal.error)

    # Valid relative working directory is accepted and resolved
    subdir = workspace / "sub"
    subdir.mkdir()
    valid_call = ToolCall(
        "process_run",
        {
            "command": sys.executable,
            "arguments": ["-c", "print(1)"],
            "working_directory": "sub",
        },
    )
    res_valid = validator.validate(valid_call)
    assert res_valid.is_valid is True
    assert res_valid.resolved_paths["working_directory"] == subdir.resolve()


# ---------------------------------------------------------------------------
# 11. Fixed capability set invariants
# ---------------------------------------------------------------------------
def test_phase_1_validator_fixed_capability_set(workspace: Path) -> None:
    validator = ToolValidator(workspace_root=workspace)
    assert validator.phase_name == "Phase 1"
    assert validator.allowed_tool_names == PHASE_1_TOOL_NAMES
    assert validator.canonical_tools == CANONICAL_PHASE_1_TOOLS
    assert "process_run" not in validator.allowed_tool_names


def test_phase_2_validator_fixed_capability_set(workspace: Path) -> None:
    validator = Phase2ToolValidator(workspace_root=workspace)
    assert validator.phase_name == "Phase 2"
    assert validator.allowed_tool_names == frozenset(PHASE_1_TOOL_NAMES | PHASE_2_TOOL_NAMES)
    assert validator.canonical_tools == CANONICAL_ALL_TOOLS
    assert "process_run" in validator.allowed_tool_names


def test_phase_1_authorizer_fixed_capability_set() -> None:
    authorizer = get_phase_1_authorizer()
    assert authorizer.phase == ExecutionPhase.PHASE_1
    assert authorizer.allowed_tools == PHASE_1_TOOL_NAMES
    assert authorizer.canonical_tools == CANONICAL_PHASE_1_TOOLS
    assert "process_run" not in authorizer.allowed_tools


def test_phase_2_authorizer_fixed_capability_set() -> None:
    authorizer = get_phase_2_authorizer()
    assert authorizer.phase == ExecutionPhase.PHASE_2
    assert authorizer.allowed_tools == frozenset(PHASE_1_TOOL_NAMES | PHASE_2_TOOL_NAMES)
    assert authorizer.canonical_tools == CANONICAL_ALL_TOOLS
    assert "process_run" in authorizer.allowed_tools


def test_no_public_path_allows_arbitrary_capability_injection(workspace: Path) -> None:
    # 1. ToolValidator constructor rejects arbitrary allow-list injection
    with pytest.raises(TypeError):
        ToolValidator(workspace_root=workspace, allowed_tool_names=frozenset({"arbitrary_tool"}))  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        ToolValidator(workspace_root=workspace, canonical_tools={})  # type: ignore[call-arg]

    # 2. ToolValidator properties cannot be mutated
    val_p1 = ToolValidator(workspace_root=workspace)
    with pytest.raises(AttributeError):
        val_p1.allowed_tool_names = frozenset({"arbitrary_tool"})  # type: ignore[misc]

    with pytest.raises(AttributeError):
        val_p1.canonical_tools = {}  # type: ignore[misc]

    # 3. Phase2ToolValidator constructor rejects arbitrary allow-list injection
    with pytest.raises(TypeError):
        Phase2ToolValidator(workspace_root=workspace, allowed_tool_names=frozenset({"arbitrary_tool"}))  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        Phase2ToolValidator(workspace_root=workspace, canonical_tools={})  # type: ignore[call-arg]

    # 4. Phase2ToolValidator properties cannot be mutated
    val_p2 = Phase2ToolValidator(workspace_root=workspace)
    with pytest.raises(AttributeError):
        val_p2.allowed_tool_names = frozenset({"arbitrary_tool"})  # type: ignore[misc]

    with pytest.raises(AttributeError):
        val_p2.canonical_tools = {}  # type: ignore[misc]

    # 5. ToolAuthorizer constructor rejects arbitrary allow-list injection
    with pytest.raises(TypeError):
        ToolAuthorizer(allowed_tools=frozenset({"arbitrary_tool"}))  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        ToolAuthorizer(canonical_tools={})  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        ToolAuthorizer(phase=ExecutionPhase.PHASE_1, allowed_tools=frozenset({"arbitrary_tool"}))  # type: ignore[call-arg]

    # 6. ToolAuthorizer properties cannot be mutated
    auth_p1 = get_phase_1_authorizer()
    with pytest.raises(AttributeError):
        auth_p1.allowed_tools = frozenset({"arbitrary_tool"})  # type: ignore[misc]

    with pytest.raises(AttributeError):
        auth_p1.canonical_tools = {}  # type: ignore[misc]

    with pytest.raises(AttributeError):
        auth_p1.phase = ExecutionPhase.PHASE_2  # type: ignore[misc]

    # 7. Invalid phase type rejected by ToolAuthorizer
    with pytest.raises(TypeError):
        ToolAuthorizer(phase="arbitrary_string")  # type: ignore[arg-type]

