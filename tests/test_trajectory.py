"""Unit tests for the isolated TrajectoryRecorder."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from tessera.storage.trajectory import TrajectoryRecorder


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create a temporary base output directory."""
    d = tmp_path / "tessera_output"
    d.mkdir()
    return d


def test_validation_event_appended_and_read_back_as_json(output_dir: Path) -> None:
    recorder = TrajectoryRecorder(output_dir=output_dir)
    run_file = recorder.start_run("run_validation_test")

    recorder.record_validation(
        tool_name="mock_tool",
        arguments={"path": "file.txt", "line": 42},
        result={"is_valid": True, "error": None},
    )

    assert run_file.exists()
    lines = run_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    event = json.loads(lines[0])
    assert event["event_type"] == "validation"
    assert event["tool_name"] == "mock_tool"
    assert event["arguments"] == {"path": "file.txt", "line": 42}
    assert event["accepted"] is True
    assert event["error"] is None
    assert "timestamp" in event


def test_execution_event_appended_and_read_back_as_json(output_dir: Path) -> None:
    recorder = TrajectoryRecorder(output_dir=output_dir)
    run_file = recorder.start_run("run_execution_test")

    recorder.record_execution(
        tool_name="mock_tool",
        arguments={"path": "file.txt"},
        result={"success": True, "output": "execution finished successfully", "error": None},
    )

    assert run_file.exists()
    lines = run_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    event = json.loads(lines[0])
    assert event["event_type"] == "execution"
    assert event["tool_name"] == "mock_tool"
    assert event["arguments"] == {"path": "file.txt"}
    assert event["success"] is True
    assert event["output"] == "execution finished successfully"
    assert event["error"] is None
    assert "timestamp" in event


def test_multiple_events_recorded_in_correct_order(output_dir: Path) -> None:
    recorder = TrajectoryRecorder(output_dir=output_dir)
    run_file = recorder.start_run("run_order_test")

    recorder.record_validation("tool_1", {"step": 1}, {"is_valid": True})
    recorder.record_execution("tool_1", {"step": 1}, {"success": True, "output": "step 1 done"})
    recorder.record_validation("tool_2", {"step": 2}, {"is_valid": False, "error": "validation failed"})
    recorder.record_execution("tool_2", {"step": 2}, {"success": False, "error": "execution failed"})

    lines = run_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4

    events = [json.loads(line) for line in lines]
    assert [e["event_type"] for e in events] == ["validation", "execution", "validation", "execution"]
    assert [e["tool_name"] for e in events] == ["tool_1", "tool_1", "tool_2", "tool_2"]
    assert [e["arguments"]["step"] for e in events] == [1, 1, 2, 2]
    assert events[0]["accepted"] is True
    assert events[1]["success"] is True
    assert events[2]["accepted"] is False
    assert events[2]["error"] == "validation failed"
    assert events[3]["success"] is False
    assert events[3]["error"] == "execution failed"


def test_different_run_ids_produce_separate_files_without_contamination(output_dir: Path) -> None:
    recorder = TrajectoryRecorder(output_dir=output_dir)

    file_a = recorder.start_run("run_a")
    recorder.record_validation("tool_a", {"id": "A"}, {"is_valid": True})

    file_b = recorder.start_run("run_b")
    recorder.record_validation("tool_b", {"id": "B"}, {"is_valid": True})

    assert file_a != file_b
    assert file_a.parent == output_dir / "trajectories"
    assert file_b.parent == output_dir / "trajectories"
    assert file_a.exists()
    assert file_b.exists()

    events_a = [json.loads(line) for line in file_a.read_text(encoding="utf-8").splitlines()]
    events_b = [json.loads(line) for line in file_b.read_text(encoding="utf-8").splitlines()]

    assert len(events_a) == 1
    assert events_a[0]["tool_name"] == "tool_a"
    assert events_a[0]["arguments"] == {"id": "A"}

    assert len(events_b) == 1
    assert events_b[0]["tool_name"] == "tool_b"
    assert events_b[0]["arguments"] == {"id": "B"}


def test_distinct_run_ids_differing_only_by_case_produce_separate_files(output_dir: Path) -> None:
    recorder = TrajectoryRecorder(output_dir=output_dir)

    file_upper = recorder.start_run("RunA")
    recorder.record_validation("tool_upper", {"run": "RunA"}, {"is_valid": True})

    file_lower = recorder.start_run("runa")
    recorder.record_validation("tool_lower", {"run": "runa"}, {"is_valid": True})

    assert file_upper != file_lower
    assert file_upper.resolve() != file_lower.resolve()

    trajectories = list((output_dir / "trajectories").glob("*.jsonl"))
    assert len(trajectories) == 2

    events_upper = [json.loads(line) for line in file_upper.read_text(encoding="utf-8").splitlines()]
    events_lower = [json.loads(line) for line in file_lower.read_text(encoding="utf-8").splitlines()]

    assert len(events_upper) == 1
    assert events_upper[0]["tool_name"] == "tool_upper"
    assert events_upper[0]["arguments"] == {"run": "RunA"}

    assert len(events_lower) == 1
    assert events_lower[0]["tool_name"] == "tool_lower"
    assert events_lower[0]["arguments"] == {"run": "runa"}


def test_recording_additional_events_after_reopening_does_not_truncate(output_dir: Path) -> None:
    recorder = TrajectoryRecorder(output_dir=output_dir)

    run_file = recorder.start_run("run_append_test")
    recorder.record_validation("tool_init", {"stage": "first"}, {"is_valid": True})

    recorder.start_run("run_append_test")
    recorder.record_execution("tool_init", {"stage": "second"}, {"success": True, "output": "appended"})

    lines = run_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    events = [json.loads(line) for line in lines]
    assert events[0]["arguments"]["stage"] == "first"
    assert events[1]["arguments"]["stage"] == "second"


def test_calling_start_run_twice_with_same_run_id_reuses_file_across_instances(output_dir: Path) -> None:
    rec1 = TrajectoryRecorder(output_dir=output_dir)
    file1 = rec1.start_run("shared_run")
    rec1.record_validation("tool_shared", {"from": "instance_1"}, {"is_valid": True})

    rec2 = TrajectoryRecorder(output_dir=output_dir)
    file2 = rec2.start_run("shared_run")
    rec2.record_execution("tool_shared", {"from": "instance_2"}, {"success": True, "output": "shared"})

    assert file1.resolve() == file2.resolve()

    trajectories = list((output_dir / "trajectories").glob("*.jsonl"))
    assert len(trajectories) == 1
    assert trajectories[0].resolve() == file1.resolve()
    assert trajectories[0].parent == output_dir / "trajectories"

    lines = file1.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    events = [json.loads(line) for line in lines]
    assert events[0]["arguments"]["from"] == "instance_1"
    assert events[1]["arguments"]["from"] == "instance_2"


def test_run_id_with_traversal_cannot_write_outside_trajectories_dir(output_dir: Path) -> None:
    recorder = TrajectoryRecorder(output_dir=output_dir)
    trajectories_dir = output_dir / "trajectories"

    disallowed_run_ids = [
        "../../escape",
        "..\\..\\escape",
        "nested/../../escape",
        "sub/run_id",
        "/escape",
        "\\escape",
        "C:\\escape",
    ]

    for bad_id in disallowed_run_ids:
        with pytest.raises(ValueError) as exc_info:
            recorder.start_run(bad_id)
        assert "invalid run_id" in str(exc_info.value).lower()

    files_outside = [p for p in output_dir.glob("*") if p.is_file()]
    assert files_outside == []

    files_in_trajectories = list(trajectories_dir.glob("*"))
    assert files_in_trajectories == []
