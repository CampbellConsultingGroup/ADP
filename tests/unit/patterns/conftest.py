"""Shared helpers for the pattern metamodel tests (934)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

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


GOLDENS = Path(__file__).parent / "goldens"


@pytest.fixture()
def golden(request: pytest.FixtureRequest) -> Callable[[str, str], None]:
    """Compare text against goldens/<name>; rewrite it under --update-goldens (935 D10)."""
    update = bool(request.config.getoption("--update-goldens", default=False))

    def _check(name: str, text: str) -> None:
        path = GOLDENS / name
        if update:
            GOLDENS.mkdir(exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            return
        assert path.exists(), f"missing golden {name}; run pytest --update-goldens"
        assert text == path.read_text(encoding="utf-8"), f"golden mismatch: {name}"

    return _check
