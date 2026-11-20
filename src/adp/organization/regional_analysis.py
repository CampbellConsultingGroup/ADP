"""Regional assessments analysis (942-regional-assessments, ADP-55k.3).

Pure: no I/O. Computed per request from a frozen :class:`RegionalSnapshot` built by
``adp.organization.regional.build_snapshot``, never stored (``test_regional_not_stored.py``):

* **applicability** of a region-specific capability in a geography, by containment both ways
  through the geography tree (a Brazil-only capability applies in the Americas column too);
* each heat map **cell**: not applicable, assessed (score and/or note, delta from the baseline),
  or not assessed. Only the exact capability x geography assessment counts -- no roll-up across
  capability levels and no inheritance between regions and countries (FR-012);
* the capability x geography **heat map** with its columns (regions by default, at most 12);
* the ``regional`` block written into each exported capability file.

The capability's own ``maturity_level`` is only ever read here, as the baseline.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from adp.organization import cap_org_analysis
from adp.organization.geo_model import GeoGraph
from adp.organization.models import (
    GeoRef,
    HeatmapCapability,
    HeatmapCell,
    HeatmapRow,
    LevelRuleError,
    RegionalHeatmap,
    UnknownReferenceError,
)

MAX_COLUMNS = 12
GLOBAL_RULE = "Global is the capability's baseline maturity; assess a region or a country"

EMPTY_BLOCK: dict[str, Any] = {
    "region_specific": False,
    "scope": [],
    "scope_needs_update": False,
    "assessments": [],
}


@dataclass(frozen=True)
class CapNode:
    id: str
    name: str
    level: int
    parent_id: str | None
    position: int = 0
    baseline: int | None = None


@dataclass(frozen=True)
class GeoNode:
    id: str
    name: str
    level: int
    parent_id: str | None
    code: str | None = None


@dataclass(frozen=True)
class Assessment:
    id: str
    capability_id: str
    geography_id: str
    maturity_level: int | None
    note: str | None
    updated_at: datetime


@dataclass(frozen=True)
class RegionalSnapshot:
    capabilities: Mapping[str, CapNode]
    geographies: Mapping[str, GeoNode]
    assessments: Mapping[tuple[str, str], Assessment]
    # Key present = region-specific; the value is its scope (possibly empty after deletes).
    scopes: Mapping[str, frozenset[str]]
    cap_order: tuple[str, ...] = ()
    ancestors: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    # 946: containment as of today across hierarchies; from the nodes' parent ids if not given.
    graph: GeoGraph | None = None

    @classmethod
    def build(
        cls,
        *,
        capabilities: Iterable[CapNode],
        geographies: Iterable[GeoNode],
        assessments: Iterable[Assessment],
        scopes: Mapping[str, frozenset[str]],
        graph: GeoGraph | None = None,
    ) -> RegionalSnapshot:
        caps = {c.id: c for c in capabilities}
        geos = {g.id: g for g in geographies}
        rows = {
            (a.capability_id, a.geography_id): a
            for a in assessments
            if a.capability_id in caps and a.geography_id in geos
        }
        order = cap_org_analysis._preorder(
            {
                c.id: cap_org_analysis.CapNode(c.id, c.name, c.level, c.parent_id, c.position)
                for c in caps.values()
            }
        )
        return cls(
            capabilities=caps,
            geographies=geos,
            assessments=rows,
            scopes={
                k: frozenset(g for g in v if g in geos) for k, v in scopes.items() if k in caps
            },
            cap_order=order,
            ancestors={g: _geo_ancestors(geos, g) for g in geos},
            graph=graph
            or GeoGraph.from_tree((g.id, g.parent_id, g.level >= 3) for g in geos.values()),
        )


def _geo_ancestors(geos: Mapping[str, GeoNode], geo_id: str) -> tuple[str, ...]:
    out: list[str] = []
    parent = geos[geo_id].parent_id
    while parent is not None and parent in geos and parent not in out:
        out.append(parent)
        parent = geos[parent].parent_id
    return tuple(out)


def geo_ref(s: RegionalSnapshot, geo_id: str) -> GeoRef:
    g = s.geographies[geo_id]
    return GeoRef(id=g.id, name=g.name, level=g.level, code=g.code)


# ── US2: applicability (FR-007) ────────────────────────────────────────────────


def applicable(s: RegionalSnapshot, cap_id: str, geo_id: str) -> bool:
    if cap_id not in s.scopes:
        return True
    # Either contains the other, or (946) they share a country -- across hierarchies.
    graph = s.graph
    assert graph is not None  # build() always sets it
    return any(graph.overlaps(scoped, geo_id) for scoped in s.scopes[cap_id])


# ── US3: cells, columns, heat map ──────────────────────────────────────────────


def cell(s: RegionalSnapshot, cap_id: str, geo_id: str) -> HeatmapCell:
    if not applicable(s, cap_id, geo_id):
        return HeatmapCell(geography_id=geo_id, state="not_applicable")
    a = s.assessments.get((cap_id, geo_id))
    if a is None:
        return HeatmapCell(geography_id=geo_id, state="not_assessed")
    baseline = s.capabilities[cap_id].baseline
    delta = (
        a.maturity_level - baseline
        if a.maturity_level is not None and baseline is not None
        else None
    )
    return HeatmapCell(
        geography_id=geo_id,
        state="assessed",
        maturity_level=a.maturity_level,
        note=a.note,
        delta=delta,
    )


def columns(s: RegionalSnapshot, requested: list[str] | None) -> list[str]:
    if not requested:
        # The reference regions: nodes directly under Global (946: other hierarchies' nodes have
        # no reference parent, so they are added as columns only on request).
        regions = [
            g
            for g in s.geographies.values()
            if g.level == 2
            and g.parent_id is not None
            and s.geographies.get(g.parent_id) is not None
            and s.geographies[g.parent_id].level == 1
        ]
        return [g.id for g in sorted(regions, key=lambda g: g.name.lower())]
    ids = list(dict.fromkeys(requested))
    if len(ids) > MAX_COLUMNS:
        raise LevelRuleError(f"At most {MAX_COLUMNS} geography columns")
    for geo_id in ids:
        g = s.geographies.get(geo_id)
        if g is None:
            raise UnknownReferenceError(f"Geography {geo_id!r} not found")
        if g.level == 1:
            raise LevelRuleError(GLOBAL_RULE)
    return ids


def heatmap(s: RegionalSnapshot, requested: list[str] | None) -> RegionalHeatmap:
    cols = columns(s, requested)
    rows: list[HeatmapRow] = []
    for cap_id in s.cap_order:
        c = s.capabilities[cap_id]
        scope = s.scopes.get(cap_id)
        rows.append(
            HeatmapRow(
                capability=HeatmapCapability(
                    id=c.id, name=c.name, level=c.level, parent_id=c.parent_id
                ),
                baseline=c.baseline,
                region_specific=scope is not None,
                scope_needs_update=scope is not None and not scope,
                cells=[cell(s, cap_id, g) for g in cols],
            )
        )
    return RegionalHeatmap(
        columns=[geo_ref(s, g) for g in cols], rows=rows, max_columns=MAX_COLUMNS
    )


# ── US4: export block (FR-016) ─────────────────────────────────────────────────


def export_block(s: RegionalSnapshot, cap_id: str) -> dict[str, Any]:
    if cap_id not in s.capabilities:
        return dict(EMPTY_BLOCK)
    scope = s.scopes.get(cap_id)
    mine = sorted(
        (a for (c, _), a in s.assessments.items() if c == cap_id),
        key=lambda a: s.geographies[a.geography_id].name.lower(),
    )
    if scope is None and not mine:
        return dict(EMPTY_BLOCK)
    return {
        "region_specific": scope is not None,
        "scope": [
            {"id": g, "name": s.geographies[g].name}
            for g in sorted(scope or (), key=lambda g: s.geographies[g].name.lower())
        ],
        "scope_needs_update": scope is not None and not scope,
        "assessments": [
            {
                "geography": {
                    "id": a.geography_id,
                    "name": s.geographies[a.geography_id].name,
                    "code": s.geographies[a.geography_id].code,
                },
                "maturity_level": a.maturity_level,
                "note": a.note,
            }
            for a in mine
        ],
    }
