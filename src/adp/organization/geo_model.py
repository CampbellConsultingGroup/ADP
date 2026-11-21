"""Geography as places, typed hierarchies and dated memberships (946 GEO-01, ADP-bo1.1).

Pure: no I/O. Built per request from rows the store reads; never stored.

* A **place** is atomic (a country in this cut). A **node** belongs to one hierarchy (Global,
  Europe, EU, APAC). A **membership** puts a node or a place under a node of the same hierarchy,
  valid from a date (inclusive, None = always) until a date (exclusive, None = open).
* As of a date, ``places(node)`` are the places reachable down active memberships;
  ``ancestors(g)`` are the nodes reachable up active memberships, across every hierarchy.
* A place may lie in another place (949 GEO-04: a subdivision or authority in its country,
  ``Entity.parent_place``). That is structural and undated: the subdivision is a descendant of its
  country and so of every node the country belongs to, and ``places(country)`` includes it.
* ``contains(a, b)``: a is b; otherwise b is a's descendant, or a is a node and b a node whose
  places are non-empty and all among a's. A place never contains a node, so a region with a
  single country is not inside that country. ``overlaps(a, b)``: either contains the other, or
  they share a place. For tree-shaped data these are exactly the old ancestor answers (research R5).

``check_membership`` / ``check_shape`` are the write invariants (spec FR-005); they raise or
return plain messages that the store turns into HTTP errors.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

EntityKind = Literal["place", "node"]
PLACE_HIERARCHY = "place"  # pseudo hierarchy id of the place-in-place edges (949)
Shape = Literal["strict_tree", "dag"]


@dataclass(frozen=True)
class Entity:
    id: str
    entity: EntityKind
    hierarchy_id: str | None = None
    parent_place: str | None = None  # 949: the country a subdivision lies in


@dataclass(frozen=True)
class Membership:
    id: str
    hierarchy_id: str
    parent_id: str
    child_id: str
    valid_from: date | None = None
    valid_to: date | None = None

    def active(self, on: date) -> bool:
        return (self.valid_from is None or self.valid_from <= on) and (
            self.valid_to is None or on < self.valid_to
        )

    def overlaps_period(self, other: Membership) -> bool:
        start_a, start_b = self.valid_from or date.min, other.valid_from or date.min
        end_a, end_b = self.valid_to or date.max, other.valid_to or date.max
        return start_a < end_b and start_b < end_a


class GeoGraph:
    def __init__(
        self, entities: Mapping[str, Entity], memberships: Iterable[Membership], as_of: date
    ) -> None:
        self.as_of = as_of
        self._entities = dict(entities)
        self._children: dict[str, list[str]] = defaultdict(list)
        self._parents: dict[str, list[Membership]] = defaultdict(list)
        for mb in memberships:
            if not mb.active(as_of):
                continue
            if mb.parent_id not in self._entities or mb.child_id not in self._entities:
                continue
            self._children[mb.parent_id].append(mb.child_id)
            self._parents[mb.child_id].append(mb)
        for e in self._entities.values():
            if e.entity == "place" and e.parent_place and e.parent_place in self._entities:
                self._children[e.parent_place].append(e.id)
                self._parents[e.id].append(
                    Membership(f"place:{e.id}", PLACE_HIERARCHY, e.parent_place, e.id)
                )
        self._places: dict[str, frozenset[str]] = {}
        self._ancestors: dict[str, frozenset[str]] = {}
        self._descendants: dict[str, frozenset[str]] = {}

    @classmethod
    def from_tree(
        cls, nodes: Iterable[tuple[str, str | None, bool]], as_of: date | None = None
    ) -> GeoGraph:
        """A graph from (id, parent id, is_place) rows -- one undated tree. Lets snapshots built
        the 940 way (and their tests) use the same containment rules."""
        rows = list(nodes)
        entities = {
            i: Entity(i, "place" if is_place else "node", None if is_place else "tree")
            for i, _, is_place in rows
        }
        memberships = [
            Membership(f"tree:{i}", "tree", parent, i) for i, parent, _ in rows if parent
        ]
        return cls(entities, memberships, as_of or date.today())

    def __contains__(self, geo_id: object) -> bool:
        return geo_id in self._entities

    def parent_place(self, geo_id: str) -> str | None:
        e = self._entities.get(geo_id)
        return e.parent_place if e is not None and e.parent_place in self._entities else None

    def hierarchy_of(self, geo_id: str) -> str | None:
        e = self._entities.get(geo_id)
        return e.hierarchy_id if e is not None and e.entity == "node" else None

    def is_place(self, geo_id: str) -> bool:
        e = self._entities.get(geo_id)
        return e is not None and e.entity == "place"

    def _walk(self, start: str, step: Mapping[str, list[str]]) -> frozenset[str]:
        seen: set[str] = set()
        stack = list(step.get(start, ()))
        while stack:
            node = stack.pop()
            if node in seen or node == start:
                continue
            seen.add(node)
            stack.extend(step.get(node, ()))
        return frozenset(seen)

    def descendants(self, geo_id: str) -> frozenset[str]:
        if geo_id not in self._descendants:
            self._descendants[geo_id] = self._walk(geo_id, self._children)
        return self._descendants[geo_id]

    def ancestors(self, geo_id: str) -> frozenset[str]:
        if geo_id not in self._ancestors:
            up = {child: [mb.parent_id for mb in mbs] for child, mbs in self._parents.items()}
            self._ancestors[geo_id] = self._walk(geo_id, up)
        return self._ancestors[geo_id]

    def places(self, geo_id: str) -> frozenset[str]:
        if geo_id not in self._places:
            if geo_id not in self._entities:
                out: frozenset[str] = frozenset()
            elif self.is_place(geo_id):
                out = frozenset({geo_id, *self.descendants(geo_id)})
            else:
                out = frozenset(d for d in self.descendants(geo_id) if self.is_place(d))
            self._places[geo_id] = out
        return self._places[geo_id]

    def parents(self, geo_id: str, hierarchy_id: str | None = None) -> list[str]:
        return sorted(
            mb.parent_id
            for mb in self._parents.get(geo_id, ())
            if hierarchy_id is None or mb.hierarchy_id == hierarchy_id
        )

    def contains(self, a: str, b: str) -> bool:
        if a not in self._entities or b not in self._entities:
            return False
        if a == b:
            return True
        if b in self.descendants(a):
            return True
        if self.is_place(a) or self.is_place(b):
            return False
        inner = self.places(b)
        return bool(inner) and inner <= self.places(a)

    def overlaps(self, a: str, b: str) -> bool:
        if a not in self._entities or b not in self._entities:
            return False
        if self.contains(a, b) or self.contains(b, a):
            return True
        return not self.places(a).isdisjoint(self.places(b))


# ── Write invariants (FR-005) ───────────────────────────────────────────────────


def check_membership(
    candidate: Membership,
    existing: Iterable[Membership],
    entities: Mapping[str, Entity],
    shape: Shape,
) -> None:
    """Raise ValueError naming the broken rule. ``existing`` may include the candidate's own id
    (an update); that row is ignored."""
    h = candidate.hierarchy_id
    parent = entities.get(candidate.parent_id)
    child = entities.get(candidate.child_id)
    if parent is None or child is None:
        missing = candidate.parent_id if parent is None else candidate.child_id
        raise ValueError(f"Geography {missing!r} not found")
    if parent.entity != "node" or parent.hierarchy_id != h:
        raise ValueError("The parent must be a node of this hierarchy")
    if child.entity == "node" and child.hierarchy_id != h:
        raise ValueError("A node from another hierarchy can't be a member here; add its places")
    if candidate.parent_id == candidate.child_id:
        raise ValueError("A node can't be a member of itself")
    if (
        candidate.valid_from is not None
        and candidate.valid_to is not None
        and candidate.valid_to <= candidate.valid_from
    ):
        raise ValueError("The end date must be after the start date")
    others = [mb for mb in existing if mb.hierarchy_id == h and mb.id != candidate.id]
    for mb in others:
        if (
            mb.parent_id == candidate.parent_id
            and mb.child_id == candidate.child_id
            and mb.overlaps_period(candidate)
        ):
            raise ValueError(
                f"{candidate.child_id} is already under {candidate.parent_id} for part of that "
                "period"
            )
    if shape == "strict_tree":
        for mb in others:
            if (
                mb.child_id == candidate.child_id
                and mb.parent_id != candidate.parent_id
                and mb.overlaps_period(candidate)
            ):
                raise ValueError(
                    f"{candidate.child_id} is already under {mb.parent_id} for part of that "
                    "period; a strict tree allows one parent at a time"
                )
    # Acyclic over every membership of the hierarchy, whatever its dates (stricter, simpler).
    up: dict[str, set[str]] = defaultdict(set)
    for mb in others:
        up[mb.child_id].add(mb.parent_id)
    stack, seen = [candidate.parent_id], set()
    while stack:
        node = stack.pop()
        if node == candidate.child_id:
            raise ValueError("That would make a cycle: the parent is already below the member")
        if node in seen:
            continue
        seen.add(node)
        stack.extend(up.get(node, ()))


def check_shape(memberships: Iterable[Membership], shape: Shape) -> list[str]:
    """Problems that stop a hierarchy being ``shape`` (only strict trees can fail)."""
    if shape != "strict_tree":
        return []
    by_child: dict[str, list[Membership]] = defaultdict(list)
    for mb in memberships:
        by_child[mb.child_id].append(mb)
    problems: list[str] = []
    for child, mbs in sorted(by_child.items()):
        for i, a in enumerate(mbs):
            if any(a.parent_id != b.parent_id and a.overlaps_period(b) for b in mbs[i + 1 :]):
                problems.append(f"{child} has two parents at the same time")
                break
    return problems
