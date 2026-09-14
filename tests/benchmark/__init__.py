"""Tessera Phase 1 Benchmark Harness and Specifications."""

from tests.benchmark.harness import (
    BenchmarkHarness,
    BenchmarkResult,
    check_ollama_availability,
)
from tests.benchmark.tasks import BENCHMARK_TASKS, BenchmarkTask, get_task

__all__ = [
    "BENCHMARK_TASKS",
    "BenchmarkHarness",
    "BenchmarkResult",
    "BenchmarkTask",
    "check_ollama_availability",
    "format_summary",
    "get_task",
    "run_all",
    "run_task",
]


def __getattr__(name: str):
    if name in ("run_task", "run_all", "format_summary"):
        from tests.benchmark import runner

        return getattr(runner, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
