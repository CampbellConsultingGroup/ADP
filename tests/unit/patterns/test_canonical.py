"""Canonical JSON/YAML and digest stability (934 US2, FR-013, FR-014)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from adp.patterns import (
    PatternDefinition,
    compute_digest,
    parse_pattern_yaml,
    to_canonical_json,
    to_canonical_yaml,
)

from .conftest import load_fixture, valid_fixture_paths

REFERENCE = "ea.integration.domain-event-backbone@1.0.0.yaml"


def _parse(text: str) -> PatternDefinition:
    result = parse_pattern_yaml(text)
    assert result.ok, result.issues
    assert result.definition is not None
    return result.definition


@pytest.mark.parametrize("path", valid_fixture_paths(), ids=lambda p: p.name)
def test_round_trip_law(path: Path) -> None:
    original = _parse(path.read_text(encoding="utf-8"))
    canonical = to_canonical_yaml(original)
    again = _parse(canonical)
    assert again == original
    assert compute_digest(again) == compute_digest(original)
    assert to_canonical_yaml(again) == canonical  # idempotent


def test_digest_format() -> None:
    assert re.fullmatch(r"[0-9a-f]{64}", compute_digest(_parse(load_fixture(REFERENCE))))


def test_digest_ignores_key_order_and_cardinality_notation() -> None:
    shorthand = _parse(load_fixture(REFERENCE))
    longhand = _parse(load_fixture("ea.integration.domain-event-backbone-longhand@1.0.0.yaml"))
    assert compute_digest(shorthand) == compute_digest(longhand)


def _reorder_roles(defn: PatternDefinition) -> PatternDefinition:
    roles = dict(reversed(list(defn.roles.items())))
    return defn.model_copy(update={"roles": roles})


def test_digest_changes_with_role_order() -> None:
    defn = _parse(load_fixture(REFERENCE))
    assert compute_digest(_reorder_roles(defn)) != compute_digest(defn)


def test_digest_changes_with_constraint_and_relationship_order() -> None:
    defn = _parse(load_fixture(REFERENCE))
    c = defn.model_copy(update={"constraints": list(reversed(defn.constraints))})
    r = defn.model_copy(update={"relationships": list(reversed(defn.relationships))})
    assert compute_digest(c) != compute_digest(defn)
    assert compute_digest(r) != compute_digest(defn)


def test_digest_changes_with_plateau_order() -> None:
    defn = _parse(load_fixture("ea.integration.mesh-to-backbone@1.0.0.yaml"))
    assert defn.transition is not None
    swapped = defn.transition.model_copy(
        update={"plateaus": list(reversed(defn.transition.plateaus))}
    )
    assert compute_digest(defn.model_copy(update={"transition": swapped})) != compute_digest(defn)


def test_digest_changes_with_one_character() -> None:
    defn = _parse(load_fixture(REFERENCE))
    assert compute_digest(defn.model_copy(update={"name": defn.name + "!"})) != compute_digest(defn)


def test_canonical_json_is_compact_and_sorted() -> None:
    js = to_canonical_json(_parse(load_fixture(REFERENCE)))
    assert ": " not in js and ", " not in js.split('"roles"')[0]
    assert js.startswith('{"constraints"')  # keys sorted
    assert '"roles":[["backbone"' in js  # roles kept as ordered pairs


def test_canonical_yaml_shape() -> None:
    text = to_canonical_yaml(
        _parse(load_fixture("ea.integration.domain-event-backbone-longhand@1.0.0.yaml"))
    )
    assert "&" not in text and "*id" not in text
    assert "cardinality: '1'" in text or 'cardinality: "1"' in text
    assert "2..*" in text
    assert text.splitlines()[0] == "pattern: ea.integration.domain-event-backbone"
    assert "polarity" not in text  # defaults omitted
    assert "lifecycle" not in text
