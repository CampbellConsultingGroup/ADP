"""Legal entity registry (947 GEO-02, ADP-bo1.2; decision ADP-90r.5).

The companies that contract, hold licences and file. ADP-native (epic OQ-B3). A legal entity may
have a parent legal entity (group ownership, no depth limit, no cycles) and may be linked to any
number of org units and applications (Q2). Nothing is inferred from an application's owning org
unit. Its typed geography links live in ``adp.organization.geo_links``.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.db import is_unique_violation
from adp.organization import geo_links
from adp.organization.models import (
    DuplicateLinkError,
    DuplicateNameError,
    HasChildrenError,
    LegalEntity,
    LegalEntityCreate,
    LegalEntityDetail,
    LegalEntityListResponse,
    LegalEntityUpdate,
    LinkRuleError,
    OrgNotFoundError,
    Ref,
)
from adp.organization.store import (
    _application_legal_entities,
    _applications,
    _legal_entities,
    _legal_entity_org_units,
    _now,
    _org_units,
)
from adp.search import ENTITY_LEGAL_ENTITY, build_text, index_entity, unindex_entity

_le = _legal_entities
_leo = _legal_entity_org_units
_ale = _application_legal_entities


# ── Tree ──────────────────────────────────────────────────────────────────────


async def _parents(session: AsyncSession) -> dict[str, tuple[str, str | None]]:
    return {
        r.id: (r.name, r.parent_id)
        for r in await session.execute(sa.select(_le.c.id, _le.c.name, _le.c.parent_id))
    }


def _path(le_id: str, tree: dict[str, tuple[str, str | None]]) -> list[Ref]:
    """Ancestors, root first (cycle-safe). ``level`` is the depth, root = 1."""
    chain: list[tuple[str, str]] = []
    seen = {le_id}
    parent = tree.get(le_id, ("", None))[1]
    while parent and parent not in seen and parent in tree:
        seen.add(parent)
        chain.append((parent, tree[parent][0]))
        parent = tree[parent][1]
    chain.reverse()
    return [Ref(id=i, name=n, level=k + 1) for k, (i, n) in enumerate(chain)]


def _would_cycle(le_id: str, parent_id: str, tree: dict[str, tuple[str, str | None]]) -> bool:
    cur: str | None = parent_id
    seen: set[str] = set()
    while cur and cur not in seen:
        if cur == le_id:
            return True
        seen.add(cur)
        cur = tree.get(cur, ("", None))[1]
    return False


# ── Search ────────────────────────────────────────────────────────────────────


def _text(r: Any, tree: dict[str, tuple[str, str | None]]) -> str:
    path = " › ".join(p.name for p in _path(r.id, tree))
    return build_text(r.name, r.registration_number, r.lei, r.description, path)


async def _index(le_id: str, session: AsyncSession) -> None:
    row = (await session.execute(sa.select(_le).where(_le.c.id == le_id))).first()
    if row is not None:
        await index_entity(ENTITY_LEGAL_ENTITY, le_id, _text(row, await _parents(session)), session)


async def search_entries(session: AsyncSession) -> list[tuple[str, str]]:
    tree = await _parents(session)
    return [(r.id, _text(r, tree)) for r in (await session.execute(sa.select(_le))).all()]


# ── Read ──────────────────────────────────────────────────────────────────────


async def _models(session: AsyncSession, ids: list[str] | None = None) -> list[LegalEntity]:
    q = sa.select(_le).order_by(sa.func.lower(_le.c.name))
    if ids is not None:
        q = q.where(_le.c.id.in_(ids))
    rows = (await session.execute(q)).all()
    if not rows:
        return []
    tree = await _parents(session)
    org: dict[str, list[str]] = defaultdict(list)
    for le_id, ou_id in (
        await session.execute(
            sa.select(_leo.c.legal_entity_id, _leo.c.org_unit_id)
            .select_from(_leo.join(_org_units, _org_units.c.id == _leo.c.org_unit_id))
            .order_by(_org_units.c.name)
        )
    ).all():
        org[le_id].append(ou_id)
    apps: dict[str, int] = dict(
        (
            await session.execute(
                sa.select(_ale.c.legal_entity_id, sa.func.count())
                .select_from(_ale.join(_applications, _applications.c.id == _ale.c.application_id))
                .group_by(_ale.c.legal_entity_id)
            )
        )
        .tuples()
        .all()
    )
    children: dict[str, int] = defaultdict(int)
    for _name, parent in tree.values():
        if parent:
            children[parent] += 1
    return [
        LegalEntity(
            id=r.id,
            name=r.name,
            registration_number=r.registration_number,
            lei=r.lei,
            description=r.description,
            parent_id=r.parent_id,
            path=_path(r.id, tree),
            org_unit_ids=org.get(r.id, []),
            application_count=int(apps.get(r.id, 0)),
            child_count=children.get(r.id, 0),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


async def list_legal_entities(session: AsyncSession) -> LegalEntityListResponse:
    items = await _models(session)
    return LegalEntityListResponse(items=items, total=len(items))


async def _require(le_id: str, session: AsyncSession) -> LegalEntity:
    found = await _models(session, [le_id])
    if not found:
        raise OrgNotFoundError(f"Legal entity {le_id!r} not found")
    return found[0]


async def get_legal_entity(le_id: str, session: AsyncSession) -> LegalEntityDetail:
    base = await _require(le_id, session)
    o = _org_units
    org_units = [
        Ref(id=r.id, name=r.name, level=r.level)
        for r in await session.execute(
            sa.select(o.c.id, o.c.name, o.c.level)
            .select_from(_leo.join(o, o.c.id == _leo.c.org_unit_id))
            .where(_leo.c.legal_entity_id == le_id)
            .order_by(o.c.name)
        )
    ]
    a = _applications
    applications = [
        Ref(id=r.id, name=r.name, level=0)
        for r in await session.execute(
            sa.select(a.c.id, a.c.name)
            .select_from(_ale.join(a, a.c.id == _ale.c.application_id))
            .where(_ale.c.legal_entity_id == le_id)
            .order_by(a.c.name)
        )
    ]
    children = [
        Ref(id=r.id, name=r.name, level=len(base.path) + 2)
        for r in await session.execute(
            sa.select(_le.c.id, _le.c.name).where(_le.c.parent_id == le_id).order_by(_le.c.name)
        )
    ]
    return LegalEntityDetail(
        **base.model_dump(), org_units=org_units, applications=applications, children=children
    )


# ── Write ─────────────────────────────────────────────────────────────────────


async def _check_unique(
    name: str | None, lei: str | None, session: AsyncSession, exclude: str | None = None
) -> None:
    if name is not None:
        q = sa.select(_le.c.id).where(sa.func.lower(_le.c.name) == name.lower())
        if exclude:
            q = q.where(_le.c.id != exclude)
        if (await session.execute(q)).first() is not None:
            raise DuplicateNameError(f"A legal entity named {name!r} already exists")
    if lei is not None:
        q = sa.select(_le.c.name).where(_le.c.lei == lei)
        if exclude:
            q = q.where(_le.c.id != exclude)
        other = (await session.execute(q)).scalar_one_or_none()
        if other is not None:
            raise DuplicateNameError(f"LEI {lei} is already used by {other!r}")


async def _check_parent(le_id: str | None, parent_id: str | None, session: AsyncSession) -> None:
    if parent_id is None:
        return
    tree = await _parents(session)
    if parent_id not in tree:
        raise OrgNotFoundError(f"Legal entity {parent_id!r} not found")
    if le_id is not None and _would_cycle(le_id, parent_id, tree):
        raise LinkRuleError("A legal entity can't be owned by itself or by one of its subsidiaries")


async def create_legal_entity(body: LegalEntityCreate, session: AsyncSession) -> LegalEntity:
    await _check_unique(body.name, body.lei, session)
    await _check_parent(None, body.parent_id, session)
    le_id = str(uuid.uuid4())
    now = _now()
    try:
        await session.execute(
            _le.insert().values(id=le_id, **body.model_dump(), created_at=now, updated_at=now)
        )
    except Exception as exc:  # a concurrent insert of the same name
        if is_unique_violation(exc):
            raise DuplicateNameError(f"A legal entity named {body.name!r} already exists") from exc
        raise
    await _index(le_id, session)
    return await _require(le_id, session)


async def update_legal_entity(
    le_id: str, body: LegalEntityUpdate, session: AsyncSession
) -> LegalEntity:
    await _require(le_id, session)
    values = body.model_dump(exclude_unset=True)
    await _check_unique(values.get("name"), values.get("lei"), session, exclude=le_id)
    if "parent_id" in values:
        await _check_parent(le_id, values["parent_id"], session)
    if values:
        await session.execute(
            _le.update().where(_le.c.id == le_id).values(**values, updated_at=_now())
        )
        tree = await _parents(session)
        # A rename changes the indexed path text of every subsidiary.
        for other in tree:
            below = any(p.id == le_id for p in _path(other, tree))
            if other == le_id or ("name" in values and below):
                await _index(other, session)
    return await _require(le_id, session)


async def delete_legal_entity(le_id: str, session: AsyncSession) -> None:
    entity = await _require(le_id, session)
    if entity.child_count:
        noun = "entity" if entity.child_count == 1 else "entities"
        raise HasChildrenError(
            f"Legal entity {entity.name!r} owns {entity.child_count} other legal {noun}."
            " Move or delete them first."
        )
    # FR-001/FR-007: its links go too (SQLite parity; migration 058 CASCADE is the safety net).
    await session.execute(_leo.delete().where(_leo.c.legal_entity_id == le_id))
    await session.execute(_ale.delete().where(_ale.c.legal_entity_id == le_id))
    await geo_links.delete_subject_links("legal_entity", le_id, session)
    await session.execute(_le.delete().where(_le.c.id == le_id))
    await unindex_entity(ENTITY_LEGAL_ENTITY, le_id, session)


# ── Links (FR-002) ────────────────────────────────────────────────────────────


async def link_org_unit(le_id: str, ou_id: str, session: AsyncSession) -> LegalEntityDetail:
    await _require(le_id, session)
    if (
        await session.execute(sa.select(_org_units.c.id).where(_org_units.c.id == ou_id))
    ).first() is None:
        raise OrgNotFoundError(f"Org unit {ou_id!r} not found")
    exists = (
        await session.execute(
            sa.select(_leo.c.org_unit_id).where(
                _leo.c.legal_entity_id == le_id, _leo.c.org_unit_id == ou_id
            )
        )
    ).first()
    if exists is not None:
        raise DuplicateLinkError("That org unit is already linked to this legal entity")
    await session.execute(
        _leo.insert().values(legal_entity_id=le_id, org_unit_id=ou_id, created_at=_now())
    )
    return await get_legal_entity(le_id, session)


async def unlink_org_unit(le_id: str, ou_id: str, session: AsyncSession) -> None:
    result = await session.execute(
        _leo.delete().where(_leo.c.legal_entity_id == le_id, _leo.c.org_unit_id == ou_id)
    )
    if not getattr(result, "rowcount", 0):
        raise OrgNotFoundError("That org unit is not linked to this legal entity")


async def legal_entities_for_org_unit(ou_id: str, session: AsyncSession) -> list[LegalEntity]:
    ids = [
        r[0]
        for r in await session.execute(
            sa.select(_leo.c.legal_entity_id).where(_leo.c.org_unit_id == ou_id)
        )
    ]
    return await _models(session, ids) if ids else []


async def _require_application(app_id: str, session: AsyncSession) -> None:
    if (
        await session.execute(sa.select(_applications.c.id).where(_applications.c.id == app_id))
    ).first() is None:
        raise OrgNotFoundError(f"Application {app_id!r} not found")


async def legal_entities_for_application(
    app_id: str, session: AsyncSession
) -> list[LegalEntity]:
    await _require_application(app_id, session)
    ids = [
        r[0]
        for r in await session.execute(
            sa.select(_ale.c.legal_entity_id).where(_ale.c.application_id == app_id)
        )
    ]
    return await _models(session, ids) if ids else []


async def link_application(app_id: str, le_id: str, session: AsyncSession) -> list[LegalEntity]:
    await _require_application(app_id, session)
    await _require(le_id, session)
    exists = (
        await session.execute(
            sa.select(_ale.c.legal_entity_id).where(
                _ale.c.application_id == app_id, _ale.c.legal_entity_id == le_id
            )
        )
    ).first()
    if exists is not None:
        raise DuplicateLinkError("That legal entity is already linked to this application")
    await session.execute(
        _ale.insert().values(application_id=app_id, legal_entity_id=le_id, created_at=_now())
    )
    return await legal_entities_for_application(app_id, session)


async def unlink_application(app_id: str, le_id: str, session: AsyncSession) -> None:
    result = await session.execute(
        _ale.delete().where(_ale.c.application_id == app_id, _ale.c.legal_entity_id == le_id)
    )
    if not getattr(result, "rowcount", 0):
        raise OrgNotFoundError("That legal entity is not linked to this application")


async def all_application_links(session: AsyncSession) -> list[tuple[str, str]]:
    """(application id, legal entity id) for every link -- export. One query."""
    return [
        (r.application_id, r.legal_entity_id)
        for r in await session.execute(
            sa.select(_ale.c.application_id, _ale.c.legal_entity_id).order_by(
                _ale.c.application_id, _ale.c.legal_entity_id
            )
        )
    ]
