"""Application capability store (937-application-capabilities, ADP-6et.1).

The middle layer of the capability model:

    business capability L3 <-> application capability L3 -> technical capability L2/L3
                                application capability L3 <- realized by applications

A shared L1-L3 catalog. Level rules mirror technical capabilities: the level is derived from the
parent (max depth 3), parent and level are immutable, and a capability with children can't be
deleted. Only L3s are mapped, and the far end of each link must be at an allowed level. These
rules live here because a foreign key can't constrain the referenced row's level.

The "missing technical capability" warning is derived on every read and never stored (spec
FR-017). Reads inner-join the far end of every link, so a dangling row (possible on SQLite,
where foreign keys aren't enforced) is never returned.

Tables are defined in ``adp.application.store`` (see the comment there).
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.application.app_capability_models import (
    MISSING_TECHNICAL_CAPABILITY,
    RULE_APP_CAP_L3,
    RULE_BUSINESS_L3,
    RULE_TECH_L2_L3,
    AppCapDepthError,
    AppCapHasChildrenError,
    AppCapNotFoundError,
    AppCapSummary,
    AppCapWarning,
    ApplicationCapability,
    ApplicationCapabilityCreate,
    ApplicationCapabilityDetail,
    ApplicationCapabilityListResponse,
    ApplicationCapabilityUpdate,
    AppRef,
    CapabilityLevelError,
    CapRef,
    DuplicateAppCapLinkError,
    DuplicateSiblingNameError,
    LinkedCapRef,
)
from adp.application.store import (
    _app_cap_realizations,
    _app_cap_tech_links,
    _app_caps,
    _applications,
    _biz_app_cap_links,
    _biz_caps,
    _rowcount,
    _tech_caps,
)
from adp.search import ENTITY_APPLICATION_CAPABILITY, build_text, index_entity, unindex_entity

logger = logging.getLogger(__name__)

MAX_LEVEL = 3

_Counts = tuple[int, int, int]  # (business, technical, realizations)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def warnings_for(level: int, technical_capability_count: int) -> list[AppCapWarning]:
    """Pure: the derived warnings for one application capability (spec US3)."""
    if level == MAX_LEVEL and technical_capability_count == 0:
        return [MISSING_TECHNICAL_CAPABILITY]
    return []


def _to_model(row: Any, counts: _Counts) -> ApplicationCapability:
    b, t, r = counts
    return ApplicationCapability(
        id=row.id,
        name=row.name,
        description=row.description,
        parent_id=row.parent_id,
        level=row.level,
        created_at=row.created_at,
        updated_at=row.updated_at,
        business_capability_count=b,
        technical_capability_count=t,
        realization_count=r,
        warnings=warnings_for(row.level, t),
    )


# ── Counts (three grouped queries, independent of catalog size) ───────────────


async def _counts(session: AsyncSession, ids: list[str] | None = None) -> dict[str, _Counts]:
    async def grouped(link: sa.Table, far: sa.Table, far_col: str) -> dict[str, int]:
        q = (
            sa.select(link.c.app_capability_id, sa.func.count())
            .select_from(link.join(far, link.c[far_col] == far.c.id))
            .group_by(link.c.app_capability_id)
        )
        if ids is not None:
            q = q.where(link.c.app_capability_id.in_(ids))
        return {k: v for k, v in (await session.execute(q)).all()}

    b = await grouped(_biz_app_cap_links, _biz_caps, "business_capability_id")
    t = await grouped(_app_cap_tech_links, _tech_caps, "tech_cap_id")
    r = await grouped(_app_cap_realizations, _applications, "app_id")
    keys = set(b) | set(t) | set(r) if ids is None else set(ids)
    return {k: (b.get(k, 0), t.get(k, 0), r.get(k, 0)) for k in keys}


# ── Catalog ───────────────────────────────────────────────────────────────────


async def _row(ac_id: str, session: AsyncSession) -> Any:
    return (await session.execute(sa.select(_app_caps).where(_app_caps.c.id == ac_id))).first()


async def _require(ac_id: str, session: AsyncSession) -> Any:
    row = await _row(ac_id, session)
    if row is None:
        raise AppCapNotFoundError(f"Application capability {ac_id!r} not found")
    return row


async def _check_sibling_name(
    name: str, parent_id: str | None, session: AsyncSession, exclude_id: str | None = None
) -> None:
    parent_match = (
        _app_caps.c.parent_id.is_(None) if parent_id is None else _app_caps.c.parent_id == parent_id
    )
    q = sa.select(_app_caps.c.id).where(
        parent_match, sa.func.lower(_app_caps.c.name) == name.lower()
    )
    if exclude_id is not None:
        q = q.where(_app_caps.c.id != exclude_id)
    if (await session.execute(q)).first() is not None:
        raise DuplicateSiblingNameError(f"A sibling named {name!r} already exists")


async def list_app_capabilities(
    session: AsyncSession, warning: AppCapWarning | None = None
) -> ApplicationCapabilityListResponse:
    rows = (
        await session.execute(sa.select(_app_caps).order_by(_app_caps.c.level, _app_caps.c.name))
    ).all()
    counts = await _counts(session)
    items = [_to_model(r, counts.get(r.id, (0, 0, 0))) for r in rows]
    if warning is not None:
        items = [i for i in items if warning in i.warnings]
    return ApplicationCapabilityListResponse(items=items, total=len(items))


async def get_app_capability(ac_id: str, session: AsyncSession) -> ApplicationCapability | None:
    row = await _row(ac_id, session)
    if row is None:
        return None
    counts = await _counts(session, [ac_id])
    return _to_model(row, counts[ac_id])


async def create_app_capability(
    body: ApplicationCapabilityCreate, session: AsyncSession
) -> ApplicationCapability:
    level = 1
    if body.parent_id is not None:
        parent = await _row(body.parent_id, session)
        if parent is None:
            raise AppCapNotFoundError(f"Parent application capability {body.parent_id!r} not found")
        if parent.level >= MAX_LEVEL:
            raise AppCapDepthError(f"Parent is level {parent.level}; maximum depth is {MAX_LEVEL}")
        level = parent.level + 1
    await _check_sibling_name(body.name, body.parent_id, session)
    ac_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _app_caps.insert().values(
            id=ac_id,
            name=body.name,
            description=body.description,
            parent_id=body.parent_id,
            level=level,
            created_at=now,
            updated_at=now,
        )
    )
    await _index(ac_id, session)
    created = await get_app_capability(ac_id, session)
    if created is None:  # pragma: no cover -- just inserted
        raise AppCapNotFoundError(ac_id)
    return created


async def update_app_capability(
    ac_id: str, body: ApplicationCapabilityUpdate, session: AsyncSession
) -> ApplicationCapability | None:
    row = await _row(ac_id, session)
    if row is None:
        return None
    values: dict[str, Any] = body.model_dump(exclude_unset=True)
    if values.get("name") is not None:
        await _check_sibling_name(values["name"], row.parent_id, session, exclude_id=ac_id)
    elif "name" in values:
        values.pop("name")  # name can't be cleared
    if values:
        values["updated_at"] = _now()
        await session.execute(_app_caps.update().where(_app_caps.c.id == ac_id).values(**values))
        await _index(ac_id, session)
        if "name" in values:
            # Descendants' indexed text includes this name in their path.
            tree = await _tree(_app_caps, session)
            for node_id in tree:
                if any(p.id == ac_id for p in _path(node_id, tree)):
                    await _index(node_id, session)
    return await get_app_capability(ac_id, session)


async def delete_app_capability(ac_id: str, session: AsyncSession) -> bool:
    if await _row(ac_id, session) is None:
        return False
    children = (
        await session.execute(
            sa.select(sa.func.count()).select_from(_app_caps).where(_app_caps.c.parent_id == ac_id)
        )
    ).scalar_one()
    if children:
        raise AppCapHasChildrenError(
            f"Application capability {ac_id!r} has {children} child capability(ies). "
            "Delete children first."
        )
    # Link rows go explicitly (SQLite parity); migration 046's CASCADE is the safety net.
    for link in (_biz_app_cap_links, _app_cap_tech_links, _app_cap_realizations):
        await session.execute(link.delete().where(link.c.app_capability_id == ac_id))
    result = await session.execute(_app_caps.delete().where(_app_caps.c.id == ac_id))
    deleted = _rowcount(result) > 0
    if deleted:
        await unindex_entity(ENTITY_APPLICATION_CAPABILITY, ac_id, session)
    return deleted


# ── Paths ─────────────────────────────────────────────────────────────────────


async def _tree(table: sa.Table, session: AsyncSession) -> dict[str, Any]:
    rows = (
        await session.execute(sa.select(table.c.id, table.c.name, table.c.level, table.c.parent_id))
    ).all()
    return {r.id: r for r in rows}


def _path(node_id: str, tree: dict[str, Any]) -> list[CapRef]:
    """Ancestors of node_id, L1 first (excluding the node itself)."""
    out: list[CapRef] = []
    seen: set[str] = set()
    current = tree.get(node_id)
    while current is not None and current.parent_id and current.parent_id not in seen:
        seen.add(current.parent_id)
        current = tree.get(current.parent_id)
        if current is not None:
            out.append(CapRef(id=current.id, name=current.name, level=current.level or 0))
    return list(reversed(out))


def _linked(ids: list[str], tree: dict[str, Any]) -> list[LinkedCapRef]:
    out = [
        LinkedCapRef(id=i, name=tree[i].name, level=tree[i].level or 0, path=_path(i, tree))
        for i in ids
        if i in tree
    ]
    return sorted(out, key=lambda c: c.name.lower())


async def _apps_by_cap(
    session: AsyncSession, ac_ids: list[str] | None = None
) -> dict[str, list[AppRef]]:
    q = sa.select(
        _app_cap_realizations.c.app_capability_id, _applications.c.id, _applications.c.name
    ).select_from(
        _app_cap_realizations.join(
            _applications, _app_cap_realizations.c.app_id == _applications.c.id
        )
    )
    if ac_ids is not None:
        q = q.where(_app_cap_realizations.c.app_capability_id.in_(ac_ids))
    out: dict[str, list[AppRef]] = defaultdict(list)
    for ac_id, app_id, name in (await session.execute(q)).all():
        out[ac_id].append(AppRef(id=app_id, name=name))
    for refs in out.values():
        refs.sort(key=lambda a: a.name.lower())
    return out


async def get_app_capability_detail(
    ac_id: str, session: AsyncSession
) -> ApplicationCapabilityDetail | None:
    base = await get_app_capability(ac_id, session)
    if base is None:
        return None
    app_tree = await _tree(_app_caps, session)
    biz_ids = [
        r[0]
        for r in (
            await session.execute(
                sa.select(_biz_app_cap_links.c.business_capability_id).where(
                    _biz_app_cap_links.c.app_capability_id == ac_id
                )
            )
        ).all()
    ]
    tech_ids = [
        r[0]
        for r in (
            await session.execute(
                sa.select(_app_cap_tech_links.c.tech_cap_id).where(
                    _app_cap_tech_links.c.app_capability_id == ac_id
                )
            )
        ).all()
    ]
    biz_tree = await _tree(_biz_caps, session) if biz_ids else {}
    tech_tree = await _tree(_tech_caps, session) if tech_ids else {}
    apps = await _apps_by_cap(session, [ac_id])
    return ApplicationCapabilityDetail(
        **base.model_dump(),
        path=_path(ac_id, app_tree),
        business_capabilities=_linked(biz_ids, biz_tree),
        technical_capabilities=_linked(tech_ids, tech_tree),
        realized_by=apps.get(ac_id, []),
    )


# ── Links ─────────────────────────────────────────────────────────────────────


async def _require_l3(ac_id: str, session: AsyncSession) -> Any:
    row = await _require(ac_id, session)
    if row.level != MAX_LEVEL:
        raise CapabilityLevelError(RULE_APP_CAP_L3)
    return row


async def _insert_link(table: sa.Table, values: dict[str, str], session: AsyncSession) -> None:
    exists = sa.and_(*(table.c[k] == v for k, v in values.items()))
    if (await session.execute(sa.select(sa.literal(1)).select_from(table).where(exists))).first():
        raise DuplicateAppCapLinkError("This link already exists")
    await session.execute(table.insert().values(**values, created_at=_now()))


async def _delete_link(table: sa.Table, values: dict[str, str], session: AsyncSession) -> bool:
    cond = sa.and_(*(table.c[k] == v for k, v in values.items()))
    return _rowcount(await session.execute(table.delete().where(cond))) > 0


async def add_business_link(ac_id: str, cap_id: str, session: AsyncSession) -> None:
    await _require_l3(ac_id, session)
    cap = (
        await session.execute(sa.select(_biz_caps.c.level).where(_biz_caps.c.id == cap_id))
    ).first()
    if cap is None:
        raise AppCapNotFoundError(f"Business capability {cap_id!r} not found")
    if cap.level != MAX_LEVEL:
        raise CapabilityLevelError(RULE_BUSINESS_L3)
    await _insert_link(
        _biz_app_cap_links, {"business_capability_id": cap_id, "app_capability_id": ac_id}, session
    )


async def remove_business_link(ac_id: str, cap_id: str, session: AsyncSession) -> bool:
    return await _delete_link(
        _biz_app_cap_links, {"business_capability_id": cap_id, "app_capability_id": ac_id}, session
    )


async def add_tech_link(ac_id: str, tc_id: str, session: AsyncSession) -> None:
    await _require_l3(ac_id, session)
    tc = (
        await session.execute(sa.select(_tech_caps.c.level).where(_tech_caps.c.id == tc_id))
    ).first()
    if tc is None:
        raise AppCapNotFoundError(f"Technical capability {tc_id!r} not found")
    if tc.level not in (2, 3):
        raise CapabilityLevelError(RULE_TECH_L2_L3)
    await _insert_link(
        _app_cap_tech_links, {"app_capability_id": ac_id, "tech_cap_id": tc_id}, session
    )


async def remove_tech_link(ac_id: str, tc_id: str, session: AsyncSession) -> bool:
    return await _delete_link(
        _app_cap_tech_links, {"app_capability_id": ac_id, "tech_cap_id": tc_id}, session
    )


async def add_realization(ac_id: str, app_id: str, session: AsyncSession) -> None:
    await _require_l3(ac_id, session)
    app = (
        await session.execute(sa.select(_applications.c.id).where(_applications.c.id == app_id))
    ).first()
    if app is None:
        raise AppCapNotFoundError(f"Application {app_id!r} not found")
    await _insert_link(
        _app_cap_realizations, {"app_capability_id": ac_id, "app_id": app_id}, session
    )


async def remove_realization(ac_id: str, app_id: str, session: AsyncSession) -> bool:
    return await _delete_link(
        _app_cap_realizations, {"app_capability_id": ac_id, "app_id": app_id}, session
    )


# ── Reverse lookups (spec US4) ────────────────────────────────────────────────


async def _summaries(ac_ids: list[str], session: AsyncSession) -> list[AppCapSummary]:
    if not ac_ids:
        return []
    tree = await _tree(_app_caps, session)
    counts = await _counts(session, ac_ids)
    apps = await _apps_by_cap(session, ac_ids)
    out = [
        AppCapSummary(
            id=i,
            name=tree[i].name,
            level=tree[i].level,
            path=_path(i, tree),
            warnings=warnings_for(tree[i].level, counts[i][1]),
            realized_by=apps.get(i, []),
        )
        for i in set(ac_ids)
        if i in tree
    ]
    return sorted(out, key=lambda s: s.name.lower())


async def _ids_where(link: sa.Table, col: str, value: str, session: AsyncSession) -> list[str]:
    q = sa.select(link.c.app_capability_id).where(link.c[col] == value)
    return [r[0] for r in (await session.execute(q)).all()]


async def list_by_business_capability(cap_id: str, session: AsyncSession) -> list[AppCapSummary]:
    return await _summaries(
        await _ids_where(_biz_app_cap_links, "business_capability_id", cap_id, session), session
    )


async def list_by_technical_capability(tc_id: str, session: AsyncSession) -> list[AppCapSummary]:
    return await _summaries(
        await _ids_where(_app_cap_tech_links, "tech_cap_id", tc_id, session), session
    )


async def list_by_application(app_id: str, session: AsyncSession) -> list[AppCapSummary]:
    return await _summaries(
        await _ids_where(_app_cap_realizations, "app_id", app_id, session), session
    )


# ── Search ────────────────────────────────────────────────────────────────────


def search_text(name: str, description: str | None, path: list[CapRef]) -> str:
    return build_text(name, description, " / ".join(p.name for p in path))


async def _index(ac_id: str, session: AsyncSession) -> None:
    row = await _row(ac_id, session)
    if row is None:
        return
    tree = await _tree(_app_caps, session)
    await index_entity(
        ENTITY_APPLICATION_CAPABILITY,
        ac_id,
        search_text(row.name, row.description, _path(ac_id, tree)),
        session,
    )


async def search_entries(session: AsyncSession) -> list[tuple[str, str]]:
    """Backfill: (id, indexed text) for every application capability, same text as the hooks."""
    tree = await _tree(_app_caps, session)
    rows = (
        await session.execute(sa.select(_app_caps.c.id, _app_caps.c.name, _app_caps.c.description))
    ).all()
    return [(r.id, search_text(r.name, r.description, _path(r.id, tree))) for r in rows]
