"""Capability-model analysis engine (938-capability-model-analysis, ADP-6et.2).

Pure functions over a per-request ``CapabilitySnapshot`` (built by ``cap_analysis_store``): no I/O,
no store imports, and ``as_of`` injected so every date rule is deterministic. Nothing computed here
is stored (spec FR-022, guard test).

    business L3 -> application capability L3 -> technical L2/L3
                   application capability L3 <- realized by applications

- ``business_rollup``: health / risk / cost / technology exposure per business capability. An L3's
  value is the worst over its contributing applications (or technical capabilities, for exposure);
  an L2/L1's is the worst over its leaf L3s, with the spread counted over leaves (FR-007). Retired
  applications are excluded but listed (FR-005).
- ``impact``: from a technical capability (and its descendants) up to business capabilities.
- ``technology_dependencies``: the derived business -> technology view (FR-014).
- ``findings``: overlaps, gaps and shared application capabilities (FR-015..FR-017).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from adp.application.app_capability_models import AppRef, CapRef, GeoRef, LinkedCapRef
from adp.application.cap_analysis_models import (
    LIFECYCLE_ORDER,
    RISK_ORDER,
    AppVia,
    CapabilityFindings,
    CapabilityGaps,
    CapabilityRollup,
    CapabilityRollupResponse,
    CostRollup,
    ExposureRollup,
    HealthRollup,
    ImpactAppCapability,
    ImpactApplication,
    ImpactBusiness,
    ImpactResult,
    LifecycleBand,
    OverlapEntry,
    OverlapReason,
    RealizationMapping,
    RedundantApp,
    RedundantEntry,
    RedundantGroup,
    RiskBand,
    RiskRollup,
    SharedEntry,
    TechnologyDependency,
)
from adp.organization.geo_model import GeoGraph  # pure, no I/O (946)

HORIZON = timedelta(days=365)
SHARED_THRESHOLD = 3
RETIRED = "retired"

_HEALTH_KEYS = ("1", "2", "3", "4", "5", "unassessed", "no_data")
_RISK_KEYS = ("high", "medium", "low", "unknown", "no_data")
_EXPOSURE_KEYS = (*LIFECYCLE_ORDER, "no_data")


# ── Mapping rationale (943) ───────────────────────────────────────────────────

# A target mapping on an application TIME says to eliminate or migrate, or a redundant mapping
# on one TIME says to invest in, is worth a second look. Advisory only (943 FR-013).
_HINTS: dict[tuple[str, str], str] = {
    ("target", "Eliminate"): "TIME says Eliminate",
    ("target", "Migrate"): "TIME says Migrate",
    ("redundant", "Invest"): "TIME says Invest",
}


def consistency_hint(rationale: str | None, time_classification: str | None) -> str | None:
    """The non-blocking hint where a mapping's rationale and its application's TIME disagree."""
    if rationale is None or time_classification is None:
        return None
    return _HINTS.get((rationale, time_classification))


# ── Snapshot ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    level: int
    parent_id: str | None


@dataclass(frozen=True)
class TechNode(Node):
    lifecycle_status: str = "current"
    end_of_life_date: date | None = None


@dataclass(frozen=True)
class AppInfo:
    id: str
    name: str
    lifecycle_status: str
    health_score: int | None
    time_classification: str | None = None
    r_strategy: str | None = None


@dataclass(frozen=True)
class Realization:
    """943: why and where an application realizes an application capability (None = unclassified
    / everywhere)."""

    rationale: str | None = None
    geography_id: str | None = None


@dataclass(frozen=True)
class GeoInfo:
    parent_id: str | None
    name: str
    code: str | None


@dataclass(frozen=True)
class RiskInfo:
    security_posture: str | None
    vulnerability_status: str | None
    end_of_support_date: date | None


@dataclass(frozen=True)
class CapabilitySnapshot:
    business: Mapping[str, Node]
    app_caps: Mapping[str, Node]
    technical: Mapping[str, TechNode]
    biz_to_ac: Mapping[str, frozenset[str]]
    ac_to_tc: Mapping[str, frozenset[str]]
    ac_to_apps: Mapping[str, frozenset[str]]
    apps: Mapping[str, AppInfo]
    risk: Mapping[str, RiskInfo]
    cost: Mapping[str, Decimal]
    risk_visible: bool
    cost_visible: bool
    # 943: keyed (app_capability_id, app_id); a missing key reads as unclassified, everywhere.
    realizations: Mapping[tuple[str, str], Realization] = field(default_factory=dict)
    # 943: only populated when some realization names a geography (research R4).
    geographies: Mapping[str, GeoInfo] = field(default_factory=dict)
    # 946: containment as of today across hierarchies (store sets it with the geographies).
    geo_graph: GeoGraph | None = None


# ── Tree helpers ──────────────────────────────────────────────────────────────


def path(node_id: str, tree: Mapping[str, Node]) -> list[CapRef]:
    """Ancestors of node_id, L1 first, excluding the node itself (cycle-safe)."""
    out: list[CapRef] = []
    seen = {node_id}
    current = tree.get(node_id)
    while current is not None and current.parent_id and current.parent_id not in seen:
        seen.add(current.parent_id)
        current = tree.get(current.parent_id)
        if current is not None:
            out.append(_ref(current))
    return list(reversed(out))


def _ref(node: Node) -> CapRef:
    return CapRef(id=node.id, name=node.name, level=node.level)


def _linked(node: Node, tree: Mapping[str, Node]) -> LinkedCapRef:
    return LinkedCapRef(id=node.id, name=node.name, level=node.level, path=path(node.id, tree))


def _children(tree: Mapping[str, Node]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for node in tree.values():
        if node.parent_id is not None:
            out.setdefault(node.parent_id, []).append(node.id)
    return out


def _descendants(node_id: str, children: Mapping[str, list[str]]) -> list[str]:
    out: list[str] = []
    stack = list(children.get(node_id, []))
    seen: set[str] = {node_id}
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        out.append(nid)
        stack.extend(children.get(nid, []))
    return out


def _by_name(nodes: Iterable[Node]) -> list[Node]:
    return sorted(nodes, key=lambda n: (n.name.lower(), n.id))


def _expand_technical(
    tc_ids: Iterable[str], snapshot: CapabilitySnapshot, children: Mapping[str, list[str]]
) -> set[str]:
    """A linked technical L2 stands for itself plus its children (FR-011, FR-013)."""
    out: set[str] = set()
    for tc in tc_ids:
        if tc in snapshot.technical:
            out.add(tc)
            out.update(t for t in _descendants(tc, children) if t in snapshot.technical)
    return out


# ── Bands ─────────────────────────────────────────────────────────────────────


def risk_band(risk: RiskInfo | None, as_of: date) -> RiskBand:
    """FR-006 fixed mapping (confirmed with the user, 2026-11-15)."""
    if risk is None:
        return "unknown"
    eos = risk.end_of_support_date
    if (
        risk.vulnerability_status in ("open_high", "critical")
        or risk.security_posture == "weak"
        or (eos is not None and eos <= as_of)
    ):
        return "high"
    if (
        risk.vulnerability_status == "open_low"
        or risk.security_posture == "adequate"
        or (eos is not None and eos <= as_of + HORIZON)
    ):
        return "medium"
    if risk.security_posture == "strong" and risk.vulnerability_status == "none_known":
        return "low"
    return "unknown"


def effective_band(tc: TechNode, as_of: date) -> LifecycleBand:
    """FR-012: status and end-of-life date combined into one ordered band."""
    eol = tc.end_of_life_date
    if tc.lifecycle_status == "retired" or (eol is not None and eol <= as_of):
        return "past_end_of_life"
    if tc.lifecycle_status == "retiring" or (eol is not None and eol <= as_of + HORIZON):
        return "retiring"
    if tc.lifecycle_status == "contained":
        return "contained"
    if tc.lifecycle_status == "emerging":
        return "emerging"
    return "current"


def _worst_of(values: Iterable[str], order: tuple[str, ...]) -> str | None:
    ranked = [order.index(v) for v in values if v in order]
    return order[min(ranked)] if ranked else None


# ── Roll-up ───────────────────────────────────────────────────────────────────


@dataclass
class _Leaf:
    """Per business L3: who contributes, and the L3's own worst values."""

    apps: dict[str, set[str]]  # app id -> application capability ids it acts through
    excluded: set[str]
    tech: set[str]
    health_worst: int | None
    risk_worst: RiskBand | None
    exposure_worst: LifecycleBand | None


def _leaf(
    cap_id: str, snapshot: CapabilitySnapshot, as_of: date, children: Mapping[str, list[str]]
) -> _Leaf:
    apps: dict[str, set[str]] = {}
    excluded: set[str] = set()
    acs = snapshot.biz_to_ac.get(cap_id, frozenset())
    for ac in acs:
        if ac not in snapshot.app_caps:
            continue
        for app_id in snapshot.ac_to_apps.get(ac, frozenset()):
            info = snapshot.apps.get(app_id)
            if info is None:
                continue
            if info.lifecycle_status == RETIRED:
                excluded.add(app_id)
            else:
                apps.setdefault(app_id, set()).add(ac)
    tech = _expand_technical(
        (tc for ac in acs if ac in snapshot.app_caps for tc in snapshot.ac_to_tc.get(ac, ())),
        snapshot,
        children,
    )
    scores = [s for a in apps if (s := snapshot.apps[a].health_score) is not None]
    bands = [risk_band(snapshot.risk.get(a), as_of) for a in apps]
    return _Leaf(
        apps=apps,
        excluded=excluded,
        tech=tech,
        health_worst=min(scores) if scores else None,
        risk_worst=_worst_of(bands, RISK_ORDER),  # type: ignore[arg-type]
        exposure_worst=_worst_of(
            (effective_band(snapshot.technical[t], as_of) for t in tech), LIFECYCLE_ORDER
        ),  # type: ignore[arg-type]
    )


def _zero(keys: tuple[str, ...]) -> dict[str, int]:
    return dict.fromkeys(keys, 0)


def _l3_spreads(
    leaf: _Leaf, snapshot: CapabilitySnapshot, as_of: date
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    health, risk, exposure = _zero(_HEALTH_KEYS), _zero(_RISK_KEYS), _zero(_EXPOSURE_KEYS)
    if not leaf.apps:
        health["no_data"] = risk["no_data"] = 1
    for app_id in leaf.apps:
        score = snapshot.apps[app_id].health_score
        health[str(score) if score is not None else "unassessed"] += 1
        risk[risk_band(snapshot.risk.get(app_id), as_of)] += 1
    if not leaf.tech:
        exposure["no_data"] = 1
    for tc in leaf.tech:
        exposure[effective_band(snapshot.technical[tc], as_of)] += 1
    return health, risk, exposure


def _parent_spreads(leaves: list[_Leaf]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    health, risk, exposure = _zero(_HEALTH_KEYS), _zero(_RISK_KEYS), _zero(_EXPOSURE_KEYS)
    for leaf in leaves:
        if leaf.health_worst is not None:
            health[str(leaf.health_worst)] += 1
        else:
            health["unassessed" if leaf.apps else "no_data"] += 1
        if leaf.risk_worst is not None:
            risk[leaf.risk_worst] += 1
        else:
            risk["unknown" if leaf.apps else "no_data"] += 1
        exposure[leaf.exposure_worst or "no_data"] += 1
    return health, risk, exposure


def _cost(app_ids: Iterable[str], snapshot: CapabilitySnapshot) -> CostRollup:
    total: Decimal | None = None
    missing = 0
    for app_id in app_ids:
        tco = snapshot.cost.get(app_id)
        if tco is None:
            missing += 1
        else:
            total = tco if total is None else total + tco
    return CostRollup(total_tco=total, apps_without_cost=missing)


def _app_vias(apps: Mapping[str, set[str]], snapshot: CapabilitySnapshot) -> list[AppVia]:
    out = [
        AppVia(
            id=app_id,
            name=snapshot.apps[app_id].name,
            via=[_ref(snapshot.app_caps[a]) for a in _ids_by_name(vias, snapshot.app_caps)],
        )
        for app_id, vias in apps.items()
    ]
    return sorted(out, key=lambda a: (a.name.lower(), a.id))


def _ids_by_name(ids: Iterable[str], tree: Mapping[str, Node]) -> list[str]:
    return [n.id for n in _by_name(tree[i] for i in ids if i in tree)]


def business_rollup(snapshot: CapabilitySnapshot, as_of: date) -> CapabilityRollupResponse:
    """FR-005..FR-010 (and FR-013 exposure) for every business capability, at every level."""
    children = _children(snapshot.business)
    tech_children = _children(snapshot.technical)
    leaves = {
        cid: _leaf(cid, snapshot, as_of, tech_children)
        for cid, node in snapshot.business.items()
        if node.level == 3
    }
    items: list[CapabilityRollup] = []
    for node in _by_name(snapshot.business.values()):
        if node.level == 3:
            group = [leaves[node.id]]
            health_spread, risk_spread, exposure_spread = _l3_spreads(group[0], snapshot, as_of)
        else:
            group = [leaves[d] for d in _descendants(node.id, children) if d in leaves]
            health_spread, risk_spread, exposure_spread = _parent_spreads(group)
        apps: dict[str, set[str]] = {}
        excluded: set[str] = set()
        for leaf in group:
            for app_id, vias in leaf.apps.items():
                apps.setdefault(app_id, set()).update(vias)
            excluded |= leaf.excluded
        healths = [lf.health_worst for lf in group if lf.health_worst is not None]
        items.append(
            CapabilityRollup(
                capability_id=node.id,
                name=node.name,
                level=node.level,
                contributing_apps=_app_vias(apps, snapshot),
                excluded_retired_apps=sorted(
                    (AppRef(id=a, name=snapshot.apps[a].name) for a in excluded),
                    key=lambda r: (r.name.lower(), r.id),
                ),
                health=HealthRollup(worst=min(healths) if healths else None, spread=health_spread),
                risk=(
                    RiskRollup(
                        worst=_worst_of(
                            (lf.risk_worst for lf in group if lf.risk_worst), RISK_ORDER
                        ),  # type: ignore[arg-type]
                        spread=risk_spread,
                    )
                    if snapshot.risk_visible
                    else None
                ),
                cost=_cost(apps, snapshot) if snapshot.cost_visible else None,
                exposure=ExposureRollup(
                    worst=_worst_of(  # type: ignore[arg-type]
                        (lf.exposure_worst for lf in group if lf.exposure_worst), LIFECYCLE_ORDER
                    ),
                    spread=exposure_spread,
                ),
            )
        )
    return CapabilityRollupResponse(
        as_of=as_of,
        risk_available=snapshot.risk_visible,
        cost_available=snapshot.cost_visible,
        items=items,
    )


# ── Impact (US3) ──────────────────────────────────────────────────────────────


def impact(snapshot: CapabilitySnapshot, tc_id: str) -> ImpactResult | None:
    """FR-011. None when the technical capability doesn't exist. No cost or risk content."""
    tc = snapshot.technical.get(tc_id)
    if tc is None:
        return None
    covered = _expand_technical([tc_id], snapshot, _children(snapshot.technical))
    ac_via: dict[str, set[str]] = {}
    for ac, tcs in snapshot.ac_to_tc.items():
        hit = tcs & covered
        if hit and ac in snapshot.app_caps:
            ac_via[ac] = set(hit)
    app_via: dict[str, set[str]] = {}
    for ac in ac_via:
        for app_id in snapshot.ac_to_apps.get(ac, frozenset()):
            if app_id in snapshot.apps:
                app_via.setdefault(app_id, set()).add(ac)
    biz_routes: dict[str, set[str]] = {}
    for biz, acs in snapshot.biz_to_ac.items():
        hit = acs & ac_via.keys()
        if hit and biz in snapshot.business:
            biz_routes[biz] = set(hit)

    def refs(ids: Iterable[str], tree: Mapping[str, Node]) -> list[CapRef]:
        return [_ref(tree[i]) for i in _ids_by_name(ids, tree)]

    return ImpactResult(
        technical_capability=_linked(tc, snapshot.technical),
        covered_technical=refs(covered, snapshot.technical),
        application_capabilities=[
            ImpactAppCapability(
                **_linked(snapshot.app_caps[ac], snapshot.app_caps).model_dump(),
                via_technical=refs(ac_via[ac], snapshot.technical),
            )
            for ac in _ids_by_name(ac_via, snapshot.app_caps)
        ],
        applications=sorted(
            (
                ImpactApplication(
                    id=app_id,
                    name=snapshot.apps[app_id].name,
                    lifecycle_status=snapshot.apps[app_id].lifecycle_status,  # type: ignore[arg-type]
                    via=refs(vias, snapshot.app_caps),
                )
                for app_id, vias in app_via.items()
            ),
            key=lambda a: (a.name.lower(), a.id),
        ),
        business_capabilities=[
            ImpactBusiness(
                **_linked(snapshot.business[b], snapshot.business).model_dump(),
                routes=refs(biz_routes[b], snapshot.app_caps),
            )
            for b in _ids_by_name(biz_routes, snapshot.business)
        ],
    )


# ── Technology dependencies (US4) ─────────────────────────────────────────────


def technology_dependencies(
    snapshot: CapabilitySnapshot, cap_id: str, as_of: date
) -> list[TechnologyDependency] | None:
    """FR-014. For an L1/L2, the union over its L3 descendants. None for an unknown capability."""
    node = snapshot.business.get(cap_id)
    if node is None:
        return None
    if node.level == 3:
        leaves = [cap_id]
    else:
        leaves = [
            d
            for d in _descendants(cap_id, _children(snapshot.business))
            if snapshot.business[d].level == 3
        ]
    tech_children = _children(snapshot.technical)
    out: list[TechnologyDependency] = []
    seen: set[tuple[str, str, str]] = set()
    for leaf in _ids_by_name(leaves, snapshot.business):
        for ac in _ids_by_name(snapshot.biz_to_ac.get(leaf, ()), snapshot.app_caps):
            tcs = _expand_technical(snapshot.ac_to_tc.get(ac, ()), snapshot, tech_children)
            for tc_id in _ids_by_name(tcs, snapshot.technical):
                key = (leaf, ac, tc_id)
                if key in seen:
                    continue
                seen.add(key)
                tc = snapshot.technical[tc_id]
                out.append(
                    TechnologyDependency(
                        technical=_linked(tc, snapshot.technical),
                        lifecycle_status=tc.lifecycle_status,  # type: ignore[arg-type]
                        end_of_life_date=tc.end_of_life_date,
                        effective_band=effective_band(tc, as_of),
                        via_app_capability=_ref(snapshot.app_caps[ac]),
                        via_business_capability=_ref(snapshot.business[leaf]),
                    )
                )
    return out


# ── Findings (US5) ────────────────────────────────────────────────────────────


def _realization(snapshot: CapabilitySnapshot, ac: str, app_id: str) -> Realization:
    return snapshot.realizations.get((ac, app_id), Realization())


def _geo_ref(snapshot: CapabilitySnapshot, geo_id: str | None) -> GeoRef | None:
    """None for no geography, and for a dangling id (it reads as everywhere, research R3)."""
    info = snapshot.geographies.get(geo_id) if geo_id else None
    return GeoRef(id=geo_id, name=info.name, code=info.code) if info and geo_id else None


def _graph(snapshot: CapabilitySnapshot) -> GeoGraph:
    if snapshot.geo_graph is not None:
        return snapshot.geo_graph
    # Hand-built snapshots (tests) give parents only: a geography with a code is a country.
    return GeoGraph.from_tree(
        (g, info.parent_id, info.code is not None) for g, info in snapshot.geographies.items()
    )


def _scopes_overlap(
    a: str | None, b: str | None, snapshot: CapabilitySnapshot, graph: GeoGraph | None = None
) -> bool:
    """Two scopes overlap when either is everywhere, or one geography contains the other, or
    (946) they share a country -- across hierarchies. An unknown geography counts as
    everywhere."""
    if a not in snapshot.geographies or b not in snapshot.geographies:
        return True
    assert a is not None and b is not None
    return (graph or _graph(snapshot)).overlaps(a, b)


def _mapping(snapshot: CapabilitySnapshot, ac: str, app_id: str) -> RealizationMapping:
    r = _realization(snapshot, ac, app_id)
    return RealizationMapping(
        via=_ref(snapshot.app_caps[ac]),
        rationale=r.rationale,  # type: ignore[arg-type]
        geography=_geo_ref(snapshot, r.geography_id),
        hint=consistency_hint(r.rationale, snapshot.apps[app_id].time_classification),
    )


def _overlap_reasons(
    apps: Mapping[str, set[str]], snapshot: CapabilitySnapshot
) -> list[OverlapReason]:
    """943 FR-007/FR-008 over every (application, application capability) mapping."""
    by_name = sorted(apps, key=lambda a: (snapshot.apps[a].name.lower(), a))
    rows = [(app, ac, _realization(snapshot, ac, app)) for app in by_name for ac in apps[app]]
    unclassified = [a for a in by_name if any(r.rationale is None for x, _, r in rows if x == a)]
    redundant = [
        a for a in by_name if any(r.rationale == "redundant" for x, _, r in rows if x == a)
    ]
    targets = [(app, r.geography_id) for app, _, r in rows if r.rationale == "target"]
    competing: set[str] = set()
    graph = _graph(snapshot) if len(targets) > 1 else None
    for i, (a, ga) in enumerate(targets):
        for b, gb in targets[i + 1 :]:
            if a != b and _scopes_overlap(ga, gb, snapshot, graph):
                competing.update((a, b))
    reasons: list[OverlapReason] = []
    if unclassified:
        reasons.append(OverlapReason(code="unclassified", application_ids=unclassified))
    if redundant:
        reasons.append(OverlapReason(code="redundant", application_ids=redundant))
    if not unclassified and not redundant and not targets:
        reasons.append(OverlapReason(code="no_target", application_ids=[]))
    if competing:
        reasons.append(
            OverlapReason(
                code="competing_targets", application_ids=[a for a in by_name if a in competing]
            )
        )
    return reasons


def _redundant_groups(snapshot: CapabilitySnapshot) -> list[RedundantGroup]:
    """943 FR-012: redundant mappings of non-retired applications, by business L3 they reach."""
    entries_by_ac: dict[str, list[RedundantEntry]] = {}
    for (ac, app_id), r in snapshot.realizations.items():
        info = snapshot.apps.get(app_id)
        if (
            r.rationale != "redundant"
            or info is None
            or info.lifecycle_status == RETIRED
            or ac not in snapshot.app_caps
            or app_id not in snapshot.ac_to_apps.get(ac, frozenset())
        ):
            continue
        entries_by_ac.setdefault(ac, []).append(
            RedundantEntry(
                application=RedundantApp(
                    id=app_id,
                    name=info.name,
                    time_classification=info.time_classification,  # type: ignore[arg-type]
                    r_strategy=info.r_strategy,  # type: ignore[arg-type]
                ),
                app_capability=_linked(snapshot.app_caps[ac], snapshot.app_caps),
                geography=_geo_ref(snapshot, r.geography_id),
                hint=consistency_hint(r.rationale, info.time_classification),
            )
        )
    if not entries_by_ac:
        return []

    def ordered(entries: list[RedundantEntry]) -> list[RedundantEntry]:
        return sorted(
            entries,
            key=lambda e: (
                e.application.name.lower(),
                e.app_capability.name.lower(),
                e.app_capability.id,
            ),
        )

    groups: list[RedundantGroup] = []
    reached: set[str] = set()
    for b in _by_name(n for n in snapshot.business.values() if n.level == 3):
        acs = [a for a in snapshot.biz_to_ac.get(b.id, ()) if a in entries_by_ac]
        if acs:
            reached.update(acs)
            groups.append(
                RedundantGroup(
                    business=_linked(b, snapshot.business),
                    entries=ordered([e for a in acs for e in entries_by_ac[a]]),
                )
            )
    orphans = [e for a, es in entries_by_ac.items() if a not in reached for e in es]
    if orphans:
        groups.append(RedundantGroup(business=None, entries=ordered(orphans)))
    return groups


def findings(snapshot: CapabilitySnapshot) -> CapabilityFindings:
    """FR-015..FR-017. Overlaps ignore Retired applications. No cost or risk content.

    943: each overlap carries its mappings' rationale and geography, a derived status and the
    reasons it needs attention (needs-attention first); ``redundant`` lists redundant mappings."""
    biz_l3 = _by_name(n for n in snapshot.business.values() if n.level == 3)
    ac_l3 = _by_name(n for n in snapshot.app_caps.values() if n.level == 3)

    overlaps: list[OverlapEntry] = []
    for b in biz_l3:
        apps: dict[str, set[str]] = {}
        for ac in snapshot.biz_to_ac.get(b.id, ()):
            if ac not in snapshot.app_caps:
                continue
            for app_id in snapshot.ac_to_apps.get(ac, ()):
                info = snapshot.apps.get(app_id)
                if info is not None and info.lifecycle_status != RETIRED:
                    apps.setdefault(app_id, set()).add(ac)
        if len(apps) >= 2:
            vias = _app_vias(apps, snapshot)
            for v in vias:
                v.mappings = [_mapping(snapshot, a.id, v.id) for a in v.via]
            reasons = _overlap_reasons(apps, snapshot)
            overlaps.append(
                OverlapEntry(
                    business=_linked(b, snapshot.business),
                    applications=vias,
                    status="needs_attention" if reasons else "explained",
                    reasons=reasons,
                )
            )
    # Needs attention first; stable within each section (already by business name).
    overlaps.sort(key=lambda o: o.status != "needs_attention")

    business_by_ac: dict[str, set[str]] = {}
    for biz, acs in snapshot.biz_to_ac.items():
        if biz not in snapshot.business:
            continue
        for ac in acs:
            business_by_ac.setdefault(ac, set()).add(biz)

    def linked_ac(n: Node) -> LinkedCapRef:
        return _linked(n, snapshot.app_caps)

    return CapabilityFindings(
        redundant=_redundant_groups(snapshot),
        overlaps=overlaps,
        gaps=CapabilityGaps(
            business_without_app_capability=[
                _linked(b, snapshot.business)
                for b in biz_l3
                if not any(ac in snapshot.app_caps for ac in snapshot.biz_to_ac.get(b.id, ()))
            ],
            app_capability_without_business=[
                linked_ac(a) for a in ac_l3 if not business_by_ac.get(a.id)
            ],
            app_capability_without_application=[
                linked_ac(a)
                for a in ac_l3
                if not any(app in snapshot.apps for app in snapshot.ac_to_apps.get(a.id, ()))
            ],
        ),
        shared=[
            SharedEntry(
                app_capability=linked_ac(a),
                business=[
                    _ref(snapshot.business[b])
                    for b in _ids_by_name(business_by_ac[a.id], snapshot.business)
                ],
                count=len(business_by_ac[a.id]),
            )
            for a in ac_l3
            if len(business_by_ac.get(a.id, ())) >= SHARED_THRESHOLD
        ],
        shared_threshold=SHARED_THRESHOLD,
    )
