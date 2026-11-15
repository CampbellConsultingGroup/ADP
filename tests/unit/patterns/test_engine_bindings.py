"""Binding resolution (936 FR-008, research D4): selectors within scope, authoritative pins."""

from __future__ import annotations

from adp.patterns.cel import default_engine
from adp.patterns.conformance_models import FindingKind, PinIn, ScopeType
from adp.patterns.engine import Budget, resolve_bindings
from adp.patterns.models import ElementType as T
from adp.patterns.models import Severity
from adp.patterns.snapshot import Scope

from .snapshots import SnapshotBuilder, make_pattern

D1 = Scope(ScopeType.BUSINESS_DOMAIN, scope_ref="d1")


def _snap():  # type: ignore[no-untyped-def]
    return (
        SnapshotBuilder()
        .domain("d1", "Claims")
        .domain("d2", "Billing")
        .capability("c1", "Claims", domain="d1")
        .capability("c2", "Billing", domain="d2")
        .app("a2", "Beta", caps=["c1"], time_classification="Invest")
        .app("a1", "Alpha", caps=["c1"], time_classification="Invest")
        .app("a3", "Gamma", caps=["c1"], time_classification="Eliminate")
        .app("b1", "Billing App", caps=["c2"], time_classification="Invest")
        .app("hub", "Event Hub", application_type="cots")
        .build()
    )


PATTERN = make_pattern(
    {
        "app": {
            "element_type": "application",
            "cardinality": "0..*",
            "selector": "it.time_classification == 'Invest'",
        },
        "hub": {
            "element_type": "application",
            "cardinality": "1",
            "selector": "it.application_type == 'cots'",
        },
    }
)


def _bind(pins=(), pattern=PATTERN, scope=D1, snap=None):  # type: ignore[no-untyped-def]
    return resolve_bindings(
        pattern, snap or _snap(), scope, list(pins), default_engine(), Budget(10_000)
    )


def test_selector_filters_candidates_in_scope_and_orders_by_name() -> None:
    result = _bind()
    assert result.ids("app") == ["a1", "a2"]  # Alpha, Beta; Gamma fails, b1 out of scope
    assert result.ids("hub") == []  # the hub is not in domain d1
    assert result.findings == []


def test_pins_are_authoritative_and_may_be_outside_scope() -> None:
    result = _bind([PinIn(role_key="hub", element_type=T.APPLICATION, element_id="hub")])
    assert result.ids("hub") == ["hub"]
    assert result.ids("app") == ["a1", "a2"]


def test_pin_failing_selector_is_bound_with_b2_warning() -> None:
    result = _bind([PinIn(role_key="hub", element_type=T.APPLICATION, element_id="a1")])
    assert result.ids("hub") == ["a1"]
    [b2] = result.findings
    assert (b2.code, b2.kind, b2.severity) == (
        "B2.pin_fails_selector",
        FindingKind.BINDING,
        Severity.WARNING,
    )
    assert [e.id for e in b2.element_refs] == ["a1"]


def test_missing_pin_is_b3_error_and_not_bound() -> None:
    result = _bind([PinIn(role_key="hub", element_type=T.APPLICATION, element_id="gone")])
    assert result.ids("hub") == []
    [b3] = result.findings
    assert (b3.code, b3.severity) == ("B3.dangling_pin", Severity.ERROR)
    assert b3.element_refs[0].id == "gone"


def test_selector_errors_are_summarised_per_role_and_excluded() -> None:
    pattern = make_pattern(
        {
            "app": {
                "element_type": "application",
                "cardinality": "0..*",
                "selector": "it.no_such_field == 1",
            }
        }
    )
    result = _bind(pattern=pattern)
    assert result.ids("app") == []
    [s] = result.findings
    assert (s.code, s.kind) == ("S:app", FindingKind.EVALUATION_ERROR)
    assert sorted(e.id for e in s.element_refs) == ["a1", "a2", "a3"]


def test_no_selector_binds_every_candidate() -> None:
    pattern = make_pattern({"app": {"element_type": "application", "cardinality": "0..*"}})
    assert _bind(pattern=pattern).ids("app") == ["a1", "a2", "a3"]


def test_role_binding_metadata() -> None:
    result = _bind()
    app = result.roles[0]
    assert (app.role_key, app.element_type, app.count, app.label) == (
        "app",
        T.APPLICATION,
        2,
        "App",
    )
    assert [e.name for e in app.elements] == ["Alpha", "Beta"]
