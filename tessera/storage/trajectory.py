"""Standalone Trajectory Recorder for Phase 1."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


class TrajectoryRecorder:
    """Records task execution trajectories to append-only JSONL files."""

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir).resolve()
        self.trajectories_dir = self.output_dir / "trajectories"
        self.trajectories_dir.mkdir(parents=True, exist_ok=True)
        self.active_run_id: str | None = None
        self.active_file_path: Path | None = None

    def _resolve_run_file(self, run_id: str) -> Path:
        """Deterministically resolve and validate run file path within trajectories directory."""
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be a non-empty string")

        # Reject path traversal, directory separators, and control/forbidden filename characters
        if "/" in run_id or "\\" in run_id or ".." in run_id:
            raise ValueError(f"Invalid run_id '{run_id}': path traversal characters are not permitted")

        forbidden_chars = set('<>:"/\\|?*\0')
        if any(ch in forbidden_chars for ch in run_id):
            raise ValueError(f"Invalid run_id '{run_id}': contains forbidden characters")

        run_hash = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        filename = f"run_{run_hash}.jsonl"
        target_path = (self.trajectories_dir / filename).resolve()

        # Strict containment check
        try:
            target_path.relative_to(self.trajectories_dir)
        except ValueError:
            raise ValueError(f"Invalid run_id '{run_id}': resolves outside trajectories directory")

        if target_path.parent != self.trajectories_dir:
            raise ValueError(f"Invalid run_id '{run_id}': cannot reside in a subfolder")

        return target_path

    def start_run(self, run_id: str) -> Path:
        """Start or reopen an existing run by run_id."""
        target_path = self._resolve_run_file(run_id)
        self.active_run_id = run_id
        self.active_file_path = target_path
        if not target_path.exists():
            target_path.touch()
        return target_path

    def _append_event(self, event: dict[str, Any]) -> None:
        """Append event to the active run's JSONL file and flush immediately."""
        if self.active_file_path is None:
            raise RuntimeError("No active run. Call start_run(run_id) before recording events.")

        line = json.dumps(event, default=str) + "\n"
        with open(self.active_file_path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

    def record_validation(
        self,
        tool_name: str,
        arguments: Mapping[str, Any] | Any,
        result: Any,
    ) -> None:
        """Record a validation event."""
        if hasattr(result, "is_valid"):
            accepted = bool(result.is_valid)
            error = getattr(result, "error", None)
        elif hasattr(result, "success"):
            accepted = bool(result.success)
            error = getattr(result, "error", None)
        elif isinstance(result, dict):
            accepted = bool(result.get("is_valid", result.get("success", result.get("accepted", False))))
            error = result.get("error")
        elif isinstance(result, bool):
            accepted = result
            error = None if result else "Validation rejected"
        else:
            accepted = bool(result)
            error = str(result) if not accepted else None

        args_dict = dict(arguments) if isinstance(arguments, (dict, Mapping)) else {"raw_arguments": arguments}

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "validation",
            "tool_name": str(tool_name),
            "arguments": args_dict,
            "accepted": accepted,
            "error": error if not accepted else None,
        }
        self._append_event(event)

    def record_execution(
        self,
        tool_name: str,
        arguments: Mapping[str, Any] | Any,
        result: Any,
    ) -> None:
        """Record an execution event."""
        if hasattr(result, "success"):
            success = bool(result.success)
            output = getattr(result, "output", None)
            error = getattr(result, "error", None)
        elif isinstance(result, dict):
            success = bool(result.get("success", True))
            output = result.get("output")
            error = result.get("error")
        elif isinstance(result, Exception):
            success = False
            output = None
            error = str(result)
        elif isinstance(result, bool):
            success = result
            output = None
            error = None if result else "Execution failed"
        else:
            success = True
            output = result
            error = None

        args_dict = dict(arguments) if isinstance(arguments, (dict, Mapping)) else {"raw_arguments": arguments}

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "execution",
            "tool_name": str(tool_name),
            "arguments": args_dict,
            "success": success,
            "output": output,
            "error": error if not success else None,
        }
        self._append_event(event)
