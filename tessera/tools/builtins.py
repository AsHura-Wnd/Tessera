"""Built-in Phase 1 tools: file_read, file_write, file_edit, file_find."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from tessera.tools.interface import ToolDefinition, ToolParameter, ToolResult


# --- Handlers ---


def handle_file_read(
    path: str | Path,
    start_line: int | None = None,
    end_line: int | None = None,
) -> ToolResult:
    """Read content from a file, optionally bounded by line numbers."""
    target_path = Path(path)
    if not target_path.exists():
        return ToolResult(success=False, error=f"File not found: '{target_path}'")
    if target_path.is_dir():
        return ToolResult(success=False, error=f"Path is a directory, not a file: '{target_path}'")

    try:
        text = target_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return ToolResult(success=False, error=f"Failed to read file: {exc}")

    lines = text.splitlines(keepends=True)
    total_lines = len(lines)

    if start_line is not None or end_line is not None:
        start_idx = max(0, (start_line - 1) if start_line is not None else 0)
        end_idx = min(total_lines, end_line if end_line is not None else total_lines)
        sliced_lines = lines[start_idx:end_idx]
        output = "".join(sliced_lines)
    else:
        output = text

    return ToolResult(success=True, output=output)


def handle_file_write(
    path: str | Path,
    content: str,
    overwrite: bool = False,
) -> ToolResult:
    """Write content to a file, creating parent directories as needed."""
    target_path = Path(path)
    if target_path.exists():
        if target_path.is_dir():
            return ToolResult(success=False, error=f"Cannot overwrite directory with file: '{target_path}'")
        if not overwrite:
            return ToolResult(
                success=False,
                error=f"File already exists and overwrite is False: '{target_path}'",
            )

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        return ToolResult(
            success=True,
            output=f"Successfully wrote {len(content)} characters to '{target_path.name}'",
        )
    except Exception as exc:
        return ToolResult(success=False, error=f"Failed to write file: {exc}")


def handle_file_edit(
    path: str | Path,
    target: str,
    replacement: str,
) -> ToolResult:
    """Replace an unambiguous target string within a file."""
    target_path = Path(path)
    if not target_path.exists():
        return ToolResult(success=False, error=f"File not found: '{target_path}'")
    if target_path.is_dir():
        return ToolResult(success=False, error=f"Path is a directory, not a file: '{target_path}'")

    try:
        content = target_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return ToolResult(success=False, error=f"Failed to read file for editing: {exc}")

    count = content.count(target)
    if count == 0:
        return ToolResult(success=False, error=f"Target string not found in '{target_path.name}'")
    if count > 1:
        return ToolResult(
            success=False,
            error=f"Target string appears {count} times in '{target_path.name}'. Edits must be unique and unambiguous.",
        )

    new_content = content.replace(target, replacement, 1)
    try:
        target_path.write_text(new_content, encoding="utf-8")
        return ToolResult(
            success=True,
            output=f"Successfully replaced target string in '{target_path.name}'",
        )
    except Exception as exc:
        return ToolResult(success=False, error=f"Failed to write edited content: {exc}")


def handle_file_find(
    directory: str | Path = ".",
    pattern: str = "*",
    content_pattern: str | None = None,
    workspace_root: str | Path | None = None,
) -> ToolResult:
    """Discover files matching a filename glob pattern and optional content regex."""
    if workspace_root is not None:
        root = Path(workspace_root).resolve()
        raw_dir = Path(directory)
        base_dir = raw_dir.resolve() if raw_dir.is_absolute() else (root / raw_dir).resolve()
        try:
            base_dir.relative_to(root)
        except ValueError:
            return ToolResult(
                success=False,
                error=f"Directory '{directory}' resolves outside workspace root '{root}'",
            )
    else:
        raw_dir = Path(directory)
        cwd = Path.cwd().resolve()
        if raw_dir.is_absolute():
            base_dir = raw_dir.resolve()
            try:
                base_dir.relative_to(cwd)
                root = cwd
            except ValueError:
                root = base_dir
        else:
            root = cwd
            base_dir = (root / raw_dir).resolve()
            try:
                base_dir.relative_to(root)
            except ValueError:
                return ToolResult(
                    success=False,
                    error=f"Directory '{directory}' resolves outside workspace root '{root}'",
                )

    if not base_dir.exists():
        return ToolResult(success=False, error=f"Directory not found: '{base_dir}'")
    if not base_dir.is_dir():
        return ToolResult(success=False, error=f"Path is not a directory: '{base_dir}'")

    matches: list[dict[str, Any]] = []
    compiled_regex = re.compile(content_pattern) if content_pattern else None

    try:
        # Search recursively using rglob unless pattern contains directory separators
        file_iter = base_dir.rglob(pattern) if "/" not in pattern and "\\" not in pattern else base_dir.glob(pattern)

        for file_path in file_iter:
            if not file_path.is_file():
                continue

            rel_path = file_path.resolve().relative_to(root)
            record: dict[str, Any] = {
                "path": str(rel_path).replace("\\", "/"),
                "size_bytes": file_path.stat().st_size,
            }

            if compiled_regex is not None:
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                    matched_lines: list[dict[str, Any]] = []
                    for line_num, line in enumerate(text.splitlines(), start=1):
                        if compiled_regex.search(line):
                            matched_lines.append({
                                "line_number": line_num,
                                "line": line.strip(),
                            })
                    if not matched_lines:
                        continue  # Skip files with no content match
                    record["matches"] = matched_lines
                except Exception:
                    continue

            matches.append(record)

        return ToolResult(success=True, output=matches)
    except Exception as exc:
        return ToolResult(success=False, error=f"Failed during file discovery: {exc}")


# --- Tool Definitions ---

FILE_READ_TOOL = ToolDefinition(
    name="file_read",
    description="Read content from a text file within the workspace.",
    parameters={
        "path": ToolParameter(
            name="path",
            type=str,
            description="Relative path of the file to read within workspace.",
            required=True,
            is_path=True,
        ),
        "start_line": ToolParameter(
            name="start_line",
            type=int,
            description="Optional 1-based start line number to begin reading from.",
            required=False,
            default=None,
        ),
        "end_line": ToolParameter(
            name="end_line",
            type=int,
            description="Optional 1-based end line number (inclusive) to stop reading at.",
            required=False,
            default=None,
        ),
    },
    handler=handle_file_read,
)

FILE_WRITE_TOOL = ToolDefinition(
    name="file_write",
    description="Write content to a file within the workspace.",
    parameters={
        "path": ToolParameter(
            name="path",
            type=str,
            description="Relative path of the file to write within workspace.",
            required=True,
            is_path=True,
        ),
        "content": ToolParameter(
            name="content",
            type=str,
            description="Text content to write to the file.",
            required=True,
        ),
        "overwrite": ToolParameter(
            name="overwrite",
            type=bool,
            description="Whether to overwrite if the file already exists (default: False).",
            required=False,
            default=False,
        ),
    },
    handler=handle_file_write,
)

FILE_EDIT_TOOL = ToolDefinition(
    name="file_edit",
    description="Replace an exact, unique target string in a file with replacement string.",
    parameters={
        "path": ToolParameter(
            name="path",
            type=str,
            description="Relative path of the file to edit within workspace.",
            required=True,
            is_path=True,
        ),
        "target": ToolParameter(
            name="target",
            type=str,
            description="Exact existing text string to be replaced (must appear exactly once).",
            required=True,
        ),
        "replacement": ToolParameter(
            name="replacement",
            type=str,
            description="New text string to replace the target with.",
            required=True,
        ),
    },
    handler=handle_file_edit,
)

FILE_FIND_TOOL = ToolDefinition(
    name="file_find",
    description="Find files by filename pattern and optional content regex within workspace.",
    parameters={
        "pattern": ToolParameter(
            name="pattern",
            type=str,
            description="Glob pattern to match file names (e.g., '*.py', 'test_*.txt'). Default is '*'.",
            required=False,
            default="*",
        ),
        "directory": ToolParameter(
            name="directory",
            type=str,
            description="Relative directory path to search within (default is workspace root '.').",
            required=False,
            default=".",
            is_path=True,
        ),
        "content_pattern": ToolParameter(
            name="content_pattern",
            type=str,
            description="Optional regular expression pattern to search for within matching files.",
            required=False,
            default=None,
        ),
    },
    handler=handle_file_find,
)

PHASE_1_BUILTIN_TOOLS: tuple[ToolDefinition, ...] = (
    FILE_READ_TOOL,
    FILE_WRITE_TOOL,
    FILE_EDIT_TOOL,
    FILE_FIND_TOOL,
)
