"""Knowledge projection text builder (935 FR-013, research D6). Pure."""

from __future__ import annotations

import yaml

from adp.patterns import parse_pattern_yaml
from adp.patterns.models import PatternDefinition
from adp.patterns.projection import build_projection, knowledge_kind_for

from .conftest import load_fixture

BACKBONE = load_fixture("ea.integration.domain-event-backbone@1.0.0.yaml")
MESH = load_fixture("ea.integration.point-to-point-mesh@1.0.0.yaml")


def _defn(text: str) -> PatternDefinition:
    result = parse_pattern_yaml(text)
    assert result.definition is not None
    return result.definition


def test_kind_mapping() -> None:
    assert knowledge_kind_for("reference-architecture") == "reference_architecture"
    for kind in ("portfolio-rule", "transition", "anti-pattern"):
        assert knowledge_kind_for(kind) == "pattern"


def test_projection_fields() -> None:
    defn = _defn(BACKBONE)
    p = build_projection(defn)
    assert p.id == p.source_ref == "adp-pattern:ea.integration.domain-event-backbone"
    assert p.kind == "reference_architecture"
    assert p.title == defn.name
    assert p.version == defn.version
    assert p.metadata == {
        "managed_by": "pattern-registry",
        "pattern_key": defn.pattern,
        "pattern_version": defn.version,
        "pattern_kind": "reference-architecture",
    }
    lines = p.full_text.splitlines()
    assert lines[0] == defn.summary
    assert f"Context: {defn.motivation.context}" in lines
    assert f"Problem: {defn.motivation.problem}" in lines
    assert "Tags: integration, event-driven" in lines


def test_empty_sections_are_omitted() -> None:
    data = yaml.safe_load(MESH)
    data["motivation"]["forces"] = []
    data["motivation"]["benefits"] = []
    data["motivation"]["liabilities"] = []
    data["tags"] = []
    p = build_projection(PatternDefinition.model_validate(data))
    assert p.kind == "pattern"
    for label in ("Forces:", "Benefits:", "Liabilities:", "Tags:"):
        assert not any(line.startswith(label) for line in p.full_text.splitlines())


def test_list_sections_joined_with_semicolons() -> None:
    data = yaml.safe_load(BACKBONE)
    data["motivation"]["forces"] = ["a", "b"]
    p = build_projection(PatternDefinition.model_validate(data))
    assert "Forces: a; b" in p.full_text.splitlines()
