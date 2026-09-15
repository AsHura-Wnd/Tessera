"""Phase 1 Agent Loop: bounded orchestration composing ModelProvider, ToolRegistry, ToolValidator, and TrajectoryRecorder."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Sequence
import json
import uuid

from tessera.models.provider import ModelProvider, ProviderOutcome, ProviderResult
from tessera.storage.trajectory import TrajectoryRecorder
from tessera.tools.interface import ToolCall, ToolResult
from tessera.tools.authorization import ToolAuthorizer, get_phase_1_authorizer
from tessera.tools.registry import ToolRegistry, get_default_registry
from tessera.tools.validator import ToolValidator


class RunStatus(str, Enum):
    """Explicit mechanical stopping outcomes for Phase 1 runs."""

    TEXT = "text"
    PROVIDER_FAILURE = "provider_failure"
    PARSE_FAILURE = "parse_failure"
    VALIDATION_FAILURE = "validation_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"
    EXECUTION_FAILURE = "execution_failure"
    STEP_LIMIT = "step_limit"


@dataclass(frozen=True)
class RunResult:
    """Structured result of a bounded agent run."""

    status: RunStatus
    run_id: str
    steps_taken: int
    text: str | None = None
    error: str | None = None
    last_tool_call: ToolCall | None = None
    last_tool_result: ToolResult | None = None

    @property
    def is_text(self) -> bool:
        return self.status == RunStatus.TEXT

    @property
    def is_failure(self) -> bool:
        return self.status in {
            RunStatus.PROVIDER_FAILURE,
            RunStatus.PARSE_FAILURE,
            RunStatus.VALIDATION_FAILURE,
            RunStatus.AUTHORIZATION_FAILURE,
            RunStatus.EXECUTION_FAILURE,
        }

    @property
    def is_step_limit(self) -> bool:
        return self.status == RunStatus.STEP_LIMIT


class AgentLoop:
    """Bounded orchestration loop for a single task run in Phase 1."""

    def __init__(
        self,
        provider: ModelProvider,
        workspace_root: str | Path,
        registry: ToolRegistry | None = None,
        validator: ToolValidator | None = None,
        recorder: TrajectoryRecorder | None = None,
        authorizer: ToolAuthorizer | None = None,
        max_steps: int = 10,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")

        self.provider = provider
        self.workspace_root = Path(workspace_root).resolve()
        self.registry = registry or get_default_registry()
        self.validator = validator or ToolValidator(
            workspace_root=self.workspace_root,
            registry=self.registry,
        )
        self.authorizer = authorizer or get_phase_1_authorizer()
        self.recorder = recorder
        self.max_steps = max_steps

    def run(self, goal: str, run_id: str | None = None) -> RunResult:
        """Execute a bounded run for the specified goal."""
        active_run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"

        if self.recorder is not None:
            self.recorder.start_run(active_run_id)

        step_count = 0
        context: list[dict[str, Any]] = []
        last_tool_call: ToolCall | None = None
        last_tool_result: ToolResult | None = None

        tool_schemas = [tool.to_schema() for tool in self.registry.list_tools()]

        while True:
            if step_count >= self.max_steps:
                return RunResult(
                    status=RunStatus.STEP_LIMIT,
                    run_id=active_run_id,
                    steps_taken=step_count,
                    error=f"Maximum step limit of {self.max_steps} reached",
                    last_tool_call=last_tool_call,
                    last_tool_result=last_tool_result,
                )

            step_count += 1

            # 1. Request exactly one proposal from ModelProvider
            provider_result: ProviderResult = self.provider.generate(
                prompt=goal,
                tools=tool_schemas,
                context=context if context else None,
            )

            # 2. Handle provider failure
            if provider_result.kind == ProviderOutcome.PROVIDER_FAILURE:
                return RunResult(
                    status=RunStatus.PROVIDER_FAILURE,
                    run_id=active_run_id,
                    steps_taken=step_count,
                    error=provider_result.error or "Model provider request failed",
                    last_tool_call=last_tool_call,
                    last_tool_result=last_tool_result,
                )

            # 3. Handle parse failure
            if provider_result.kind == ProviderOutcome.PARSE_FAILURE:
                return RunResult(
                    status=RunStatus.PARSE_FAILURE,
                    run_id=active_run_id,
                    steps_taken=step_count,
                    error=provider_result.error or "Model response could not be parsed",
                    last_tool_call=last_tool_call,
                    last_tool_result=last_tool_result,
                )

            # 4. Handle text response
            if provider_result.kind == ProviderOutcome.TEXT:
                return RunResult(
                    status=RunStatus.TEXT,
                    run_id=active_run_id,
                    steps_taken=step_count,
                    text=provider_result.text,
                    last_tool_call=last_tool_call,
                    last_tool_result=last_tool_result,
                )

            # 5. Handle tool call
            if provider_result.kind == ProviderOutcome.TOOL_CALL:
                tool_call = provider_result.tool_call
                assert tool_call is not None
                last_tool_call = tool_call

                # Validate proposed tool call
                val_result = self.validator.validate(tool_call)

                # Record validation event
                if self.recorder is not None:
                    self.recorder.record_validation(
                        tool_name=tool_call.tool_name,
                        arguments=tool_call.arguments,
                        result=val_result,
                    )

                # Validation failure terminates run immediately without execution
                if not val_result.is_valid or val_result.tool is None:
                    return RunResult(
                        status=RunStatus.VALIDATION_FAILURE,
                        run_id=active_run_id,
                        steps_taken=step_count,
                        error=val_result.error or "Tool validation rejected",
                        last_tool_call=tool_call,
                    )

                # Authorize validated tool for current execution phase
                auth_result = self.authorizer.authorize(
                    tool_name=tool_call.tool_name,
                    tool=val_result.tool,
                )

                # Authorization failure terminates run immediately without execution
                if not auth_result.is_authorized:
                    return RunResult(
                        status=RunStatus.AUTHORIZATION_FAILURE,
                        run_id=active_run_id,
                        steps_taken=step_count,
                        error=auth_result.error or "Tool authorization rejected",
                        last_tool_call=tool_call,
                    )

                # Prepare resolved arguments and execute the validated tool definition directly
                exec_args = dict(tool_call.arguments)
                if val_result.resolved_paths:
                    exec_args.update(val_result.resolved_paths)

                tool_result: ToolResult = val_result.tool.execute(**exec_args)
                last_tool_result = tool_result

                # Record execution event
                if self.recorder is not None:
                    self.recorder.record_execution(
                        tool_name=tool_call.tool_name,
                        arguments=exec_args,
                        result=tool_result,
                    )

                # Tool execution failure terminates run immediately
                if not tool_result.success:
                    return RunResult(
                        status=RunStatus.EXECUTION_FAILURE,
                        run_id=active_run_id,
                        steps_taken=step_count,
                        error=tool_result.error or "Tool execution failed",
                        last_tool_call=tool_call,
                        last_tool_result=tool_result,
                    )

                # Anchor root user goal at the start of context if not already present
                if not context:
                    context.append({
                        "role": "user",
                        "content": goal,
                    })

                # Append structured serializable observation context for next iteration
                context.append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": tool_call.tool_name,
                                "arguments": dict(tool_call.arguments),
                            }
                        }
                    ],
                })
                formatted_output = (
                    json.dumps(tool_result.output)
                    if isinstance(tool_result.output, (dict, list))
                    else (str(tool_result.output) if tool_result.output is not None else "")
                )
                context.append({
                    "role": "tool",
                    "tool_name": tool_call.tool_name,
                    "content": formatted_output,
                })
