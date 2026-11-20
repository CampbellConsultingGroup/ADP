"""Capability <-> org unit analysis (941-capability-org-mappings, ADP-55k.2).

Pure: no I/O. Everything here is computed per request from a frozen :class:`Snapshot` built by
``adp.organization.cap_mappings.build_snapshot`` and is never stored (FR-013, guard test
``test_cap_org_analysis_not_stored.py``):

* the **effective owner** of a capability: its own owner, else its nearest owned ancestor;
* the **geography note** on a performer whose geography is outside the unit's operating places;
* the **findings**: L1/L2 with no owner, shared-service candidates (L3s performed by two or more
  independent branches of the org tree), unmapped L3s and owned L3s with no performer;
* an org unit's **footprint**, including its descendant units' work, attributed.

Lists follow the capability tree in pre-order (siblings by position, then name); org units sort
by name. An empty ``geographies`` list on a performer means "no specific geography".
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from adp.organization.geo_model import GeoGraph
from adp.organization.models import (
    CapabilityOrgFindings,
    CapabilityOrgMapping,
    CapabilityOrgView,
    FindingCapability,
    FindingCounts,
    FootprintEntry,
    FootprintL1,
    FootprintL2,
    FootprintL3,
    FootprintPerformer,
    OrgUnitFootprint,
    Ref,
    SharedServiceCandidate,
    SharedServicePerformer,
)


@dataclass(frozen=True)
class CapNode:
    id: str
    name: str
    level: int
    parent_id: str | None
    position: int = 0


@dataclass(frozen=True)
class OuNode:
    id: str
    name: str
    level: int
    parent_id: str | None


@dataclass(frozen=True)
class GeoNode:
    id: str
    name: str
    level: int
    parent_id: str | None


@dataclass(frozen=True)
class MappingRow:
    id: str
    capability_id: str
    org_unit_id: str
    role: str
    geography_id: str | None = None


@dataclass(frozen=True)
class Snapshot:
    capabilities: Mapping[str, CapNode]
    org_units: Mapping[str, OuNode]
    geographies: Mapping[str, GeoNode]
    operates_in: Mapping[str, frozenset[str]]
    mappings: tuple[MappingRow, ...]
    # 946: containment as of today, across hierarchies. build() derives one from the nodes'
    # parent ids when the caller gives none (pure tests).
    graph: GeoGraph | None = None
    # Derived indexes, filled by build().
    owners: Mapping[str, str] = field(default_factory=dict)
    by_capability: Mapping[str, tuple[MappingRow, ...]] = field(default_factory=dict)
    cap_order: tuple[str, ...] = ()

    @classmethod
    def build(
        cls,
        *,
        capabilities: Iterable[CapNode],
        org_units: Iterable[OuNode],
        geographies: Iterable[GeoNode],
        operates_in: Mapping[str, frozenset[str]],
        mappings: Iterable[MappingRow],
        graph: GeoGraph | None = None,
    ) -> Snapshot:
        caps = {c.id: c for c in capabilities}
        ous = {o.id: o for o in org_units}
        geos = {g.id: g for g in geographies}
        # Mappings whose capability or org unit is gone are dropped (SQLite has no cascade).
        rows = tuple(
            r for r in mappings if r.capability_id in caps and r.org_unit_id in ous
        )
        owners = {r.capability_id: r.org_unit_id for r in rows if r.role == "owner"}
        by_cap: dict[str, list[MappingRow]] = defaultdict(list)
        for r in rows:
            by_cap[r.capability_id].append(r)
        return cls(
            capabilities=caps,
            org_units=ous,
            geographies=geos,
            graph=graph
            or GeoGraph.from_tree((g.id, g.parent_id, g.level >= 3) for g in geos.values()),
            operates_in=dict(operates_in),
            mappings=rows,
            owners=owners,
            by_capability={k: tuple(v) for k, v in by_cap.items()},
            cap_order=_preorder(caps),
        )


def _preorder(caps: Mapping[str, CapNode]) -> tuple[str, ...]:
    children: dict[str | None, list[CapNode]] = defaultdict(list)
    for c in caps.values():
        parent = c.parent_id if c.parent_id in caps else None
        children[parent].append(c)
    out: list[str] = []

    def walk(parent: str | None) -> None:
        for c in sorted(children[parent], key=lambda n: (n.position, n.name.lower())):
            out.append(c.id)
            walk(c.id)

    walk(None)
    return tuple(out)


# ── Refs and paths ─────────────────────────────────────────────────────────────


def _cap_ref(s: Snapshot, cap_id: str) -> Ref:
    c = s.capabilities[cap_id]
    return Ref(id=c.id, name=c.name, level=c.level)


def _ou_ref(s: Snapshot, ou_id: str) -> Ref:
    o = s.org_units[ou_id]
    return Ref(id=o.id, name=o.name, level=o.level)


def _geo_ref(s: Snapshot, geo_id: str) -> Ref | None:
    g = s.geographies.get(geo_id)
    return Ref(id=g.id, name=g.name, level=g.level) if g else None


def _cap_ancestors(s: Snapshot, cap_id: str) -> list[str]:
    """Ancestor capability ids, nearest first."""
    out: list[str] = []
    parent = s.capabilities[cap_id].parent_id
    while parent is not None and parent in s.capabilities and parent not in out:
        out.append(parent)
        parent = s.capabilities[parent].parent_id
    return out


def _ou_ancestors(s: Snapshot, ou_id: str) -> list[str]:
    out: list[str] = []
    parent = s.org_units[ou_id].parent_id
    while parent is not None and parent in s.org_units and parent not in out:
        out.append(parent)
        parent = s.org_units[parent].parent_id
    return out


def _finding_cap(s: Snapshot, cap_id: str) -> FindingCapability:
    c = s.capabilities[cap_id]
    path = [_cap_ref(s, a) for a in reversed(_cap_ancestors(s, cap_id))]
    return FindingCapability(id=c.id, name=c.name, level=c.level, path=path)


def _by_name(s: Snapshot, ou_ids: Iterable[str]) -> list[str]:
    return sorted(set(ou_ids), key=lambda o: (s.org_units[o].name.lower(), o))


# ── US1: effective owner ───────────────────────────────────────────────────────


def effective_owner(s: Snapshot, cap_id: str) -> tuple[str | None, str | None]:
    """(owner org unit id, ancestor capability id it is inherited from, or None if its own)."""
    own = s.owners.get(cap_id)
    if own is not None:
        return own, None
    for ancestor in _cap_ancestors(s, cap_id):
        if ancestor in s.owners:
            return s.owners[ancestor], ancestor
    return None, None


# ── US2: geography note ────────────────────────────────────────────────────────


def outside_operating_geographies(s: Snapshot, ou_id: str, geo_id: str | None) -> bool:
    """FR-006: true when the geography is neither an operating geography of the unit nor inside
    one. A unit with no operating geographies has nothing to compare against, so never flagged."""
    operating = s.operates_in.get(ou_id) or frozenset()
    if geo_id is None or not operating:
        return False
    if s.graph is None or geo_id not in s.graph:
        return False  # unknown geography: nothing to compare against
    # 946: "inside" through memberships as of today, so a performer in Japan is inside APAC.
    return not any(s.graph.contains(op, geo_id) for op in operating)


def _mapping(s: Snapshot, r: MappingRow) -> CapabilityOrgMapping:
    return CapabilityOrgMapping(
        id=r.id,
        capability_id=r.capability_id,
        org_unit=_ou_ref(s, r.org_unit_id),
        role=r.role,  # type: ignore[arg-type]
        geography=_geo_ref(s, r.geography_id) if r.geography_id else None,
        outside_operating_geographies=(
            r.role == "performer"
            and outside_operating_geographies(s, r.org_unit_id, r.geography_id)
        ),
    )


def _sorted_mappings(s: Snapshot, rows: Iterable[MappingRow]) -> list[MappingRow]:
    def key(r: MappingRow) -> tuple[str, str]:
        geo = s.geographies.get(r.geography_id) if r.geography_id else None
        return (s.org_units[r.org_unit_id].name.lower(), geo.name.lower() if geo else "")

    return sorted(rows, key=key)


def view(s: Snapshot, cap_id: str) -> CapabilityOrgView:
    rows = s.by_capability.get(cap_id, ())
    own = s.owners.get(cap_id)
    eff, inherited_from = effective_owner(s, cap_id)
    return CapabilityOrgView(
        capability_id=cap_id,
        level=s.capabilities[cap_id].level,
        owner=_ou_ref(s, own) if own else None,
        effective_owner=_ou_ref(s, eff) if eff else None,
        owner_inherited_from=_cap_ref(s, inherited_from) if inherited_from else None,
        performers=[
            _mapping(s, r) for r in _sorted_mappings(s, (r for r in rows if r.role == "performer"))
        ],
        contributors=[
            _mapping(s, r)
            for r in _sorted_mappings(s, (r for r in rows if r.role == "contributor"))
        ],
    )


def views(s: Snapshot) -> list[CapabilityOrgView]:
    """Every capability with a mapping of its own or an effective owner, in tree order."""
    out: list[CapabilityOrgView] = []
    for cap_id in s.cap_order:
        v = view(s, cap_id)
        if v.effective_owner or v.performers or v.contributors:
            out.append(v)
    return out


# ── US3: findings ──────────────────────────────────────────────────────────────


def _performer_geos(s: Snapshot, rows: Iterable[MappingRow]) -> dict[str, list[Ref]]:
    """Per org unit, the named geographies it performs in; [] when it performs everywhere."""
    everywhere: set[str] = set()
    named: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        if r.geography_id is None or r.geography_id not in s.geographies:
            everywhere.add(r.org_unit_id)
        else:
            named[r.org_unit_id].add(r.geography_id)
    out: dict[str, list[Ref]] = {}
    for ou in everywhere | set(named):
        geos = [] if ou in everywhere else sorted(named[ou], key=lambda g: s.geographies[g].name)
        out[ou] = [ref for g in geos if (ref := _geo_ref(s, g)) is not None]
    return out


def _shared_service(s: Snapshot, cap_id: str) -> SharedServiceCandidate | None:
    performers = [r for r in s.by_capability.get(cap_id, ()) if r.role == "performer"]
    geos = _performer_geos(s, performers)
    units = set(geos)
    folded: dict[str, str | None] = {}
    for ou in units:
        # Fold into the top-most ancestor that also performs this capability (its branch head).
        heads = [a for a in _ou_ancestors(s, ou) if a in units]
        folded[ou] = heads[-1] if heads else None
    branches = sum(1 for v in folded.values() if v is None)
    if branches < 2:
        return None
    return SharedServiceCandidate(
        capability=_finding_cap(s, cap_id),
        branches=branches,
        performers=[
            SharedServicePerformer(
                org_unit=_ou_ref(s, ou),
                org_unit_path=[_ou_ref(s, a) for a in reversed(_ou_ancestors(s, ou))],
                geographies=geos[ou],
                folded_into=_ou_ref(s, head) if (head := folded[ou]) else None,
            )
            for ou in _by_name(s, units)
        ],
    )


def findings(s: Snapshot) -> CapabilityOrgFindings:
    no_owner: list[FindingCapability] = []
    shared: list[SharedServiceCandidate] = []
    unmapped: list[FindingCapability] = []
    owned_no_performer: list[FindingCapability] = []
    l1_l2 = l3 = 0
    for cap_id in s.cap_order:
        level = s.capabilities[cap_id].level
        owner, _ = effective_owner(s, cap_id)
        if level in (1, 2):
            l1_l2 += 1
            if owner is None:
                no_owner.append(_finding_cap(s, cap_id))
            continue
        l3 += 1
        has_performer = any(r.role == "performer" for r in s.by_capability.get(cap_id, ()))
        if not has_performer:
            (owned_no_performer if owner else unmapped).append(_finding_cap(s, cap_id))
            continue
        candidate = _shared_service(s, cap_id)
        if candidate is not None:
            shared.append(candidate)
    return CapabilityOrgFindings(
        no_owner=no_owner,
        shared_service=shared,
        unmapped=unmapped,
        owned_no_performer=owned_no_performer,
        counts=FindingCounts(
            no_owner=len(no_owner),
            shared_service=len(shared),
            unmapped=len(unmapped),
            owned_no_performer=len(owned_no_performer),
            l1_l2_total=l1_l2,
            l3_total=l3,
        ),
    )


# ── US4: footprint ─────────────────────────────────────────────────────────────


def _subtree(s: Snapshot, ou_id: str) -> set[str]:
    return {o for o in s.org_units if o == ou_id or ou_id in _ou_ancestors(s, o)}


def footprint(s: Snapshot, ou_id: str) -> OrgUnitFootprint:
    """FR-014/015. Raises KeyError for an unknown org unit (the route checks first)."""
    units = _subtree(s, ou_id)
    mine = [r for r in s.mappings if r.org_unit_id in units]
    performed: dict[str, list[MappingRow]] = defaultdict(list)
    for r in mine:
        if r.role == "performer" and s.capabilities[r.capability_id].level == 3:
            performed[r.capability_id].append(r)

    l1s: list[FootprintL1] = []
    l2s_by_l1: dict[str, list[FootprintL2]] = defaultdict(list)
    l3s_by_l2: dict[str, list[FootprintL3]] = defaultdict(list)
    for cap_id in s.cap_order:
        if cap_id not in performed:
            continue
        ancestors = _cap_ancestors(s, cap_id)
        if len(ancestors) != 2:
            continue  # an L3 whose chain is incomplete can't be placed
        geos = _performer_geos(s, performed[cap_id])
        l3s_by_l2[ancestors[0]].append(
            FootprintL3(
                capability=_cap_ref(s, cap_id),
                performed_by=[
                    FootprintPerformer(org_unit=_ou_ref(s, ou), geographies=geos[ou])
                    for ou in _by_name(s, geos)
                ],
            )
        )
    for cap_id in s.cap_order:
        if cap_id in l3s_by_l2:
            parent = s.capabilities[cap_id].parent_id
            if parent is not None:
                l2s_by_l1[parent].append(
                    FootprintL2(
                        capability=_cap_ref(s, cap_id),
                        l3_count=len(l3s_by_l2[cap_id]),
                        l3s=l3s_by_l2[cap_id],
                    )
                )
    for cap_id in s.cap_order:
        if cap_id in l2s_by_l1:
            l2s = l2s_by_l1[cap_id]
            l1s.append(
                FootprintL1(
                    capability=_cap_ref(s, cap_id),
                    l3_count=sum(l2.l3_count for l2 in l2s),
                    l2s=l2s,
                )
            )

    def entries(role: str) -> list[FootprintEntry]:
        order = {c: i for i, c in enumerate(s.cap_order)}
        rows = sorted(
            (r for r in mine if r.role == role),
            key=lambda r: (order.get(r.capability_id, 0), s.org_units[r.org_unit_id].name.lower()),
        )
        seen: set[tuple[str, str]] = set()
        out: list[FootprintEntry] = []
        for r in rows:
            if (r.capability_id, r.org_unit_id) in seen:
                continue
            seen.add((r.capability_id, r.org_unit_id))
            out.append(
                FootprintEntry(
                    capability=_finding_cap(s, r.capability_id), org_unit=_ou_ref(s, r.org_unit_id)
                )
            )
        return out

    return OrgUnitFootprint(
        org_unit=_ou_ref(s, ou_id),
        performs=l1s,
        l3_total=sum(l1.l3_count for l1 in l1s),
        owns=entries("owner"),
        contributes=entries("contributor"),
    )


# ── US5: export block (FR-019) ─────────────────────────────────────────────────


def export_block(s: Snapshot, cap_id: str) -> dict[str, object]:
    """The ``organization`` block written into a capability's exported file."""
    if cap_id not in s.capabilities:
        return {"owner": None, "effective_owner": None, "performers": [], "contributors": []}
    v = view(s, cap_id)

    def ref(r: Ref | None) -> dict[str, str] | None:
        return {"id": r.id, "name": r.name} if r else None

    return {
        "owner": ref(v.owner),
        "effective_owner": (
            {
                "id": v.effective_owner.id,
                "name": v.effective_owner.name,
                "inherited_from": v.owner_inherited_from.id if v.owner_inherited_from else None,
            }
            if v.effective_owner
            else None
        ),
        "performers": [
            {"org_unit": ref(p.org_unit), "geography": ref(p.geography)} for p in v.performers
        ],
        "contributors": [{"org_unit": ref(c.org_unit)} for c in v.contributors],
    }
