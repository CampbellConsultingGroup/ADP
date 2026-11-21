"""Capability <-> org unit mappings: writes and reads (941-capability-org-mappings, ADP-55k.2).

The table and the narrow ``business_capabilities`` mirror live in ``adp.organization.store`` so
its org-unit and geography deletes can clean up (research R1/R3). Level rules are enforced here,
because an FK can't check the far row's level (937 precedent):

* owner       -> L1 or L2, at most one per capability (replace-only via :func:`set_owner`);
* performer   -> L3, optional geography;
* contributor -> L3, no geography.

Everything derived (effective owner, notes, findings, footprint) comes from
:mod:`adp.organization.cap_org_analysis` over :func:`build_snapshot` and is never stored.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adp.organization import cap_org_analysis as an
from adp.organization.cap_org_analysis import CapNode, GeoNode, MappingRow, OuNode, Snapshot
from adp.organization.models import (
    AddMapping,
    CapabilityOrgFindings,
    CapabilityOrgMapping,
    CapabilityOrgMappingsResponse,
    CapabilityOrgView,
    DuplicateLinkError,
    LevelRuleError,
    OrgNotFoundError,
    OrgUnitFootprint,
    UnknownReferenceError,
)
from adp.organization.store import (
    REFERENCE_HIERARCHY_ID,
    _business_capabilities,
    _capability_org_mappings,
    _geographies,
    _now,
    _operating_today,
    _org_unit_geo_links,
    _org_units,
    display_level,
    geo_graph,
)

OWNER_LEVEL_RULE = "Owners are set at L2 or L1, not L3"
L3_RULE = "Performers and contributors are mapped at L3"

_t = _capability_org_mappings


# ── Snapshot ───────────────────────────────────────────────────────────────────


async def build_snapshot(session: AsyncSession) -> Snapshot:
    """Four queries (research R4). Mappings are inner-joined to the capability mirror and org
    units, so a row left dangling (SQLite has no FK cascade) never surfaces."""
    b = _business_capabilities
    caps = [
        CapNode(r.id, r.name, int(r.level), r.parent_id, int(r.position or 0))
        for r in await session.execute(
            sa.select(b.c.id, b.c.name, b.c.level, b.c.parent_id, b.c.position)
        )
    ]
    o = _org_units
    ous = [
        OuNode(r.id, r.name, int(r.level), r.parent_id)
        for r in await session.execute(sa.select(o.c.id, o.c.name, o.c.level, o.c.parent_id))
    ]
    geo_rows = (
        await session.execute(
            sa.select(
                _geographies.c.id,
                _geographies.c.name,
                _geographies.c.entity,
                _org_unit_geo_links.c.org_unit_id,
            ).select_from(
                # 947 Q1b: operating geographies are the operates_in links active today.
                _geographies.outerjoin(
                    _org_unit_geo_links,
                    sa.and_(
                        _org_unit_geo_links.c.geography_id == _geographies.c.id,
                        _operating_today(),
                    ),
                )
            )
        )
    ).all()
    graph = await geo_graph(session)
    geos: dict[str, GeoNode] = {}
    operates: dict[str, set[str]] = {}
    for r in geo_rows:
        parents = graph.parents(r.id, REFERENCE_HIERARCHY_ID)
        geos.setdefault(
            r.id,
            GeoNode(r.id, r.name, display_level(r.entity, r.id), parents[0] if parents else None),
        )
        if r.org_unit_id is not None:
            operates.setdefault(r.org_unit_id, set()).add(r.id)
    rows = [
        MappingRow(r.id, r.capability_id, r.org_unit_id, r.role, r.geography_id)
        for r in await session.execute(
            sa.select(_t.c.id, _t.c.capability_id, _t.c.org_unit_id, _t.c.role, _t.c.geography_id)
            .join(b, b.c.id == _t.c.capability_id)
            .join(_org_units, _org_units.c.id == _t.c.org_unit_id)
        )
    ]
    return Snapshot.build(
        capabilities=caps,
        org_units=ous,
        geographies=geos.values(),
        operates_in={k: frozenset(v) for k, v in operates.items()},
        mappings=rows,
        graph=graph,
    )


# ── Checks ─────────────────────────────────────────────────────────────────────


async def _capability_level(cap_id: str, session: AsyncSession) -> int:
    level = (
        await session.execute(
            sa.select(_business_capabilities.c.level).where(_business_capabilities.c.id == cap_id)
        )
    ).scalar_one_or_none()
    if level is None:
        raise OrgNotFoundError(f"Capability {cap_id!r} not found")
    return int(level)


async def _require_ref(table: sa.Table, ref_id: str, label: str, session: AsyncSession) -> None:
    found = (
        await session.execute(sa.select(table.c.id).where(table.c.id == ref_id))
    ).scalar_one_or_none()
    if found is None:
        raise UnknownReferenceError(f"{label} {ref_id!r} not found")


# ── Writes ─────────────────────────────────────────────────────────────────────


async def set_owner(
    cap_id: str, org_unit_id: str | None, session: AsyncSession
) -> tuple[CapabilityOrgView, str | None]:
    """FR-001/002: set, replace or clear the one owner. Returns the view and the previous owner."""
    level = await _capability_level(cap_id, session)
    if level == 3:
        raise LevelRuleError(OWNER_LEVEL_RULE)
    if org_unit_id is not None:
        await _require_ref(_org_units, org_unit_id, "Org unit", session)
    owner_filter = sa.and_(_t.c.capability_id == cap_id, _t.c.role == "owner")
    previous = (
        await session.execute(sa.select(_t.c.org_unit_id).where(owner_filter))
    ).scalar_one_or_none()
    if previous != org_unit_id:
        await session.execute(_t.delete().where(owner_filter))
        if org_unit_id is not None:
            await session.execute(
                _t.insert().values(
                    id=str(uuid.uuid4()),
                    capability_id=cap_id,
                    org_unit_id=org_unit_id,
                    role="owner",
                    geography_id=None,
                    created_at=_now(),
                )
            )
    return an.view(await build_snapshot(session), cap_id), previous


async def add_mapping(body: AddMapping, session: AsyncSession) -> CapabilityOrgMapping:
    """FR-003/004: a performer (optional geography) or contributor on an L3."""
    if await _capability_level(body.capability_id, session) != 3:
        raise LevelRuleError(L3_RULE)
    await _require_ref(_org_units, body.org_unit_id, "Org unit", session)
    if body.geography_id is not None:
        await _require_ref(_geographies, body.geography_id, "Geography", session)
    geo = (
        _t.c.geography_id.is_(None)
        if body.geography_id is None
        else _t.c.geography_id == body.geography_id
    )
    exists = (
        await session.execute(
            sa.select(_t.c.id).where(
                _t.c.capability_id == body.capability_id,
                _t.c.org_unit_id == body.org_unit_id,
                _t.c.role == body.role,
                geo,
            )
        )
    ).first()
    if exists is not None:
        raise DuplicateLinkError(
            f"That org unit is already a {body.role} of this capability"
            + (" in that geography" if body.geography_id else "")
        )
    mapping_id = str(uuid.uuid4())
    try:
        await session.execute(
            _t.insert().values(
                id=mapping_id,
                capability_id=body.capability_id,
                org_unit_id=body.org_unit_id,
                role=body.role,
                geography_id=body.geography_id,
                created_at=_now(),
            )
        )
    except IntegrityError as exc:  # a concurrent duplicate; the unique index is the backstop
        raise DuplicateLinkError("That mapping already exists") from exc
    snap = await build_snapshot(session)
    view = an.view(snap, body.capability_id)
    return next(m for m in [*view.performers, *view.contributors] if m.id == mapping_id)


async def remove_mapping(mapping_id: str, session: AsyncSession) -> Any:
    """Delete one performer or contributor mapping; returns the removed row for the log line."""
    row = (await session.execute(sa.select(_t).where(_t.c.id == mapping_id))).first()
    if row is None:
        raise OrgNotFoundError(f"Mapping {mapping_id!r} not found")
    await session.execute(_t.delete().where(_t.c.id == mapping_id))
    return row


# ── Reads ──────────────────────────────────────────────────────────────────────


async def list_views(session: AsyncSession) -> CapabilityOrgMappingsResponse:
    return CapabilityOrgMappingsResponse(items=an.views(await build_snapshot(session)))


async def get_findings(session: AsyncSession) -> CapabilityOrgFindings:
    return an.findings(await build_snapshot(session))


async def get_footprint(ou_id: str, session: AsyncSession) -> OrgUnitFootprint:
    snap = await build_snapshot(session)
    if ou_id not in snap.org_units:
        raise OrgNotFoundError(f"Org unit {ou_id!r} not found")
    return an.footprint(snap, ou_id)
