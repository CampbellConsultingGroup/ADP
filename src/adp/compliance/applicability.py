"""Derived framework applicability (948 GEO-03, ADP-bo1.3). Pure: no I/O, the date is passed in.

A framework has a jurisdiction (places and hierarchy nodes) and trigger relations (947 typed
geography relations, per subject type). For a subject on a date the answer is three-valued, with
the evidence that decided it (spec FR-004):

1. no jurisdiction or no triggers recorded          -> unknown
2. repealed, or not in force on the date            -> does_not_apply
3. no active link with a trigger relation            -> unknown
4. a trigger link whose geography overlaps the scope -> applies (every matching link is evidence)
5. otherwise                                         -> does_not_apply

An application's links include those of its legal entities, marked ``via`` (Q1). Geography is
resolved by 946's ``GeoGraph`` as of the same date, so a country joining or leaving a bloc changes
the answer with no backfill. Nothing here is stored (FR-006).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

from adp.organization.geo_model import GeoGraph

Status = Literal["applies", "does_not_apply", "unknown"]
How = Literal["same", "inside", "covers", "shares_countries"]


@dataclass(frozen=True)
class FrameworkFacts:
    id: str
    name: str
    status: str
    in_force_from: date | None
    geography_ids: tuple[str, ...]
    triggers: frozenset[tuple[str, str]]  # (subject type, relation)


@dataclass(frozen=True)
class LinkFact:
    subject_type: str  # whose link it is: application or legal_entity
    relation: str
    geography_id: str
    valid_from: date | None = None
    valid_to: date | None = None
    via_id: str | None = None  # the legal entity an application's link came through
    via_name: str | None = None

    def active(self, on: date) -> bool:
        return (self.valid_from is None or self.valid_from <= on) and (
            self.valid_to is None or on < self.valid_to
        )


@dataclass(frozen=True)
class Match:
    link: LinkFact
    scope_id: str
    how: How
    path: tuple[str, ...]  # geography ids from the link's geography up to the scope (inside)


@dataclass(frozen=True)
class Result:
    status: Status
    reason: str | None
    matches: tuple[Match, ...] = ()


def _label(relation: str, labels: Mapping[str, str]) -> str:
    return labels.get(relation, relation.replace("_", " ")).lower()


def _labels(relations: Iterable[str], labels: Mapping[str, str]) -> str:
    names = sorted({_label(r, labels) for r in relations})
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]


def path_up(graph: GeoGraph, start: str, goal: str) -> tuple[str, ...]:
    """Shortest chain of geography ids from ``start`` up to ``goal`` through memberships active in
    the graph (any hierarchy); empty when there is none."""
    seen = {start}
    queue: deque[tuple[str, ...]] = deque([(start,)])
    while queue:
        chain = queue.popleft()
        if chain[-1] == goal:
            return chain
        for parent in graph.parents(chain[-1]):
            if parent not in seen:
                seen.add(parent)
                queue.append((*chain, parent))
    return ()


def _meet(graph: GeoGraph, link_geo: str, scope: str) -> tuple[How, tuple[str, ...]] | None:
    if link_geo == scope:
        return "same", (link_geo,)
    if graph.contains(scope, link_geo):
        return "inside", path_up(graph, link_geo, scope)
    if graph.contains(link_geo, scope):
        return "covers", ()
    if graph.overlaps(link_geo, scope):
        return "shares_countries", ()
    return None


def not_in_force(f: FrameworkFacts, as_of: date) -> str | None:
    if f.status == "repealed":
        return "The framework is repealed"
    if f.in_force_from is not None and as_of < f.in_force_from:
        return f"Not in force until {f.in_force_from.isoformat()}"
    if f.in_force_from is None and f.status == "not_yet_applicable":
        return "The framework is not yet applicable"
    return None


def compute_framework_applicability(
    framework: FrameworkFacts,
    links: Iterable[LinkFact],
    graph: GeoGraph,
    as_of: date,
    relation_labels: Mapping[str, str] | None = None,
) -> Result:
    labels = relation_labels or {}
    if not framework.geography_ids or not framework.triggers:
        return Result("unknown", "No jurisdiction recorded for this framework")
    stopped = not_in_force(framework, as_of)
    if stopped:
        return Result("does_not_apply", stopped)
    relevant = [
        lk
        for lk in links
        if (lk.subject_type, lk.relation) in framework.triggers and lk.active(as_of)
    ]
    if not relevant:
        wanted = _labels((r for _, r in framework.triggers), labels)
        return Result("unknown", f"No {wanted} links recorded")
    matches = tuple(
        Match(lk, scope, how, path)
        for lk in relevant
        for scope in framework.geography_ids
        if (met := _meet(graph, lk.geography_id, scope)) is not None
        for how, path in [met]
    )
    if matches:
        return Result("applies", None, matches)
    used = _labels((lk.relation for lk in relevant), labels)
    return Result("does_not_apply", f"None of its {used} links are in the jurisdiction")
