"""The real 934 fixtures against realistic in-memory estates (936 T008, SC-002/SC-003)."""

from __future__ import annotations

import random

from adp.patterns import compute_digest, parse_pattern_yaml
from adp.patterns.conformance_models import ConformanceStatus, FindingKind, PinIn, ScopeType
from adp.patterns.engine import discover, evaluate_pattern
from adp.patterns.models import ElementType as T
from adp.patterns.snapshot import Scope

from .conftest import load_fixture
from .snapshots import SnapshotBuilder

BACKBONE = parse_pattern_yaml(
    load_fixture("ea.integration.domain-event-backbone@1.0.0.yaml")
).definition
MESH = parse_pattern_yaml(load_fixture("ea.integration.point-to-point-mesh@1.0.0.yaml")).definition
TRANSITION = parse_pattern_yaml(
    load_fixture("ea.integration.mesh-to-backbone@1.0.0.yaml")
).definition
CLAIMS = Scope(ScopeType.BUSINESS_DOMAIN, scope_ref="claims")
HUB_PIN = [PinIn(role_key="backbone", element_type=T.APPLICATION, element_id="hub")]


def _estate(direct: bool):  # type: ignore[no-untyped-def]
    """Two Claims apps and one Billing app, all wired through the hub; optionally one direct
    cross-domain integration claims-core → billing."""
    b = (
        SnapshotBuilder()
        .domain("claims", "Claims")
        .domain("billing", "Billing")
        .capability("c-claims", "Claims", domain="claims")
        .capability("c-bill", "Billing", domain="billing")
        .app("core", "Claims Core", caps=["c-claims"], time_classification="Invest")
        .app("portal", "Claims Portal", caps=["c-claims"], time_classification="Tolerate")
        .app("bill", "Billing", caps=["c-bill"], time_classification="Invest")
        .app(
            "hub",
            "Enterprise Event Hub",
            application_type="cots",
            architecture_pattern="event-backbone",
        )
    )
    for app in ("core", "portal", "bill"):
        b.integration(f"{app}->hub", app, "hub", integration_type="event")
        b.integration(f"hub->{app}", "hub", app, integration_type="event")
    if direct:
        b.integration("core->bill", "core", "bill")
    return b.build()


def _codes(report):  # type: ignore[no-untyped-def]
    return {f.code: f for f in report.findings}


def test_reference_fixture_non_conformant_on_direct_cross_domain_integration() -> None:
    report = evaluate_pattern(BACKBONE, _estate(direct=True), CLAIMS, HUB_PIN)
    assert report.status == ConformanceStatus.NON_CONFORMANT
    c1 = _codes(report)["C1"]
    assert c1.kind == FindingKind.VIOLATION
    assert [e.name for e in c1.element_refs] == ["Claims Core → Billing"]
    bindings = {b.role_key: b.count for b in report.bindings}
    assert bindings == {"backbone": 1, "domain_app": 2, "cross_domain_integration": 5}


def test_reference_fixture_conformant_when_all_routed_through_the_hub() -> None:
    report = evaluate_pattern(BACKBONE, _estate(direct=False), CLAIMS, HUB_PIN)
    assert "C1" not in _codes(report)
    assert report.status == ConformanceStatus.CONFORMANT, report.findings


def test_without_the_pin_the_broad_backbone_selector_breaks_cardinality() -> None:
    report = evaluate_pattern(BACKBONE, _estate(direct=False), CLAIMS, [])
    assert "K:backbone" in _codes(report)  # GT-8: why pins are authoritative


def test_mesh_discovery_finds_direct_cross_domain_integrations() -> None:
    report = discover(MESH, _estate(direct=True), digest=compute_digest(MESH))
    [c1] = report.matches
    names = {e.name for e in c1.element_refs}
    assert "Claims Core → Billing" in names
    # hub integrations are 'cross-domain' too under the fixture's selector: the hub has no
    # domain, and all() over an empty list is true (spec Edge Cases).
    assert report.match_count == len(names) == 7


def test_transition_plateaus() -> None:
    pins = [PinIn(role_key="backbone", element_type=T.APPLICATION, element_id="hub")]
    report = evaluate_pattern(TRANSITION, _estate(direct=True), CLAIMS, pins)
    assert report.plateau is not None
    assert (report.plateau.reached, report.plateau.next, report.plateau.blocking) == (
        "PL1",
        "PL2",
        ["C2"],
    )
    done = evaluate_pattern(TRANSITION, _estate(direct=False), CLAIMS, pins)
    assert done.plateau is not None and done.plateau.reached == "PL2"
    none = evaluate_pattern(TRANSITION, _estate(direct=True), CLAIMS, [])
    assert none.plateau is not None and none.plateau.reached is None


def test_report_is_deterministic_under_shuffled_input() -> None:
    snap = _estate(direct=True)
    first = evaluate_pattern(BACKBONE, snap, CLAIMS, HUB_PIN).model_dump(exclude={"evaluated_at"})
    rng = random.Random(3)
    for _ in range(50):
        shuffled = {t: dict(rng.sample(list(m.items()), len(m))) for t, m in snap.elements.items()}
        snap2 = type(snap)(
            elements=shuffled,
            unavailable_fields=snap.unavailable_fields,
            realizes_pairs=snap.realizes_pairs,
            _by_pair=snap._by_pair,
        )
        again = evaluate_pattern(BACKBONE, snap2, CLAIMS, HUB_PIN)
        assert again.model_dump(exclude={"evaluated_at"}) == first
