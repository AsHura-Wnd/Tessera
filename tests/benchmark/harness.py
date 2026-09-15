"""Benchmark harness for Tessera Phase 1.

Executes canonical benchmark tasks against isolated workspaces using either:
1. Deterministic Mode: A scripted ModelProvider (evaluates infrastructure integrity).
2. Ollama Mode: An actual Ollama-backed model (evaluates real model capability).

Verifies the resulting filesystem state using the frozen DeterministicVerifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping, Sequence
import uuid

from tessera.agent.loop import AgentLoop, RunResult, RunStatus
from tessera.models.provider import ModelProvider, OllamaProvider, ProviderResult
from tessera.storage.trajectory import TrajectoryRecorder
from tessera.verification.verifier import DeterministicVerifier, VerificationResult
from tests.benchmark.tasks import BenchmarkTask, get_task


class ScriptedProvider(ModelProvider):
    """Deterministic mock provider that emits a predetermined sequence of ProviderResults.

    Does not implement or simulate tool logic. It merely serves the exact model decisions
    (tool calls or text) that a model would propose.
    """

    def __init__(self, responses: Sequence[ProviderResult]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.call_history: list[dict[str, Any]] = []

    @property
    def responses_remaining(self) -> int:
        return max(0, len(self._responses) - self._index)

    def generate(
        self,
        prompt: str,
        tools: Sequence[Mapping[str, Any]] | None = None,
        context: Sequence[Mapping[str, Any]] | None = None,
    ) -> ProviderResult:
        self.call_history.append({
            "step": self._index + 1,
            "prompt": prompt,
            "tools_count": len(tools) if tools else 0,
            "context_count": len(context) if context else 0,
        })
        if self._index < len(self._responses):
            res = self._responses[self._index]
            self._index += 1
            return res
        return ProviderResult.create_text("Scripted provider exhausted.")


def check_ollama_availability(
    model: str,
    host: str | None = None,
    client: Any | None = None,
) -> tuple[bool, str | None]:
    """Check whether local Ollama is running and the specified model is installed."""
    try:
        if client is not None:
            c = client
        else:
            import ollama
            c = ollama.Client(host=host) if host else ollama.Client()

        models_resp = c.list()
        raw_models = getattr(models_resp, "models", None)
        if raw_models is None and isinstance(models_resp, dict):
            raw_models = models_resp.get("models", [])

        installed_models: list[str] = []
        for m in (raw_models or []):
            name = getattr(m, "model", None) or getattr(m, "name", None)
            if name is None and isinstance(m, dict):
                name = m.get("model") or m.get("name")
            if name:
                installed_models.append(str(name))

    except Exception as exc:
        return False, f"Ollama daemon is not reachable: {exc}"

    # Match exact model tag, or with/without ':latest'
    matches = any(
        m == model
        or m == f"{model}:latest"
        or (model.endswith(":latest") and m == model[:-7])
        for m in installed_models
    )
    if not matches:
        return False, (
            f"Requested model '{model}' is not installed in local Ollama. "
            f"Installed models: {installed_models}. "
            f"Please run 'ollama pull {model}' to install it."
        )

    return True, None


def compute_failure_category(
    overall_passed: bool,
    run_status: str,
    verification_passed: bool,
    agent_error: str | None = None,
) -> str | None:
    """Compute an explicit failure category for transparent error attribution."""
    if overall_passed:
        return None
    if run_status == RunStatus.PROVIDER_FAILURE.value:
        return "provider_failure"
    if run_status == RunStatus.PARSE_FAILURE.value:
        return "parse_failure"
    if run_status == RunStatus.VALIDATION_FAILURE.value:
        return "validation_failure"
    if run_status == RunStatus.AUTHORIZATION_FAILURE.value:
        return "authorization_failure"
    if run_status == RunStatus.EXECUTION_FAILURE.value:
        return "execution_failure"
    if run_status == RunStatus.STEP_LIMIT.value:
        return "step_limit"
    if run_status == "exception":
        return "exception"
    if not verification_passed:
        return "deterministic_verification_failure"
    return "unknown_failure"


@dataclass(frozen=True)
class BenchmarkResult:
    """Minimal serializable outcome of a benchmark task execution."""

    task_id: str
    mode: str
    run_id: str
    run_status: str
    steps_taken: int
    agent_error: str | None
    verification_passed: bool
    verification_error: str | None
    overall_passed: bool
    model: str | None = None
    failure_category: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to plain JSON-serializable dictionary."""
        return {
            "task_id": self.task_id,
            "mode": self.mode,
            "model": self.model,
            "run_id": self.run_id,
            "run_status": self.run_status,
            "steps_taken": self.steps_taken,
            "agent_error": self.agent_error,
            "verification_passed": self.verification_passed,
            "verification_error": self.verification_error,
            "overall_passed": self.overall_passed,
            "failure_category": self.failure_category,
            "details": self.details,
        }


class BenchmarkHarness:
    """External evaluation harness for running benchmark tasks."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def setup_fixture(task: BenchmarkTask, workspace_dir: Path) -> None:
        """Create the isolated fixture tree specified by the benchmark task."""
        workspace_dir.mkdir(parents=True, exist_ok=True)
        for rel_path, content in task.fixture_files.items():
            target_path = workspace_dir / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")

    def _execute_task(
        self,
        task: BenchmarkTask,
        provider: ModelProvider,
        mode: str,
        model: str,
        base_dir: Path | None = None,
        keep_workspace: bool = False,
    ) -> BenchmarkResult:
        """Execute a task in an isolated workspace with AgentLoop and verify."""
        is_temporary = base_dir is None
        if is_temporary:
            temp_root = tempfile.mkdtemp(prefix=f"tessera_bm_{mode}_{task.task_id.lower().replace('-', '_')}_")
            root_dir = Path(temp_root).resolve()
        else:
            unique_run = uuid.uuid4().hex[:8]
            root_dir = (Path(base_dir).resolve() / f"{task.task_id}_{mode}_{unique_run}")
            root_dir.mkdir(parents=True, exist_ok=True)

        workspace_dir = root_dir / "workspace"
        traj_dir = root_dir / "trajectories"
        traj_dir.mkdir(parents=True, exist_ok=True)

        run_id = f"run_{task.task_id.lower().replace('-', '_')}_{uuid.uuid4().hex[:6]}"
        run_status = "unknown"
        steps_taken = 0
        agent_error: str | None = None
        verification_passed = False
        verification_error: str | None = None
        trajectory_file: str | None = None

        try:
            # 1. Setup fixture files
            self.setup_fixture(task, workspace_dir)

            # 2. Setup recorder
            recorder = TrajectoryRecorder(output_dir=traj_dir)

            # 3. Setup and execute AgentLoop
            if task.task_type == "RUN" or task.task_id.startswith("RUN-"):
                from tessera.tools.authorization import get_phase_2_authorizer
                from tessera.tools.registry import get_phase_2_registry
                from tessera.tools.validator import Phase2ToolValidator

                p2_registry = get_phase_2_registry()
                p2_validator = Phase2ToolValidator(workspace_root=workspace_dir, registry=p2_registry)
                p2_authorizer = get_phase_2_authorizer()
                loop = AgentLoop(
                    provider=provider,
                    workspace_root=workspace_dir,
                    registry=p2_registry,
                    validator=p2_validator,
                    authorizer=p2_authorizer,
                    recorder=recorder,
                    max_steps=task.max_steps,
                )
            else:
                loop = AgentLoop(
                    provider=provider,
                    workspace_root=workspace_dir,
                    recorder=recorder,
                    max_steps=task.max_steps,
                )
            run_result: RunResult = loop.run(goal=task.goal, run_id=run_id)

            run_status = run_result.status.value
            steps_taken = run_result.steps_taken
            agent_error = run_result.error

            # 4. Verify filesystem state with DeterministicVerifier
            verifier = DeterministicVerifier(workspace_root=workspace_dir)
            verif_result: VerificationResult = verifier.verify(task.verification_spec)

            verification_passed = verif_result.passed
            verification_error = verif_result.error

            # Locate recorded trajectory file if any
            if recorder.active_file_path and recorder.active_file_path.exists():
                trajectory_file = str(recorder.active_file_path)

        except Exception as exc:
            run_status = "exception"
            agent_error = f"Unhandled exception during benchmark execution: {exc}"
            verification_passed = False
            verification_error = "Verification not reached or failed due to exception"
        finally:
            if is_temporary and not keep_workspace:
                shutil.rmtree(root_dir, ignore_errors=True)

        overall_passed = bool(
            verification_passed
            and run_status == RunStatus.TEXT.value
            and agent_error is None
        )

        failure_category = compute_failure_category(
            overall_passed=overall_passed,
            run_status=run_status,
            verification_passed=verification_passed,
            agent_error=agent_error,
        )

        details: dict[str, Any] = {
            "task_name": task.name,
            "max_steps": task.max_steps,
        }
        if keep_workspace:
            details["workspace_dir"] = str(workspace_dir)
            details["trajectory_dir"] = str(traj_dir)
        if trajectory_file:
            details["trajectory_file"] = trajectory_file

        return BenchmarkResult(
            task_id=task.task_id,
            mode=mode,
            model=model,
            run_id=run_id,
            run_status=run_status,
            steps_taken=steps_taken,
            agent_error=agent_error,
            verification_passed=verification_passed,
            verification_error=verification_error,
            overall_passed=overall_passed,
            failure_category=failure_category,
            details=details,
        )

    def run_deterministic(
        self,
        task_or_id: BenchmarkTask | str,
        base_dir: Path | None = None,
        keep_workspace: bool = False,
        custom_provider: ModelProvider | None = None,
    ) -> BenchmarkResult:
        """Execute a benchmark task in deterministic scripted mode."""
        task = get_task(task_or_id) if isinstance(task_or_id, str) else task_or_id
        provider = custom_provider or ScriptedProvider(responses=task.deterministic_responses)
        return self._execute_task(
            task=task,
            provider=provider,
            mode="deterministic",
            model="scripted",
            base_dir=base_dir,
            keep_workspace=keep_workspace,
        )

    def run_ollama(
        self,
        task_or_id: BenchmarkTask | str,
        model: str,
        host: str | None = None,
        options: Mapping[str, Any] | None = None,
        client: Any | None = None,
        base_dir: Path | None = None,
        keep_workspace: bool = False,
        skip_model_check: bool = False,
    ) -> BenchmarkResult:
        """Execute a benchmark task using an actual Ollama-backed model."""
        task = get_task(task_or_id) if isinstance(task_or_id, str) else task_or_id

        if not model or not isinstance(model, str) or not model.strip():
            raise ValueError("A non-empty model identifier must be explicitly provided for Ollama mode (e.g. 'qwen3:8b')")

        # Check model availability unless explicitly bypassed (e.g. in unit tests with mock client)
        if not skip_model_check:
            available, reason = check_ollama_availability(model=model, host=host, client=client)
            if not available:
                return BenchmarkResult(
                    task_id=task.task_id,
                    mode="ollama",
                    model=model,
                    run_id=f"run_{task.task_id.lower().replace('-', '_')}_unavailable",
                    run_status=RunStatus.PROVIDER_FAILURE.value,
                    steps_taken=0,
                    agent_error=reason,
                    verification_passed=False,
                    verification_error="Execution skipped: model or Ollama server unavailable",
                    overall_passed=False,
                    failure_category="provider_failure",
                    details={
                        "task_name": task.name,
                        "max_steps": task.max_steps,
                        "reason": reason,
                    },
                )

        provider = OllamaProvider(
            model=model,
            host=host,
            client=client,
            options=options,
        )

        return self._execute_task(
            task=task,
            provider=provider,
            mode="ollama",
            model=model,
            base_dir=base_dir,
            keep_workspace=keep_workspace,
        )
