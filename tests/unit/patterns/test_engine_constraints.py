"""Implicit and declared constraints (936 FR-009–FR-012, FR-015/FR-016; research D4)."""

from __future__ import annotations

from typing import Any

import pytest

from adp.patterns.cel import default_engine
from adp.patterns.conformance_models import EvalLimits, FindingKind, PinIn, ScopeType
from adp.patterns.engine import evaluate_pattern
from adp.patterns.models import ElementType as T
from adp.patterns.models import Severity
from adp.patterns.snapshot import Scope

from .snapshots import SnapshotBuilder, make_pattern

PORTFOLIO = Scope(ScopeType.PORTFOLIO)
APP = {"element_type": "application", "cardinality": "0..*"}


def _report(pattern, snap, pins=(), limits=None, scope=PORTFOLIO):  # type: ignore[no-untyped-def]
    return evaluate_pattern(
        pattern,
        snap,
        scope,
        list(pins),
        engine=default_engine(),
        limits=limits or EvalLimits(),
    )


def _codes(report) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {f.code: f for f in report.findings}


def _apps(*names: str) -> SnapshotBuilder:
    b = SnapshotBuilder()
    for n in names:
        b.app(n, n.upper())
    return b


# ── K: cardinality ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("card", "n", "ok"),
    [
        ("1", 1, True),
        ("1", 0, False),
        ("1", 2, False),
        ("2..*", 2, True),
        ("2..*", 1, False),
        ("0..1", 0, True),
        ("0..1", 2, False),
        ("0..*", 5, True),
    ],
)
def test_role_cardinality(card: str, n: int, ok: bool) -> None:
    pattern = make_pattern({"x": {"element_type": "application", "cardinality": card}})
    snap = _apps(*[f"a{i}" for i in range(n)]).build()
    k = _codes(_report(pattern, snap)).get("K:x")
    assert (k is None) == ok
    if k is not None:
        assert (k.kind, k.severity) == (FindingKind.VIOLATION, Severity.ERROR)


def test_per_cardinality_counts_through_relationship_evidence() -> None:
    pattern = make_pattern(
        {
            "capability": {"element_type": "business_capability", "cardinality": "1..*"},
            "sor": {"element_type": "application", "cardinality": "1 per capability"},
        },
        relationships=[
            {
                "id": "R1",
                "source": "sor",
                "target": "capability",
                "type": "serves",
                "required": False,
            }
        ],
    )
    snap = (
        SnapshotBuilder()
        .capability("c1", "Orders")
        .capability("c2", "Billing")
        .capability("c3", "Empty")
        .app("a1", "OMS", caps=["c1"])
        .app("a2", "ERP", caps=["c2"])
        .app("a3", "ERP2", caps=["c2"])
        .build()
    )
    k = _codes(_report(pattern, snap))["K:sor/capability"]
    assert sorted(e.id for e in k.element_refs) == ["c2", "c3"]  # 2 SoRs; 0 SoRs


# ── E: relationship evidence ────────────────────────────────────────────────────────
def _pub_pattern(rel_type: str = "publishes", via: str | None = None):  # type: ignore[no-untyped-def]
    rel: dict[str, Any] = {"id": "R1", "source": "src", "target": "dst", "type": rel_type}
    roles: dict[str, Any] = {"src": APP, "dst": APP}
    if via:
        rel["via"] = via
        roles[via] = APP
    return make_pattern(roles, relationships=[rel])


def _pinned(**roles: list[str]) -> list[PinIn]:
    return [
        PinIn(role_key=r, element_type=T.APPLICATION, element_id=i)
        for r, ids in roles.items()
        for i in ids
    ]


def test_publishes_needs_source_to_target_integration() -> None:
    snap = _apps("a", "b", "c").integration("i1", "a", "c").build()
    report = _report(_pub_pattern(), snap, _pinned(src=["a", "b"], dst=["c"]))
    e = _codes(report)["E:R1"]
    assert [x.id for x in e.element_refs] == ["b"]
    assert e.severity == Severity.ERROR


def test_consumes_is_reverse_direction_and_integrates_with_either() -> None:
    snap = _apps("a", "b").integration("i1", "b", "a").build()
    pins = _pinned(src=["a"], dst=["b"])
    assert "E:R1" not in _codes(_report(_pub_pattern("consumes"), snap, pins))
    assert "E:R1" in _codes(_report(_pub_pattern("publishes"), snap, pins))
    assert "E:R1" not in _codes(_report(_pub_pattern("integrates_with"), snap, pins))
    assert "E:R1" not in _codes(_report(_pub_pattern("depends_on"), snap, pins))


def test_via_requires_first_hop_to_the_mediator() -> None:
    snap = (
        _apps("a", "b", "hub", "c")
        .integration("i1", "a", "hub")
        .integration("i2", "b", "c")
        .build()
    )
    pins = _pinned(src=["a", "b"], dst=["c"], hub=["hub"])
    e = _codes(_report(_pub_pattern(via="hub"), snap, pins))["E:R1"]
    assert [x.id for x in e.element_refs] == ["b"]  # b goes direct, not via the hub


def test_serves_and_realizes_evidence() -> None:
    snap = (
        SnapshotBuilder()
        .capability("c1", "C")
        .tcap("t1", "T")
        .app("a1", "A", caps=["c1"], tcaps_provided=["t1"])
        .app("a2", "B")
        .build()
    )
    for rel, target_type, target in (
        ("serves", "business_capability", "c1"),
        ("realizes", "technical_capability", "t1"),
    ):
        pattern = make_pattern(
            {"app": APP, "tgt": {"element_type": target_type, "cardinality": "0..*"}},
            relationships=[{"id": "R1", "source": "app", "target": "tgt", "type": rel}],
        )
        pins = [
            *_pinned(app=["a1", "a2"]),
            PinIn(role_key="tgt", element_type=T(target_type), element_id=target),
        ]
        e = _codes(_report(pattern, snap, pins))["E:R1"]
        assert [x.id for x in e.element_refs] == ["a2"], rel


def test_unsupported_type_pair_is_unverifiable_info() -> None:
    pattern = make_pattern(
        {"app": APP, "cap": {"element_type": "business_capability", "cardinality": "0..*"}},
        relationships=[{"id": "R1", "source": "app", "target": "cap", "type": "publishes"}],
    )
    snap = SnapshotBuilder().capability("c1", "C").app("a1", "A").build()
    e = _codes(_report(pattern, snap))["E:R1"]
    assert (e.kind, e.severity) == (FindingKind.UNVERIFIABLE, Severity.INFO)


def test_optional_relationship_is_not_checked() -> None:
    pattern = make_pattern(
        {"src": APP, "dst": APP},
        relationships=[
            {"id": "R1", "source": "src", "target": "dst", "type": "publishes", "required": False}
        ],
    )
    snap = _apps("a", "b").build()
    assert "E:R1" not in _codes(_report(pattern, snap, _pinned(src=["a"], dst=["b"])))


# ── Declared constraints: polarity matrix ──────────────────────────────────────────
def _with_constraint(
    expr: str,
    *,
    polarity: str = "require",
    for_each: str | None = "x",
    severity: str = "error",
    kind: str = "reference-architecture",
):  # type: ignore[no-untyped-def]
    c: dict[str, Any] = {
        "id": "C1",
        "rule": "r",
        "expr": expr,
        "polarity": polarity,
        "severity": severity,
    }
    if for_each:
        c["for_each"] = for_each
    return make_pattern({"x": APP}, constraints=[c], kind=kind)


SNAP3 = None


def _snap3():  # type: ignore[no-untyped-def]
    return (
        SnapshotBuilder()
        .app("a1", "A", health_score=5)
        .app("a2", "B", health_score=2)
        .app("a3", "C", health_score=1)
        .build()
    )


def test_require_for_each_lists_offenders() -> None:
    c1 = _codes(_report(_with_constraint("it.health_score >= 2"), _snap3()))["C1"]
    assert (c1.kind, [e.id for e in c1.element_refs]) == (FindingKind.VIOLATION, ["a3"])


def test_require_without_for_each_is_one_violation() -> None:
    c1 = _codes(_report(_with_constraint("size(bindings['x']) > 5", for_each=None), _snap3()))["C1"]
    assert c1.kind == FindingKind.VIOLATION and c1.element_refs == []
    assert "C1" not in _codes(
        _report(_with_constraint("size(bindings['x']) == 3", for_each=None), _snap3())
    )


def test_detect_for_each_lists_matches() -> None:
    pattern = _with_constraint(
        "it.health_score <= 2", polarity="detect", severity="warning", kind="anti-pattern"
    )
    c1 = _codes(_report(pattern, _snap3()))["C1"]
    assert (c1.kind, c1.severity) == (FindingKind.MATCH, Severity.WARNING)
    assert [e.id for e in c1.element_refs] == ["a2", "a3"]


def test_detect_without_for_each() -> None:
    pattern = _with_constraint(
        "size(role('x')) == 3",
        polarity="detect",
        for_each=None,
        severity="warning",
        kind="anti-pattern",
    )
    assert _codes(_report(pattern, _snap3()))["C1"].kind == FindingKind.MATCH


def test_scope_and_functions_are_available() -> None:
    expr = "size(scope['applications']) == 3 && bound(it, 'x') && it.id in role('x')"
    assert "C1" not in _codes(_report(_with_constraint(expr), _snap3()))


# ── Errors, gated fields, limits ────────────────────────────────────────────────────
def test_non_bool_result_is_evaluation_error() -> None:
    c1 = _codes(_report(_with_constraint("it.name"), _snap3()))["C1"]
    assert (c1.kind, c1.severity) == (FindingKind.EVALUATION_ERROR, Severity.ERROR)
    assert len(c1.element_refs) == 3


def test_missing_gated_field_is_field_unavailable() -> None:
    snap = SnapshotBuilder().app("a1", "A").unavailable("tco").build()
    c1 = _codes(_report(_with_constraint("it.tco < 100.0"), snap))["C1"]
    assert (c1.kind, c1.severity) == (FindingKind.FIELD_UNAVAILABLE, Severity.ERROR)


def test_missing_ungated_field_is_evaluation_error() -> None:
    snap = SnapshotBuilder().app("a1", "A").unavailable("tco").build()
    c1 = _codes(_report(_with_constraint("it.typo_field == 1"), snap))["C1"]
    assert c1.kind == FindingKind.EVALUATION_ERROR


def test_limit_stops_only_that_constraint() -> None:
    pattern = make_pattern(
        {"x": APP},
        constraints=[
            {"id": "C1", "rule": "r", "for_each": "x", "expr": "true"},
            {"id": "C2", "rule": "r", "for_each": "x", "expr": "false"},
        ],
    )
    snap = _apps(*[f"a{i}" for i in range(10)]).build()
    report = _report(pattern, snap, limits=EvalLimits(max_element_evaluations=15))
    codes = _codes(report)
    assert codes["L1.limit_exceeded"].kind == FindingKind.LIMIT
    assert "C2" in codes["L1.limit_exceeded"].rule


def test_element_refs_are_capped_and_flagged() -> None:
    snap = _apps(*[f"a{i:03d}" for i in range(120)]).build()
    c1 = _codes(_report(_with_constraint("false"), snap))["C1"]
    assert len(c1.element_refs) == 100 and c1.truncated


def test_empty_for_each_role_evaluates_nothing() -> None:
    assert "C1" not in _codes(_report(_with_constraint("false"), SnapshotBuilder().build()))


def test_evidence_rule_reads_naturally() -> None:
    snap = _apps("a", "b").build()
    e = _codes(_report(_pub_pattern("publishes"), snap, _pinned(src=["a"], dst=["b"])))["E:R1"]
    assert e.rule == "Each 'Src' must publish to 'Dst'"
