"""Table-driven unit tests for _reaches() -- ADP-d8u.6, research.md Decision 2.

Pure BFS, no I/O -- driven entirely from a plain dict[str, list[str]]
adjacency representation, no session fixture, no async, mirroring
test_objective_status.py's own dependency-free style for compute_status().
The thin async wrapper (_would_create_cycle, which self-checks then fetches
existing edges before delegating here) is exercised indirectly via the
contract tests in tests/contract/test_strategy_api_contract.py.

Edge convention (matches _objective_dependencies / _would_create_cycle):
edges[X] = [Y, ...] means "X depends on Y". _reaches(start, target, edges)
asks: following existing depends_on edges forward from `start`, can
`target` be reached? _would_create_cycle(objective_id, depends_on_id, ...)
calls _reaches(depends_on_id, objective_id, edges) -- if the objective
about to be depended-on can already reach back to the objective doing the
depending, adding the new edge would close a loop.
"""

from __future__ import annotations

import pytest

from adp.strategy.initiatives import _reaches


@pytest.mark.parametrize(
    "edges, start, target, expected",
    [
        # No edges at all -- nothing is reachable from anything.
        ({}, "A", "B", False),
        # Direct edge A -> B (A depends on B): B is directly reachable from A.
        # This is also the "direct 2-cycle" shape -- if B already depends on
        # A, adding A depends_on B would close a 2-cycle, detected via
        # _reaches(B, A, ...) below.
        ({"A": ["B"]}, "A", "B", True),
        ({"A": ["B"]}, "B", "A", False),
        # 3-node chain: A -> B -> C. C is transitively reachable from A.
        ({"A": ["B"], "B": ["C"]}, "A", "C", True),
        # Longer (5+ node) chain: A -> B -> C -> D -> E.
        ({"A": ["B"], "B": ["C"], "C": ["D"], "D": ["E"]}, "A", "E", True),
        # Non-cyclic branch: A -> B, A -> C (siblings). B cannot reach C.
        ({"A": ["B", "C"]}, "B", "C", False),
        # Unrelated node -- target simply not present in the graph at all.
        ({"A": ["B"]}, "A", "Z", False),
        # start == target with no self-edge -- trivially not reachable.
        ({"A": ["B"]}, "A", "A", False),
    ],
)
def test_reaches(edges, start, target, expected) -> None:
    assert _reaches(start, target, edges) is expected
