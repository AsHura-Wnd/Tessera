"""Unit tests for the AgentLoop <-> ModelProvider native conversation protocol."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from unittest.mock import MagicMock

import pytest

from tessera.agent.loop import AgentLoop, RunStatus
from tessera.models.provider import (
    ModelProvider,
    OllamaProvider,
    ProviderOutcome,
    ProviderResult,
)
from tessera.tools.interface import ToolCall, ToolResult


class RecordingModelProvider(ModelProvider):
    """Deterministic mock provider recording exact prompts and contexts per turn."""

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
            "context": [dict(c) for c in context] if context else None,
        })
        if not self.responses:
            raise RuntimeError("RecordingModelProvider exhausted configured responses")
        return self.responses.pop(0)


class MockOllamaClient:
    """Mock client capturing chat kwargs passed to ollama."""

    def __init__(self, response: Any = None) -> None:
        self.response = response
        self.last_kwargs: dict[str, Any] = {}

    def chat(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return self.response


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


def test_initial_goal_appears_once_and_not_reappended(workspace: Path) -> None:
    """Requirements 1, 2, 3, 4, 5:

    1. Initial goal appears exactly once as root instruction.
    2. Goal is not re-appended after tool execution.
    3. Previous assistant action is represented structurally as a tool call.
    4. Tool result is represented structurally and associated with the tool.
    5. Context ordering is user -> assistant tool call -> tool result.
    """
    goal = "Create output.txt containing hello"
    provider = RecordingModelProvider([
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={"path": "output.txt", "content": "hello", "overwrite": True},
        ),
        ProviderResult.create_text("Output file created successfully."),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        max_steps=5,
    )

    result = loop.run(goal=goal)
    assert result.status == RunStatus.TEXT
    assert result.steps_taken == 2

    # Step 1 inspection
    assert len(provider.call_history) == 2
    step1 = provider.call_history[0]
    assert step1["prompt"] == goal
    assert step1["context"] is None

    # Step 2 inspection
    step2 = provider.call_history[1]
    ctx = step2["context"]
    assert ctx is not None
    assert len(ctx) == 3

    # Turn ordering: user -> assistant -> tool
    assert ctx[0]["role"] == "user"
    assert ctx[0]["content"] == goal

    assert ctx[1]["role"] == "assistant"
    assert "tool_calls" in ctx[1]
    assert len(ctx[1]["tool_calls"]) == 1
    assert ctx[1]["tool_calls"][0]["function"]["name"] == "file_write"
    assert ctx[1]["tool_calls"][0]["function"]["arguments"] == {
        "path": "output.txt",
        "content": "hello",
        "overwrite": True,
    }

    assert ctx[2]["role"] == "tool"
    assert ctx[2]["tool_name"] == "file_write"
    assert "Successfully wrote" in ctx[2]["content"]

    # Ensure goal is NOT re-appended at end of context
    assert all(m.get("content") != goal for m in ctx[1:])
    # Ensure goal occurs exactly once in the entire conversation
    goal_messages = [m for m in ctx if m.get("role") == "user" and m.get("content") == goal]
    assert len(goal_messages) == 1


def test_multiple_sequential_tool_turns_preserve_ordering(workspace: Path) -> None:
    """Requirements 5, 6, 7:

    - Multiple sequential tool turns preserve correct ordering:
      user -> assistant 1 -> tool 1 -> assistant 2 -> tool 2 -> assistant text.
    - Terminal text response terminates normally.
    """
    (workspace / "notes.txt").write_text("Secret Token: tok_12345\n", encoding="utf-8")
    goal = "Find notes.txt and extract token"

    provider = RecordingModelProvider([
        ProviderResult.create_tool_call(
            tool_name="file_find",
            arguments={"pattern": "notes.txt"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "notes.txt"},
        ),
        ProviderResult.create_text("Token is tok_12345"),
    ])

    loop = AgentLoop(
        provider=provider,
        workspace_root=workspace,
        max_steps=5,
    )

    result = loop.run(goal=goal)
    assert result.status == RunStatus.TEXT
    assert result.text == "Token is tok_12345"
    assert result.steps_taken == 3

    step3 = provider.call_history[2]
    ctx = step3["context"]
    assert ctx is not None
    assert len(ctx) == 5

    # Check exact sequence of roles
    roles = [m["role"] for m in ctx]
    assert roles == ["user", "assistant", "tool", "assistant", "tool"]

    # Verify tool association
    assert ctx[1]["tool_calls"][0]["function"]["name"] == "file_find"
    assert ctx[2]["tool_name"] == "file_find"
    assert "notes.txt" in ctx[2]["content"]

    assert ctx[3]["tool_calls"][0]["function"]["name"] == "file_read"
    assert ctx[4]["tool_name"] == "file_read"
    assert "Secret Token: tok_12345" in ctx[4]["content"]

    # Verify serializability
    serialized = json.dumps(ctx)
    assert serialized is not None
    assert json.loads(serialized) == ctx


def test_ollama_provider_translates_context_without_reappending_goal() -> None:
    """Requirements 8, 9:

    - OllamaProvider translates structured context correctly into its native representation.
    - User goal remains at the root and is not re-appended after tool responses.
    """
    mock_client = MockOllamaClient(
        response={
            "message": {
                "role": "assistant",
                "content": "All done.",
                "tool_calls": None,
            }
        }
    )
    provider = OllamaProvider(client=mock_client)

    goal = "Find database and write path"
    structured_context = [
        {"role": "user", "content": goal},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "file_find",
                        "arguments": {"pattern": "db.sqlite"},
                    }
                }
            ],
        },
        {
            "role": "tool",
            "tool_name": "file_find",
            "content": '[{"path": "data/db.sqlite", "size_bytes": 100}]',
        },
    ]

    result = provider.generate(
        prompt=goal,
        tools=[{"name": "file_find", "parameters": {}}],
        context=structured_context,
    )

    assert result.kind == ProviderOutcome.TEXT
    assert result.text == "All done."

    messages = mock_client.last_kwargs.get("messages", [])
    assert len(messages) == 3

    # Check that root message is user goal
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == goal

    # Check assistant message formatting
    assert messages[1]["role"] == "assistant"
    assert messages[1]["tool_calls"][0]["function"]["name"] == "file_find"
    assert messages[1]["tool_calls"][0]["function"]["arguments"] == {"pattern": "db.sqlite"}

    # Check tool message formatting
    assert messages[2]["role"] == "tool"
    assert messages[2]["tool_name"] == "file_find"
    assert messages[2]["content"] == '[{"path": "data/db.sqlite", "size_bytes": 100}]'

    # Verify that goal was NOT re-appended as message 4
    assert len(messages) == 3


def test_ollama_provider_single_tool_call_restriction_enforced() -> None:
    """Requirement 12: One-tool-call Phase 1 restriction remains unchanged."""
    mock_client = MockOllamaClient(
        response={
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"function": {"name": "file_read", "arguments": {"path": "a.txt"}}},
                    {"function": {"name": "file_read", "arguments": {"path": "b.txt"}}},
                ],
            }
        }
    )
    provider = OllamaProvider(client=mock_client)

    result = provider.generate(prompt="Read both files")
    assert result.kind == ProviderOutcome.PARSE_FAILURE
    assert "at most one tool call per response" in (result.error or "").lower()
