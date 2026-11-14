"""Cardinality shorthand grammar (934 FR-008, data-model.md)."""

from __future__ import annotations

import pytest

from adp.patterns.cardinality import CardinalityError, format_cardinality, parse_cardinality


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1", (1, 1, None)),
        ("0..1", (0, 1, None)),
        ("2..*", (2, None, None)),
        ("0..*", (0, None, None)),
        ("1 per capability", (1, 1, "capability")),
        ("1..3 per x", (1, 3, "x")),
        ("  3  ", (3, 3, None)),
    ],
)
def test_shorthand_valid(text: str, expected: tuple[int, int | None, str | None]) -> None:
    assert parse_cardinality(text) == expected


@pytest.mark.parametrize(
    "text", ["*..1", "1 per", "0", "3..2", "-1", "a", "", "1..", "1 per Bad-Role", "1.5", "0..0"]
)
def test_shorthand_invalid(text: str) -> None:
    with pytest.raises(CardinalityError):
        parse_cardinality(text)


@pytest.mark.parametrize(
    ("triple", "text"),
    [
        ((1, 1, None), "1"),
        ((0, 1, None), "0..1"),
        ((2, None, None), "2..*"),
        ((1, 1, "capability"), "1 per capability"),
        ((1, 3, "x"), "1..3 per x"),
    ],
)
def test_format_round_trip(triple: tuple[int, int | None, str | None], text: str) -> None:
    assert format_cardinality(*triple) == text
    assert parse_cardinality(format_cardinality(*triple)) == triple
