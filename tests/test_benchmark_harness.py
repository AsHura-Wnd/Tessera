"""Tests for the Tessera Phase 1 Benchmark Harness (Deterministic Mode).

Verifies the 10 critical harness requirements:
1. Task fixture creation accuracy.
2. Scripted provider driving task through AgentLoop.
3. Tool execution actually occurring (not direct benchmark file mutation).
4. DeterministicVerifier determining the final result.
5. Deliberately broken expected output producing benchmark FAIL.
6. Task workspace isolation.
7. Deterministic repeatability across repeated runs.
8. All 10 benchmark specifications loadable with valid schemas.
9. Benchmark runner executing all 10 tasks to PASS.
10. Benchmark execution leaving repository source tree unmodified.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import pytest

from tessera.models.provider import ProviderResult
from tessera.verification.verifier import DeterministicVerifier, VerificationSpec
from tests.benchmark.harness import BenchmarkHarness, BenchmarkResult, ScriptedProvider
from tests.benchmark.runner import format_summary, run_all, run_task
from tests.benchmark.tasks import BENCHMARK_TASKS, BenchmarkTask, get_task, list_tasks


def test_01_fixture_creation_accuracy(tmp_path: Path) -> None:
    """Requirement 1: A known benchmark task fixture is created correctly."""
    task = get_task("FIND-01")
    workspace = tmp_path / "workspace"
    BenchmarkHarness.setup_fixture(task, workspace)

    assert (workspace / "docs" / "guide.txt").is_file()
    assert (workspace / "docs" / "guide.txt").read_text(encoding="utf-8") == "User manual for the service.\n"

    assert (workspace / "src" / "core" / "app.py").is_file()
    assert "DB_PATH = 'storage/backups/2026/database.sqlite'" in (workspace / "src" / "core" / "app.py").read_text(encoding="utf-8")

    assert (workspace / "storage" / "backups" / "2026" / "database.sqlite").is_file()
    assert (workspace / "storage" / "backups" / "2026" / "database.sqlite").read_text(encoding="utf-8") == "SQLITE_BINARY_DUMMY_HEADER\n"

    # Deliverable artifact must NOT exist initially
    assert not (workspace / "found_db.txt").exists()


def test_02_scripted_provider_drives_agent_loop(tmp_path: Path) -> None:
    """Requirement 2: A deterministic scripted provider can drive a task through AgentLoop."""
    task = get_task("DO-01")
    harness = BenchmarkHarness()
    result = harness.run_deterministic(task, base_dir=tmp_path, keep_workspace=True)

    assert result.overall_passed is True
    assert result.run_status == "text"
    assert result.steps_taken == 2
    assert result.agent_error is None
    assert result.verification_passed is True
    assert result.verification_error is None


def test_03_tool_execution_actually_occurs_and_records_trajectory(tmp_path: Path) -> None:
    """Requirement 3: Tool execution actually occurs rather than the benchmark mutating files directly."""
    task = get_task("FIND-01")
    harness = BenchmarkHarness()
    result = harness.run_deterministic(task, base_dir=tmp_path, keep_workspace=True)

    assert result.overall_passed is True
    traj_file_path = result.details.get("trajectory_file")
    assert traj_file_path is not None
    traj_path = Path(traj_file_path)
    assert traj_path.exists()

    events = [json.loads(line) for line in traj_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Verify trajectory events recorded the actual tool validations and executions
    val_events = [e for e in events if e.get("event_type") == "validation"]
    exec_events = [e for e in events if e.get("event_type") == "execution"]

    assert len(val_events) == 2
    assert val_events[0]["tool_name"] == "file_find"
    assert val_events[0]["accepted"] is True
    assert val_events[1]["tool_name"] == "file_write"
    assert val_events[1]["accepted"] is True

    assert len(exec_events) == 2
    assert exec_events[0]["tool_name"] == "file_find"
    assert exec_events[0]["success"] is True
    assert exec_events[1]["tool_name"] == "file_write"
    assert exec_events[1]["success"] is True

    # The file found_db.txt exists because file_write executed
    workspace = Path(result.details["workspace_dir"])
    assert (workspace / "found_db.txt").read_text(encoding="utf-8") == "storage/backups/2026/database.sqlite\n"


def test_04_deterministic_verifier_determines_final_result(tmp_path: Path) -> None:
    """Requirement 4: DeterministicVerifier determines the final result."""
    task = get_task("DO-03")
    harness = BenchmarkHarness()
    result = harness.run_deterministic(task, base_dir=tmp_path, keep_workspace=True)

    # Cross-check directly with DeterministicVerifier on the workspace
    workspace = Path(result.details["workspace_dir"])
    direct_verifier = DeterministicVerifier(workspace)
    direct_verif_result = direct_verifier.verify(task.verification_spec)

    assert direct_verif_result.passed is True
    assert result.verification_passed == direct_verif_result.passed
    assert result.overall_passed is True


def test_05_deliberately_broken_expected_output_produces_fail(tmp_path: Path) -> None:
    """Requirement 5: A deliberately broken expected output produces benchmark FAIL."""
    task = get_task("FIND-03")
    harness = BenchmarkHarness()

    # Custom provider that writes the WRONG port number (distractor 3000 instead of 9443)
    broken_responses = [
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "config/deploy.env"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "port.txt",
                "content": "3000\n",  # WRONG VALUE!
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Extracted port 3000."),
    ]
    broken_provider = ScriptedProvider(responses=broken_responses)

    result = harness.run_deterministic(
        task,
        base_dir=tmp_path,
        keep_workspace=True,
        custom_provider=broken_provider,
    )

    # Verification MUST fail and overall outcome MUST be FAIL
    assert result.verification_passed is False
    assert result.overall_passed is False
    assert result.verification_error is not None
    assert "port.txt" in result.verification_error


def test_05b_mutating_source_fixture_produces_fail(tmp_path: Path) -> None:
    """Requirement 5b: Mutating an initial fixture file also produces benchmark FAIL."""
    task = get_task("DO-04")
    harness = BenchmarkHarness()

    # Custom provider that writes active users, but also corrupts raw_users.txt
    corrupting_responses = [
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "data/raw_users.txt"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "data/active_users.txt",
                "content": "alice\ncarol\neve\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "data/raw_users.txt",
                "content": "CORRUPTED CONTENT\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Done filtering."),
    ]
    broken_provider = ScriptedProvider(responses=corrupting_responses)

    result = harness.run_deterministic(
        task,
        base_dir=tmp_path,
        keep_workspace=True,
        custom_provider=broken_provider,
    )

    assert result.verification_passed is False
    assert result.overall_passed is False
    assert result.verification_error is not None
    assert "data/raw_users.txt" in result.verification_error


def test_06_task_workspace_isolation(tmp_path: Path) -> None:
    """Requirement 6: Task workspaces are isolated."""
    harness = BenchmarkHarness()

    res1 = harness.run_deterministic("FIND-01", base_dir=tmp_path, keep_workspace=True)
    res2 = harness.run_deterministic("FIND-02", base_dir=tmp_path, keep_workspace=True)

    ws1 = Path(res1.details["workspace_dir"])
    ws2 = Path(res2.details["workspace_dir"])

    assert ws1 != ws2
    assert (ws1 / "found_db.txt").exists()
    assert not (ws1 / "log_inventory.txt").exists()

    assert (ws2 / "log_inventory.txt").exists()
    assert not (ws2 / "found_db.txt").exists()
    assert not (ws2 / "storage" / "backups" / "2026" / "database.sqlite").exists()


def test_07_repeated_deterministic_runs_produce_same_outcome() -> None:
    """Requirement 7: Repeated deterministic runs produce the same outcome."""
    task = get_task("DO-05")
    harness = BenchmarkHarness()

    results: list[BenchmarkResult] = []
    for _ in range(3):
        results.append(harness.run_deterministic(task))

    for res in results:
        assert res.overall_passed is True
        assert res.verification_passed is True
        assert res.run_status == "text"
        assert res.steps_taken == 4
        assert res.agent_error is None
        assert res.verification_error is None


def test_08_all_benchmark_specifications_loadable() -> None:
    """Requirement 8: All benchmark specifications can be loaded by the harness."""
    assert len(BENCHMARK_TASKS) == 12
    expected_ids = [
        "FIND-01", "FIND-02", "FIND-03", "FIND-04", "FIND-05",
        "DO-01", "DO-02", "DO-03", "DO-04", "DO-05",
        "RUN-01", "RUN-02",
    ]
    assert list(BENCHMARK_TASKS.keys()) == expected_ids

    all_tasks = list_tasks()
    assert len(all_tasks) == 12

    for task in all_tasks:
        assert task.task_id in expected_ids
        assert task.task_type in ("FIND", "DO", "RUN")
        assert len(task.name) > 0
        assert len(task.goal) > 0
        assert task.max_steps >= 1
        assert len(task.deterministic_responses) >= 1
        assert len(task.deterministic_responses) <= task.max_steps
        assert isinstance(task.verification_spec, VerificationSpec)
        assert get_task(task.task_id) is task


def test_09_runner_executes_all_deterministic_tasks() -> None:
    """Requirement 9: The runner can execute all deterministic tasks to PASS."""
    results = run_all()
    assert len(results) == 12

    for res in results:
        task = get_task(res.task_id)
        assert res.overall_passed is True, f"Task {res.task_id} failed: {res.verification_error or res.agent_error}"
        assert res.verification_passed is True
        assert res.run_status == "text"
        assert res.steps_taken <= task.max_steps
        assert res.agent_error is None
        assert res.verification_error is None

    summary = format_summary(results)
    assert "AGGREGATE: 12/12 passed (0 failed)" in summary


def test_10_benchmark_execution_does_not_modify_repo_tree() -> None:
    """Requirement 10: No benchmark execution modifies the repository source tree."""
    # Check git status before
    status_proc = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    status_before = status_proc.stdout

    # Run a full benchmark suite
    results = run_all()
    assert len(results) == len(BENCHMARK_TASKS)
    assert all(r.overall_passed for r in results)

    # Check git status after
    status_proc_after = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    status_after = status_proc_after.stdout

    # No files should have been added, modified, or deleted by the benchmark execution
    assert status_after == status_before
