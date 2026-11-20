"""Geography hierarchies, nodes and dated memberships (946 GEO-01, ADP-bo1.1).

A hierarchy has a kind (regulatory, data residency, sales, ...) and a shape (strict tree or DAG).
Nodes belong to one hierarchy; memberships put a node or a place under a node of the same
hierarchy for a period. Every write is checked by the pure ``geo_model`` invariants against the
hierarchy's current memberships (FR-005). A hierarchy with a system of record (the UN M49
reference, later imported ones) is read-only here; regulatory, data residency and tax
hierarchies also need write_compliance (FR-006/FR-007). Tables live in
``adp.organization.store`` so its geography delete can clean up.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.organization.geo_model import (
    Entity,
    Membership,
    check_membership,
    check_shape,
)
from adp.organization.models import (
    AddMemberships,
    DuplicateSiblingError,
    Geography,
    GeoHierarchy,
    GeoHierarchyCreate,
    GeoHierarchyDetail,
    GeoHierarchyListResponse,
    GeoHierarchyUpdate,
    GeoMembership,
    GeoMembershipUpdate,
    GeoNodeCreate,
    GeoNodeRef,
    HasChildrenError,
    HierarchyRuleError,
    MembershipConflictError,
    OrgNotFoundError,
)
from adp.organization.store import (
    _geo_hierarchies,
    _geo_memberships,
    _geographies,
    _now,
    check_node_name,
    get_geography,
    require_hierarchy_write,
    require_kind_write,
)

_h = _geo_hierarchies
_g = _geographies
_m = _geo_memberships


async def _hierarchy_row(hierarchy_id: str, session: AsyncSession) -> Any:
    row = (await session.execute(sa.select(_h).where(_h.c.id == hierarchy_id))).first()
    if row is None:
        raise OrgNotFoundError(f"Hierarchy {hierarchy_id!r} not found")
    return row


async def _writable(hierarchy_id: str, session: AsyncSession, can_write_compliance: bool) -> Any:
    row = await _hierarchy_row(hierarchy_id, session)
    require_hierarchy_write(row, can_write_compliance)
    return row


def _model(row: Any, nodes: int, memberships: int) -> GeoHierarchy:
    return GeoHierarchy(
        id=row.id,
        name=row.name,
        kind=row.kind,
        shape=row.shape,
        system_of_record=row.system_of_record,
        description=row.description,
        read_only=bool(row.system_of_record),
        node_count=nodes,
        membership_count=memberships,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _counts(session: AsyncSession) -> tuple[dict[str, int], dict[str, int]]:
    nodes = dict(
        (
            await session.execute(
                sa.select(_g.c.hierarchy_id, sa.func.count())
                .where(_g.c.hierarchy_id.is_not(None))
                .group_by(_g.c.hierarchy_id)
            )
        )
        .tuples()
        .all()
    )
    memberships = dict(
        (
            await session.execute(
                sa.select(_m.c.hierarchy_id, sa.func.count()).group_by(_m.c.hierarchy_id)
            )
        )
        .tuples()
        .all()
    )
    return nodes, memberships


async def list_hierarchies(session: AsyncSession) -> GeoHierarchyListResponse:
    q = sa.select(_h).order_by(_h.c.kind, sa.func.lower(_h.c.name))
    rows = (await session.execute(q)).all()
    nodes, memberships = await _counts(session)
    items = [_model(r, nodes.get(r.id, 0), memberships.get(r.id, 0)) for r in rows]
    return GeoHierarchyListResponse(items=items, total=len(items))


def _membership(row: Any, child_entity: str, as_of: date) -> GeoMembership:
    mb = Membership(row.id, row.hierarchy_id, row.parent_id, row.child_id, row.valid_from,
                    row.valid_to)
    return GeoMembership(
        id=row.id,
        hierarchy_id=row.hierarchy_id,
        parent_id=row.parent_id,
        child_id=row.child_id,
        child_entity=child_entity,  # type: ignore[arg-type]
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        active=mb.active(as_of),
    )


async def get_hierarchy(
    hierarchy_id: str, session: AsyncSession, as_of: date | None = None
) -> GeoHierarchyDetail | None:
    row = (await session.execute(sa.select(_h).where(_h.c.id == hierarchy_id))).first()
    if row is None:
        return None
    on = as_of or date.today()
    nodes = [
        GeoNodeRef(id=r.id, name=r.name)
        for r in await session.execute(
            sa.select(_g.c.id, _g.c.name)
            .where(_g.c.hierarchy_id == hierarchy_id)
            .order_by(sa.func.lower(_g.c.name))
        )
    ]
    child = _g.alias("child")
    memberships = [
        _membership(r, r.child_entity, on)
        for r in await session.execute(
            sa.select(_m, child.c.entity.label("child_entity"))
            .join(child, child.c.id == _m.c.child_id)
            .where(_m.c.hierarchy_id == hierarchy_id)
            .order_by(_m.c.parent_id, child.c.name, _m.c.valid_from)
        )
    ]
    counts_nodes, counts_members = await _counts(session)
    base = _model(row, counts_nodes.get(row.id, 0), counts_members.get(row.id, 0))
    return GeoHierarchyDetail(
        **base.model_dump(), as_of=on, nodes=nodes, memberships=memberships
    )


async def _check_hierarchy_name(
    name: str, session: AsyncSession, exclude_id: str | None = None
) -> None:
    q = sa.select(_h.c.id).where(sa.func.lower(_h.c.name) == name.lower())
    if exclude_id is not None:
        q = q.where(_h.c.id != exclude_id)
    if (await session.execute(q)).first() is not None:
        raise DuplicateSiblingError(f"A hierarchy named {name!r} already exists")


async def create_hierarchy(
    body: GeoHierarchyCreate, session: AsyncSession, can_write_compliance: bool = True
) -> GeoHierarchy:
    require_kind_write(body.kind, can_write_compliance)  # FR-007 applies to creating one too
    await _check_hierarchy_name(body.name, session)
    hierarchy_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _h.insert().values(
            id=hierarchy_id,
            name=body.name,
            kind=body.kind,
            shape=body.shape,
            system_of_record=None,
            description=body.description,
            created_at=now,
            updated_at=now,
        )
    )
    row = await _hierarchy_row(hierarchy_id, session)
    return _model(row, 0, 0)


async def _memberships(hierarchy_id: str, session: AsyncSession) -> list[Membership]:
    return [
        Membership(r.id, r.hierarchy_id, r.parent_id, r.child_id, r.valid_from, r.valid_to)
        for r in await session.execute(sa.select(_m).where(_m.c.hierarchy_id == hierarchy_id))
    ]


async def update_hierarchy(
    hierarchy_id: str,
    body: GeoHierarchyUpdate,
    session: AsyncSession,
    can_write_compliance: bool = True,
) -> GeoHierarchy | None:
    if (await session.execute(sa.select(_h.c.id).where(_h.c.id == hierarchy_id))).first() is None:
        return None
    row = await _writable(hierarchy_id, session, can_write_compliance)
    values = body.model_dump(exclude_unset=True)
    if values.get("name") is None:
        values.pop("name", None)
    else:
        await _check_hierarchy_name(values["name"], session, exclude_id=hierarchy_id)
    if values.get("shape") is None:
        values.pop("shape", None)
    elif values["shape"] != row.shape:
        problems = check_shape(await _memberships(hierarchy_id, session), values["shape"])
        if problems:
            raise HierarchyRuleError(
                "Can't make it a strict tree: " + "; ".join(problems[:5])
                + (f" (and {len(problems) - 5} more)" if len(problems) > 5 else "")
            )
    if values:
        values["updated_at"] = _now()
        await session.execute(_h.update().where(_h.c.id == hierarchy_id).values(**values))
    detail = await get_hierarchy(hierarchy_id, session)
    assert detail is not None
    return GeoHierarchy(**detail.model_dump(exclude={"as_of", "nodes", "memberships"}))


async def delete_hierarchy(
    hierarchy_id: str, session: AsyncSession, can_write_compliance: bool = True
) -> bool:
    if (await session.execute(sa.select(_h.c.id).where(_h.c.id == hierarchy_id))).first() is None:
        return False
    await _writable(hierarchy_id, session, can_write_compliance)
    n = (
        await session.execute(
            sa.select(sa.func.count()).select_from(_g).where(_g.c.hierarchy_id == hierarchy_id)
        )
    ).scalar_one()
    if n:
        raise HasChildrenError(f"The hierarchy has {n} node(s). Delete them first.")
    await session.execute(_m.delete().where(_m.c.hierarchy_id == hierarchy_id))
    await session.execute(_h.delete().where(_h.c.id == hierarchy_id))
    return True


# ── Nodes and memberships ─────────────────────────────────────────────────────


async def _entities(ids: set[str], session: AsyncSession) -> dict[str, Entity]:
    return {
        r.id: Entity(r.id, r.entity, r.hierarchy_id)
        for r in await session.execute(
            sa.select(_g.c.id, _g.c.entity, _g.c.hierarchy_id).where(_g.c.id.in_(ids))
        )
    }


def _rule_error(exc: ValueError) -> Exception:
    msg = str(exc)
    if "already under" in msg:
        return MembershipConflictError(msg)
    return HierarchyRuleError(msg)


async def add_memberships(
    hierarchy_id: str,
    body: AddMemberships,
    session: AsyncSession,
    can_write_compliance: bool = True,
) -> list[GeoMembership]:
    """FR-004/FR-005: all-or-nothing; each new membership is checked against the hierarchy's
    memberships including the ones added earlier in the same request."""
    row = await _writable(hierarchy_id, session, can_write_compliance)
    existing = await _memberships(hierarchy_id, session)
    child_ids = list(dict.fromkeys(body.child_ids))
    entities = await _entities({body.parent_id, *child_ids}, session)
    new: list[Membership] = []
    for cid in child_ids:
        candidate = Membership(
            str(uuid.uuid4()), hierarchy_id, body.parent_id, cid, body.valid_from, body.valid_to
        )
        try:
            check_membership(candidate, existing + new, entities, row.shape)
        except ValueError as exc:
            raise _rule_error(exc) from exc
        new.append(candidate)
    now = _now()
    for mb in new:
        await session.execute(
            _m.insert().values(
                id=mb.id,
                hierarchy_id=hierarchy_id,
                parent_id=mb.parent_id,
                child_id=mb.child_id,
                valid_from=mb.valid_from,
                valid_to=mb.valid_to,
                created_at=now,
                updated_at=now,
            )
        )
    on = date.today()
    return [
        GeoMembership(
            id=mb.id,
            hierarchy_id=hierarchy_id,
            parent_id=mb.parent_id,
            child_id=mb.child_id,
            child_entity=entities[mb.child_id].entity,
            valid_from=mb.valid_from,
            valid_to=mb.valid_to,
            active=mb.active(on),
        )
        for mb in new
    ]


async def _membership_row(membership_id: str, session: AsyncSession) -> Any:
    row = (await session.execute(sa.select(_m).where(_m.c.id == membership_id))).first()
    if row is None:
        raise OrgNotFoundError(f"Membership {membership_id!r} not found")
    return row


async def update_membership(
    membership_id: str,
    body: GeoMembershipUpdate,
    session: AsyncSession,
    can_write_compliance: bool = True,
) -> GeoMembership:
    current = await _membership_row(membership_id, session)
    hierarchy = await _writable(current.hierarchy_id, session, can_write_compliance)
    values = body.model_dump(exclude_unset=True)
    candidate = Membership(
        current.id,
        current.hierarchy_id,
        current.parent_id,
        current.child_id,
        values.get("valid_from", current.valid_from),
        values.get("valid_to", current.valid_to),
    )
    entities = await _entities({current.parent_id, current.child_id}, session)
    try:
        check_membership(
            candidate, await _memberships(current.hierarchy_id, session), entities,
            hierarchy.shape,
        )
    except ValueError as exc:
        raise _rule_error(exc) from exc
    await session.execute(
        _m.update()
        .where(_m.c.id == membership_id)
        .values(valid_from=candidate.valid_from, valid_to=candidate.valid_to, updated_at=_now())
    )
    return _membership(
        await _membership_row(membership_id, session),
        entities[current.child_id].entity,
        date.today(),
    )


async def delete_membership(
    membership_id: str, session: AsyncSession, can_write_compliance: bool = True
) -> None:
    current = await _membership_row(membership_id, session)
    await _writable(current.hierarchy_id, session, can_write_compliance)
    await session.execute(_m.delete().where(_m.c.id == membership_id))


async def create_node(
    hierarchy_id: str,
    body: GeoNodeCreate,
    session: AsyncSession,
    can_write_compliance: bool = True,
) -> Geography:
    await _writable(hierarchy_id, session, can_write_compliance)
    await check_node_name(hierarchy_id, body.name, session)
    node_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _g.insert().values(
            id=node_id,
            name=body.name,
            code=None,
            m49=None,
            entity="node",
            hierarchy_id=hierarchy_id,
            place_type=None,
            created_at=now,
            updated_at=now,
        )
    )
    if body.parent_id is not None:
        await add_memberships(
            hierarchy_id,
            AddMemberships(parent_id=body.parent_id, child_ids=[node_id],
                           valid_from=body.valid_from),
            session,
            can_write_compliance,
        )
    geo = await get_geography(node_id, session)
    assert geo is not None
    return geo
