"""YAML guards, issue reporting and the never-raises guarantee.

934 FR-009, FR-012, SC-003, SC-004.
"""

from __future__ import annotations

import random
import statistics
import time

import pytest

from adp.patterns import parse_pattern_yaml

from .conftest import load_fixture

REFERENCE = "ea.integration.domain-event-backbone@1.0.0.yaml"


def test_oversized_document_rejected() -> None:
    text = "# " + "x" * (256 * 1024) + "\n"
    result = parse_pattern_yaml(text)
    assert [i.code for i in result.issues] == ["P1.too_large"]
    assert result.definition is None


def test_exactly_256kb_is_not_too_large() -> None:
    pad = 256 * 1024 - len(load_fixture(REFERENCE).encode()) - 3
    text = load_fixture(REFERENCE) + "#" + "x" * pad + "\n"
    assert len(text.encode()) <= 256 * 1024
    assert parse_pattern_yaml(text).ok


def test_alias_reports_position() -> None:
    issue = parse_pattern_yaml("a: &x [1]\nb: *x\n").issues[0]
    assert issue.code == "P2.alias"
    assert issue.line is not None


def test_yaml_syntax_error_has_line() -> None:
    issue = parse_pattern_yaml("a: [unclosed\n").issues[0]
    assert issue.code == "P5.yaml_syntax"
    assert issue.line is not None and issue.column is not None


def test_cel_error_carries_path_and_column() -> None:
    text = load_fixture(REFERENCE).replace(
        "expr: \"it.time_classification != 'Eliminate'\"", 'expr: "it.time_classification =="'
    )
    issues = parse_pattern_yaml(text).issues
    assert [(i.code, i.path) for i in issues] == [("V7.compile", "constraints[1].expr")]
    assert issues[0].column is not None


def test_cel_issue_keeps_definition() -> None:
    text = load_fixture(REFERENCE).replace("it.time_classification != 'Eliminate'", "'oops'")
    result = parse_pattern_yaml(text)
    assert not result.ok
    assert result.definition is not None  # draft is still usable by the registry (935)


def test_cel_not_run_when_structure_invalid() -> None:
    text = (
        load_fixture(REFERENCE)
        .replace("owner_role: enterprise", "owner_role: solution")
        .replace("it.time_classification != 'Eliminate'", "'oops'")
    )
    assert [i.code for i in parse_pattern_yaml(text).issues] == ["V9.owner_role"]


def test_bytes_input_accepted() -> None:
    assert parse_pattern_yaml(load_fixture(REFERENCE).encode("utf-8")).ok


@pytest.mark.parametrize("bad", ["", "   ", "null", "42", "[]", "~", b"\xff\xfe\x00", b"\x00" * 50])
def test_degenerate_inputs(bad: str | bytes) -> None:
    result = parse_pattern_yaml(bad)
    assert not result.ok
    assert result.issues


def test_never_raises_fuzz() -> None:
    rng = random.Random(934)
    reference = load_fixture(REFERENCE)
    samples: list[str | bytes] = [
        bytes(rng.getrandbits(8) for _ in range(rng.randint(0, 400))) for _ in range(200)
    ]
    samples += [reference[: rng.randint(0, len(reference))] for _ in range(50)]
    for sample in samples:
        result = parse_pattern_yaml(sample)  # must not raise
        assert result.ok or result.issues


def test_reference_validates_under_100ms() -> None:
    text = load_fixture(REFERENCE)
    parse_pattern_yaml(text)  # warm-up (engine construction)
    timings = []
    for _ in range(5):
        start = time.perf_counter()
        assert parse_pattern_yaml(text).ok
        timings.append(time.perf_counter() - start)
    assert statistics.median(timings) < 0.1
