"""Regional assessments: writes and reads (942-regional-assessments, ADP-55k.3).

Tables live in ``adp.organization.store`` so its geography delete can clean up (research R1).
Rules enforced here:

* an assessment names a region or a country, never Global (that is the capability's own
  ``maturity_level``, the baseline -- which nothing here ever writes, SC-004);
* at most one assessment per capability and geography (upsert);
* a region-specific scope names regions or countries, at least one when flagged (the model).

Applicability, heat map cells and the export block come from the pure
:mod:`adp.organization.regional_analysis` over :func:`build_snapshot`, never stored.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.organization import regional_analysis as ra
from adp.organization.models import (
    GeoRef,
    LevelRuleError,
    OrgNotFoundError,
    RegionalAssessment,
    RegionalAssessmentListResponse,
    RegionalHeatmap,
    RegionScope,
    SetRegionalAssessment,
    SetRegionScope,
    UnknownReferenceError,
)
from adp.organization.regional_analysis import Assessment, CapNode, GeoNode, RegionalSnapshot
from adp.organization.store import (
    REFERENCE_HIERARCHY_ID,
    _business_capabilities,
    _capability_regional_assessments,
    _geographies,
    _now,
    _region_specific_capabilities,
    _region_specific_capability_geographies,
    display_level,
    geo_graph,
)

_ra = _capability_regional_assessments
_b = _business_capabilities
_g = _geographies


# ── Checks ─────────────────────────────────────────────────────────────────────


async def _require_capability(cap_id: str, session: AsyncSession) -> None:
    found = (await session.execute(sa.select(_b.c.id).where(_b.c.id == cap_id))).first()
    if found is None:
        raise OrgNotFoundError(f"Capability {cap_id!r} not found")


async def _geography(
    geo_id: str, session: AsyncSession, *, missing: type[Exception] = OrgNotFoundError
) -> GeoRef:
    row = (
        await session.execute(
            sa.select(_g.c.id, _g.c.name, _g.c.entity, _g.c.code).where(_g.c.id == geo_id)
        )
    ).first()
    if row is None:
        raise missing(f"Geography {geo_id!r} not found")
    level = display_level(row.entity, row.id)
    if level == 1:
        raise LevelRuleError(ra.GLOBAL_RULE)
    return GeoRef(id=row.id, name=row.name, level=level, code=row.code)


def _assessment(row: sa.Row, geo: GeoRef) -> RegionalAssessment:
    return RegionalAssessment(
        id=row.id,
        capability_id=row.capability_id,
        geography=geo,
        maturity_level=row.maturity_level,
        note=row.note,
        updated_at=row.updated_at,
    )


# ── Assessments (US1) ──────────────────────────────────────────────────────────


async def set_assessment(
    cap_id: str, geo_id: str, body: SetRegionalAssessment, session: AsyncSession
) -> tuple[RegionalAssessment, bool]:
    """FR-001/002: record or change the one assessment for this capability and geography.
    Returns (assessment, created)."""
    await _require_capability(cap_id, session)
    geo = await _geography(geo_id, session)
    where = sa.and_(_ra.c.capability_id == cap_id, _ra.c.geography_id == geo_id)
    existing = (await session.execute(sa.select(_ra.c.id).where(where))).scalar_one_or_none()
    now = _now()
    values = {"maturity_level": body.maturity_level, "note": body.note, "updated_at": now}
    if existing is None:
        await session.execute(
            _ra.insert().values(
                id=str(uuid.uuid4()),
                capability_id=cap_id,
                geography_id=geo_id,
                created_at=now,
                **values,
            )
        )
    else:
        await session.execute(_ra.update().where(where).values(**values))
    row = (await session.execute(sa.select(_ra).where(where))).one()
    return _assessment(row, geo), existing is None


async def remove_assessment(cap_id: str, geo_id: str, session: AsyncSession) -> None:
    result = await session.execute(
        _ra.delete().where(_ra.c.capability_id == cap_id, _ra.c.geography_id == geo_id)
    )
    if not getattr(result, "rowcount", 0):
        raise OrgNotFoundError(f"No assessment of {cap_id!r} in {geo_id!r}")


async def list_assessments(
    session: AsyncSession, capability_id: str | None = None
) -> RegionalAssessmentListResponse:
    query = (
        sa.select(_ra, _g.c.name.label("geo_name"), _g.c.entity.label("geo_entity"), _g.c.code)
        .join(_g, _g.c.id == _ra.c.geography_id)
        .join(_b, _b.c.id == _ra.c.capability_id)  # hide rows whose capability is gone
        .order_by(_g.c.name, _ra.c.capability_id)
    )
    if capability_id is not None:
        query = query.where(_ra.c.capability_id == capability_id)
    items = [
        _assessment(
            r,
            GeoRef(
                id=r.geography_id,
                name=r.geo_name,
                level=display_level(r.geo_entity, r.geography_id),
                code=r.code,
            ),
        )
        for r in await session.execute(query)
    ]
    return RegionalAssessmentListResponse(items=items, total=len(items))


# ── Region-specific scope (US2) ────────────────────────────────────────────────


async def get_scope(cap_id: str, session: AsyncSession) -> RegionScope:
    await _require_capability(cap_id, session)
    flagged = (
        await session.execute(
            sa.select(_region_specific_capabilities.c.capability_id).where(
                _region_specific_capabilities.c.capability_id == cap_id
            )
        )
    ).first() is not None
    sg = _region_specific_capability_geographies
    geos = [
        GeoRef(id=r.id, name=r.name, level=display_level(r.entity, r.id), code=r.code)
        for r in await session.execute(
            sa.select(_g.c.id, _g.c.name, _g.c.entity, _g.c.code)
            .join(sg, sg.c.geography_id == _g.c.id)
            .where(sg.c.capability_id == cap_id)
            .order_by(_g.c.name)
        )
    ]
    return RegionScope(
        capability_id=cap_id,
        region_specific=flagged,
        geographies=geos,
        scope_needs_update=flagged and not geos,
    )


async def set_scope(cap_id: str, body: SetRegionScope, session: AsyncSession) -> RegionScope:
    """FR-006: replace the scope. ``region_specific=False`` clears the flag and its geographies."""
    await _require_capability(cap_id, session)
    for geo_id in body.geography_ids:
        await _geography(geo_id, session, missing=UnknownReferenceError)
    sg = _region_specific_capability_geographies
    await session.execute(sg.delete().where(sg.c.capability_id == cap_id))
    await session.execute(
        _region_specific_capabilities.delete().where(
            _region_specific_capabilities.c.capability_id == cap_id
        )
    )
    if body.region_specific:
        now = _now()
        await session.execute(
            _region_specific_capabilities.insert().values(capability_id=cap_id, created_at=now)
        )
        for geo_id in body.geography_ids:
            await session.execute(
                sg.insert().values(capability_id=cap_id, geography_id=geo_id, created_at=now)
            )
    return await get_scope(cap_id, session)


# ── Snapshot and derived reads (US3, US4) ──────────────────────────────────────


async def build_snapshot(session: AsyncSession) -> RegionalSnapshot:
    """Four queries (research R3). Rows whose capability or geography is gone are dropped."""
    caps = [
        CapNode(r.id, r.name, int(r.level), r.parent_id, int(r.position or 0), r.maturity_level)
        for r in await session.execute(
            sa.select(
                _b.c.id, _b.c.name, _b.c.level, _b.c.parent_id, _b.c.position, _b.c.maturity_level
            )
        )
    ]
    graph = await geo_graph(session)

    def _ref_parent(geo_id: str) -> str | None:
        parents = graph.parents(geo_id, REFERENCE_HIERARCHY_ID)
        return parents[0] if parents else None

    geos = [
        GeoNode(r.id, r.name, display_level(r.entity, r.id), _ref_parent(r.id), r.code)
        for r in await session.execute(sa.select(_g.c.id, _g.c.name, _g.c.entity, _g.c.code))
    ]
    assessments = [
        Assessment(r.id, r.capability_id, r.geography_id, r.maturity_level, r.note, r.updated_at)
        for r in await session.execute(sa.select(_ra))
    ]
    sg = _region_specific_capability_geographies
    scopes: dict[str, set[str]] = {}
    for r in await session.execute(
        sa.select(_region_specific_capabilities.c.capability_id, sg.c.geography_id).select_from(
            _region_specific_capabilities.outerjoin(
                sg, sg.c.capability_id == _region_specific_capabilities.c.capability_id
            )
        )
    ):
        scopes.setdefault(r.capability_id, set())
        if r.geography_id is not None:
            scopes[r.capability_id].add(r.geography_id)
    return RegionalSnapshot.build(
        capabilities=caps,
        geographies=geos,
        assessments=assessments,
        scopes={k: frozenset(v) for k, v in scopes.items()},
        graph=graph,
    )


async def get_heatmap(requested: list[str] | None, session: AsyncSession) -> RegionalHeatmap:
    return ra.heatmap(await build_snapshot(session), requested)
