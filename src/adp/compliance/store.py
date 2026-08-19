"""Compliance domain store — async SQLAlchemy CRUD (COMPLY-01, COMPLY-02).

Provides RegulatoryFramework/Control (COMPLY-01) and ControlMapping (COMPLY-02) persistence using a
dedicated session factory (mirrors adp.business.store's shape). All functions accept an AsyncSession
and are called from the router inside a `Depends(_get_session)`-yielded session.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.compliance.models import (
    ComplianceStatus,
    ComplianceSummaryResponse,
    Control,
    ControlCreate,
    ControlMapping,
    ControlMappingWrite,
    ControlNode,
    ControlNotFoundError,
    ControlUpdate,
    CrossFrameworkParentError,
    CyclicParentError,
    DuplicateControlCodeError,
    EntityStatusCounts,
    FrameworkCoverageRollup,
    InvalidPatternTargetError,
    MappingNotFoundError,
    MappingTargetNotFoundError,
    MappingTargetType,
    ParentNotFoundError,
    RegulatoryFramework,
    RegulatoryFrameworkCreate,
    RegulatoryFrameworkDetail,
    RegulatoryFrameworkUpdate,
)

# ── Table definitions (SQLAlchemy Core — no ORM mapper needed) ────────────────
# Migration owns FK/PK/UNIQUE/CHECK constraints (032_compliance_framework_registry.py);
# these Table() objects are DML-only, per the project's existing convention.

_metadata = sa.MetaData()

_frameworks = sa.Table(
    "regulatory_frameworks",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("jurisdiction", sa.String(255), nullable=False),
    sa.Column("authority", sa.String(255), nullable=False),
    sa.Column("version", sa.String(100), nullable=False),
    sa.Column("effective_date", sa.Date(), nullable=True),
    sa.Column("source_url", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_controls = sa.Table(
    "controls",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("framework_id", sa.String(36), nullable=False),
    sa.Column("parent_id", sa.String(36), nullable=True),
    sa.Column("code", sa.String(100), nullable=False),
    sa.Column("title", sa.String(255), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("position", sa.Integer(), nullable=False, default=0),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

# ── Mapping tables (COMPLY-02) — DML-only, migration 033 owns FK/PK/CHECK ──────
# Four entity-targeted tables + one estate-wide table with no target leg
# (Clarification Session 2026-08-18; research.md D1). Shared column shape.

def _mapping_columns() -> tuple[sa.Column, ...]:
    """A sa.Column instance can only ever belong to one Table -- returns fresh instances on
    every call so each of the five mapping tables below gets its own set."""
    return (
        sa.Column("compliance_status", sa.Text(), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.Date(), nullable=True),
        sa.Column("assessed_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


_control_capability_mapping = sa.Table(
    "control_capability_mapping",
    _metadata,
    sa.Column("control_id", sa.String(36), primary_key=True),
    sa.Column("capability_id", sa.String(36), primary_key=True),
    *_mapping_columns(),
)

_control_application_mapping = sa.Table(
    "control_application_mapping",
    _metadata,
    sa.Column("control_id", sa.String(36), primary_key=True),
    sa.Column("application_id", sa.String(36), primary_key=True),
    *_mapping_columns(),
)

_control_design_mapping = sa.Table(
    "control_design_mapping",
    _metadata,
    sa.Column("control_id", sa.String(36), primary_key=True),
    sa.Column("design_id", sa.Text(), primary_key=True),
    *_mapping_columns(),
)

_control_pattern_mapping = sa.Table(
    "control_pattern_mapping",
    _metadata,
    sa.Column("control_id", sa.String(36), primary_key=True),
    sa.Column("pattern_id", sa.String(), primary_key=True),
    *_mapping_columns(),
)

_control_organization_mapping = sa.Table(
    "control_organization_mapping",
    _metadata,
    sa.Column("control_id", sa.String(36), primary_key=True),
    *_mapping_columns(),
)

# ── Narrow mirror tables for target existence/kind validation (research.md D4) ─
# Only the columns needed for validation -- not full domain objects. Same
# physical Postgres database, same session; extends adp.strategy.store's own
# design_exists/application_exists idiom so adp.compliance imports zero other
# domain packages.

_capabilities_mirror = sa.Table(
    "business_capabilities", _metadata, sa.Column("id", sa.String(36), primary_key=True)
)
_applications_mirror = sa.Table(
    "applications", _metadata, sa.Column("id", sa.String(36), primary_key=True)
)
_designs_mirror = sa.Table(
    "designs", _metadata, sa.Column("id", sa.Text(), primary_key=True)
)
_knowledge_items_mirror = sa.Table(
    "knowledge_items",
    _metadata,
    sa.Column("id", sa.String(), primary_key=True),
    sa.Column("kind", sa.Text(), nullable=False),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rowcount(result: Any) -> int:
    """DML executes return CursorResult at runtime; session.execute is typed as
    Result[Any], which lacks rowcount (mirrors adp.business.store's identical helper)."""
    return cast("sa.CursorResult[Any]", result).rowcount


# ── Module-level session factory (set by deps or tests) ───────────────────────

_engine: Any = None
_session_factory: Any = None


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


def get_session() -> AsyncSession:
    return _get_session_factory()()


# ── Row → model helpers ─────────────────────────────────────────────────────

def _row_to_framework(row: Any) -> RegulatoryFramework:
    return RegulatoryFramework(
        id=row.id, name=row.name, jurisdiction=row.jurisdiction, authority=row.authority,
        version=row.version, effective_date=row.effective_date, source_url=row.source_url,
        created_at=row.created_at, updated_at=row.updated_at,
    )


def _row_to_control(row: Any) -> Control:
    return Control(
        id=row.id, framework_id=row.framework_id, parent_id=row.parent_id, code=row.code,
        title=row.title, description=row.description, position=row.position,
        created_at=row.created_at, updated_at=row.updated_at,
    )


def _assemble_control_tree(rows: list[Any]) -> list[ControlNode]:
    """Assemble a flat list of control rows into a parent_id-nested tree, ordered by
    position at every level (research.md D8 — depth is derived, not stored)."""
    nodes: dict[str, ControlNode] = {
        row.id: ControlNode(**_row_to_control(row).model_dump(), children=[]) for row in rows
    }
    roots: list[ControlNode] = []
    children_by_parent: dict[str | None, list[ControlNode]] = {}
    for row in rows:
        children_by_parent.setdefault(row.parent_id, []).append(nodes[row.id])

    def _attach(node: ControlNode) -> None:
        kids = sorted(children_by_parent.get(node.id, []), key=lambda n: n.position)
        node.children = kids
        for kid in kids:
            _attach(kid)

    for row in rows:
        if row.parent_id is None:
            _attach(nodes[row.id])
            roots.append(nodes[row.id])
    return sorted(roots, key=lambda n: n.position)


# ── RegulatoryFramework CRUD ─────────────────────────────────────────────────

async def create_framework(
    data: RegulatoryFrameworkCreate, session: AsyncSession
) -> RegulatoryFramework:
    fw_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _frameworks.insert().values(
            id=fw_id, name=data.name.strip(), jurisdiction=data.jurisdiction.strip(),
            authority=data.authority.strip(), version=data.version.strip(),
            effective_date=data.effective_date, source_url=data.source_url,
            created_at=now, updated_at=now,
        )
    )
    return RegulatoryFramework(
        id=fw_id, name=data.name.strip(), jurisdiction=data.jurisdiction.strip(),
        authority=data.authority.strip(), version=data.version.strip(),
        effective_date=data.effective_date, source_url=data.source_url,
        created_at=now, updated_at=now,
    )


async def list_frameworks(session: AsyncSession) -> list[RegulatoryFramework]:
    result = await session.execute(sa.select(_frameworks).order_by(_frameworks.c.name))
    return [_row_to_framework(row) for row in result]


async def get_framework(framework_id: str, session: AsyncSession) -> RegulatoryFramework | None:
    result = await session.execute(
        sa.select(_frameworks).where(_frameworks.c.id == framework_id)
    )
    row = result.first()
    return _row_to_framework(row) if row is not None else None


async def get_framework_detail(
    framework_id: str, session: AsyncSession
) -> RegulatoryFrameworkDetail | None:
    """Fetches the framework plus every control row where framework_id matches, assembling
    the parent_id-nested tree. Correctly returns controls=[] when no control rows exist yet
    (every case until create_control is exercised) -- this function needs no changes once
    controls are populated (data-model.md)."""
    fw = await get_framework(framework_id, session)
    if fw is None:
        return None
    result = await session.execute(
        sa.select(_controls)
        .where(_controls.c.framework_id == framework_id)
        .order_by(_controls.c.position)
    )
    rows = list(result)
    return RegulatoryFrameworkDetail(**fw.model_dump(), controls=_assemble_control_tree(rows))


async def update_framework(
    framework_id: str, data: RegulatoryFrameworkUpdate, session: AsyncSession
) -> RegulatoryFramework | None:
    existing = await get_framework(framework_id, session)
    if existing is None:
        return None

    updates: dict[str, Any] = {"updated_at": _now()}
    for field in ("name", "jurisdiction", "authority", "version"):
        value = getattr(data, field)
        if value is not None:
            updates[field] = value.strip()
    # Nullable fields: an explicitly provided value (incl. null) clears/sets it;
    # an omitted field is left unchanged (model_fields_set distinguishes them).
    if "effective_date" in data.model_fields_set:
        updates["effective_date"] = data.effective_date
    if "source_url" in data.model_fields_set:
        updates["source_url"] = data.source_url

    await session.execute(
        _frameworks.update().where(_frameworks.c.id == framework_id).values(**updates)
    )
    return await get_framework(framework_id, session)


async def delete_framework(framework_id: str, session: AsyncSession) -> bool:
    """Deletes the framework. Cascading to every control beneath it, at every hierarchy
    level, is handled entirely by the migration's ON DELETE CASCADE (research.md D2) --
    no application-layer recursion needed."""
    result = await session.execute(
        _frameworks.delete().where(_frameworks.c.id == framework_id)
    )
    return _rowcount(result) > 0


# ── Control CRUD ──────────────────────────────────────────────────────────────

async def _get_control_row(control_id: str, session: AsyncSession) -> Any:
    result = await session.execute(_controls.select().where(_controls.c.id == control_id))
    return result.first()


async def create_control(
    framework_id: str, data: ControlCreate, session: AsyncSession
) -> Control:
    if data.parent_id is not None:
        parent = await _get_control_row(data.parent_id, session)
        if parent is None:
            raise ParentNotFoundError(data.parent_id)
        if parent.framework_id != framework_id:
            raise CrossFrameworkParentError(data.parent_id, framework_id, parent.framework_id)

    ctrl_id = str(uuid.uuid4())
    now = _now()
    try:
        await session.execute(
            _controls.insert().values(
                id=ctrl_id, framework_id=framework_id, parent_id=data.parent_id,
                code=data.code.strip(), title=data.title.strip(),
                description=data.description.strip(), position=data.position,
                created_at=now, updated_at=now,
            )
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateControlCodeError(framework_id, data.code.strip()) from exc
        raise

    return Control(
        id=ctrl_id, framework_id=framework_id, parent_id=data.parent_id,
        code=data.code.strip(), title=data.title.strip(),
        description=data.description.strip(), position=data.position,
        created_at=now, updated_at=now,
    )


async def update_control(
    control_id: str, data: ControlUpdate, session: AsyncSession
) -> Control | None:
    existing_row = await _get_control_row(control_id, session)
    if existing_row is None:
        return None
    existing = _row_to_control(existing_row)

    updates: dict[str, Any] = {"updated_at": _now()}

    if "parent_id" in data.model_fields_set and data.parent_id != existing.parent_id:
        if data.parent_id is not None:
            parent = await _get_control_row(data.parent_id, session)
            if parent is None:
                raise ParentNotFoundError(data.parent_id)
            if parent.framework_id != existing.framework_id:
                raise CrossFrameworkParentError(
                    data.parent_id, existing.framework_id, parent.framework_id
                )
            # Cycle check: the proposed parent must not be this control itself, nor any
            # of its own descendants (research.md D5). Walking DOWN from control_id and
            # checking membership is equivalent to, and simpler than, walking up from the
            # proposed parent -- either the proposed parent is control_id itself, or it's
            # reachable from control_id by descending, or neither (no cycle).
            if data.parent_id == control_id or await _is_descendant(
                control_id, data.parent_id, session
            ):
                raise CyclicParentError(control_id, data.parent_id)
        updates["parent_id"] = data.parent_id

    if data.code is not None and data.code.strip() != existing.code:
        updates["code"] = data.code.strip()
    if data.title is not None:
        updates["title"] = data.title.strip()
    if "description" in data.model_fields_set:
        updates["description"] = (
            data.description.strip() if data.description is not None else None
        )
    if data.position is not None:
        updates["position"] = data.position

    try:
        await session.execute(
            _controls.update().where(_controls.c.id == control_id).values(**updates)
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateControlCodeError(
                existing.framework_id, updates.get("code", existing.code)
            ) from exc
        raise

    refreshed_row = await _get_control_row(control_id, session)
    return _row_to_control(refreshed_row)


async def _is_descendant(ancestor_id: str, candidate_id: str, session: AsyncSession) -> bool:
    """True if candidate_id is a descendant (child, grandchild, ...) of ancestor_id."""
    ancestor_row = await _get_control_row(ancestor_id, session)
    result = await session.execute(
        sa.select(_controls.c.id, _controls.c.parent_id)
        .where(_controls.c.framework_id == ancestor_row.framework_id)
    )
    rows = {row.id: row.parent_id for row in result}
    current = candidate_id
    seen: set[str] = set()
    while current in rows and current not in seen:
        seen.add(current)
        parent = rows[current]
        if parent == ancestor_id:
            return True
        if parent is None:
            return False
        current = parent
    return False


async def delete_control(control_id: str, session: AsyncSession) -> bool:
    """Deletes the control. Cascading to every descendant control beneath it is handled
    entirely by the migration's self-referencing ON DELETE CASCADE (research.md D2)."""
    result = await session.execute(_controls.delete().where(_controls.c.id == control_id))
    return _rowcount(result) > 0


async def get_control(control_id: str, session: AsyncSession) -> Control | None:
    """New in COMPLY-02 -- COMPLY-01 never needed a standalone getter outside
    get_framework_detail's tree assembly."""
    row = await _get_control_row(control_id, session)
    return _row_to_control(row) if row is not None else None


# ── Target existence/kind checks (research.md D4/D5) ────────────────────────

async def capability_exists(capability_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        sa.select(_capabilities_mirror.c.id).where(_capabilities_mirror.c.id == capability_id)
    )
    return result.first() is not None


async def application_exists(application_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        sa.select(_applications_mirror.c.id).where(_applications_mirror.c.id == application_id)
    )
    return result.first() is not None


async def design_exists(design_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        sa.select(_designs_mirror.c.id).where(_designs_mirror.c.id == design_id)
    )
    return result.first() is not None


async def get_knowledge_item_kind(pattern_id: str, session: AsyncSession) -> str | None:
    """Returns the knowledge_items row's `kind`, or None if pattern_id doesn't exist -- feeds
    both existence and the D5 kind == 'pattern' check in one query."""
    result = await session.execute(
        sa.select(_knowledge_items_mirror.c.kind)
        .where(_knowledge_items_mirror.c.id == pattern_id)
    )
    row = result.first()
    return row.kind if row is not None else None


# ── ControlMapping CRUD (COMPLY-02) ──────────────────────────────────────────

def _row_to_mapping(
    row: Any, target_type: MappingTargetType, target_id: str | None
) -> ControlMapping:
    return ControlMapping(
        control_id=row.control_id,
        target_type=target_type,
        target_id=target_id,
        compliance_status=ComplianceStatus(row.compliance_status),
        evidence_ref=row.evidence_ref,
        assessed_at=row.assessed_at,
        assessed_by=row.assessed_by,
        created_at=row.created_at,
    )


def _mapping_write_values(data: ControlMappingWrite) -> dict[str, Any]:
    """The mutable fields only -- deliberately excludes created_at, which must be set once
    on insert and never touched again by an update."""
    return {
        "compliance_status": data.compliance_status.value,
        "evidence_ref": data.evidence_ref,
        "assessed_at": data.assessed_at,
        "assessed_by": data.assessed_by,
    }


def _is_unique_violation(exc: Exception) -> bool:
    """Mirrors create_control/update_control's identical inline check."""
    text = str(exc).lower()
    return "unique" in text or "duplicate" in text or "23505" in text


async def _upsert_entity_mapping(
    table: sa.Table,
    target_column: str,
    target_type: MappingTargetType,
    control_id: str,
    target_id: str,
    data: ControlMappingWrite,
    session: AsyncSession,
) -> ControlMapping:
    """Shared upsert body for the four entity-targeted mapping tables: select-then-branch
    (UPDATE if a row for this (control_id, target) pair already exists, else INSERT),
    matching adp.store.store's own DesignStore.save() upsert idiom (deliberately NOT
    Postgres's ON CONFLICT DO UPDATE, which contract tests can't exercise against the
    SQLite fixture every other compliance contract test uses -- research.md D3, revised).
    A concurrent double-write racing the exists-check is self-healed by catching the
    resulting unique-violation and falling back to UPDATE, rather than surfacing a 409 on
    what spec.md FR-007/FR-008 defines as a normal, expected re-mapping. Callers validate
    control/target existence first."""
    where = sa.and_(table.c.control_id == control_id, table.c[target_column] == target_id)
    values = _mapping_write_values(data)

    existing = await session.execute(sa.select(table.c.control_id).where(where))
    if existing.first() is not None:
        await session.execute(table.update().where(where).values(**values))
    else:
        try:
            await session.execute(
                table.insert().values(
                    control_id=control_id, **{target_column: target_id},
                    created_at=_now(), **values,
                )
            )
        except Exception as exc:
            if not _is_unique_violation(exc):
                raise
            await session.execute(table.update().where(where).values(**values))

    result = await session.execute(sa.select(table).where(where))
    row = result.one()
    return _row_to_mapping(row, target_type, target_id)


async def upsert_capability_mapping(
    control_id: str, capability_id: str, data: ControlMappingWrite, session: AsyncSession
) -> ControlMapping:
    if await get_control(control_id, session) is None:
        raise ControlNotFoundError(control_id)
    if not await capability_exists(capability_id, session):
        raise MappingTargetNotFoundError("capability", capability_id)
    return await _upsert_entity_mapping(
        _control_capability_mapping, "capability_id", MappingTargetType.CAPABILITY,
        control_id, capability_id, data, session,
    )


async def upsert_application_mapping(
    control_id: str, application_id: str, data: ControlMappingWrite, session: AsyncSession
) -> ControlMapping:
    if await get_control(control_id, session) is None:
        raise ControlNotFoundError(control_id)
    if not await application_exists(application_id, session):
        raise MappingTargetNotFoundError("application", application_id)
    return await _upsert_entity_mapping(
        _control_application_mapping, "application_id", MappingTargetType.APPLICATION,
        control_id, application_id, data, session,
    )


async def upsert_design_mapping(
    control_id: str, design_id: str, data: ControlMappingWrite, session: AsyncSession
) -> ControlMapping:
    if await get_control(control_id, session) is None:
        raise ControlNotFoundError(control_id)
    if not await design_exists(design_id, session):
        raise MappingTargetNotFoundError("design", design_id)
    return await _upsert_entity_mapping(
        _control_design_mapping, "design_id", MappingTargetType.DESIGN,
        control_id, design_id, data, session,
    )


async def upsert_pattern_mapping(
    control_id: str, pattern_id: str, data: ControlMappingWrite, session: AsyncSession
) -> ControlMapping:
    if await get_control(control_id, session) is None:
        raise ControlNotFoundError(control_id)
    kind = await get_knowledge_item_kind(pattern_id, session)
    if kind is None:
        raise MappingTargetNotFoundError("pattern", pattern_id)
    if kind != "pattern":
        raise InvalidPatternTargetError(pattern_id, kind)
    return await _upsert_entity_mapping(
        _control_pattern_mapping, "pattern_id", MappingTargetType.PATTERN,
        control_id, pattern_id, data, session,
    )


async def upsert_organization_mapping(
    control_id: str, data: ControlMappingWrite, session: AsyncSession
) -> ControlMapping:
    """Single-column PK on control_id (research.md D1/D9) -- at most one estate-wide mapping
    per Control, no target existence check beyond the Control itself. Same select-then-branch
    upsert shape as _upsert_entity_mapping, just without a second key column."""
    if await get_control(control_id, session) is None:
        raise ControlNotFoundError(control_id)

    table = _control_organization_mapping
    where = table.c.control_id == control_id
    values = _mapping_write_values(data)

    existing = await session.execute(sa.select(table.c.control_id).where(where))
    if existing.first() is not None:
        await session.execute(table.update().where(where).values(**values))
    else:
        try:
            await session.execute(
                table.insert().values(control_id=control_id, created_at=_now(), **values)
            )
        except Exception as exc:
            if not _is_unique_violation(exc):
                raise
            await session.execute(table.update().where(where).values(**values))

    result = await session.execute(sa.select(table).where(where))
    row = result.one()
    return _row_to_mapping(row, MappingTargetType.ORGANIZATION, None)


async def list_mappings_for_control(
    control_id: str, session: AsyncSession
) -> list[ControlMapping]:
    """Raises ControlNotFoundError if the control doesn't exist; otherwise unions all five
    mapping tables filtered by control_id, tagging each row with its target_type."""
    if await get_control(control_id, session) is None:
        raise ControlNotFoundError(control_id)

    mappings: list[ControlMapping] = []

    result = await session.execute(
        sa.select(_control_capability_mapping).where(
            _control_capability_mapping.c.control_id == control_id
        )
    )
    mappings += [
        _row_to_mapping(row, MappingTargetType.CAPABILITY, row.capability_id) for row in result
    ]

    result = await session.execute(
        sa.select(_control_application_mapping).where(
            _control_application_mapping.c.control_id == control_id
        )
    )
    mappings += [
        _row_to_mapping(row, MappingTargetType.APPLICATION, row.application_id) for row in result
    ]

    result = await session.execute(
        sa.select(_control_design_mapping).where(
            _control_design_mapping.c.control_id == control_id
        )
    )
    mappings += [
        _row_to_mapping(row, MappingTargetType.DESIGN, row.design_id) for row in result
    ]

    result = await session.execute(
        sa.select(_control_pattern_mapping).where(
            _control_pattern_mapping.c.control_id == control_id
        )
    )
    mappings += [
        _row_to_mapping(row, MappingTargetType.PATTERN, row.pattern_id) for row in result
    ]

    result = await session.execute(
        sa.select(_control_organization_mapping).where(
            _control_organization_mapping.c.control_id == control_id
        )
    )
    mappings += [_row_to_mapping(row, MappingTargetType.ORGANIZATION, None) for row in result]

    return mappings


async def list_mappings_for_capability(
    capability_id: str, session: AsyncSession
) -> list[ControlMapping]:
    result = await session.execute(
        sa.select(_control_capability_mapping).where(
            _control_capability_mapping.c.capability_id == capability_id
        )
    )
    return [
        _row_to_mapping(row, MappingTargetType.CAPABILITY, row.capability_id) for row in result
    ]


async def list_mappings_for_application(
    application_id: str, session: AsyncSession
) -> list[ControlMapping]:
    result = await session.execute(
        sa.select(_control_application_mapping).where(
            _control_application_mapping.c.application_id == application_id
        )
    )
    return [
        _row_to_mapping(row, MappingTargetType.APPLICATION, row.application_id) for row in result
    ]


async def list_mappings_for_design(
    design_id: str, session: AsyncSession
) -> list[ControlMapping]:
    result = await session.execute(
        sa.select(_control_design_mapping).where(
            _control_design_mapping.c.design_id == design_id
        )
    )
    return [_row_to_mapping(row, MappingTargetType.DESIGN, row.design_id) for row in result]


async def list_mappings_for_pattern(
    pattern_id: str, session: AsyncSession
) -> list[ControlMapping]:
    result = await session.execute(
        sa.select(_control_pattern_mapping).where(
            _control_pattern_mapping.c.pattern_id == pattern_id
        )
    )
    return [_row_to_mapping(row, MappingTargetType.PATTERN, row.pattern_id) for row in result]


async def delete_capability_mapping(
    control_id: str, capability_id: str, session: AsyncSession
) -> None:
    result = await session.execute(
        _control_capability_mapping.delete().where(
            sa.and_(
                _control_capability_mapping.c.control_id == control_id,
                _control_capability_mapping.c.capability_id == capability_id,
            )
        )
    )
    if _rowcount(result) == 0:
        raise MappingNotFoundError(control_id, "capability", capability_id)


async def delete_application_mapping(
    control_id: str, application_id: str, session: AsyncSession
) -> None:
    result = await session.execute(
        _control_application_mapping.delete().where(
            sa.and_(
                _control_application_mapping.c.control_id == control_id,
                _control_application_mapping.c.application_id == application_id,
            )
        )
    )
    if _rowcount(result) == 0:
        raise MappingNotFoundError(control_id, "application", application_id)


async def delete_design_mapping(control_id: str, design_id: str, session: AsyncSession) -> None:
    result = await session.execute(
        _control_design_mapping.delete().where(
            sa.and_(
                _control_design_mapping.c.control_id == control_id,
                _control_design_mapping.c.design_id == design_id,
            )
        )
    )
    if _rowcount(result) == 0:
        raise MappingNotFoundError(control_id, "design", design_id)


async def delete_pattern_mapping(
    control_id: str, pattern_id: str, session: AsyncSession
) -> None:
    result = await session.execute(
        _control_pattern_mapping.delete().where(
            sa.and_(
                _control_pattern_mapping.c.control_id == control_id,
                _control_pattern_mapping.c.pattern_id == pattern_id,
            )
        )
    )
    if _rowcount(result) == 0:
        raise MappingNotFoundError(control_id, "pattern", pattern_id)


async def delete_organization_mapping(control_id: str, session: AsyncSession) -> None:
    result = await session.execute(
        _control_organization_mapping.delete().where(
            _control_organization_mapping.c.control_id == control_id
        )
    )
    if _rowcount(result) == 0:
        raise MappingNotFoundError(control_id, "organization", None)


# ── Derived Compliance Status (COMPLY-03, specs/923-derived-compliance-status/) ────────────
# compute_compliance_status() is a pure, no-I/O aggregation function, built and tested
# standalone before any caller depends on it (research.md D2/D3, mirrors adp.strategy.store.
# compute_status() and adp.application.store.compute_business_value_score()'s own precedent).
# get_entity_compliance_status() is the thin async dispatch wrapper that gathers a real
# entity's current ControlMapping statuses and forwards them to it.

_SUPPORTED_ENTITY_TYPES = (
    MappingTargetType.CAPABILITY,
    MappingTargetType.APPLICATION,
    MappingTargetType.DESIGN,
    MappingTargetType.PATTERN,
)


def compute_compliance_status(statuses: list[ComplianceStatus]) -> ComplianceStatus:
    """Pure, no-I/O aggregation (research.md D5): minimum-aggregation, mirroring the Application
    Health rubric's MIN()  -- one Non-Compliant control anywhere dominates the result rather than
    being averaged away.

    Decision table, evaluated in order:
      1. No mapped controls at all                                -> NOT_ASSESSED
      2. Any NON_COMPLIANT                                        -> NON_COMPLIANT
      3. Else, any PARTIAL or NOT_ASSESSED                        -> PARTIAL
      4. Else, any COMPLIANT                                      -> COMPLIANT
      5. Else (every status is NOT_APPLICABLE)                    -> NOT_APPLICABLE

    Row 5 resolves spec.md's Q1 (an entity whose every mapped control is Not Applicable, with none
    Compliant, is a genuinely distinct outcome -- not folded into Not Assessed, per user
    clarification during /speckit.specify).
    """
    if not statuses:
        return ComplianceStatus.NOT_ASSESSED
    if any(s == ComplianceStatus.NON_COMPLIANT for s in statuses):
        return ComplianceStatus.NON_COMPLIANT
    if any(s in (ComplianceStatus.PARTIAL, ComplianceStatus.NOT_ASSESSED) for s in statuses):
        return ComplianceStatus.PARTIAL
    if any(s == ComplianceStatus.COMPLIANT for s in statuses):
        return ComplianceStatus.COMPLIANT
    return ComplianceStatus.NOT_APPLICABLE


async def get_entity_compliance_status(
    entity_type: MappingTargetType, entity_id: str, session: AsyncSession
) -> ComplianceStatus:
    """Thin async dispatch wrapper (research.md D3/D4): fetches entity_id's current
    ControlMapping rows via the matching existing list_mappings_for_* function, then forwards
    their statuses to compute_compliance_status().

    entity_type must be one of the four FK-enforced, entity-targeted mapping types (Capability/
    Application/Design/Pattern) -- ORGANIZATION has no per-entity lookup at all (a standing,
    estate-wide obligation keyed only by control_id, per COMPLY-02's schema) and is explicitly out
    of scope for this per-entity function (spec.md Assumptions); passing it, or any other
    unsupported value, raises ValueError rather than silently returning a status.

    Does not itself validate that entity_id refers to an existing entity -- the underlying
    list_mappings_for_* functions already return an empty list (not an error) for an entity_id
    with zero mappings, and zero mappings correctly derives to NOT_ASSESSED either way.
    """
    if entity_type not in _SUPPORTED_ENTITY_TYPES:
        raise ValueError(
            f"get_entity_compliance_status() does not support entity_type {entity_type!r}; "
            f"must be one of {[t.value for t in _SUPPORTED_ENTITY_TYPES]}"
        )

    if entity_type == MappingTargetType.CAPABILITY:
        mappings = await list_mappings_for_capability(entity_id, session)
    elif entity_type == MappingTargetType.APPLICATION:
        mappings = await list_mappings_for_application(entity_id, session)
    elif entity_type == MappingTargetType.DESIGN:
        mappings = await list_mappings_for_design(entity_id, session)
    else:
        mappings = await list_mappings_for_pattern(entity_id, session)

    return compute_compliance_status([m.compliance_status for m in mappings])


# ── Compliance Rollup Reporting (COMPLY-04, specs/924-compliance-rollup-reporting/) ─────────
# Two read-only aggregate views over the same COMPLY-01/02 data, both built on
# compute_compliance_status() (COMPLY-03) via one shared bucketing helper (research.md D1).

_EntityRow = tuple[MappingTargetType, str, ComplianceStatus]

_FIELD_BY_STATUS: dict[ComplianceStatus, str] = {
    ComplianceStatus.COMPLIANT: "compliant_count",
    ComplianceStatus.PARTIAL: "partial_count",
    ComplianceStatus.NON_COMPLIANT: "non_compliant_count",
    ComplianceStatus.NOT_ASSESSED: "not_assessed_count",
    ComplianceStatus.NOT_APPLICABLE: "not_applicable_count",
}


def _bucket_entities_by_status(rows: list[_EntityRow]) -> EntityStatusCounts:
    """Pure, no I/O (research.md D1): groups rows by (target_type, target_id), calls
    compute_compliance_status() once per group (COMPLY-03, unmodified), tallies the results into
    EntityStatusCounts. Shared by both get_framework_coverage_rollup() and
    get_compliance_summary() -- the only thing that differs between them is which rows they pass
    in (framework-scoped vs. estate-wide, research.md D3).

    Note: not_assessed_count is structurally always 0 here. An entity only appears as a group
    when it has at least one row, and compute_compliance_status() resolves any nonempty status
    list containing NOT_ASSESSED to PARTIAL, never NOT_ASSESSED (its rule 3) -- the only way to
    reach NOT_ASSESSED is an empty list, which never occurs for a group that exists at all. The
    field is still present (FR-002's "cover all five buckets"), just always 0 in practice."""
    groups: dict[tuple[MappingTargetType, str], list[ComplianceStatus]] = {}
    for target_type, target_id, status in rows:
        groups.setdefault((target_type, target_id), []).append(status)

    tallies = dict.fromkeys(_FIELD_BY_STATUS.values(), 0)
    for statuses in groups.values():
        tallies[_FIELD_BY_STATUS[compute_compliance_status(statuses)]] += 1

    return EntityStatusCounts(**tallies)


async def _framework_entity_rows(framework_id: str, session: AsyncSession) -> list[_EntityRow]:
    """Every entity-targeted ControlMapping row whose control belongs to framework_id, tagged
    with its target_type. Four small queries (mirrors list_mappings_for_control's own five-way-
    union style, filtered via a join on framework_id instead of a direct control_id equality --
    research.md D3), not one UNION, consistent with this module's existing idiom."""
    rows: list[_EntityRow] = []

    result = await session.execute(
        sa.select(
            _control_capability_mapping.c.capability_id,
            _control_capability_mapping.c.compliance_status,
        )
        .select_from(
            _control_capability_mapping.join(
                _controls, _control_capability_mapping.c.control_id == _controls.c.id
            )
        )
        .where(_controls.c.framework_id == framework_id)
    )
    rows += [
        (MappingTargetType.CAPABILITY, r.capability_id, ComplianceStatus(r.compliance_status))
        for r in result
    ]

    result = await session.execute(
        sa.select(
            _control_application_mapping.c.application_id,
            _control_application_mapping.c.compliance_status,
        )
        .select_from(
            _control_application_mapping.join(
                _controls, _control_application_mapping.c.control_id == _controls.c.id
            )
        )
        .where(_controls.c.framework_id == framework_id)
    )
    rows += [
        (MappingTargetType.APPLICATION, r.application_id, ComplianceStatus(r.compliance_status))
        for r in result
    ]

    result = await session.execute(
        sa.select(_control_design_mapping.c.design_id, _control_design_mapping.c.compliance_status)
        .select_from(
            _control_design_mapping.join(
                _controls, _control_design_mapping.c.control_id == _controls.c.id
            )
        )
        .where(_controls.c.framework_id == framework_id)
    )
    rows += [
        (MappingTargetType.DESIGN, r.design_id, ComplianceStatus(r.compliance_status))
        for r in result
    ]

    result = await session.execute(
        sa.select(
            _control_pattern_mapping.c.pattern_id, _control_pattern_mapping.c.compliance_status
        )
        .select_from(
            _control_pattern_mapping.join(
                _controls, _control_pattern_mapping.c.control_id == _controls.c.id
            )
        )
        .where(_controls.c.framework_id == framework_id)
    )
    rows += [
        (MappingTargetType.PATTERN, r.pattern_id, ComplianceStatus(r.compliance_status))
        for r in result
    ]

    return rows


async def _framework_organization_rows(
    framework_id: str, session: AsyncSession
) -> list[ComplianceStatus]:
    """Every organization-scoped (estate-wide) mapping's status for controls in this framework.
    No target_id at all -- never fed into _bucket_entities_by_status(), which is entity-keyed;
    aggregated separately for FrameworkCoverageRollup.organization_status (spec.md FR-003)."""
    result = await session.execute(
        sa.select(_control_organization_mapping.c.compliance_status)
        .select_from(
            _control_organization_mapping.join(
                _controls, _control_organization_mapping.c.control_id == _controls.c.id
            )
        )
        .where(_controls.c.framework_id == framework_id)
    )
    return [ComplianceStatus(r.compliance_status) for r in result]


async def get_framework_coverage_rollup(
    framework_id: str, include_application: bool, session: AsyncSession
) -> FrameworkCoverageRollup | None:
    """US1: one framework's coverage picture. Returns None if framework_id doesn't exist
    (router maps to 404, mirroring get_framework_detail's own None-means-404 convention).

    include_application=False drops every APPLICATION-tagged row before bucketing (research.md
    D2 -- filter-before-aggregate, a deliberate contrast with list_control_mappings' own
    filter-after-fetch precedent, since aggregation happens in this layer, not the router)."""
    if await get_framework(framework_id, session) is None:
        return None

    entity_rows = await _framework_entity_rows(framework_id, session)
    if not include_application:
        entity_rows = [r for r in entity_rows if r[0] != MappingTargetType.APPLICATION]
    entity_counts = _bucket_entities_by_status(entity_rows)

    org_statuses = await _framework_organization_rows(framework_id, session)
    organization_status = compute_compliance_status(org_statuses) if org_statuses else None

    return FrameworkCoverageRollup(
        framework_id=framework_id, entity_counts=entity_counts,
        organization_status=organization_status,
    )


async def _estate_entity_rows(session: AsyncSession) -> list[_EntityRow]:
    """Every entity-targeted ControlMapping row across the whole estate, no framework filter at
    all (research.md D3) -- needed for the platform-wide summary's "overall" (cross-framework)
    entity status, unlike _framework_entity_rows above. No join to controls needed since there is
    no framework_id filter to apply."""
    rows: list[_EntityRow] = []

    result = await session.execute(
        sa.select(
            _control_capability_mapping.c.capability_id,
            _control_capability_mapping.c.compliance_status,
        )
    )
    rows += [
        (MappingTargetType.CAPABILITY, r.capability_id, ComplianceStatus(r.compliance_status))
        for r in result
    ]

    result = await session.execute(
        sa.select(
            _control_application_mapping.c.application_id,
            _control_application_mapping.c.compliance_status,
        )
    )
    rows += [
        (MappingTargetType.APPLICATION, r.application_id, ComplianceStatus(r.compliance_status))
        for r in result
    ]

    result = await session.execute(
        sa.select(_control_design_mapping.c.design_id, _control_design_mapping.c.compliance_status)
    )
    rows += [
        (MappingTargetType.DESIGN, r.design_id, ComplianceStatus(r.compliance_status))
        for r in result
    ]

    result = await session.execute(
        sa.select(
            _control_pattern_mapping.c.pattern_id, _control_pattern_mapping.c.compliance_status
        )
    )
    rows += [
        (MappingTargetType.PATTERN, r.pattern_id, ComplianceStatus(r.compliance_status))
        for r in result
    ]

    return rows


async def get_compliance_summary(
    include_application: bool, session: AsyncSession
) -> ComplianceSummaryResponse:
    """US2: platform-wide framework count / overall coverage % / at-risk count, backing the
    Overview dashboard's Compliance domain card. coverage_percent is None (never a bare 0.0) when
    zero entities anywhere have any mapped control (spec.md FR-009)."""
    fw_count_result = await session.execute(sa.select(sa.func.count()).select_from(_frameworks))
    framework_count = fw_count_result.scalar_one()

    entity_rows = await _estate_entity_rows(session)
    if not include_application:
        entity_rows = [r for r in entity_rows if r[0] != MappingTargetType.APPLICATION]
    counts = _bucket_entities_by_status(entity_rows)

    total = (
        counts.compliant_count + counts.partial_count + counts.non_compliant_count
        + counts.not_assessed_count + counts.not_applicable_count
    )
    coverage_percent = None if total == 0 else 100 * counts.compliant_count / total
    at_risk_count = counts.non_compliant_count + counts.partial_count

    return ComplianceSummaryResponse(
        framework_count=framework_count, coverage_percent=coverage_percent,
        at_risk_count=at_risk_count,
    )
