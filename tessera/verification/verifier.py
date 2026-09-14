"""Phase 1 Deterministic Verifier: standalone read-only filesystem verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class VerificationSpec:
    """Explicit specification of expected deterministic filesystem state."""

    file_exists: tuple[str, ...] = ()
    file_not_exists: tuple[str, ...] = ()
    exact_contents: Mapping[str, str] = field(default_factory=dict)
    contains_content: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    does_not_contain_content: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    forbidden_files: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Normalize file_exists
        fe = self.file_exists
        if isinstance(fe, str):
            fe = (fe,)
        elif not isinstance(fe, (tuple, list)):
            raise TypeError("VerificationSpec 'file_exists' must be a string or sequence of strings")
        for item in fe:
            if not isinstance(item, str) or not item.strip():
                raise TypeError("VerificationSpec 'file_exists' items must be non-empty strings")
        object.__setattr__(self, "file_exists", tuple(fe))

        # Normalize file_not_exists
        fne = self.file_not_exists
        if isinstance(fne, str):
            fne = (fne,)
        elif not isinstance(fne, (tuple, list)):
            raise TypeError("VerificationSpec 'file_not_exists' must be a string or sequence of strings")
        for item in fne:
            if not isinstance(item, str) or not item.strip():
                raise TypeError("VerificationSpec 'file_not_exists' items must be non-empty strings")
        object.__setattr__(self, "file_not_exists", tuple(fne))

        # Normalize forbidden_files (collateral check)
        ff = self.forbidden_files
        if isinstance(ff, str):
            ff = (ff,)
        elif not isinstance(ff, (tuple, list)):
            raise TypeError("VerificationSpec 'forbidden_files' must be a string or sequence of strings")
        for item in ff:
            if not isinstance(item, str) or not item.strip():
                raise TypeError("VerificationSpec 'forbidden_files' items must be non-empty strings")
        object.__setattr__(self, "forbidden_files", tuple(ff))

        # Normalize exact_contents
        ec = self.exact_contents
        if not isinstance(ec, Mapping):
            raise TypeError("VerificationSpec 'exact_contents' must be a mapping of path to expected string")
        norm_ec: dict[str, str] = {}
        for k, v in ec.items():
            if not isinstance(k, str) or not k.strip():
                raise TypeError("VerificationSpec 'exact_contents' keys must be non-empty strings")
            if not isinstance(v, str):
                raise TypeError(f"VerificationSpec 'exact_contents' value for '{k}' must be a string, got {type(v).__name__}")
            norm_ec[k] = v
        object.__setattr__(self, "exact_contents", norm_ec)

        # Normalize contains_content
        cc = self.contains_content
        if not isinstance(cc, Mapping):
            raise TypeError("VerificationSpec 'contains_content' must be a mapping")
        norm_cc: dict[str, tuple[str, ...]] = {}
        for k, v in cc.items():
            if not isinstance(k, str) or not k.strip():
                raise TypeError("VerificationSpec 'contains_content' keys must be non-empty strings")
            if isinstance(v, str):
                norm_cc[k] = (v,)
            elif isinstance(v, (tuple, list)):
                for item in v:
                    if not isinstance(item, str):
                        raise TypeError(f"VerificationSpec 'contains_content' item for '{k}' must be string, got {type(item).__name__}")
                norm_cc[k] = tuple(v)
            else:
                raise TypeError(f"VerificationSpec 'contains_content' value for '{k}' must be string or sequence of strings")
        object.__setattr__(self, "contains_content", norm_cc)

        # Normalize does_not_contain_content
        dncc = self.does_not_contain_content
        if not isinstance(dncc, Mapping):
            raise TypeError("VerificationSpec 'does_not_contain_content' must be a mapping")
        norm_dncc: dict[str, tuple[str, ...]] = {}
        for k, v in dncc.items():
            if not isinstance(k, str) or not k.strip():
                raise TypeError("VerificationSpec 'does_not_contain_content' keys must be non-empty strings")
            if isinstance(v, str):
                norm_dncc[k] = (v,)
            elif isinstance(v, (tuple, list)):
                for item in v:
                    if not isinstance(item, str):
                        raise TypeError(f"VerificationSpec 'does_not_contain_content' item for '{k}' must be string, got {type(item).__name__}")
                norm_dncc[k] = tuple(v)
            else:
                raise TypeError(f"VerificationSpec 'does_not_contain_content' value for '{k}' must be string or sequence of strings")
        object.__setattr__(self, "does_not_contain_content", norm_dncc)

        if not self.has_checks():
            raise ValueError("Verification specification must define at least one expected condition/check")

    def has_checks(self) -> bool:
        """Check if at least one verification condition is specified."""
        return bool(
            self.file_exists
            or self.file_not_exists
            or self.exact_contents
            or self.contains_content
            or self.does_not_contain_content
            or self.forbidden_files
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable dictionary representation."""
        res: dict[str, Any] = {}
        if self.file_exists:
            res["file_exists"] = list(self.file_exists)
        if self.file_not_exists:
            res["file_not_exists"] = list(self.file_not_exists)
        if self.exact_contents:
            res["exact_contents"] = dict(self.exact_contents)
        if self.contains_content:
            res["contains_content"] = {k: list(v) for k, v in self.contains_content.items()}
        if self.does_not_contain_content:
            res["does_not_contain_content"] = {k: list(v) for k, v in self.does_not_contain_content.items()}
        if self.forbidden_files:
            res["forbidden_files"] = list(self.forbidden_files)
        return res

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> VerificationSpec:
        """Create VerificationSpec from a mapping."""
        if not isinstance(data, Mapping):
            raise TypeError(f"Verification specification must be a mapping, got {type(data).__name__}")
        return cls(
            file_exists=data.get("file_exists", ()),
            file_not_exists=data.get("file_not_exists", ()),
            exact_contents=data.get("exact_contents", {}),
            contains_content=data.get("contains_content", {}),
            does_not_contain_content=data.get("does_not_contain_content", {}),
            forbidden_files=data.get("forbidden_files", ()),
        )


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of deterministic filesystem verification."""

    passed: bool
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.passed

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable dictionary representation."""
        return {
            "passed": self.passed,
            "error": self.error,
            "details": self.details,
        }


class DeterministicVerifier:
    """Standalone, read-only deterministic filesystem verifier for Phase 1 tasks."""

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        if not self.workspace_root.exists() or not self.workspace_root.is_dir():
            raise ValueError(f"Workspace root does not exist or is not a directory: {self.workspace_root}")

    def _resolve_safe_path(self, path_str: str | Path) -> Path:
        """Resolve path and ensure it does not escape workspace_root."""
        if not path_str or not str(path_str).strip():
            raise ValueError("Path in verification specification cannot be empty")

        raw_path = Path(path_str)
        if raw_path.is_absolute():
            resolved = raw_path.resolve()
        else:
            resolved = (self.workspace_root / raw_path).resolve()

        try:
            resolved.relative_to(self.workspace_root)
        except ValueError:
            raise ValueError(f"Path '{path_str}' escapes workspace root '{self.workspace_root}'")

        return resolved

    def verify(self, spec: VerificationSpec | Mapping[str, Any]) -> VerificationResult:
        """Deterministically check workspace against the provided verification specification."""
        if isinstance(spec, Mapping):
            parsed_spec = VerificationSpec.from_dict(spec)
        elif isinstance(spec, VerificationSpec):
            parsed_spec = spec
        else:
            raise TypeError(f"Verification spec must be a VerificationSpec or mapping, got {type(spec).__name__}")

        check_details: list[dict[str, Any]] = []

        # 1. Check: file_exists
        for rel_path in parsed_spec.file_exists:
            target = self._resolve_safe_path(rel_path)
            if not target.exists():
                check_details.append({
                    "check": "file_exists",
                    "path": rel_path,
                    "passed": False,
                    "message": f"Expected file does not exist: '{rel_path}'",
                })
            elif target.is_dir():
                check_details.append({
                    "check": "file_exists",
                    "path": rel_path,
                    "passed": False,
                    "message": f"Expected file '{rel_path}' exists but is a directory",
                })
            else:
                check_details.append({
                    "check": "file_exists",
                    "path": rel_path,
                    "passed": True,
                    "message": f"Expected file exists: '{rel_path}'",
                })

        # 2. Check: file_not_exists
        for rel_path in parsed_spec.file_not_exists:
            target = self._resolve_safe_path(rel_path)
            if target.exists():
                check_details.append({
                    "check": "file_not_exists",
                    "path": rel_path,
                    "passed": False,
                    "message": f"File was expected not to exist but was found: '{rel_path}'",
                })
            else:
                check_details.append({
                    "check": "file_not_exists",
                    "path": rel_path,
                    "passed": True,
                    "message": f"File correctly does not exist: '{rel_path}'",
                })

        # 3. Check: forbidden_files (collateral check)
        for rel_path in parsed_spec.forbidden_files:
            target = self._resolve_safe_path(rel_path)
            if target.exists():
                check_details.append({
                    "check": "forbidden_file",
                    "path": rel_path,
                    "passed": False,
                    "message": f"Forbidden collateral file was found: '{rel_path}'",
                })
            else:
                check_details.append({
                    "check": "forbidden_file",
                    "path": rel_path,
                    "passed": True,
                    "message": f"Forbidden file correctly absent: '{rel_path}'",
                })

        # 4. Check: exact_contents
        for rel_path, expected_text in parsed_spec.exact_contents.items():
            target = self._resolve_safe_path(rel_path)
            if not target.exists():
                check_details.append({
                    "check": "exact_content",
                    "path": rel_path,
                    "passed": False,
                    "expected": expected_text,
                    "actual": None,
                    "message": f"Cannot check exact content: file does not exist: '{rel_path}'",
                })
            elif target.is_dir():
                check_details.append({
                    "check": "exact_content",
                    "path": rel_path,
                    "passed": False,
                    "expected": expected_text,
                    "actual": None,
                    "message": f"Cannot check exact content: path is a directory: '{rel_path}'",
                })
            else:
                actual_text = target.read_text(encoding="utf-8", errors="replace")
                if actual_text == expected_text:
                    check_details.append({
                        "check": "exact_content",
                        "path": rel_path,
                        "passed": True,
                        "message": f"Exact content matches for: '{rel_path}'",
                    })
                else:
                    check_details.append({
                        "check": "exact_content",
                        "path": rel_path,
                        "passed": False,
                        "expected": expected_text,
                        "actual": actual_text,
                        "message": f"Content mismatch for '{rel_path}': expected {expected_text!r}, got {actual_text!r}",
                    })

        # 5. Check: contains_content
        for rel_path, substrings in parsed_spec.contains_content.items():
            target = self._resolve_safe_path(rel_path)
            if not target.exists():
                check_details.append({
                    "check": "contains_content",
                    "path": rel_path,
                    "passed": False,
                    "expected": list(substrings),
                    "actual": None,
                    "message": f"Cannot check contains content: file does not exist: '{rel_path}'",
                })
            elif target.is_dir():
                check_details.append({
                    "check": "contains_content",
                    "path": rel_path,
                    "passed": False,
                    "expected": list(substrings),
                    "actual": None,
                    "message": f"Cannot check contains content: path is a directory: '{rel_path}'",
                })
            else:
                actual_text = target.read_text(encoding="utf-8", errors="replace")
                for sub in substrings:
                    if sub in actual_text:
                        check_details.append({
                            "check": "contains_content",
                            "path": rel_path,
                            "substring": sub,
                            "passed": True,
                            "message": f"File '{rel_path}' contains expected substring {sub!r}",
                        })
                    else:
                        check_details.append({
                            "check": "contains_content",
                            "path": rel_path,
                            "substring": sub,
                            "passed": False,
                            "expected": sub,
                            "actual": actual_text,
                            "message": f"File '{rel_path}' does not contain expected substring {sub!r}",
                        })

        # 6. Check: does_not_contain_content
        for rel_path, forbidden_substrings in parsed_spec.does_not_contain_content.items():
            target = self._resolve_safe_path(rel_path)
            if not target.exists():
                check_details.append({
                    "check": "does_not_contain_content",
                    "path": rel_path,
                    "passed": False,
                    "forbidden": list(forbidden_substrings),
                    "actual": None,
                    "message": f"Cannot check does not contain: file does not exist: '{rel_path}'",
                })
            elif target.is_dir():
                check_details.append({
                    "check": "does_not_contain_content",
                    "path": rel_path,
                    "passed": False,
                    "forbidden": list(forbidden_substrings),
                    "actual": None,
                    "message": f"Cannot check does not contain: path is a directory: '{rel_path}'",
                })
            else:
                actual_text = target.read_text(encoding="utf-8", errors="replace")
                for sub in forbidden_substrings:
                    if sub in actual_text:
                        check_details.append({
                            "check": "does_not_contain_content",
                            "path": rel_path,
                            "substring": sub,
                            "passed": False,
                            "forbidden": sub,
                            "actual": actual_text,
                            "message": f"File '{rel_path}' contains forbidden substring {sub!r}",
                        })
                    else:
                        check_details.append({
                            "check": "does_not_contain_content",
                            "path": rel_path,
                            "substring": sub,
                            "passed": True,
                            "message": f"File '{rel_path}' does not contain forbidden substring {sub!r}",
                        })

        all_passed = all(c["passed"] for c in check_details)
        failures = [c["message"] for c in check_details if not c["passed"]]
        error = "; ".join(failures) if failures else None

        details = {
            "passed": all_passed,
            "total_checks": len(check_details),
            "passed_checks": sum(1 for c in check_details if c["passed"]),
            "failed_checks": len(failures),
            "checks": check_details,
            "errors": failures,
        }

        return VerificationResult(
            passed=all_passed,
            error=error,
            details=details,
        )


def verify(workspace_root: str | Path, spec: VerificationSpec | Mapping[str, Any]) -> VerificationResult:
    """Convenience function to deterministically verify a workspace against a specification."""
    verifier = DeterministicVerifier(workspace_root=workspace_root)
    return verifier.verify(spec=spec)
