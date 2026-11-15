"""Derived status and transition plateau (936 FR-013/FR-014). Pure functions."""

from __future__ import annotations

import pytest

from adp.patterns.conformance_models import (
    BindingResult,
    ElementRef,
    Finding,
    RoleBinding,
)
from adp.patterns.conformance_models import (
    ConformanceStatus as S,
)
from adp.patterns.conformance_models import (
    FindingKind as K,
)
from adp.patterns.engine import compute_conformance_status, compute_transition_plateau
from adp.patterns.models import ElementType
from adp.patterns.models import Severity as Sev

from .snapshots import make_pattern

BOUND = BindingResult(
    roles=[
        RoleBinding(
            role_key="x",
            element_type=ElementType.APPLICATION,
            label="X",
            elements=[ElementRef(type=ElementType.APPLICATION, id="a", name="A")],
            count=1,
        )
    ]
)
UNBOUND = BindingResult(
    roles=[RoleBinding(role_key="x", element_type=ElementType.APPLICATION, label="X")]
)


def f(code: str, kind: K, sev: Sev) -> Finding:
    return Finding(code=code, kind=kind, severity=sev, rule="r")


@pytest.mark.parametrize(
    ("findings", "expected"),
    [
        ([], S.CONFORMANT),
        ([f("C1", K.VIOLATION, Sev.ERROR)], S.NON_CONFORMANT),
        ([f("B3", K.BINDING, Sev.ERROR)], S.NON_CONFORMANT),
        ([f("L1", K.LIMIT, Sev.ERROR)], S.NON_CONFORMANT),
        ([f("C1", K.MATCH, Sev.ERROR)], S.NON_CONFORMANT),
        ([f("C1", K.EVALUATION_ERROR, Sev.ERROR)], S.INDETERMINATE),
        ([f("C1", K.FIELD_UNAVAILABLE, Sev.ERROR)], S.INDETERMINATE),
        ([f("C1", K.FIELD_UNAVAILABLE, Sev.WARNING)], S.CONFORMANT),
        ([f("C1", K.VIOLATION, Sev.WARNING)], S.CONFORMANT_WITH_WARNINGS),
        ([f("C1", K.MATCH, Sev.WARNING)], S.CONFORMANT_WITH_WARNINGS),
        ([f("B2", K.BINDING, Sev.WARNING)], S.CONFORMANT),
        ([f("E:R1", K.UNVERIFIABLE, Sev.INFO), f("C9", K.VIOLATION, Sev.INFO)], S.CONFORMANT),
        # precedence: first matching row wins
        (
            [f("C1", K.VIOLATION, Sev.WARNING), f("C2", K.EVALUATION_ERROR, Sev.ERROR)],
            S.INDETERMINATE,
        ),
        (
            [f("C2", K.EVALUATION_ERROR, Sev.ERROR), f("C1", K.VIOLATION, Sev.ERROR)],
            S.NON_CONFORMANT,
        ),
    ],
)
def test_status_table(findings: list[Finding], expected: S) -> None:
    assert compute_conformance_status(findings, BOUND) == expected


def test_nothing_bound_is_not_applicable_even_with_errors() -> None:
    assert compute_conformance_status([f("K:x", K.VIOLATION, Sev.ERROR)], UNBOUND) == (
        S.NOT_APPLICABLE
    )


TRANSITION = make_pattern(
    {"x": {"element_type": "application", "cardinality": "0..*"}},
    constraints=[{"id": c, "rule": "r", "expr": "true"} for c in ("C1", "C2", "C3")],
    kind="transition",
    transition={
        "from_pattern": "ea.test.old",
        "strategy": "strangler",
        "plateaus": [
            {"id": "PL1", "name": "One", "exit_criteria": ["C1"]},
            {"id": "PL2", "name": "Two", "exit_criteria": ["C1", "C2"]},
            {"id": "PL3", "name": "Three", "exit_criteria": ["C1", "C2", "C3"]},
        ],
    },
)


def test_plateau_none_reached() -> None:
    state = compute_transition_plateau(TRANSITION, [f("C1", K.VIOLATION, Sev.ERROR)])
    assert state is not None
    assert (state.reached, state.next, state.blocking) == (None, "PL1", ["C1"])


def test_plateau_partial() -> None:
    state = compute_transition_plateau(
        TRANSITION,
        [f("C2", K.FIELD_UNAVAILABLE, Sev.ERROR), f("C3", K.EVALUATION_ERROR, Sev.ERROR)],
    )
    assert state is not None
    assert (state.reached, state.next, state.blocking) == ("PL1", "PL2", ["C2"])


def test_plateau_all_reached_and_info_ignored() -> None:
    state = compute_transition_plateau(TRANSITION, [f("E:R1", K.UNVERIFIABLE, Sev.INFO)])
    assert state is not None
    assert (state.reached, state.next, state.blocking) == ("PL3", None, [])


def test_non_transition_has_no_plateau() -> None:
    pattern = make_pattern({"x": {"element_type": "application", "cardinality": "0..*"}})
    assert compute_transition_plateau(pattern, []) is None
