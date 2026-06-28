"""Tests for schema generator, --check mode, determinism, and --validate (US3 / SC-003)."""

import json
from pathlib import Path

import pytest

from adp.generate import check, generate, validate

# ── Determinism ───────────────────────────────────────────────────────────────


def test_generator_determinism() -> None:
    """generate() must return byte-identical output on repeated calls (NFR-001)."""
    first = generate()
    second = generate()
    assert first == second


def test_generated_schema_is_valid_json() -> None:
    schema = json.loads(generate())
    assert isinstance(schema, dict)


# ── --check mode: no drift ────────────────────────────────────────────────────


def test_check_mode_no_drift(tmp_path: Path) -> None:
    """check() returns silently when the committed schema matches generated output."""
    committed = tmp_path / "schema.json"
    committed.write_text(generate(), encoding="utf-8")
    check(committed_path=committed)  # must not raise or exit


# ── --check mode: drift detected ─────────────────────────────────────────────


def test_check_mode_detects_drift(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """check() exits 1 with drift message when schema would change."""
    stale = tmp_path / "schema.json"
    stale.write_text('{"old": true}\n', encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        check(committed_path=stale)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "drift" in captured.err.lower() or str(stale) in captured.err


# ── --check mode: file not found ─────────────────────────────────────────────


def test_check_mode_file_not_found(tmp_path: Path) -> None:
    """check() raises FileNotFoundError with a clear message when schema is absent."""
    missing = tmp_path / "nonexistent.json"
    with pytest.raises(FileNotFoundError, match="adp-generate"):
        check(committed_path=missing)


# ── --validate mode ───────────────────────────────────────────────────────────


def test_validate_mode_valid_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """validate() exits 0 and prints success for a valid ArchitectureDescription."""
    valid_data = {
        "schema_version": "1.0.0",
        "id": "D-001",
        "title": "Test",
        "created_at": "2026-06-27T00:00:00Z",
        "updated_at": "2026-06-27T00:00:00Z",
    }
    path = tmp_path / "valid.json"
    path.write_text(json.dumps(valid_data), encoding="utf-8")

    validate(path)  # must not raise
    captured = capsys.readouterr()
    assert "valid" in captured.out.lower() or "intact" in captured.out.lower()


def test_validate_mode_invalid_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """validate() exits 1 with error message for invalid JSON content."""
    bad_data = {"schema_version": "not-semver", "id": "D-001", "title": "T",
                "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        validate(path)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "validation" in captured.err.lower() or "semver" in captured.err.lower()
