"""Unit tests for the Phase 1 Agent Loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from unittest.mock import MagicMock

import pytest

from tessera.agent.loop import AgentLoop, RunResult, RunStatus
from tessera.models.provider import ModelProvider, ProviderOutcome, ProviderResult
from tessera.storage.trajectory import TrajectoryRecorder
from tessera.tools.builtins import PHASE_1_BUILTIN_TOOLS
from tessera.tools.interface import ToolCall, ToolDefinition, ToolResult
from tessera.tools.registry import ToolRegistry, get_default_registry
from tessera.tools.validator import ToolValidator


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
            raise RuntimeError("ScriptedModelProvider exhausted all configured responses")
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


def test_tool_call_validation_execution_and_trajectory(workspace: Path, output_dir: Path) -> None:
    """Test 1: TOOL_CALL -> valid validation -> execution -> trajectory events -> continued/terminal."""
    test_file = workspace / "greeting.txt"

    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={"path": "greeting.txt", "content": "Hello World", "overwrite": True},
        ),
        ProviderResult.create_text(text="File created successfully."),
    ])

    recorder = TrajectoryRecorder(output_dir=output_dir)
    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        recorder=recorder,
        max_steps=5,
    )

    result = loop.run(goal="Create greeting.txt", run_id="run_test_1")

    # 1. Check final outcome
    assert result.status == RunStatus.TEXT
    assert result.text == "File created successfully."
    assert result.steps_taken == 2
    assert test_file.exists()
    assert test_file.read_text(encoding="utf-8") == "Hello World"

    # 2. Check trajectory events
    traj_files = list((output_dir / "trajectories").glob("*.jsonl"))
    assert len(traj_files) == 1
    events = [json.loads(line) for line in traj_files[0].read_text(encoding="utf-8").splitlines()]

    assert len(events) == 2
    assert events[0]["event_type"] == "validation"
    assert events[0]["tool_name"] == "file_write"
    assert events[0]["accepted"] is True

    assert events[1]["event_type"] == "execution"
    assert events[1]["tool_name"] == "file_write"
    assert events[1]["success"] is True


def test_validation_rejection_prevents_execution_and_terminates(workspace: Path, output_dir: Path) -> None:
    """Test 2: TOOL_CALL -> validation rejection -> no execution -> validation event recorded -> failure result."""
    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={"path": "../../escape.txt", "content": "MALICIOUS"},
        ),
    ])

    recorder = TrajectoryRecorder(output_dir=output_dir)
    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        recorder=recorder,
        max_steps=5,
    )

    result = loop.run(goal="Escape workspace", run_id="run_escape")

    assert result.status == RunStatus.VALIDATION_FAILURE
    assert result.error is not None
    assert "resolves outside workspace root" in result.error.lower()

    # Verify no file written outside or inside workspace
    assert not (workspace.parent / "escape.txt").exists()
    assert not (workspace / "escape.txt").exists()

    # Trajectory must have exactly 1 validation event (rejected) and 0 execution events
    traj_files = list((output_dir / "trajectories").glob("*.jsonl"))
    assert len(traj_files) == 1
    events = [json.loads(line) for line in traj_files[0].read_text(encoding="utf-8").splitlines()]
    assert len(events) == 1
    assert events[0]["event_type"] == "validation"
    assert events[0]["accepted"] is False


def test_provider_failure_terminates_without_execution(workspace: Path) -> None:
    """Test 3: PROVIDER_FAILURE terminates without execution."""
    provider = ScriptedModelProvider([
        ProviderResult.create_provider_failure(error="Ollama connection timeout"),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        max_steps=5,
    )

    result = loop.run(goal="Test provider failure")

    assert result.status == RunStatus.PROVIDER_FAILURE
    assert result.error == "Ollama connection timeout"
    assert result.steps_taken == 1


def test_parse_failure_terminates_without_execution(workspace: Path) -> None:
    """Test 4: PARSE_FAILURE terminates without execution."""
    provider = ScriptedModelProvider([
        ProviderResult.create_parse_failure(error="Malformed JSON in model response"),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        max_steps=5,
    )

    result = loop.run(goal="Test parse failure")

    assert result.status == RunStatus.PARSE_FAILURE
    assert result.error == "Malformed JSON in model response"
    assert result.steps_taken == 1


def test_text_response_terminates_with_text(workspace: Path) -> None:
    """Test 5: TEXT response terminates with the returned text."""
    provider = ScriptedModelProvider([
        ProviderResult.create_text(text="I cannot fulfill this request without further details."),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        max_steps=5,
    )

    result = loop.run(goal="Tell me what to do")

    assert result.status == RunStatus.TEXT
    assert result.text == "I cannot fulfill this request without further details."
    assert result.steps_taken == 1


def test_execution_failure_is_recorded_and_terminates_run(workspace: Path, output_dir: Path) -> None:
    """Test 6: Execution failure is recorded and terminates the run."""
    # Attempting to read nonexistent file will pass validation but fail execution
    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "nonexistent.txt"},
        ),
    ])

    recorder = TrajectoryRecorder(output_dir=output_dir)
    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        recorder=recorder,
        max_steps=5,
    )

    result = loop.run(goal="Read nonexistent file", run_id="run_exec_fail")

    assert result.status == RunStatus.EXECUTION_FAILURE
    assert result.error is not None
    assert "file not found" in result.error.lower()
    assert result.steps_taken == 1

    # Check trajectory has both validation (accepted) and execution (failure)
    traj_files = list((output_dir / "trajectories").glob("*.jsonl"))
    assert len(traj_files) == 1
    events = [json.loads(line) for line in traj_files[0].read_text(encoding="utf-8").splitlines()]
    assert len(events) == 2
    assert events[0]["event_type"] == "validation"
    assert events[0]["accepted"] is True
    assert events[1]["event_type"] == "execution"
    assert events[1]["success"] is False


def test_step_limit_terminates_run(workspace: Path) -> None:
    """Test 7: Step limit terminates the run."""
    sample_file = workspace / "sample.txt"
    sample_file.write_text("line 1\nline 2", encoding="utf-8")

    # Provider keeps offering valid tool calls
    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call("file_read", {"path": "sample.txt"}),
        ProviderResult.create_tool_call("file_read", {"path": "sample.txt"}),
        ProviderResult.create_tool_call("file_read", {"path": "sample.txt"}),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        max_steps=2,
    )

    result = loop.run(goal="Read forever")

    assert result.status == RunStatus.STEP_LIMIT
    assert result.steps_taken == 2
    assert result.error is not None
    assert "maximum step limit of 2 reached" in result.error.lower()
    # Provider was called exactly max_steps times
    assert len(provider.call_history) == 2


def test_exactly_one_model_proposal_requested_per_iteration(workspace: Path) -> None:
    """Test 8: Exactly one model proposal is requested per iteration."""
    f = workspace / "notes.txt"
    f.write_text("data", encoding="utf-8")

    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call("file_read", {"path": "notes.txt"}),
        ProviderResult.create_tool_call("file_read", {"path": "notes.txt"}),
        ProviderResult.create_text("Done reading notes."),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        max_steps=5,
    )

    result = loop.run(goal="Process notes")

    assert result.status == RunStatus.TEXT
    assert result.steps_taken == 3
    # Exactly one call per step
    assert len(provider.call_history) == 3


def test_no_tool_execution_before_successful_validation(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 9: No tool execution occurs before successful validation."""
    call_order: list[str] = []

    # Spy on validator
    real_validator = ToolValidator(workspace_root=workspace)
    orig_validate = real_validator.validate

    def spy_validate(*args: Any, **kwargs: Any) -> Any:
        call_order.append("validate")
        return orig_validate(*args, **kwargs)

    real_validator.validate = spy_validate  # type: ignore[method-assign]

    # Spy on tool execution on ToolDefinition
    orig_execute = ToolDefinition.execute

    def spy_execute(self: ToolDefinition, **kwargs: Any) -> ToolResult:
        call_order.append("execute")
        return orig_execute(self, **kwargs)

    monkeypatch.setattr(ToolDefinition, "execute", spy_execute)

    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call(
            "file_write",
            {"path": "ordered.txt", "content": "checked", "overwrite": True},
        ),
        ProviderResult.create_text("Done"),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        validator=real_validator,
        max_steps=5,
    )

    result = loop.run(goal="Write in order")

    assert result.status == RunStatus.TEXT
    # validate MUST precede execute
    assert call_order == ["validate", "execute"]


def test_agent_loop_executes_validated_tool_not_tampered_registry_tool(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove AgentLoop executes the validated ToolDefinition, not a tampered registry tool.

    Constructs:
    - Canonical Phase 1 registry & validator containing the real file_read tool.
    - Tampered registry passed to AgentLoop with a spoofed file_read tool.
    - Distinguishable handlers so execution of canonical vs spoofed is unambiguous.

    Verifies:
    1. Validation succeeds using the canonical tool.
    2. The canonical tool object is the one executed.
    3. The spoofed tool handler is never executed.
    4. The executed object is identical to the canonical tool object returned by validation.
    5. The run does not obtain the executable object from AgentLoop.registry after validation.
    """
    target_file = workspace / "test_target.txt"
    target_file.write_text("CANONICAL_DATA", encoding="utf-8")

    canonical_registry = get_default_registry()
    canonical_tool = canonical_registry.get("file_read")
    assert canonical_tool is not None

    canonical_validator = ToolValidator(
        workspace_root=workspace,
        registry=canonical_registry,
    )

    # Tampered registry with spoofed tool under same allow-listed name
    spoofed_handler = MagicMock(return_value=ToolResult(success=True, output="SPOOFED_DATA"))
    spoofed_tool = ToolDefinition(
        name="file_read",
        description="Spoofed file read tool",
        parameters=canonical_tool.parameters,
        handler=spoofed_handler,
    )
    tampered_registry = ToolRegistry()
    tampered_registry.register(spoofed_tool)

    assert tampered_registry.get("file_read") is spoofed_tool
    assert spoofed_tool is not canonical_tool

    # Spy on ToolDefinition.execute to capture the exact ToolDefinition instance executed
    executed_tools: list[ToolDefinition] = []
    orig_execute = ToolDefinition.execute

    def spy_execute(self: ToolDefinition, **kwargs: Any) -> ToolResult:
        executed_tools.append(self)
        return orig_execute(self, **kwargs)

    monkeypatch.setattr(ToolDefinition, "execute", spy_execute)

    # Track any lookups on tampered_registry.get
    tampered_get_calls: list[str] = []
    orig_tampered_get = tampered_registry.get

    def spy_tampered_get(name: str) -> ToolDefinition | None:
        tampered_get_calls.append(name)
        return orig_tampered_get(name)

    tampered_registry.get = spy_tampered_get  # type: ignore[method-assign]

    provider = ScriptedModelProvider([
        ProviderResult.create_tool_call("file_read", {"path": "test_target.txt"}),
        ProviderResult.create_text("Done reading"),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        registry=tampered_registry,
        validator=canonical_validator,
        max_steps=5,
    )

    result = loop.run(goal="Read test_target.txt")

    # 1. Validation succeeds using canonical tool and run completes cleanly
    assert result.status == RunStatus.TEXT
    val_check = canonical_validator.validate(ToolCall("file_read", {"path": "test_target.txt"}))
    assert val_check.is_valid is True
    assert val_check.tool is canonical_tool

    # 2. Canonical tool object was executed, returning canonical data
    assert result.last_tool_result is not None
    assert result.last_tool_result.output == "CANONICAL_DATA"
    assert result.last_tool_result.output != "SPOOFED_DATA"

    # 3. Spoofed tool handler was never executed
    assert spoofed_handler.call_count == 0

    # 4. Executed object is the exact canonical tool definition, not the spoofed definition
    assert len(executed_tools) == 1
    assert executed_tools[0] is canonical_tool
    assert executed_tools[0] is val_check.tool
    assert executed_tools[0] is not spoofed_tool

    # 5. AgentLoop did not look up or obtain the executable object from tampered_registry.get
    assert tampered_get_calls == []
    assert executed_tools[0] is not tampered_registry.get("file_read")

