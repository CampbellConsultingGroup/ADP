"""Shared helpers for the pattern metamodel tests (934)."""

from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
VALID = FIXTURES / "valid"
INVALID = FIXTURES / "invalid"


def load_fixture(name: str) -> str:
    """Return the text of a fixture, looked up in valid/ then invalid/."""
    for base in (VALID, INVALID):
        path = base / name
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(name)


def valid_fixture_paths() -> list[Path]:
    return sorted(VALID.glob("*.yaml"))


def invalid_fixture_paths() -> list[Path]:
    return sorted(INVALID.glob("*.yaml"))


def expected_from_header(text: str) -> tuple[str, str]:
    """Invalid fixtures start with `# expect: <code> <path>` (path may be empty)."""
    first = text.splitlines()[0]
    assert first.startswith("# expect:"), (
        "invalid fixture must start with '# expect: <code> <path>'"
    )
    parts = first[len("# expect:") :].split()
    code = parts[0]
    path = parts[1] if len(parts) > 1 else ""
    return code, path
