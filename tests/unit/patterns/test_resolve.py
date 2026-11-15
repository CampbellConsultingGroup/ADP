"""Reference resolution: R1–R4 (935 FR-003, research D3)."""

from __future__ import annotations

from adp.patterns import parse_pattern_yaml
from adp.patterns.models import Severity
from adp.patterns.resolve import ReferenceLookups, referenced_ids, resolve_references

from .conftest import load_fixture

BACKBONE = "ea.integration.domain-event-backbone@1.0.0.yaml"


def _defn(name: str = BACKBONE):  # type: ignore[no-untyped-def]
    result = parse_pattern_yaml(load_fixture(name))
    assert result.definition is not None
    return result.definition


def _all(defn) -> ReferenceLookups:  # type: ignore[no-untyped-def]
    ids = referenced_ids(defn)
    return ReferenceLookups(
        principles=frozenset(ids.principles),
        controls=frozenset(ids.controls),
        patterns=frozenset(ids.patterns),
        applications=frozenset(ids.applications),
    )


def test_everything_resolves_gives_no_issue() -> None:
    defn = _defn()
    assert resolve_references(defn, _all(defn), blocking=True) == []


def test_referenced_ids_collects_each_kind() -> None:
    ids = referenced_ids(_defn())
    assert ids.principles == ["P-API-FIRST", "P-NO-P2P"]
    assert ids.patterns == ["ea.integration.point-to-point-mesh", "ea.data.one-sor-per-capability"]


def test_unresolved_are_warnings_when_not_blocking() -> None:
    issues = resolve_references(_defn(), ReferenceLookups(), blocking=False)
    codes = [(i.code, i.path) for i in issues]
    assert ("R1.unresolved_principle", "motivation.principles[0]") in codes
    assert ("R1.unresolved_principle", "motivation.principles[1]") in codes
    assert ("R3.unresolved_relation", "relations[0].target") in codes
    assert ("R3.unresolved_relation", "relations[1].target") in codes
    assert all(i.severity == Severity.WARNING for i in issues)


def test_unresolved_are_errors_when_blocking() -> None:
    issues = resolve_references(_defn(), ReferenceLookups(), blocking=True)
    assert issues and all(i.severity == Severity.ERROR for i in issues)


def test_partial_resolution_reports_only_missing() -> None:
    defn = _defn()
    lookups = _all(defn)
    lookups = ReferenceLookups(
        principles=lookups.principles - {"P-NO-P2P"},
        controls=lookups.controls,
        patterns=lookups.patterns,
        applications=lookups.applications,
    )
    issues = resolve_references(defn, lookups, blocking=True)
    assert [(i.code, i.path) for i in issues] == [
        ("R1.unresolved_principle", "motivation.principles[1]")
    ]
    assert "P-NO-P2P" in issues[0].message


def test_controls_and_implementations_are_resolved() -> None:
    import yaml

    from adp.patterns.models import PatternDefinition

    data = yaml.safe_load(load_fixture(BACKBONE))
    data["motivation"]["controls"] = ["ctl-1"]
    data["known_implementations"] = ["app-1", "app-2"]
    defn = PatternDefinition.model_validate(data)
    lookups = ReferenceLookups(
        principles=frozenset(referenced_ids(defn).principles),
        patterns=frozenset(referenced_ids(defn).patterns),
        applications=frozenset({"app-2"}),
    )
    codes = [(i.code, i.path) for i in resolve_references(defn, lookups, blocking=False)]
    assert codes == [
        ("R2.unresolved_control", "motivation.controls[0]"),
        ("R4.unresolved_implementation", "known_implementations[0]"),
    ]
