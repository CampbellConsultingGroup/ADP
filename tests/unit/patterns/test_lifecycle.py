"""Pattern version lifecycle transition table (935 FR-007, data-model.md)."""

from __future__ import annotations

import itertools

import pytest

from adp.patterns.lifecycle import allowed_transitions, is_allowed
from adp.patterns.registry_models import PatternLifecycle as L

_ALLOWED = {
    (L.DRAFT, L.PROPOSED),
    (L.PROPOSED, L.CURRENT),
    (L.PROPOSED, L.DRAFT),
    (L.CURRENT, L.DEPRECATED),
    (L.DEPRECATED, L.CURRENT),
    (L.DEPRECATED, L.DECOMMISSIONED),
}


@pytest.mark.parametrize(("src", "dst"), list(itertools.product(L, L)))
def test_transition_matrix(src: L, dst: L) -> None:
    assert is_allowed(src, dst) == ((src, dst) in _ALLOWED)
    assert (dst in allowed_transitions(src)) == ((src, dst) in _ALLOWED)


def test_decommissioned_is_terminal() -> None:
    assert allowed_transitions(L.DECOMMISSIONED) == frozenset()


def test_states_are_the_five_documented() -> None:
    assert [s.value for s in L] == ["draft", "proposed", "current", "deprecated", "decommissioned"]


def test_allowed_transitions_is_ordered_list_friendly() -> None:
    # The API returns allowed transitions in declared state order.
    from adp.patterns.lifecycle import allowed_transitions_ordered

    assert allowed_transitions_ordered(L.PROPOSED) == [L.DRAFT, L.CURRENT]
    assert allowed_transitions_ordered(L.DEPRECATED) == [L.CURRENT, L.DECOMMISSIONED]
