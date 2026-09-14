"""Benchmark runner for Tessera Phase 1.

Can run a single named task or all 10 tasks in deterministic mode or Ollama mode,
report individual results, and report aggregate pass/fail metrics.
"""

from __future__ import annotations

import argparse
import sys
from typing import Mapping, Sequence

from tests.benchmark.harness import BenchmarkHarness, BenchmarkResult
from tests.benchmark.tasks import BENCHMARK_TASKS, get_task


def run_task(
    task_id: str,
    mode: str = "deterministic",
    model: str | None = None,
    host: str | None = None,
    options: Mapping[str, Any] | None = None,
    keep_workspace: bool = False,
) -> BenchmarkResult:
    """Execute a single named benchmark task in deterministic or ollama mode."""
    task = get_task(task_id)
    harness = BenchmarkHarness()
    if mode == "deterministic":
        return harness.run_deterministic(task, keep_workspace=keep_workspace)
    elif mode == "ollama":
        if not model:
            raise ValueError("--model must be explicitly specified when running in 'ollama' mode (e.g. --model qwen3:8b)")
        return harness.run_ollama(task, model=model, host=host, options=options, keep_workspace=keep_workspace)
    else:
        raise ValueError(f"Unknown benchmark mode: '{mode}'. Supported modes: 'deterministic', 'ollama'")


def run_all(
    mode: str = "deterministic",
    model: str | None = None,
    host: str | None = None,
    options: Mapping[str, Any] | None = None,
    keep_workspaces: bool = False,
    repeat: int = 1,
) -> list[BenchmarkResult]:
    """Execute all 10 benchmark tasks sequentially in deterministic or ollama mode."""
    if repeat < 1:
        raise ValueError(f"repeat must be at least 1, got {repeat}")
    if mode == "ollama" and not model:
        raise ValueError("--model must be explicitly specified when running in 'ollama' mode (e.g. --model qwen3:8b)")

    harness = BenchmarkHarness()
    results: list[BenchmarkResult] = []
    for _ in range(repeat):
        for task in BENCHMARK_TASKS.values():
            if mode == "deterministic":
                res = harness.run_deterministic(task, keep_workspace=keep_workspaces)
            elif mode == "ollama":
                assert model is not None
                res = harness.run_ollama(
                    task,
                    model=model,
                    host=host,
                    options=options,
                    keep_workspace=keep_workspaces,
                )
            else:
                raise ValueError(f"Unknown benchmark mode: '{mode}'")
            results.append(res)
    return results


def format_summary(results: Sequence[BenchmarkResult]) -> str:
    """Format per-task outcomes and aggregate pass/fail statistics."""
    if not results:
        return "No benchmark results to display."

    first_res = results[0]
    mode = first_res.mode.upper()
    model = first_res.model or "scripted"

    lines: list[str] = [
        "=" * 70,
        f"TESSERA BENCHMARK REPORT -- MODE: {mode} (MODEL: {model})",
        "=" * 70,
    ]

    total = len(results)
    passed = 0
    failed_tasks: list[str] = []
    category_counts: dict[str, int] = {}

    for res in results:
        status_label = "PASS" if res.overall_passed else "FAIL"
        if res.overall_passed:
            passed += 1
        else:
            failed_tasks.append(res.task_id)
            cat = res.failure_category or "unknown_failure"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        detail_info = f"steps: {res.steps_taken}, status: {res.run_status}"
        if not res.overall_passed:
            if res.failure_category:
                detail_info += f", failure: {res.failure_category}"
            if res.agent_error:
                detail_info += f", error: {res.agent_error}"
            elif not res.verification_passed and res.verification_error:
                detail_info += f", verif_error: {res.verification_error}"

        lines.append(f"{res.task_id:<8} {status_label:<6} ({detail_info})")

    lines.append("=" * 70)
    lines.append(f"AGGREGATE: {passed}/{total} passed ({total - passed} failed)")
    if failed_tasks:
        lines.append(f"FAILED TASKS: {', '.join(failed_tasks)}")
        breakdown_str = ", ".join(f"{k}: {v}" for k, v in sorted(category_counts.items()))
        lines.append(f"FAILURE BREAKDOWN: {breakdown_str}")
    lines.append("=" * 70)

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for benchmark execution."""
    parser = argparse.ArgumentParser(description="Tessera Phase 1 Benchmark Runner")
    parser.add_argument(
        "--mode",
        choices=["deterministic", "ollama"],
        default="deterministic",
        help="Benchmark execution mode (default: deterministic)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Ollama model identifier (required when --mode ollama, e.g. qwen3:8b, qwen4:14b)",
    )
    parser.add_argument(
        "--task",
        "-t",
        type=str,
        default=None,
        help="Run a specific benchmark task ID (e.g. FIND-01)",
    )
    parser.add_argument(
        "--repeat",
        "-r",
        type=int,
        default=1,
        help="Number of independent repetitions to run (default: 1)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Ollama host URL (optional, default: localhost)",
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Preserve workspace and trajectory directories after execution",
    )

    args = parser.parse_args(argv)

    if args.mode == "ollama" and not args.model:
        parser.error("--model is required when --mode is 'ollama'. Specify an installed Ollama model tag (e.g. --model qwen3:8b)")

    if args.task:
        results: list[BenchmarkResult] = []
        for _ in range(args.repeat):
            res = run_task(
                args.task,
                mode=args.mode,
                model=args.model,
                host=args.host,
                keep_workspace=args.keep_workspace,
            )
            results.append(res)
        summary = format_summary(results)
        print(summary)
        return 0 if all(r.overall_passed for r in results) else 1

    results = run_all(
        mode=args.mode,
        model=args.model,
        host=args.host,
        keep_workspaces=args.keep_workspace,
        repeat=args.repeat,
    )
    summary = format_summary(results)
    print(summary)
    return 0 if all(r.overall_passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
