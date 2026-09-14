"""Unit tests for Phase 1 Deterministic Verifier."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tessera.verification.verifier import (
    DeterministicVerifier,
    VerificationResult,
    VerificationSpec,
    verify,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


def _hash_dir(dir_path: Path) -> dict[str, str]:
    """Compute sha256 hash for every file in dir_path."""
    hashes: dict[str, str] = {}
    for p in sorted(dir_path.rglob("*")):
        if p.is_file():
            rel = p.relative_to(dir_path).as_posix()
            hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


def test_existing_file_exact_content_passes(workspace: Path) -> None:
    """Test 1: Existing file with exact expected content -> PASS."""
    target = workspace / "result.txt"
    target.write_text("HELLO WORLD", encoding="utf-8")

    spec = VerificationSpec(
        file_exists=["result.txt"],
        exact_contents={"result.txt": "HELLO WORLD"},
    )

    verifier = DeterministicVerifier(workspace_root=workspace)
    result = verifier.verify(spec)

    assert result.passed is True
    assert result.error is None
    assert result.details["total_checks"] == 2
    assert result.details["passed_checks"] == 2
    assert result.details["failed_checks"] == 0
    assert len(result.details["errors"]) == 0


def test_missing_expected_file_fails(workspace: Path) -> None:
    """Test 2: Missing expected file -> FAIL."""
    spec = VerificationSpec(file_exists=["nonexistent.txt"])

    verifier = DeterministicVerifier(workspace_root=workspace)
    result = verifier.verify(spec)

    assert result.passed is False
    assert result.error is not None
    assert "Expected file does not exist: 'nonexistent.txt'" in result.error
    assert result.details["failed_checks"] == 1


def test_existing_file_incorrect_content_fails(workspace: Path) -> None:
    """Test 3: Existing file with incorrect content -> FAIL."""
    target = workspace / "output.txt"
    target.write_text("ACTUAL VALUE", encoding="utf-8")

    spec = VerificationSpec(exact_contents={"output.txt": "EXPECTED VALUE"})

    verifier = DeterministicVerifier(workspace_root=workspace)
    result = verifier.verify(spec)

    assert result.passed is False
    assert result.error is not None
    assert "Content mismatch for 'output.txt'" in result.error
    assert result.details["failed_checks"] == 1
    mismatch = result.details["checks"][0]
    assert mismatch["expected"] == "EXPECTED VALUE"
    assert mismatch["actual"] == "ACTUAL VALUE"


def test_expected_file_does_not_exist_fails(workspace: Path) -> None:
    """Test 4: Expected file does not exist -> appropriate FAIL when file is found."""
    # When file exists but was expected NOT to exist
    forbidden = workspace / "unexpected.tmp"
    forbidden.write_text("should not exist", encoding="utf-8")

    spec = VerificationSpec(file_not_exists=["unexpected.tmp"])

    verifier = DeterministicVerifier(workspace_root=workspace)
    result = verifier.verify(spec)

    assert result.passed is False
    assert result.error is not None
    assert "File was expected not to exist but was found: 'unexpected.tmp'" in result.error

    # When file correctly does not exist
    clean_spec = VerificationSpec(file_not_exists=["truly_absent.tmp"])
    clean_result = verifier.verify(clean_spec)
    assert clean_result.passed is True
    assert clean_result.error is None


def test_explicit_content_present_check_passes(workspace: Path) -> None:
    """Test 5: Explicit content-present check -> PASS."""
    target = workspace / "report.log"
    target.write_text("2026-09-11 [INFO] Task status: SUCCESS, processed 42 records", encoding="utf-8")

    spec = VerificationSpec(
        contains_content={
            "report.log": ["status: SUCCESS", "processed 42 records"],
        }
    )

    verifier = DeterministicVerifier(workspace_root=workspace)
    result = verifier.verify(spec)

    assert result.passed is True
    assert result.error is None
    assert result.details["passed_checks"] == 2


def test_explicit_content_absent_check_fails_when_forbidden_content_exists(workspace: Path) -> None:
    """Test 6: Explicit content-absent check -> FAIL when forbidden content exists."""
    target = workspace / "log.txt"
    target.write_text("DEBUG: trace stack overflow error occurred", encoding="utf-8")

    spec = VerificationSpec(
        does_not_contain_content={
            "log.txt": ["stack overflow error"],
        }
    )

    verifier = DeterministicVerifier(workspace_root=workspace)
    result = verifier.verify(spec)

    assert result.passed is False
    assert result.error is not None
    assert "contains forbidden substring 'stack overflow error'" in result.error

    # When forbidden content is absent -> PASS
    safe_spec = VerificationSpec(
        does_not_contain_content={
            "log.txt": ["FATAL_CRASH"],
        }
    )
    safe_result = verifier.verify(safe_spec)
    assert safe_result.passed is True


def test_multiple_expected_files_pass_when_all_correct(workspace: Path) -> None:
    """Test 7: Multiple expected files -> PASS when all are correct."""
    f1 = workspace / "a.txt"
    f1.write_text("content a", encoding="utf-8")
    f2 = workspace / "sub" / "b.txt"
    f2.parent.mkdir(parents=True, exist_ok=True)
    f2.write_text("content b", encoding="utf-8")

    spec = VerificationSpec(
        file_exists=["a.txt", "sub/b.txt"],
        exact_contents={"a.txt": "content a", "sub/b.txt": "content b"},
        contains_content={"a.txt": ["content"], "sub/b.txt": ["content"]},
    )

    verifier = DeterministicVerifier(workspace_root=workspace)
    result = verifier.verify(spec)

    assert result.passed is True
    assert result.error is None
    assert result.details["failed_checks"] == 0
    assert result.details["passed_checks"] == 6


def test_multiple_expected_files_fail_when_one_incorrect_or_missing(workspace: Path) -> None:
    """Test 8: Multiple expected files -> FAIL when one is incorrect/missing."""
    f1 = workspace / "a.txt"
    f1.write_text("content a", encoding="utf-8")
    f2 = workspace / "b.txt"
    f2.write_text("WRONG CONTENT", encoding="utf-8")
    # c.txt is not created

    spec = VerificationSpec(
        file_exists=["a.txt", "b.txt", "c.txt"],
        exact_contents={"a.txt": "content a", "b.txt": "EXPECTED B"},
    )

    verifier = DeterministicVerifier(workspace_root=workspace)
    result = verifier.verify(spec)

    assert result.passed is False
    assert result.details["failed_checks"] == 2
    assert "Expected file does not exist: 'c.txt'" in result.error
    assert "Content mismatch for 'b.txt'" in result.error


def test_verification_does_not_modify_workspace(workspace: Path) -> None:
    """Test 9: Verification does not modify the workspace."""
    f1 = workspace / "file1.txt"
    f1.write_text("original 1", encoding="utf-8")
    f2 = workspace / "dir" / "file2.txt"
    f2.parent.mkdir(parents=True, exist_ok=True)
    f2.write_text("original 2", encoding="utf-8")

    initial_hashes = _hash_dir(workspace)

    spec = VerificationSpec(
        file_exists=["file1.txt", "dir/file2.txt", "missing.txt"],
        exact_contents={"file1.txt": "original 1", "dir/file2.txt": "wrong"},
        file_not_exists=["ghost.txt"],
        forbidden_files=["file1.txt"],
    )

    verifier = DeterministicVerifier(workspace_root=workspace)
    result = verifier.verify(spec)

    # Verification executed and failed
    assert result.passed is False

    # Verify workspace filesystem state is byte-for-byte identical
    post_hashes = _hash_dir(workspace)
    assert post_hashes == initial_hashes


def test_same_workspace_and_spec_produces_deterministic_result(workspace: Path) -> None:
    """Test 10: Same workspace + same specification produces deterministic result."""
    target = workspace / "steady.txt"
    target.write_text("stable data 12345", encoding="utf-8")

    spec = VerificationSpec(
        file_exists=["steady.txt", "missing.txt"],
        exact_contents={"steady.txt": "stable data 12345"},
        contains_content={"steady.txt": ["data 123", "nonexistent"]},
    )

    verifier = DeterministicVerifier(workspace_root=workspace)

    results: list[VerificationResult] = [verifier.verify(spec) for _ in range(10)]

    first = results[0]
    for r in results[1:]:
        assert r.passed == first.passed
        assert r.error == first.error
        assert r.details == first.details


def test_malformed_verification_specification_rejected_clearly(workspace: Path) -> None:
    """Test 11: Malformed verification specification is rejected clearly."""
    verifier = DeterministicVerifier(workspace_root=workspace)

    # Empty specification with no checks
    with pytest.raises(ValueError, match="at least one expected condition"):
        verifier.verify(VerificationSpec())

    # Path traversal escaping workspace root
    with pytest.raises(ValueError, match="escapes workspace root"):
        verifier.verify(VerificationSpec(file_exists=["../../outside.txt"]))

    # Empty path string
    with pytest.raises(TypeError, match="non-empty strings"):
        verifier.verify(VerificationSpec(file_exists=[""]))

    # Non-string path
    with pytest.raises(TypeError):
        verifier.verify(VerificationSpec(file_exists=[123]))  # type: ignore[list-item]

    # Non-string exact_contents value
    with pytest.raises(TypeError, match="must be a string"):
        verifier.verify(VerificationSpec(exact_contents={"file.txt": 999}))  # type: ignore[dict-item]

    # Invalid spec object type
    with pytest.raises(TypeError, match="VerificationSpec or mapping"):
        verifier.verify("not a spec")  # type: ignore[arg-type]


def test_verifier_does_not_invoke_model_provider_or_tools(workspace: Path) -> None:
    """Test 12: Verifier does not invoke model/provider/tools and has no authority."""
    import tessera.verification.verifier as v_mod

    # Verify that verifier module does not import agent loop, model provider, or tool registry
    imported_modules = set(sys.modules.keys())
    assert "tessera.agent.loop" not in v_mod.__dict__
    assert "AgentLoop" not in v_mod.__dict__
    assert "ModelProvider" not in v_mod.__dict__
    assert "ToolValidator" not in v_mod.__dict__
    assert "ToolRegistry" not in v_mod.__dict__

    # Verifier has only read-only methods and no execute/modify capabilities
    verifier = DeterministicVerifier(workspace_root=workspace)
    assert not hasattr(verifier, "execute")
    assert not hasattr(verifier, "run")
    assert not hasattr(verifier, "mutate")
    assert not hasattr(verifier, "modify")
    assert not hasattr(verifier, "delete")
    assert not hasattr(verifier, "create")


def test_collateral_forbidden_files_check(workspace: Path) -> None:
    """Test collateral/unexpected-file conditions: forbidden_files check."""
    temp_file = workspace / "temp.log"
    temp_file.write_text("temporary debug log", encoding="utf-8")

    # Forbidden file is present -> FAIL
    fail_spec = VerificationSpec(forbidden_files=["temp.log"])
    res_fail = verify(workspace_root=workspace, spec=fail_spec)
    assert res_fail.passed is False
    assert "Forbidden collateral file was found: 'temp.log'" in res_fail.error

    # Forbidden file is absent -> PASS
    pass_spec = VerificationSpec(forbidden_files=["absent.log"])
    res_pass = verify(workspace_root=workspace, spec=pass_spec)
    assert res_pass.passed is True
    assert res_pass.error is None


def test_verification_spec_dict_serialization(workspace: Path) -> None:
    """Test VerificationSpec structure, dict mapping, and serializability."""
    doc = workspace / "doc.txt"
    doc.write_text("Chapter 1: Intro\nSummary: Done", encoding="utf-8")

    spec_dict: dict[str, Any] = {
        "file_exists": ["doc.txt"],
        "file_not_exists": ["ghost.txt"],
        "contains_content": {"doc.txt": ["Chapter 1", "Summary"]},
        "does_not_contain_content": {"doc.txt": ["Chapter 2"]},
    }

    res = verify(workspace_root=workspace, spec=spec_dict)
    assert res.passed is True
    assert res.error is None
    assert bool(res) is True

    # Check to_dict on result
    res_dict = res.to_dict()
    assert res_dict["passed"] is True
    assert res_dict["error"] is None
    assert "details" in res_dict
    assert res_dict["details"]["total_checks"] == 5

    # Check to_dict on VerificationSpec
    spec = VerificationSpec.from_dict(spec_dict)
    serialized = spec.to_dict()
    assert serialized["file_exists"] == ["doc.txt"]
    assert serialized["file_not_exists"] == ["ghost.txt"]
    assert serialized["contains_content"] == {"doc.txt": ["Chapter 1", "Summary"]}


def test_verifier_rejects_invalid_workspace_root() -> None:
    """Test DeterministicVerifier rejects nonexistent or non-directory workspace_root."""
    with pytest.raises(ValueError, match="does not exist or is not a directory"):
        DeterministicVerifier(workspace_root="nonexistent_directory_xyz_123")
