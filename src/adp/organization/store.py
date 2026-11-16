"""Org Units and Geography store (940-org-units-geography, ADP-55k.1).

Two governed trees with 937's hierarchy rules (research R3): the level is derived from the parent
(max 3), parent and level are fixed after creation, a node with children can't be deleted, and
sibling names are unique ignoring case (migration 048 backs this with an expression index).

Applications are reached through a NARROW mirror of the ``applications`` table (research R2): the
review queue reads and bulk-updates ``owning_org_unit_id`` through it, and ``adp.application``
never imports this package at store level. The review queue never writes the free-text
``owning_business_unit`` (spec SC-004).
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.organization.models import (
    GEOGRAPHY_KINDS,
    ISO2,
    ORG_UNIT_KINDS,
    DepthError,
    DuplicateCodeError,
    DuplicateLinkError,
    DuplicateSiblingError,
    Geography,
    GeographyCreate,
    GeographyListResponse,
    GeographyUpdate,
    HasChildrenError,
    InvalidCodeError,
    OrgNotFoundError,
    OrgUnit,
    OrgUnitCreate,
    OrgUnitDetail,
    OrgUnitListResponse,
    OrgUnitUpdate,
    Ref,
    ResolveResult,
    ResolveUnmatched,
    UnmatchedListResponse,
    UnmatchedValue,
)
from adp.search import ENTITY_ORG_UNIT, build_text, index_entity, unindex_entity

logger = logging.getLogger(__name__)

MAX_LEVEL = 3

_metadata = sa.MetaData()

_geographies = sa.Table(
    "geographies",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("code", sa.String(8), nullable=True),
    sa.Column("m49", sa.String(3), nullable=True),
    sa.Column("parent_id", sa.String(36), sa.ForeignKey("geographies.id"), nullable=True),
    sa.Column("level", sa.SmallInteger(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_org_units = sa.Table(
    "org_units",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("parent_id", sa.String(36), sa.ForeignKey("org_units.id"), nullable=True),
    sa.Column("level", sa.SmallInteger(), nullable=False),
    sa.Column(
        "primary_geography_id",
        sa.String(36),
        sa.ForeignKey("geographies.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_org_unit_geographies = sa.Table(
    "org_unit_geographies",
    _metadata,
    sa.Column(
        "org_unit_id",
        sa.String(36),
        sa.ForeignKey("org_units.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "geography_id",
        sa.String(36),
        sa.ForeignKey("geographies.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("org_unit_id", "geography_id"),
)

# Narrow mirror (research R2). A fixture creating both this metadata and
# adp.application.store's must create astore first and exclude this table here.
_applications = sa.Table(
    "applications",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("owning_business_unit", sa.String(255)),
    sa.Column("owning_org_unit_id", sa.String(36)),
)

# 941-capability-org-mappings: narrow, read-only mirror of the business capability tree (research
# R1). Fixtures that also create adp.business.store's or adp.application.store's metadata must
# create those first and exclude this table here. ``position`` is nullable so astore's own
# narrower mirror (no position) still works when it was created first.
_business_capabilities = sa.Table(
    "business_capabilities",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("level", sa.Integer(), nullable=False),
    sa.Column("parent_id", sa.String(36), nullable=True),
    sa.Column("position", sa.Integer(), nullable=True),
)

# 941: owner (L1/L2, one per capability), performer (L3, optional geography), contributor (L3).
# Mirrors migration 049; the level rules are enforced in adp.organization.cap_mappings.
_capability_org_mappings = sa.Table(
    "capability_org_mappings",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column(
        "capability_id",
        sa.String(36),
        sa.ForeignKey("business_capabilities.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "org_unit_id",
        sa.String(36),
        sa.ForeignKey("org_units.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("role", sa.String(16), nullable=False),
    sa.Column(
        "geography_id",
        sa.String(36),
        sa.ForeignKey("geographies.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
        "role IN ('owner', 'performer', 'contributor')", name="ck_cap_org_mapping_role"
    ),
    sa.CheckConstraint(
        "role = 'performer' OR geography_id IS NULL", name="ck_cap_org_mapping_geo_performer_only"
    ),
)
sa.Index(
    "uq_cap_org_mapping_owner",
    _capability_org_mappings.c.capability_id,
    unique=True,
    sqlite_where=_capability_org_mappings.c.role == "owner",
    postgresql_where=_capability_org_mappings.c.role == "owner",
)
sa.Index(
    "uq_cap_org_mapping",
    _capability_org_mappings.c.capability_id,
    _capability_org_mappings.c.org_unit_id,
    _capability_org_mappings.c.role,
    sa.func.coalesce(_capability_org_mappings.c.geography_id, ""),
    unique=True,
)

_engine = None
_session_factory: async_sessionmaker | None = None


def _get_session_factory() -> async_sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        import os

        db_url = os.environ.get(
            "ADP_DATABASE_URL", "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
        )
        _engine = create_async_engine(db_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rowcount(result: Any) -> int:
    return cast("sa.CursorResult[Any]", result).rowcount


# ── Shared tree rules (research R3) ───────────────────────────────────────────


async def _row(table: sa.Table, node_id: str, session: AsyncSession) -> Any:
    return (await session.execute(sa.select(table).where(table.c.id == node_id))).first()


async def _require(table: sa.Table, node_id: str, label: str, session: AsyncSession) -> Any:
    row = await _row(table, node_id, session)
    if row is None:
        raise OrgNotFoundError(f"{label} {node_id!r} not found")
    return row


async def _level_under(
    table: sa.Table, parent_id: str | None, label: str, session: AsyncSession
) -> int:
    if parent_id is None:
        return 1
    parent = await _require(table, parent_id, f"Parent {label.lower()}", session)
    if parent.level >= MAX_LEVEL:
        raise DepthError(f"Parent is level {parent.level}; maximum depth is {MAX_LEVEL}")
    return int(parent.level) + 1


async def _check_sibling(
    table: sa.Table,
    name: str,
    parent_id: str | None,
    session: AsyncSession,
    exclude_id: str | None = None,
) -> None:
    parent_match = (
        table.c.parent_id.is_(None) if parent_id is None else table.c.parent_id == parent_id
    )
    q = sa.select(table.c.id).where(parent_match, sa.func.lower(table.c.name) == name.lower())
    if exclude_id is not None:
        q = q.where(table.c.id != exclude_id)
    if (await session.execute(q)).first() is not None:
        raise DuplicateSiblingError(f"A sibling named {name!r} already exists")


async def _refuse_if_children(
    table: sa.Table, node_id: str, label: str, session: AsyncSession
) -> None:
    n = (
        await session.execute(
            sa.select(sa.func.count()).select_from(table).where(table.c.parent_id == node_id)
        )
    ).scalar_one()
    if n:
        raise HasChildrenError(f"{label} {node_id!r} has {n} child(ren). Remove them first.")


async def _tree(table: sa.Table, session: AsyncSession) -> dict[str, Any]:
    rows = (
        await session.execute(sa.select(table.c.id, table.c.name, table.c.level, table.c.parent_id))
    ).all()
    return {r.id: r for r in rows}


def _path(node_id: str, tree: dict[str, Any]) -> list[Ref]:
    """Ancestors of node_id, root first (cycle-safe)."""
    out: list[Ref] = []
    seen = {node_id}
    cur = tree.get(node_id)
    while cur is not None and cur.parent_id and cur.parent_id not in seen:
        seen.add(cur.parent_id)
        cur = tree.get(cur.parent_id)
        if cur is not None:
            out.append(Ref(id=cur.id, name=cur.name, level=cur.level))
    return list(reversed(out))


# ── Org units ─────────────────────────────────────────────────────────────────


def _search_text(row: Any, tree: dict[str, Any]) -> str:
    path = " › ".join(p.name for p in _path(row.id, tree))
    return build_text(row.name, row.description, path)


async def _index_org_unit(ou_id: str, session: AsyncSession) -> None:
    row = await _row(_org_units, ou_id, session)
    if row is None:
        return
    await index_entity(
        ENTITY_ORG_UNIT, ou_id, _search_text(row, await _tree(_org_units, session)), session
    )


async def search_entries(session: AsyncSession) -> list[tuple[str, str]]:
    """(id, indexed text) for every org unit -- the backfill uses the write hooks' text."""
    rows = (await session.execute(sa.select(_org_units))).all()
    tree = await _tree(_org_units, session)
    return [(r.id, _search_text(r, tree)) for r in rows]


async def _org_unit_models(session: AsyncSession, ids: list[str] | None = None) -> list[OrgUnit]:
    q = sa.select(_org_units).order_by(_org_units.c.level, _org_units.c.name)
    if ids is not None:
        q = q.where(_org_units.c.id.in_(ids))
    rows = (await session.execute(q)).all()
    if not rows:
        return []
    tree = await _tree(_org_units, session)
    geo: dict[str, list[str]] = defaultdict(list)
    for ou, g in (
        await session.execute(
            sa.select(_org_unit_geographies.c.org_unit_id, _org_unit_geographies.c.geography_id)
            .select_from(
                _org_unit_geographies.join(
                    _geographies, _geographies.c.id == _org_unit_geographies.c.geography_id
                )
            )
            .order_by(_geographies.c.name)
        )
    ).all():
        geo[ou].append(g)
    counts: dict[str, int] = dict(
        (
            await session.execute(
                sa.select(_applications.c.owning_org_unit_id, sa.func.count())
                .where(_applications.c.owning_org_unit_id.is_not(None))
                .group_by(_applications.c.owning_org_unit_id)
            )
        )
        .tuples()
        .all()
    )
    return [
        OrgUnit(
            id=r.id,
            name=r.name,
            description=r.description,
            parent_id=r.parent_id,
            level=r.level,
            kind=ORG_UNIT_KINDS[r.level],
            primary_geography_id=r.primary_geography_id,
            geography_ids=geo.get(r.id, []),
            path=_path(r.id, tree),
            application_count=int(counts.get(r.id, 0)),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


async def list_org_units(session: AsyncSession) -> OrgUnitListResponse:
    items = await _org_unit_models(session)
    return OrgUnitListResponse(items=items, total=len(items))


async def org_unit_exists(ou_id: str, session: AsyncSession) -> bool:
    return await _row(_org_units, ou_id, session) is not None


async def get_org_unit(ou_id: str, session: AsyncSession) -> OrgUnitDetail | None:
    models = await _org_unit_models(session, [ou_id])
    if not models:
        return None
    apps = (
        await session.execute(
            sa.select(_applications.c.id, _applications.c.name)
            .where(_applications.c.owning_org_unit_id == ou_id)
            .order_by(_applications.c.name)
        )
    ).all()
    geos = (
        await session.execute(
            sa.select(_geographies.c.id, _geographies.c.name, _geographies.c.level)
            .where(_geographies.c.id.in_(models[0].geography_ids))
            .order_by(_geographies.c.name)
        )
    ).all()
    return OrgUnitDetail(
        **models[0].model_dump(),
        applications=[Ref(id=a.id, name=a.name, level=0) for a in apps],
        geographies=[Ref(id=g.id, name=g.name, level=g.level) for g in geos],
    )


async def _require_geography(geo_id: str | None, session: AsyncSession) -> None:
    if geo_id is not None:
        await _require(_geographies, geo_id, "Geography", session)


async def create_org_unit(body: OrgUnitCreate, session: AsyncSession) -> OrgUnit:
    level = await _level_under(_org_units, body.parent_id, "Org unit", session)
    await _check_sibling(_org_units, body.name, body.parent_id, session)
    await _require_geography(body.primary_geography_id, session)
    ou_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _org_units.insert().values(
            id=ou_id,
            name=body.name,
            description=body.description,
            parent_id=body.parent_id,
            level=level,
            primary_geography_id=body.primary_geography_id,
            created_at=now,
            updated_at=now,
        )
    )
    await _index_org_unit(ou_id, session)
    return (await _org_unit_models(session, [ou_id]))[0]


async def update_org_unit(ou_id: str, body: OrgUnitUpdate, session: AsyncSession) -> OrgUnit | None:
    row = await _row(_org_units, ou_id, session)
    if row is None:
        return None
    values: dict[str, Any] = body.model_dump(exclude_unset=True)
    if values.get("name") is not None:
        await _check_sibling(_org_units, values["name"], row.parent_id, session, exclude_id=ou_id)
    elif "name" in values:
        values.pop("name")  # a name can't be cleared
    if "primary_geography_id" in values:
        await _require_geography(values["primary_geography_id"], session)
    if values:
        values["updated_at"] = _now()
        await session.execute(_org_units.update().where(_org_units.c.id == ou_id).values(**values))
        await _index_org_unit(ou_id, session)
        if "name" in values:
            # Descendants' indexed text includes this name in their path.
            tree = await _tree(_org_units, session)
            for node_id in tree:
                if any(p.id == ou_id for p in _path(node_id, tree)):
                    await _index_org_unit(node_id, session)
    return (await _org_unit_models(session, [ou_id]))[0]


async def delete_org_unit(ou_id: str, session: AsyncSession) -> bool:
    if await _row(_org_units, ou_id, session) is None:
        return False
    await _refuse_if_children(_org_units, ou_id, "Org unit", session)
    # FR-013: applications keep their free text and lose only the link. Explicit for SQLite
    # parity; migration 048's ON DELETE SET NULL / CASCADE are the safety net.
    await session.execute(
        _applications.update()
        .where(_applications.c.owning_org_unit_id == ou_id)
        .values(owning_org_unit_id=None)
    )
    await session.execute(
        _org_unit_geographies.delete().where(_org_unit_geographies.c.org_unit_id == ou_id)
    )
    # 941: its capability mappings go too; owned capabilities fall back to their parent's owner
    # (the effective owner is derived). Migration 049's CASCADE is the safety net.
    await session.execute(
        _capability_org_mappings.delete().where(_capability_org_mappings.c.org_unit_id == ou_id)
    )
    deleted = (
        _rowcount(await session.execute(_org_units.delete().where(_org_units.c.id == ou_id))) > 0
    )
    if deleted:
        await unindex_entity(ENTITY_ORG_UNIT, ou_id, session)
    return deleted


# ── Org unit <-> geography (US3) ──────────────────────────────────────────────


async def link_geography(ou_id: str, geo_id: str, session: AsyncSession) -> OrgUnit:
    await _require(_org_units, ou_id, "Org unit", session)
    await _require(_geographies, geo_id, "Geography", session)
    exists = (
        await session.execute(
            sa.select(_org_unit_geographies.c.org_unit_id).where(
                _org_unit_geographies.c.org_unit_id == ou_id,
                _org_unit_geographies.c.geography_id == geo_id,
            )
        )
    ).first()
    if exists is not None:
        raise DuplicateLinkError(f"Org unit {ou_id!r} is already linked to geography {geo_id!r}")
    await session.execute(
        _org_unit_geographies.insert().values(
            org_unit_id=ou_id, geography_id=geo_id, created_at=_now()
        )
    )
    return (await _org_unit_models(session, [ou_id]))[0]


async def unlink_geography(ou_id: str, geo_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _org_unit_geographies.delete().where(
            _org_unit_geographies.c.org_unit_id == ou_id,
            _org_unit_geographies.c.geography_id == geo_id,
        )
    )
    return _rowcount(result) > 0


async def org_units_for_geography(geo_id: str, session: AsyncSession) -> list[OrgUnit] | None:
    if await _row(_geographies, geo_id, session) is None:
        return None
    ids = [
        r[0]
        for r in (
            await session.execute(
                sa.select(_org_unit_geographies.c.org_unit_id).where(
                    _org_unit_geographies.c.geography_id == geo_id
                )
            )
        ).all()
    ]
    return await _org_unit_models(session, ids) if ids else []


# ── Geography (US2) ───────────────────────────────────────────────────────────


def _validate_code(code: str | None, level: int) -> None:
    if code is None:
        return
    if level != 3:
        raise InvalidCodeError("Only countries carry an ISO code; use m49 for regions")
    if not ISO2.match(code):
        raise InvalidCodeError(f"Country code {code!r} must be two uppercase letters (ISO 3166-1)")


async def _check_code_unique(
    code: str | None, session: AsyncSession, exclude_id: str | None = None
) -> None:
    if code is None:
        return
    q = sa.select(_geographies.c.id).where(_geographies.c.code == code)
    if exclude_id is not None:
        q = q.where(_geographies.c.id != exclude_id)
    if (await session.execute(q)).first() is not None:
        raise DuplicateCodeError(f"Country code {code!r} is already used")


async def _geography_models(session: AsyncSession, ids: list[str] | None = None) -> list[Geography]:
    q = sa.select(_geographies).order_by(_geographies.c.level, _geographies.c.name)
    if ids is not None:
        q = q.where(_geographies.c.id.in_(ids))
    rows = (await session.execute(q)).all()
    tree = await _tree(_geographies, session)
    counts: dict[str, int] = dict(
        (
            await session.execute(
                sa.select(_org_unit_geographies.c.geography_id, sa.func.count()).group_by(
                    _org_unit_geographies.c.geography_id
                )
            )
        )
        .tuples()
        .all()
    )
    return [
        Geography(
            id=r.id,
            name=r.name,
            code=r.code,
            m49=r.m49,
            parent_id=r.parent_id,
            level=r.level,
            kind=GEOGRAPHY_KINDS[r.level],
            path=_path(r.id, tree),
            org_unit_count=int(counts.get(r.id, 0)),
        )
        for r in rows
    ]


async def list_geographies(session: AsyncSession) -> GeographyListResponse:
    items = await _geography_models(session)
    return GeographyListResponse(items=items, total=len(items))


async def get_geography(geo_id: str, session: AsyncSession) -> Geography | None:
    models = await _geography_models(session, [geo_id])
    return models[0] if models else None


async def create_geography(body: GeographyCreate, session: AsyncSession) -> Geography:
    level = await _level_under(_geographies, body.parent_id, "Geography", session)
    _validate_code(body.code, level)
    await _check_sibling(_geographies, body.name, body.parent_id, session)
    await _check_code_unique(body.code, session)
    geo_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _geographies.insert().values(
            id=geo_id,
            name=body.name,
            code=body.code,
            m49=body.m49,
            parent_id=body.parent_id,
            level=level,
            created_at=now,
            updated_at=now,
        )
    )
    return (await _geography_models(session, [geo_id]))[0]


async def update_geography(
    geo_id: str, body: GeographyUpdate, session: AsyncSession
) -> Geography | None:
    row = await _row(_geographies, geo_id, session)
    if row is None:
        return None
    values: dict[str, Any] = body.model_dump(exclude_unset=True)
    if values.get("name") is not None:
        await _check_sibling(
            _geographies, values["name"], row.parent_id, session, exclude_id=geo_id
        )
    elif "name" in values:
        values.pop("name")
    if "code" in values:
        _validate_code(values["code"], row.level)
        await _check_code_unique(values["code"], session, exclude_id=geo_id)
    if values:
        values["updated_at"] = _now()
        await session.execute(
            _geographies.update().where(_geographies.c.id == geo_id).values(**values)
        )
    return (await _geography_models(session, [geo_id]))[0]


async def _clear_mapping_geography(geo_id: str, session: AsyncSession) -> None:
    """941 FR-007 / research R3: performers on this geography lose it. Where the same capability
    and unit already performs "everywhere", the geography row is dropped instead, so clearing it
    can't collide with the COALESCE unique index."""
    m = _capability_org_mappings
    e = _capability_org_mappings.alias("everywhere")
    await session.execute(
        m.delete().where(
            m.c.geography_id == geo_id,
            sa.exists().where(
                e.c.capability_id == m.c.capability_id,
                e.c.org_unit_id == m.c.org_unit_id,
                e.c.role == m.c.role,
                e.c.geography_id.is_(None),
            ),
        )
    )
    await session.execute(m.update().where(m.c.geography_id == geo_id).values(geography_id=None))


async def delete_geography(geo_id: str, session: AsyncSession) -> bool:
    if await _row(_geographies, geo_id, session) is None:
        return False
    await _refuse_if_children(_geographies, geo_id, "Geography", session)
    await _clear_mapping_geography(geo_id, session)
    await session.execute(
        _org_units.update()
        .where(_org_units.c.primary_geography_id == geo_id)
        .values(primary_geography_id=None)
    )
    await session.execute(
        _org_unit_geographies.delete().where(_org_unit_geographies.c.geography_id == geo_id)
    )
    return (
        _rowcount(await session.execute(_geographies.delete().where(_geographies.c.id == geo_id)))
        > 0
    )


# ── Review queue (US4, research R5) ───────────────────────────────────────────


def _unmatched_filter() -> Any:
    return sa.and_(
        _applications.c.owning_org_unit_id.is_(None),
        _applications.c.owning_business_unit.is_not(None),
        sa.func.trim(_applications.c.owning_business_unit) != "",
    )


async def list_unmatched(session: AsyncSession) -> UnmatchedListResponse:
    rows = (
        await session.execute(
            sa.select(
                _applications.c.owning_business_unit, _applications.c.id, _applications.c.name
            )
            .where(_unmatched_filter())
            .order_by(_applications.c.name)
        )
    ).all()
    by_value: dict[str, list[Ref]] = defaultdict(list)
    for value, app_id, name in rows:
        by_value[value].append(Ref(id=app_id, name=name, level=0))
    items = [
        UnmatchedValue(value=v, application_count=len(apps), sample_applications=apps[:5])
        for v, apps in by_value.items()
    ]
    items.sort(key=lambda u: (-u.application_count, u.value))
    return UnmatchedListResponse(items=items, total=len(items))


async def resolve_unmatched(body: ResolveUnmatched, session: AsyncSession) -> ResolveResult:
    """Link every unlinked application whose free text is exactly ``body.value``. The free text is
    never written (SC-004); an org unit is created only when ``body.create`` asks for it."""
    if body.create is not None:
        org_unit = await create_org_unit(
            OrgUnitCreate(
                name=body.create.name,
                description=body.create.description,
                parent_id=body.create.parent_id,
            ),
            session,
        )
        ou_id = org_unit.id
    else:
        assert body.org_unit_id is not None  # validated by the model
        await _require(_org_units, body.org_unit_id, "Org unit", session)
        ou_id = body.org_unit_id
    result = await session.execute(
        _applications.update()
        .where(_unmatched_filter(), _applications.c.owning_business_unit == body.value)
        .values(owning_org_unit_id=ou_id)
    )
    return ResolveResult(
        org_unit=(await _org_unit_models(session, [ou_id]))[0], updated_count=_rowcount(result)
    )
