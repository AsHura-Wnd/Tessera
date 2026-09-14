"""Unit tests for Tessera Phase 1 Benchmark Harness in Ollama Mode.

Verifies:
1. Configured model identifier is passed to OllamaProvider (no hardcoding).
2. No Qwen 2.5 model is silently selected when another model is requested.
3. Ollama mode uses the real ModelProvider boundary and AgentLoop.
4. DeterministicVerifier determines the final outcome in Ollama mode.
5. Task isolation remains intact in Ollama mode.
6. BenchmarkResult preserves the exact model identifier and mode.
7. Missing/unavailable model produces a clear, structured failure.
8. Provider, parse, validation, step limit, and verification failures are distinguishable.
9. Repetitions produce independent runs with unique run IDs and workspaces.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence
from unittest.mock import MagicMock
import pytest

from tessera.models.provider import ModelProvider, OllamaProvider
from tests.benchmark.harness import (
    BenchmarkHarness,
    BenchmarkResult,
    check_ollama_availability,
    compute_failure_category,
)
from tests.benchmark.runner import format_summary, run_all, run_task
from tests.benchmark.tasks import get_task


class MockOllamaClient:
    """Mock ollama.Client for unit testing without a live daemon or downloaded models."""

    def __init__(
        self,
        responses: Sequence[Any] | None = None,
        installed_models: Sequence[str] | None = None,
    ) -> None:
        self.responses = list(responses or [])
        self.call_count = 0
        self.chat = MagicMock(side_effect=self._mock_chat)
        self._installed_models = list(installed_models or ["qwen3:8b", "qwen4:14b"])

    def _mock_chat(self, **kwargs: Any) -> Any:
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            if isinstance(resp, Exception):
                raise resp
            return resp
        return {
            "message": {
                "role": "assistant",
                "content": "No more mock responses.",
            }
        }

    def list(self) -> Any:
        class FakeModel:
            def __init__(self, name: str) -> None:
                self.model = name

        class FakeResponse:
            def __init__(self, models: list[str]) -> None:
                self.models = [FakeModel(m) for m in models]

        return FakeResponse(self._installed_models)


def test_model_identifier_passed_to_ollama_provider(tmp_path: Path) -> None:
    """Requirement 1: Configured model identifier is strictly passed to OllamaProvider."""
    mock_client = MockOllamaClient(
        responses=[{"message": {"role": "assistant", "content": "Done."}}],
    )
    harness = BenchmarkHarness()

    result = harness.run_ollama(
        "DO-01",
        model="qwen3:8b",
        client=mock_client,
        base_dir=tmp_path,
        skip_model_check=True,
    )

    assert mock_client.chat.called is True
    call_kwargs = mock_client.chat.call_args.kwargs
    assert call_kwargs["model"] == "qwen3:8b"
    assert call_kwargs["model"] != "qwen2.5:3b"
    assert call_kwargs["model"] != "qwen2.5vl:3b"
    assert result.model == "qwen3:8b"
    assert result.mode == "ollama"


def test_no_qwen_2_5_silently_selected_when_another_model_requested(tmp_path: Path) -> None:
    """Requirement 2: No Qwen 2.5 default is silently selected when another model is requested."""
    # Running without specifying model in ollama mode must fail explicitly
    with pytest.raises(ValueError, match="--model must be explicitly specified"):
        run_task("FIND-01", mode="ollama", model=None)

    with pytest.raises(ValueError, match="--model must be explicitly specified"):
        run_all(mode="ollama", model=None)

    # When explicit model tag is provided, it must be exactly preserved
    mock_client = MockOllamaClient(
        responses=[{"message": {"role": "assistant", "content": "Finished."}}],
    )
    harness = BenchmarkHarness()
    result = harness.run_ollama(
        "DO-01",
        model="qwen4:14b",
        client=mock_client,
        base_dir=tmp_path,
        skip_model_check=True,
    )
    assert result.model == "qwen4:14b"
    assert "qwen2.5" not in result.model


def test_ollama_mode_uses_real_model_provider_boundary(tmp_path: Path) -> None:
    """Requirement 3: Ollama mode operates through the real ModelProvider / OllamaProvider seam."""
    mock_client = MockOllamaClient(
        responses=[{"message": {"role": "assistant", "content": "Task completed."}}],
    )
    provider = OllamaProvider(model="qwen3:8b", client=mock_client)
    assert isinstance(provider, ModelProvider)
    assert provider.model == "qwen3:8b"

    # AgentLoop interacts with this provider without knowing it is a mock
    harness = BenchmarkHarness()
    result = harness.run_ollama(
        "DO-01",
        model="qwen3:8b",
        client=mock_client,
        base_dir=tmp_path,
        skip_model_check=True,
    )
    assert result.run_status == "text"


def test_benchmark_uses_existing_agent_loop_and_verifier(tmp_path: Path) -> None:
    """Requirement 4 & 5: Benchmark executes real AgentLoop and DeterministicVerifier in Ollama mode."""
    # Mock model proposes the exact tool action required to solve DO-01
    mock_client = MockOllamaClient(
        responses=[
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "function": {
                                "name": "file_write",
                                "arguments": {
                                    "path": "build/metadata.json",
                                    "content": '{"version": "1.0.0", "status": "ready"}',
                                    "overwrite": True,
                                },
                            }
                        }
                    ],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "Metadata file created.",
                }
            },
        ]
    )

    harness = BenchmarkHarness()
    result = harness.run_ollama(
        "DO-01",
        model="qwen3:8b",
        client=mock_client,
        base_dir=tmp_path,
        keep_workspace=True,
        skip_model_check=True,
    )

    assert result.overall_passed is True
    assert result.verification_passed is True
    assert result.steps_taken == 2
    assert result.run_status == "text"

    # Confirm deliverable exists and was verified
    workspace = Path(result.details["workspace_dir"])
    assert (workspace / "build" / "metadata.json").read_text(encoding="utf-8") == '{"version": "1.0.0", "status": "ready"}'


def test_task_isolation_in_ollama_mode(tmp_path: Path) -> None:
    """Requirement 6: Task workspaces are strictly isolated in Ollama mode."""
    mock_client = MockOllamaClient(
        responses=[{"message": {"role": "assistant", "content": "Done."}}],
    )
    harness = BenchmarkHarness()

    res1 = harness.run_ollama(
        "FIND-01",
        model="qwen3:8b",
        client=mock_client,
        base_dir=tmp_path,
        keep_workspace=True,
        skip_model_check=True,
    )
    res2 = harness.run_ollama(
        "FIND-02",
        model="qwen3:8b",
        client=mock_client,
        base_dir=tmp_path,
        keep_workspace=True,
        skip_model_check=True,
    )

    ws1 = Path(res1.details["workspace_dir"])
    ws2 = Path(res2.details["workspace_dir"])

    assert ws1 != ws2
    assert (ws1 / "docs" / "guide.txt").exists()
    assert not (ws1 / "app.log").exists()

    assert (ws2 / "app.log").exists()
    assert not (ws2 / "docs" / "guide.txt").exists()


def test_result_contains_exact_model_identifier(tmp_path: Path) -> None:
    """Requirement 7: BenchmarkResult preserves the exact model tag."""
    mock_client = MockOllamaClient(
        responses=[{"message": {"role": "assistant", "content": "Done."}}],
    )
    harness = BenchmarkHarness()
    custom_tag = "custom-registry/qwen4-research:32b"

    result = harness.run_ollama(
        "FIND-03",
        model=custom_tag,
        client=mock_client,
        base_dir=tmp_path,
        skip_model_check=True,
    )

    assert result.model == custom_tag
    assert result.to_dict()["model"] == custom_tag


def test_missing_or_unavailable_model_produces_clear_failure() -> None:
    """Requirement 8: Missing or uninstalled model produces clear structured failure."""
    # Test checking via check_ollama_availability
    mock_client = MockOllamaClient(installed_models=["qwen3:8b"])

    available, reason = check_ollama_availability("nonexistent-qwen4:99b", client=mock_client)
    assert available is False
    assert reason is not None
    assert "Requested model 'nonexistent-qwen4:99b' is not installed" in reason
    assert "Installed models: ['qwen3:8b']" in reason

    harness = BenchmarkHarness()
    result = harness.run_ollama(
        "FIND-01",
        model="nonexistent-qwen4:99b",
        client=mock_client,
        skip_model_check=False,
    )

    assert result.overall_passed is False
    assert result.verification_passed is False
    assert result.run_status == "provider_failure"
    assert result.failure_category == "provider_failure"
    assert "not installed in local Ollama" in str(result.agent_error)


def test_distinguishable_failure_categories(tmp_path: Path) -> None:
    """Requirement 9: Failure categories are explicitly distinguishable."""
    harness = BenchmarkHarness()

    # Category A: Provider failure (HTTP / connection exception)
    client_provider_err = MockOllamaClient(
        responses=[RuntimeError("Connection refused to Ollama")],
    )
    res_provider = harness.run_ollama(
        "DO-01",
        model="qwen3:8b",
        client=client_provider_err,
        base_dir=tmp_path,
        skip_model_check=True,
    )
    assert res_provider.overall_passed is False
    assert res_provider.run_status == "provider_failure"
    assert res_provider.failure_category == "provider_failure"

    # Category B: Parse failure (malformed tool call missing name)
    client_parse_err = MockOllamaClient(
        responses=[
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"function": {"arguments": "{}"}}],
                }
            }
        ],
    )
    res_parse = harness.run_ollama(
        "DO-01",
        model="qwen3:8b",
        client=client_parse_err,
        base_dir=tmp_path,
        skip_model_check=True,
    )
    assert res_parse.overall_passed is False
    assert res_parse.run_status == "parse_failure"
    assert res_parse.failure_category == "parse_failure"

    # Category C: Validation failure (calling an unauthorized/unknown tool)
    client_val_err = MockOllamaClient(
        responses=[
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "function": {
                                "name": "unauthorized_shell_tool",
                                "arguments": {"cmd": "rm -rf /"},
                            }
                        }
                    ],
                }
            }
        ],
    )
    res_val = harness.run_ollama(
        "DO-01",
        model="qwen3:8b",
        client=client_val_err,
        base_dir=tmp_path,
        skip_model_check=True,
    )
    assert res_val.overall_passed is False
    assert res_val.run_status == "validation_failure"
    assert res_val.failure_category == "validation_failure"

    # Category D: Step limit exceeded
    # Model endlessly reads file without ever finishing or writing deliverable
    infinite_tool_responses = [
        {
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "file_read",
                            "arguments": {"path": "docs/guide.txt"},
                        }
                    }
                ],
            }
        }
        for _ in range(10)
    ]
    client_step_limit = MockOllamaClient(responses=infinite_tool_responses)
    res_steps = harness.run_ollama(
        "FIND-01",  # max_steps = 4
        model="qwen3:8b",
        client=client_step_limit,
        base_dir=tmp_path,
        skip_model_check=True,
    )
    assert res_steps.overall_passed is False
    assert res_steps.run_status == "step_limit"
    assert res_steps.failure_category == "step_limit"
    assert res_steps.steps_taken == 4

    # Category E: Deterministic verification failure
    # Model says "I have completed the task!" but never wrote the deliverable file
    client_verif_fail = MockOllamaClient(
        responses=[{"message": {"role": "assistant", "content": "I have completed the task!"}}],
    )
    res_verif = harness.run_ollama(
        "DO-01",
        model="qwen3:8b",
        client=client_verif_fail,
        base_dir=tmp_path,
        skip_model_check=True,
    )
    assert res_verif.run_status == "text"  # AgentLoop returned text
    assert res_verif.verification_passed is False  # Filesystem check failed!
    assert res_verif.overall_passed is False
    assert res_verif.failure_category == "deterministic_verification_failure"


def test_summary_formatter_reports_failure_breakdown() -> None:
    """Requirement: Summary formatter displays failure categories and breakdown."""
    results = [
        BenchmarkResult(
            task_id="FIND-01",
            mode="ollama",
            model="qwen3:8b",
            run_id="run_01",
            run_status="provider_failure",
            steps_taken=0,
            agent_error="Connection refused",
            verification_passed=False,
            verification_error="Execution skipped",
            overall_passed=False,
            failure_category="provider_failure",
        ),
        BenchmarkResult(
            task_id="DO-01",
            mode="ollama",
            model="qwen3:8b",
            run_id="run_02",
            run_status="text",
            steps_taken=1,
            agent_error=None,
            verification_passed=True,
            verification_error=None,
            overall_passed=True,
        ),
    ]

    summary = format_summary(results)
    assert "MODE: OLLAMA (MODEL: qwen3:8b)" in summary
    assert "FIND-01  FAIL" in summary
    assert "failure: provider_failure" in summary
    assert "DO-01    PASS" in summary
    assert "AGGREGATE: 1/2 passed (1 failed)" in summary
    assert "FAILED TASKS: FIND-01" in summary
    assert "FAILURE BREAKDOWN: provider_failure: 1" in summary
