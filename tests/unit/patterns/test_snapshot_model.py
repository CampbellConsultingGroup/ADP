"""PortfolioSnapshot model: domain derivation, cross_domain, scope membership (936 T002)."""

from __future__ import annotations

from adp.patterns.conformance_models import ScopeType
from adp.patterns.models import ElementType as T
from adp.patterns.snapshot import GATED_FIELDS, Scope, in_scope

from .snapshots import SnapshotBuilder


def _estate():  # type: ignore[no-untyped-def]
    return (
        SnapshotBuilder()
        .domain("d1", "Claims")
        .domain("d2", "Billing")
        .domain("d3", "Empty")
        .capability("c1", "Claims", domain="d1")
        .capability("c1a", "Intake", parent="c1", level=2)
        .capability("c1a1", "First notice", parent="c1a", level=3)
        .capability("c2", "Billing", domain="d2")
        .app("a1", "Claims Core", caps=["c1a1"])
        .app("a2", "Billing Hub", caps=["c2"])
        .app("a3", "Shared CRM", caps=["c1", "c2"])
        .app("a4", "Orphan", caps=[])
        .app("hub", "Event Hub")
        .integration("i1", "a1", "a2", integration_type="event")
        .integration("i2", "a1", "a3")
        .integration("i3", "a4", "a1")
        .integration("i4", "a2", "hub")
        .tcap("t1", "Streaming")
        .agent("g1", "Triage")
        .build()
    )


def test_domains_come_from_the_l1_ancestor() -> None:
    s = _estate()
    assert s.element(T.APPLICATION, "a1")["domain_ids"] == ["d1"]
    assert s.element(T.APPLICATION, "a3")["domain_ids"] == ["d1", "d2"]
    assert s.element(T.APPLICATION, "a4")["domain_ids"] == []
    assert s.element(T.BUSINESS_CAPABILITY, "c1a1")["domain_id"] == "d1"


def test_integration_endpoints_and_cross_domain() -> None:
    s = _estate()
    i1 = s.element(T.INTEGRATION, "i1")
    assert i1["name"] == "Claims Core → Billing Hub"
    assert i1["source"] == {"id": "a1", "name": "Claims Core", "domain_ids": ["d1"]}
    assert i1["cross_domain"] is True
    assert s.element(T.INTEGRATION, "i2")["cross_domain"] is False  # a3 shares d1
    assert s.element(T.INTEGRATION, "i3")["cross_domain"] is None  # a4 has no domain


def test_domain_scope() -> None:
    s = _estate()
    sc = Scope(ScopeType.BUSINESS_DOMAIN, scope_ref="d1")
    assert in_scope(s, sc, T.APPLICATION) == ["a1", "a3"]
    assert in_scope(s, sc, T.INTEGRATION) == ["i1", "i2", "i3"]
    assert in_scope(s, sc, T.BUSINESS_CAPABILITY) == ["c1", "c1a", "c1a1"]
    assert in_scope(s, sc, T.BUSINESS_DOMAIN) == ["d1"]
    assert in_scope(s, sc, T.TECHNICAL_CAPABILITY) == ["t1"]
    assert in_scope(s, sc, T.AGENT) == ["g1"]
    assert in_scope(s, Scope(ScopeType.BUSINESS_DOMAIN, scope_ref="d3"), T.APPLICATION) == []


def test_application_set_and_portfolio_scopes() -> None:
    s = _estate()
    sc = Scope(ScopeType.APPLICATION_SET, member_ids=frozenset({"a2", "zz"}))
    assert in_scope(s, sc, T.APPLICATION) == ["a2"]
    assert in_scope(s, sc, T.INTEGRATION) == ["i1", "i4"]
    assert in_scope(s, Scope(ScopeType.PORTFOLIO), T.APPLICATION) == ["a1", "a2", "a3", "a4", "hub"]


def test_gated_fields_absent_when_unavailable() -> None:
    s = SnapshotBuilder().app("a1", "X", tco=10.0, sla="99.9").unavailable("tco").build()
    app = s.element(T.APPLICATION, "a1")
    assert "tco" not in app and app["sla"] == "99.9"
    assert s.unavailable_fields == frozenset({"tco"})
    assert {"tco", "security_posture", "renewal_date"} <= GATED_FIELDS


def test_evidence_indexes() -> None:
    s = (
        SnapshotBuilder()
        .capability("c1", "C")
        .tcap("t1", "T")
        .app("a1", "A", caps=["c1"], tcaps_provided=["t1"])
        .app("a2", "B")
        .integration("i1", "a1", "a2")
        .build()
    )
    assert s.integrations_between("a1", "a2") == ["i1"]
    assert s.integrations_between("a2", "a1") == []
    assert s.serves("a1", "c1") and not s.serves("a2", "c1")
    assert s.realizes("a1", "t1") and not s.realizes("a2", "t1")
