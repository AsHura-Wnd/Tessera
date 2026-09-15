"""Tests for Phase 2 Evaluation Benchmark Fixtures (EVAL-01, EVAL-02, EVAL-03).

Verifies that:
1. EVAL-01 fixture test_calc.py initially fails against calc.py, passes when repaired,
   and deterministic benchmark execution succeeds end-to-end.
2. EVAL-02 fixture check_config.py initially fails against config.json, passes when repaired,
   and deterministic benchmark execution succeeds end-to-end.
3. EVAL-03 fixture app.py initially fails against expired token.txt, logs/deploy.log contains
   the active token, app.py passes when updated, and deterministic benchmark execution succeeds end-to-end.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from tests.benchmark.harness import BenchmarkHarness
from tests.benchmark.tasks import get_task


def test_eval_01_fixture_validity_and_deterministic_execution(tmp_path: Path) -> None:
    """EVAL-01: Proves initial failure, valid repair, and deterministic pass."""
    task = get_task("EVAL-01")
    workspace = tmp_path / "eval01_ws"

    # 1. Setup fixture files
    BenchmarkHarness.setup_fixture(task, workspace)
    assert (workspace / "calc.py").is_file()
    assert (workspace / "test_calc.py").is_file()
    assert not (workspace / "status.txt").exists()

    # 2. Verify initial test execution fails as intended
    proc_initial = subprocess.run(
        [sys.executable, "test_calc.py"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
    )
    assert proc_initial.returncode != 0
    assert "AssertionError" in proc_initial.stderr or proc_initial.returncode != 0

    # 3. Verify that correcting calc.py allows test_calc.py to pass
    (workspace / "calc.py").write_text("def multiply(a, b):\n    return a * b\n", encoding="utf-8")
    proc_repaired = subprocess.run(
        [sys.executable, "test_calc.py"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
    )
    assert proc_repaired.returncode == 0
    assert "TESTS_PASSED" in proc_repaired.stdout

    # 4. Run deterministic benchmark through harness
    harness = BenchmarkHarness()
    result = harness.run_deterministic(task, base_dir=tmp_path, keep_workspace=True)

    assert result.overall_passed is True
    assert result.run_status == "text"
    assert result.verification_passed is True
    assert result.verification_error is None
    assert result.agent_error is None

    final_ws = Path(result.details["workspace_dir"])
    assert (final_ws / "status.txt").read_text(encoding="utf-8") == "TESTS_PASSED\n"
    # Final workspace tests pass
    proc_final = subprocess.run(
        [sys.executable, "test_calc.py"],
        cwd=str(final_ws),
        capture_output=True,
        text=True,
    )
    assert proc_final.returncode == 0
    assert "TESTS_PASSED" in proc_final.stdout


def test_eval_02_fixture_validity_and_deterministic_execution(tmp_path: Path) -> None:
    """EVAL-02: Proves initial failure, valid repair, and deterministic pass."""
    task = get_task("EVAL-02")
    workspace = tmp_path / "eval02_ws"

    # 1. Setup fixture files
    BenchmarkHarness.setup_fixture(task, workspace)
    assert (workspace / "config.json").is_file()
    assert (workspace / "check_config.py").is_file()
    assert not (workspace / "status.txt").exists()

    # 2. Verify initial config check fails
    proc_initial = subprocess.run(
        [sys.executable, "check_config.py"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
    )
    assert proc_initial.returncode == 1
    assert "Invalid environment: development" in proc_initial.stderr

    # 3. Verify updating config.json allows check_config.py to pass
    repaired_config = (
        '{\n'
        '  "service_name": "gateway",\n'
        '  "port": 8080,\n'
        '  "environment": "production"\n'
        '}\n'
    )
    (workspace / "config.json").write_text(repaired_config, encoding="utf-8")
    proc_repaired = subprocess.run(
        [sys.executable, "check_config.py"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
    )
    assert proc_repaired.returncode == 0
    assert "CONFIG_VALID" in proc_repaired.stdout

    # 4. Run deterministic benchmark through harness
    harness = BenchmarkHarness()
    result = harness.run_deterministic(task, base_dir=tmp_path, keep_workspace=True)

    assert result.overall_passed is True
    assert result.run_status == "text"
    assert result.verification_passed is True
    assert result.verification_error is None
    assert result.agent_error is None

    final_ws = Path(result.details["workspace_dir"])
    assert (final_ws / "status.txt").read_text(encoding="utf-8") == "CONFIG_REPAIRED\n"
    proc_final = subprocess.run(
        [sys.executable, "check_config.py"],
        cwd=str(final_ws),
        capture_output=True,
        text=True,
    )
    assert proc_final.returncode == 0
    assert "CONFIG_VALID" in proc_final.stdout


def test_eval_03_fixture_validity_and_deterministic_execution(tmp_path: Path) -> None:
    """EVAL-03: Proves initial failure, log-based token resolution, and deterministic pass."""
    task = get_task("EVAL-03")
    workspace = tmp_path / "eval03_ws"

    # 1. Setup fixture files
    BenchmarkHarness.setup_fixture(task, workspace)
    assert (workspace / "app.py").is_file()
    assert (workspace / "token.txt").is_file()
    assert (workspace / "logs" / "deploy.log").is_file()
    assert not (workspace / "status.txt").exists()

    # 2. Verify initial auth check fails
    proc_initial = subprocess.run(
        [sys.executable, "app.py"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
    )
    assert proc_initial.returncode == 1
    assert "Authentication failed for token: 'OLD-EXPIRED-TOKEN-000'" in proc_initial.stderr

    # 3. Verify log contains the active token
    log_content = (workspace / "logs" / "deploy.log").read_text(encoding="utf-8")
    assert "Active valid token issued: SEC-ALPHA-99482-PROD" in log_content

    # 4. Verify writing active token allows app.py to pass
    (workspace / "token.txt").write_text("SEC-ALPHA-99482-PROD\n", encoding="utf-8")
    proc_repaired = subprocess.run(
        [sys.executable, "app.py"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
    )
    assert proc_repaired.returncode == 0
    assert "AUTH_SUCCESS" in proc_repaired.stdout

    # 5. Run deterministic benchmark through harness
    harness = BenchmarkHarness()
    result = harness.run_deterministic(task, base_dir=tmp_path, keep_workspace=True)

    assert result.overall_passed is True
    assert result.run_status == "text"
    assert result.verification_passed is True
    assert result.verification_error is None
    assert result.agent_error is None

    final_ws = Path(result.details["workspace_dir"])
    assert (final_ws / "status.txt").read_text(encoding="utf-8") == "TOKEN_REPAIRED\n"
    proc_final = subprocess.run(
        [sys.executable, "app.py"],
        cwd=str(final_ws),
        capture_output=True,
        text=True,
    )
    assert proc_final.returncode == 0
    assert "AUTH_SUCCESS" in proc_final.stdout
