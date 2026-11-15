"""Pattern version lifecycle state machine (935 FR-007). Pure, no I/O.

Deliberately differs from the design lifecycle (`adp.api.routers.lifecycle`): versions are
immutable once proposed, so there is no reset-to-draft after promotion and no ``complete``
state (spec GT-11).
"""

from __future__ import annotations

from adp.patterns.registry_models import PatternLifecycle as L

_TRANSITIONS: dict[L, frozenset[L]] = {
    L.DRAFT: frozenset({L.PROPOSED}),
    L.PROPOSED: frozenset({L.CURRENT, L.DRAFT}),
    L.CURRENT: frozenset({L.DEPRECATED}),
    L.DEPRECATED: frozenset({L.CURRENT, L.DECOMMISSIONED}),
    L.DECOMMISSIONED: frozenset(),
}


def allowed_transitions(state: L) -> frozenset[L]:
    """Every state a version in ``state`` may move to."""
    return _TRANSITIONS[state]


def allowed_transitions_ordered(state: L) -> list[L]:
    """:func:`allowed_transitions` in declared state order (stable for the API and UI)."""
    allowed = _TRANSITIONS[state]
    return [s for s in L if s in allowed]


def is_allowed(src: L, dst: L) -> bool:
    return dst in _TRANSITIONS[src]
