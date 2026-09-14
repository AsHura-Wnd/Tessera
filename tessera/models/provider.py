"""Model provider interface and Ollama adapter for Phase 1.

The model provider is an untrusted proposal generator with zero execution
authority. It does not call tools, does not validate arguments, does not
check allow-lists, does not record trajectories, and does not retry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import json
from typing import Any, Mapping, Sequence

from tessera.tools.interface import ToolCall


class ProviderOutcome(str, Enum):
    """The four possible outcomes of a single model proposal."""

    TOOL_CALL = "tool_call"
    TEXT = "text"
    PROVIDER_FAILURE = "provider_failure"
    PARSE_FAILURE = "parse_failure"


@dataclass(frozen=True)
class ProviderResult:
    """Structured result representing exactly one model proposal outcome."""

    kind: ProviderOutcome
    tool_call: ToolCall | None = None
    text: str | None = None
    error: str | None = None
    raw_response: Any = None

    @property
    def is_tool_call(self) -> bool:
        return self.kind == ProviderOutcome.TOOL_CALL

    @property
    def is_text(self) -> bool:
        return self.kind == ProviderOutcome.TEXT

    @property
    def is_provider_failure(self) -> bool:
        return self.kind == ProviderOutcome.PROVIDER_FAILURE

    @property
    def is_parse_failure(self) -> bool:
        return self.kind == ProviderOutcome.PARSE_FAILURE

    @property
    def tool_name(self) -> str | None:
        return self.tool_call.tool_name if self.tool_call is not None else None

    @property
    def arguments(self) -> Mapping[str, Any] | None:
        return self.tool_call.arguments if self.tool_call is not None else None

    @classmethod
    def create_tool_call(
        cls,
        tool_name: str,
        arguments: Mapping[str, Any] | None = None,
        raw_response: Any = None,
    ) -> ProviderResult:
        """Create a valid tool-call proposal outcome."""
        return cls(
            kind=ProviderOutcome.TOOL_CALL,
            tool_call=ToolCall(tool_name=tool_name, arguments=dict(arguments or {})),
            raw_response=raw_response,
        )

    @classmethod
    def create_text(
        cls,
        text: str,
        raw_response: Any = None,
    ) -> ProviderResult:
        """Create an explicit non-tool-call text response outcome."""
        return cls(
            kind=ProviderOutcome.TEXT,
            text=text,
            raw_response=raw_response,
        )

    @classmethod
    def create_provider_failure(
        cls,
        error: str,
        raw_response: Any = None,
    ) -> ProviderResult:
        """Create a provider or request failure outcome."""
        return cls(
            kind=ProviderOutcome.PROVIDER_FAILURE,
            error=error,
            raw_response=raw_response,
        )

    @classmethod
    def create_parse_failure(
        cls,
        error: str,
        raw_response: Any = None,
    ) -> ProviderResult:
        """Create a parse or format failure outcome."""
        return cls(
            kind=ProviderOutcome.PARSE_FAILURE,
            error=error,
            raw_response=raw_response,
        )


class ModelProvider(ABC):
    """Abstract interface for model providers proposing tool actions."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        tools: Sequence[Mapping[str, Any]] | None = None,
        context: Sequence[Mapping[str, Any]] | None = None,
    ) -> ProviderResult:
        """Query the model with a prompt/goal and available tool schemas.

        Returns a ProviderResult representing exactly one of:
        1. A valid structured tool call (TOOL_CALL)
        2. An explicit non-tool-call text response (TEXT)
        3. A provider/request failure (PROVIDER_FAILURE)
        4. A parse/format failure (PARSE_FAILURE)
        """
        ...


class OllamaProvider(ModelProvider):
    """Concrete ModelProvider adapter for local Ollama instances."""

    def __init__(
        self,
        model: str = "qwen2.5:3b",
        host: str | None = None,
        client: Any | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> None:
        self.model = model
        self.host = host
        self.options = dict(options) if options is not None else None
        self._client = client

    @property
    def client(self) -> Any:
        """Lazily initialize or return the Ollama client."""
        if self._client is None:
            import ollama
            self._client = ollama.Client(host=self.host) if self.host else ollama.Client()
        return self._client

    def generate(
        self,
        prompt: str,
        tools: Sequence[Mapping[str, Any]] | None = None,
        context: Sequence[Mapping[str, Any]] | None = None,
    ) -> ProviderResult:
        """Query Ollama and return a single structured ProviderResult."""
        messages: list[dict[str, Any]] = []
        if context:
            for item in context:
                if isinstance(item, Mapping):
                    messages.append(dict(item))
                else:
                    return ProviderResult.create_provider_failure(
                        f"Invalid context item: expected Mapping, got {type(item).__name__}"
                    )
        if prompt:
            messages.append({"role": "user", "content": prompt})

        formatted_tools: list[dict[str, Any]] = []
        if tools:
            for tool in tools:
                if hasattr(tool, "to_schema") and callable(tool.to_schema):
                    tool_dict = tool.to_schema()
                elif isinstance(tool, Mapping):
                    tool_dict = dict(tool)
                else:
                    return ProviderResult.create_provider_failure(
                        f"Invalid tool schema: expected Mapping or ToolDefinition, got {type(tool).__name__}"
                    )

                if not isinstance(tool_dict, Mapping):
                    return ProviderResult.create_provider_failure(
                        f"Tool schema conversion failed: expected Mapping, got {type(tool_dict).__name__}"
                    )

                if "type" in tool_dict and "function" in tool_dict:
                    formatted_tools.append(dict(tool_dict))
                else:
                    formatted_tools.append({
                        "type": "function",
                        "function": dict(tool_dict),
                    })

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if formatted_tools:
            kwargs["tools"] = formatted_tools
        if self.options:
            kwargs["options"] = self.options

        try:
            response = self.client.chat(**kwargs)
        except Exception as e:
            return ProviderResult.create_provider_failure(
                error=f"Model provider request failed: {e}",
                raw_response=None,
            )

        return self._parse_chat_response(response)

    @classmethod
    def _parse_chat_response(cls, response: Any) -> ProviderResult:
        """Parse Ollama ChatResponse or mapping into exactly one outcome."""
        try:
            if response is None:
                return ProviderResult.create_parse_failure(
                    error="Received null response from model provider",
                    raw_response=None,
                )

            # 1. Extract message container
            message = getattr(response, "message", None)
            if message is None and isinstance(response, Mapping):
                message = response.get("message", response)

            if message is None:
                return ProviderResult.create_parse_failure(
                    error="Malformed response from model provider: no message found",
                    raw_response=response,
                )

            # 2. Extract tool_calls and content
            tool_calls = getattr(message, "tool_calls", None)
            if tool_calls is None and isinstance(message, Mapping):
                tool_calls = message.get("tool_calls")

            content = getattr(message, "content", None)
            if content is None and isinstance(message, Mapping):
                content = message.get("content")

            # 3. Handle native tool_calls
            if tool_calls is not None and len(tool_calls) > 0:
                if len(tool_calls) > 1:
                    return ProviderResult.create_parse_failure(
                        error=f"Phase 1 supports at most one tool call per response, but {len(tool_calls)} were returned",
                        raw_response=response,
                    )

                tc = tool_calls[0]
                func = getattr(tc, "function", None)
                if func is None and isinstance(tc, Mapping):
                    func = tc.get("function", tc)

                if func is None:
                    return ProviderResult.create_parse_failure(
                        error="Tool call is missing function definition",
                        raw_response=response,
                    )

                tool_name = getattr(func, "name", None)
                if tool_name is None and isinstance(func, Mapping):
                    tool_name = func.get("name")

                raw_args = getattr(func, "arguments", None)
                if raw_args is None and isinstance(func, Mapping):
                    raw_args = func.get("arguments")

                if not isinstance(tool_name, str) or not tool_name.strip():
                    return ProviderResult.create_parse_failure(
                        error=f"Invalid tool call shape: tool name must be a non-empty string, got {tool_name!r}",
                        raw_response=response,
                    )

                if raw_args is None:
                    parsed_args: Mapping[str, Any] = {}
                elif isinstance(raw_args, Mapping):
                    parsed_args = dict(raw_args)
                elif isinstance(raw_args, str):
                    try:
                        loaded = json.loads(raw_args)
                    except Exception as e:
                        return ProviderResult.create_parse_failure(
                            error=f"Malformed JSON in tool call arguments: {e}",
                            raw_response=response,
                        )
                    if not isinstance(loaded, Mapping):
                        return ProviderResult.create_parse_failure(
                            error=f"Invalid tool call shape: arguments must parse to a JSON object, got {type(loaded).__name__}",
                            raw_response=response,
                        )
                    parsed_args = dict(loaded)
                else:
                    return ProviderResult.create_parse_failure(
                        error=f"Invalid tool call shape: arguments must be a dict or JSON object, got {type(raw_args).__name__}",
                        raw_response=response,
                    )

                return ProviderResult.create_tool_call(
                    tool_name=tool_name.strip(),
                    arguments=parsed_args,
                    raw_response=response,
                )

            # 4. Handle text or JSON content (when no native tool_calls)
            if content is None:
                return ProviderResult.create_parse_failure(
                    error="Empty model response: no tool calls and no content",
                    raw_response=response,
                )

            text_content = str(content).strip()
            if not text_content:
                return ProviderResult.create_parse_failure(
                    error="Empty model response: content is empty and no tool calls",
                    raw_response=response,
                )

            # Check if content attempted to emit a JSON tool call
            cleaned_json = text_content
            if cleaned_json.startswith("```"):
                lines = cleaned_json.splitlines()
                if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
                    cleaned_json = "\n".join(lines[1:-1]).strip()

            if cleaned_json.startswith("{"):
                try:
                    parsed_json = json.loads(cleaned_json)
                except Exception as e:
                    return ProviderResult.create_parse_failure(
                        error=f"Malformed JSON in model response: {e}",
                        raw_response=response,
                    )

                if isinstance(parsed_json, Mapping):
                    tool_name = parsed_json.get("name")
                    arguments = parsed_json.get("arguments")
                    if isinstance(tool_name, str) and tool_name.strip() and isinstance(arguments, Mapping):
                        return ProviderResult.create_tool_call(
                            tool_name=tool_name.strip(),
                            arguments=dict(arguments),
                            raw_response=response,
                        )

                # JSON content that does not match the exact Phase 1 tool-call format fails explicitly
                return ProviderResult.create_parse_failure(
                    error="JSON content does not match the supported Phase 1 tool-call format ({'name': ..., 'arguments': ...})",
                    raw_response=response,
                )

            # 5. Regular plain text response
            return ProviderResult.create_text(
                text=text_content,
                raw_response=response,
            )
        except Exception as e:
            return ProviderResult.create_parse_failure(
                error=f"Failed to parse model response: {e}",
                raw_response=response,
            )
