"""Read views over the geography model (949 GEO-04, ADP-bo1.4). Derived on read, never stored.

* ``placements``: for one place on a date, the nodes of each hierarchy that contain it.
* ``footprint``: every place an application reaches through its active geography links and its
  legal entities' links, each with the links that reach it and its placements.
* ``matrix``: places x hierarchies, each cell the nodes containing the place.

The pure functions take a resolved ``GeoGraph`` and plain dictionaries; ``footprint_for`` and
``matrix_for`` read what they need (a fixed handful of queries).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.organization import geo_links, legal_entities
from adp.organization import store as ostore
from adp.organization.geo_model import GeoGraph
from adp.organization.models import (
    FootprintLink,
    FootprintPlace,
    GeoFootprint,
    GeoLink,
    GeoNodeRef,
    HierarchyPlacement,
    MatrixHierarchy,
    MatrixRow,
    OrgNotFoundError,
    PlaceMatrix,
    PlaceRef,
)


@dataclass(frozen=True)
class HierarchyInfo:
    id: str
    name: str
    kind: str


def placements(
    graph: GeoGraph,
    place_id: str,
    hierarchies: Mapping[str, HierarchyInfo],
    node_names: Mapping[str, str],
    hierarchy_ids: Iterable[str] | None = None,
) -> list[HierarchyPlacement]:
    wanted = set(hierarchy_ids) if hierarchy_ids is not None else None
    by_hierarchy: dict[str, list[str]] = defaultdict(list)
    for node in graph.ancestors(place_id):
        h = graph.hierarchy_of(node)
        if h is None or h not in hierarchies or (wanted is not None and h not in wanted):
            continue
        by_hierarchy[h].append(node)
    out = []
    for h, nodes in by_hierarchy.items():
        # Most specific first: a node with more ancestors sits lower in the hierarchy.
        nodes.sort(key=lambda n: (-len(graph.ancestors(n)), node_names.get(n, n).lower()))
        info = hierarchies[h]
        out.append(
            HierarchyPlacement(
                hierarchy_id=h,
                hierarchy_name=info.name,
                hierarchy_kind=info.kind,
                nodes=[GeoNodeRef(id=n, name=node_names.get(n, n)) for n in nodes],
            )
        )
    out.sort(key=lambda p: (p.hierarchy_kind != "reference", p.hierarchy_name.lower()))
    return out


def reached_places(graph: GeoGraph, geography_id: str) -> list[str]:
    """The places a link to ``geography_id`` reaches: itself for a place; for a node its places,
    leaving out subdivisions whose country is also reached (the country already covers them)."""
    if graph.is_place(geography_id):
        return [geography_id]
    places = graph.places(geography_id)
    return sorted(p for p in places if graph.parent_place(p) not in places)


def footprint(
    application_id: str,
    links: Iterable[tuple[str, FootprintLink]],  # (geography id, link)
    graph: GeoGraph,
    place_refs: Mapping[str, PlaceRef],
    hierarchies: Mapping[str, HierarchyInfo],
    node_names: Mapping[str, str],
) -> GeoFootprint:
    by_place: dict[str, list[FootprintLink]] = defaultdict(list)
    unresolved: list[FootprintLink] = []
    for geo_id, link in links:
        reached = reached_places(graph, geo_id)
        if not reached:
            unresolved.append(link)
        for p in reached:
            by_place[p].append(link)
    places = [
        FootprintPlace(
            place=place_refs.get(p) or PlaceRef(id=p, name=p),
            links=sorted(by_place[p], key=lambda lk: (lk.relation_label, lk.geography.name)),
            placements=placements(graph, p, hierarchies, node_names),
        )
        for p in by_place
    ]
    places.sort(key=lambda fp: fp.place.name.lower())
    return GeoFootprint(
        as_of=graph.as_of, application_id=application_id, places=places, unresolved=unresolved
    )


def matrix(
    graph: GeoGraph,
    place_refs: Mapping[str, PlaceRef],
    hierarchies: Mapping[str, HierarchyInfo],
    node_names: Mapping[str, str],
) -> PlaceMatrix:
    def order(ref: PlaceRef) -> tuple[str, int, str]:
        country = place_refs.get(ref.parent_place_id or "") if ref.parent_place_id else None
        top = (country or ref).name.lower()
        return (top, 0 if country is None else 1, ref.name.lower())

    rows = []
    for ref in sorted(place_refs.values(), key=order):
        cells = {
            pl.hierarchy_id: pl.nodes
            for pl in placements(graph, ref.id, hierarchies, node_names)
        }
        rows.append(MatrixRow(place=ref, cells=cells))
    cols = sorted(hierarchies.values(), key=lambda h: (h.kind != "reference", h.name.lower()))
    return PlaceMatrix(
        as_of=graph.as_of,
        hierarchies=[MatrixHierarchy(id=h.id, name=h.name, kind=h.kind) for h in cols],
        rows=rows,
    )


# ── Store wrappers ────────────────────────────────────────────────────────────


async def _reference(
    session: AsyncSession,
) -> tuple[dict[str, PlaceRef], dict[str, HierarchyInfo], dict[str, str]]:
    g, h = ostore._geographies, ostore._geo_hierarchies
    places: dict[str, PlaceRef] = {}
    names: dict[str, str] = {}
    for r in await session.execute(
        sa.select(g.c.id, g.c.name, g.c.code, g.c.entity, g.c.place_type, g.c.parent_place_id)
    ):
        names[r.id] = r.name
        if r.entity == "place":
            places[r.id] = PlaceRef(
                id=r.id,
                name=r.name,
                code=r.code,
                place_type=r.place_type,
                parent_place_id=r.parent_place_id,
            )
    hierarchies = {
        r.id: HierarchyInfo(r.id, r.name, r.kind)
        for r in await session.execute(sa.select(h.c.id, h.c.name, h.c.kind))
    }
    return places, hierarchies, names


async def matrix_for(
    session: AsyncSession, as_of: date | None = None, hierarchy_ids: list[str] | None = None
) -> PlaceMatrix:
    places, hierarchies, names = await _reference(session)
    if hierarchy_ids:
        unknown = [i for i in hierarchy_ids if i not in hierarchies]
        if unknown:
            raise OrgNotFoundError(f"Hierarchy {unknown[0]!r} not found")
        hierarchies = {i: hierarchies[i] for i in hierarchy_ids}
    graph = await ostore.geo_graph(session, as_of)
    return matrix(graph, places, hierarchies, names)


async def footprint_for(
    application_id: str, session: AsyncSession, as_of: date | None = None
) -> GeoFootprint:
    on = as_of or date.today()
    labels = {
        r.relation: r.label
        for subject in ("application", "legal_entity")
        for r in geo_links.relations().subjects[subject]
    }
    own = await geo_links.list_links("application", application_id, session, on)
    pairs: list[tuple[str, FootprintLink]] = []

    def add(items: Iterable[GeoLink], via: GeoNodeRef | None) -> None:
        for lk in items:
            pairs.append(
                (
                    lk.geography.id,
                    FootprintLink(
                        relation=lk.relation,
                        relation_label=labels.get(lk.relation, lk.relation),
                        geography=lk.geography,
                        via_legal_entity=via,
                        valid_from=lk.valid_from,
                        valid_to=lk.valid_to,
                    ),
                )
            )

    add(own.items, None)
    for le in await legal_entities.legal_entities_for_application(application_id, session):
        le_links = await geo_links.list_links("legal_entity", le.id, session, on)
        add(le_links.items, GeoNodeRef(id=le.id, name=le.name))
    places, hierarchies, names = await _reference(session)
    graph = await ostore.geo_graph(session, on)
    return footprint(application_id, pairs, graph, places, hierarchies, names)
