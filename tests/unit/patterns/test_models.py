"""Pattern definition structure and cross-field rules V1–V9 (934 US1, FR-001..FR-012)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adp.patterns import PatternDefinition, parse_pattern_yaml

from .conftest import expected_from_header, invalid_fixture_paths, load_fixture, valid_fixture_paths


@pytest.mark.parametrize("path", valid_fixture_paths(), ids=lambda p: p.name)
def test_valid_fixture_parses_without_issues(path: Path) -> None:
    result = parse_pattern_yaml(path.read_text(encoding="utf-8"))
    assert result.issues == []
    assert result.ok
    assert isinstance(result.definition, PatternDefinition)


@pytest.mark.parametrize("path", invalid_fixture_paths(), ids=lambda p: p.name)
def test_invalid_fixture_yields_exactly_its_code(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    code, expected_path = expected_from_header(text)
    result = parse_pattern_yaml(text)
    assert not result.ok
    assert [(i.code, i.path) for i in result.issues] == [(code, expected_path)], result.issues
    assert all(i.message for i in result.issues)


def test_role_order_is_preserved() -> None:
    defn = parse_pattern_yaml(
        load_fixture("ea.integration.domain-event-backbone@1.0.0.yaml")
    ).definition
    assert defn is not None
    assert list(defn.roles) == ["backbone", "domain_app", "cross_domain_integration"]


def test_cardinality_shorthand_is_normalised() -> None:
    defn = parse_pattern_yaml(load_fixture("ea.data.one-sor-per-capability@1.0.0.yaml")).definition
    assert defn is not None
    card = defn.roles["system_of_record"].cardinality
    assert (card.min, card.max, card.per) == (1, 1, "capability")
    assert defn.roles["capability"].cardinality.max is None


def test_multiple_rule_violations_are_all_reported() -> None:
    text = """
pattern: ea.test.multi
version: 1.0.0
kind: portfolio-rule
name: Multi
summary: Three independent problems.
owner_role: solution
motivation: {context: c, problem: p}
roles:
  app: {element_type: application, cardinality: "1"}
relationships:
  - {id: R1, source: app, target: ghost, type: serves}
relations:
  - {type: requires, target: ea.test.multi}
"""
    codes = sorted(i.code for i in parse_pattern_yaml(text).issues)
    assert codes == ["V2.unknown_role", "V8.self_relation", "V9.owner_role"]


def test_self_loop_relationship_allowed() -> None:
    defn = parse_pattern_yaml(
        load_fixture("ea.integration.point-to-point-mesh@1.0.0.yaml")
    ).definition
    assert defn is not None
    assert defn.relationships[0].source == defn.relationships[0].target == "app"


def test_definition_is_frozen() -> None:
    defn = parse_pattern_yaml(
        load_fixture("ea.integration.domain-event-backbone@1.0.0.yaml")
    ).definition
    assert defn is not None
    with pytest.raises(Exception):  # pydantic ValidationError on frozen instance
        defn.name = "changed"  # type: ignore[misc]


def test_role_cap_enforced() -> None:
    roles = "\n".join(
        f'  r{i}: {{element_type: application, cardinality: "0..*"}}' for i in range(26)
    )
    text = f"""pattern: ea.test.big
version: 1.0.0
kind: portfolio-rule
name: Big
summary: Too many roles.
owner_role: enterprise
motivation: {{context: c, problem: p}}
roles:
{roles}
"""
    issues = parse_pattern_yaml(text).issues
    assert [i.path for i in issues] == ["roles"]
