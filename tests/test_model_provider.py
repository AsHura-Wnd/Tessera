"""Unit tests for tightened ModelProvider interface and OllamaProvider adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence
from unittest.mock import MagicMock

import pytest

from tessera.models.provider import (
    ModelProvider,
    OllamaProvider,
    ProviderOutcome,
    ProviderResult,
)
from tessera.tools.builtins import FILE_READ_TOOL, FILE_WRITE_TOOL
from tessera.tools.interface import ToolCall, ToolDefinition
from tessera.tools.validator import ToolValidator


class FakeModelClient:
    """Mock client mimicking ollama.Client without running a local Ollama daemon."""

    def __init__(self, response: Any = None, side_effect: Any = None) -> None:
        self.response = response
        self.chat = MagicMock(side_effect=side_effect or self._mock_chat)

    def _mock_chat(self, **kwargs: Any) -> Any:
        return self.response


def test_valid_native_ollama_tool_call_produces_normalized_tool_call() -> None:
    mock_client = FakeModelClient(
        response={
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "file_read",
                            "arguments": {"path": "src/main.py", "start_line": 1},
                        }
                    }
                ],
            }
        }
    )
    provider = OllamaProvider(client=mock_client)

    result = provider.generate(
        prompt="Read src/main.py",
        tools=[FILE_READ_TOOL.to_schema()],
    )

    assert result.kind == ProviderOutcome.TOOL_CALL
    assert result.is_tool_call is True
    assert result.is_text is False
    assert result.is_provider_failure is False
    assert result.is_parse_failure is False
    assert result.tool_name == "file_read"
    assert result.arguments == {"path": "src/main.py", "start_line": 1}
    assert result.tool_call == ToolCall(
        tool_name="file_read",
        arguments={"path": "src/main.py", "start_line": 1},
    )
    assert result.error is None


def test_valid_native_json_string_arguments_normalized_to_dict() -> None:
    mock_client = FakeModelClient(
        response={
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "file_read",
                            "arguments": '{"path": "data.json", "start_line": 10}',
                        }
                    }
                ],
            }
        }
    )
    provider = OllamaProvider(client=mock_client)

    result = provider.generate(
        prompt="Read data.json lines 10+",
        tools=[FILE_READ_TOOL.to_schema()],
    )

    assert result.kind == ProviderOutcome.TOOL_CALL
    assert result.tool_name == "file_read"
    assert result.arguments == {"path": "data.json", "start_line": 10}


def test_normal_text_response_classified_as_text() -> None:
    plain_text = "I have inspected the workspace. All tasks are completed."
    mock_client = FakeModelClient(
        response={
            "message": {
                "role": "assistant",
                "content": plain_text,
                "tool_calls": None,
            }
        }
    )
    provider = OllamaProvider(client=mock_client)

    result = provider.generate(
        prompt="Status report",
        tools=[FILE_READ_TOOL.to_schema()],
    )

    assert result.kind == ProviderOutcome.TEXT
    assert result.is_text is True
    assert result.is_tool_call is False
    assert result.is_provider_failure is False
    assert result.is_parse_failure is False
    assert result.text == plain_text
    assert result.tool_call is None
    assert result.error is None


def test_malformed_tool_arguments_classified_as_parse_failure() -> None:
    mock_client = FakeModelClient(
        response={
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "file_read",
                            "arguments": '{"path": "incomplete.txt", "start_line": ',
                        }
                    }
                ],
            }
        }
    )
    provider = OllamaProvider(client=mock_client)

    result = provider.generate(
        prompt="Read incomplete file",
        tools=[FILE_READ_TOOL.to_schema()],
    )

    assert result.kind == ProviderOutcome.PARSE_FAILURE
    assert result.is_parse_failure is True
    assert result.is_provider_failure is False
    assert result.is_tool_call is False
    assert result.is_text is False
    assert result.error is not None
    assert "malformed json" in result.error.lower()
    # Verify no silent retry was performed
    assert mock_client.chat.call_count == 1


def test_multiple_tool_calls_rejected_as_parse_failure() -> None:
    mock_client = FakeModelClient(
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

    result = provider.generate(
        prompt="Read both files",
        tools=[FILE_READ_TOOL.to_schema()],
    )

    assert result.kind == ProviderOutcome.PARSE_FAILURE
    assert result.is_parse_failure is True
    assert result.is_provider_failure is False
    assert result.error is not None
    assert "at most one tool call" in result.error.lower()
    assert mock_client.chat.call_count == 1


def test_invalid_or_missing_tool_name_rejected_as_parse_failure() -> None:
    mock_client = FakeModelClient(
        response={
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"function": {"name": "", "arguments": {"path": "a.txt"}}}
                ],
            }
        }
    )
    provider = OllamaProvider(client=mock_client)

    result = provider.generate(prompt="Read file")

    assert result.kind == ProviderOutcome.PARSE_FAILURE
    assert result.is_parse_failure is True
    assert result.error is not None
    assert "tool name must be a non-empty string" in result.error.lower()


def test_empty_model_response_classified_as_parse_failure() -> None:
    mock_client = FakeModelClient(
        response={
            "message": {
                "role": "assistant",
                "content": "   ",
                "tool_calls": [],
            }
        }
    )
    provider = OllamaProvider(client=mock_client)

    result = provider.generate(prompt="Do something")

    assert result.kind == ProviderOutcome.PARSE_FAILURE
    assert result.is_parse_failure is True
    assert result.error is not None
    assert "empty model response" in result.error.lower()


def test_speculative_json_format_rejected_as_parse_failure() -> None:
    """Speculative tool-call formats are rejected as parse failure, not guessed."""
    speculative_formats = [
        '{"tool": "file_read", "arguments": {"path": "a.txt"}}',
        '{"tool_name": "file_read", "arguments": {"path": "a.txt"}}',
        '{"name": "file_read", "parameters": {"path": "a.txt"}}',
        '{"function": {"name": "file_read", "arguments": {"path": "a.txt"}}}',
    ]

    for body in speculative_formats:
        mock_client = FakeModelClient(
            response={
                "message": {
                    "role": "assistant",
                    "content": body,
                    "tool_calls": None,
                }
            }
        )
        provider = OllamaProvider(client=mock_client)
        result = provider.generate(prompt="Run tool")

        assert result.kind == ProviderOutcome.PARSE_FAILURE
        assert result.is_parse_failure is True
        assert result.error is not None
        assert "does not match the supported phase 1 tool-call format" in result.error.lower()


def test_provider_request_failure_classified_as_provider_failure() -> None:
    """Network, connection, or daemon errors return provider_failure, not parse_failure."""
    mock_client = FakeModelClient(
        side_effect=ConnectionError("Failed to connect to Ollama at http://127.0.0.1:11434")
    )
    provider = OllamaProvider(client=mock_client)

    result = provider.generate(
        prompt="Status check",
        tools=[FILE_READ_TOOL.to_schema()],
    )

    assert result.kind == ProviderOutcome.PROVIDER_FAILURE
    assert result.is_provider_failure is True
    assert result.is_parse_failure is False
    assert result.is_tool_call is False
    assert result.is_text is False
    assert result.error is not None
    assert "model provider request failed" in result.error.lower()


def test_parser_exception_is_not_mislabeled_as_provider_failure() -> None:
    """Unexpected exceptions during response parsing yield parse_failure, not provider_failure."""

    class CorruptResponse:
        @property
        def message(self) -> Any:
            raise RuntimeError("Unexpected failure reading response message")

    corrupt_response = CorruptResponse()
    mock_client = FakeModelClient(response=corrupt_response)
    provider = OllamaProvider(client=mock_client)

    result = provider.generate(prompt="Test prompt")

    # Client request succeeded
    assert mock_client.chat.call_count == 1

    # Demonstrated that parsing failure is not mislabeled as PROVIDER_FAILURE
    assert result.kind == ProviderOutcome.PARSE_FAILURE
    assert result.is_parse_failure is True
    assert result.is_provider_failure is False
    assert result.error is not None
    assert "failed to parse model response" in result.error.lower()


def test_invalid_tool_schema_not_silently_ignored() -> None:
    """Unsupported or invalid tool schemas return an explicit provider failure."""
    mock_client = FakeModelClient(response={"message": {"role": "assistant", "content": "ok"}})
    provider = OllamaProvider(client=mock_client)

    invalid_tools = [
        "not_a_schema_object",
        12345,
        object(),
    ]

    for invalid_tool in invalid_tools:
        result = provider.generate(
            prompt="Do task",
            tools=[invalid_tool],  # type: ignore[list-item]
        )

        assert result.kind == ProviderOutcome.PROVIDER_FAILURE
        assert result.is_provider_failure is True
        assert result.error is not None
        assert "invalid tool schema" in result.error.lower()
        # Ensure client was never called with invalid schema
        assert mock_client.chat.call_count == 0


def test_provider_does_not_execute_tools_or_invoke_validator(tmp_path: Path) -> None:
    """Verify the provider has zero execution authority and causes no side effects."""
    sensitive_file = tmp_path / "sensitive.txt"
    sensitive_file.write_text("DO_NOT_OVERWRITE", encoding="utf-8")

    # The mock model proposes a file_write that would overwrite sensitive.txt
    mock_client = FakeModelClient(
        response={
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "file_write",
                            "arguments": {
                                "path": str(sensitive_file),
                                "content": "MALICIOUS_OVERWRITE",
                            },
                        }
                    }
                ],
            }
        }
    )

    validator_mock = MagicMock(spec=ToolValidator)
    tool_handler_mock = MagicMock(return_value=None)
    fake_tool = ToolDefinition(
        name="file_write",
        description="Write file",
        parameters=FILE_WRITE_TOOL.parameters,
        handler=tool_handler_mock,
    )

    provider = OllamaProvider(client=mock_client)
    result = provider.generate(
        prompt="Overwrite sensitive file",
        tools=[fake_tool.to_schema()],
    )

    # 1. Structured proposal is returned
    assert result.kind == ProviderOutcome.TOOL_CALL
    assert result.tool_name == "file_write"

    # 2. Tool handler was NEVER executed by the provider
    assert tool_handler_mock.call_count == 0

    # 3. Tool validator was NEVER invoked by the provider
    assert validator_mock.validate.call_count == 0

    # 4. File on disk was NOT modified
    assert sensitive_file.read_text(encoding="utf-8") == "DO_NOT_OVERWRITE"


def test_model_provider_interface_is_swappable() -> None:
    """Prove a second, trivial fake provider can be substituted without code changes."""

    class MockEchoProvider(ModelProvider):
        """Trivial alternative provider returning a fixed tool proposal."""

        def __init__(self, tool_name: str, args: dict[str, Any]) -> None:
            self.tool_name = tool_name
            self.args = args

        def generate(
            self,
            prompt: str,
            tools: Sequence[Mapping[str, Any]] | None = None,
            context: Sequence[Mapping[str, Any]] | None = None,
        ) -> ProviderResult:
            return ProviderResult.create_tool_call(
                tool_name=self.tool_name,
                arguments=self.args,
            )

    # Both classes implement the ModelProvider interface
    assert issubclass(MockEchoProvider, ModelProvider)
    assert issubclass(OllamaProvider, ModelProvider)

    # Consumer function that only depends on ModelProvider interface
    def execute_agent_step(provider: ModelProvider, goal: str) -> ProviderResult:
        return provider.generate(prompt=goal)

    ollama_mock_client = FakeModelClient(
        response={
            "message": {
                "role": "assistant",
                "content": "Finished",
                "tool_calls": None,
            }
        }
    )
    ollama_provider: ModelProvider = OllamaProvider(client=ollama_mock_client)
    echo_provider: ModelProvider = MockEchoProvider(
        tool_name="file_read",
        args={"path": "foo.txt"},
    )

    # Both providers can be passed to execute_agent_step interchangeably
    res1 = execute_agent_step(ollama_provider, "Report status")
    assert res1.kind == ProviderOutcome.TEXT
    assert res1.text == "Finished"

    res2 = execute_agent_step(echo_provider, "Read foo")
    assert res2.kind == ProviderOutcome.TOOL_CALL
    assert res2.tool_name == "file_read"
    assert res2.arguments == {"path": "foo.txt"}


def test_ollama_provider_default_thinking_behavior_is_false() -> None:
    """Requirement 1: Default OllamaProvider explicitly requests think=False."""
    mock_client = FakeModelClient(
        response={
            "message": {
                "role": "assistant",
                "content": "Hello world",
                "tool_calls": None,
            }
        }
    )
    provider = OllamaProvider(client=mock_client)
    assert provider.think is False

    result = provider.generate(prompt="Hello")
    assert result.kind == ProviderOutcome.TEXT
    assert mock_client.chat.called is True
    call_kwargs = mock_client.chat.call_args.kwargs
    assert call_kwargs.get("think") is False


def test_ollama_provider_thinking_does_not_depend_on_model_name() -> None:
    """Requirement 2: Default think=False behavior does not depend on model name."""
    models_to_test = ["qwen3:8b", "qwen2.5:3b", "llama3:8b", "deepseek-r1:7b", "mistral:latest"]
    for model_name in models_to_test:
        mock_client = FakeModelClient(
            response={
                "message": {
                    "role": "assistant",
                    "content": f"Response from {model_name}",
                    "tool_calls": None,
                }
            }
        )
        provider = OllamaProvider(model=model_name, client=mock_client)
        assert provider.think is False

        provider.generate(prompt="Hi")
        call_kwargs = mock_client.chat.call_args.kwargs
        assert call_kwargs["model"] == model_name
        assert call_kwargs.get("think") is False


def test_ollama_provider_thinking_can_be_explicitly_enabled() -> None:
    """Requirement 3: Caller can explicitly enable thinking via parameter or options."""
    # Via constructor parameter think=True
    mock_client1 = FakeModelClient(
        response={"message": {"role": "assistant", "content": "Thought out", "tool_calls": None}}
    )
    provider1 = OllamaProvider(client=mock_client1, think=True)
    assert provider1.think is True
    provider1.generate(prompt="Think deeply")
    assert mock_client1.chat.call_args.kwargs.get("think") is True

    # Via constructor parameter think="high" (or other levels)
    mock_client2 = FakeModelClient(
        response={"message": {"role": "assistant", "content": "Thought out", "tool_calls": None}}
    )
    provider2 = OllamaProvider(client=mock_client2, think="high")
    assert provider2.think == "high"
    provider2.generate(prompt="Think deeply")
    assert mock_client2.chat.call_args.kwargs.get("think") == "high"

    # Via options dictionary
    mock_client3 = FakeModelClient(
        response={"message": {"role": "assistant", "content": "Thought out", "tool_calls": None}}
    )
    provider3 = OllamaProvider(client=mock_client3, options={"think": True})
    assert provider3.think is True
    provider3.generate(prompt="Think deeply")
    assert mock_client3.chat.call_args.kwargs.get("think") is True


def test_ollama_provider_handles_mock_without_think_kwarg_gracefully() -> None:
    """Requirement 4: Provider falls back gracefully if client rejects think kwarg."""
    class StrictLegacyMockClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def chat(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
            if "think" in kwargs:
                raise TypeError("chat() got an unexpected keyword argument 'think'")
            self.calls.append({"model": model, "messages": messages, **kwargs})
            return {"message": {"role": "assistant", "content": "Legacy response", "tool_calls": None}}

    legacy_client = StrictLegacyMockClient()
    provider = OllamaProvider(client=legacy_client)
    res = provider.generate(prompt="Legacy test")
    assert res.kind == ProviderOutcome.TEXT
    assert res.text == "Legacy response"
    assert len(legacy_client.calls) == 1
    assert "think" not in legacy_client.calls[0]
