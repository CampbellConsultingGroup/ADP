"""Business Architecture store — async SQLAlchemy CRUD (ADP-SPEC-033/034/035).

Provides capability, value stream, domain, and stage-capability persistence using
the shared KB session factory. All functions accept an AsyncSession and are called
from the router inside `async with session_factory() as session: ...` blocks.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.business.models import (
    BusinessCapability,
    BusinessCapabilityCreate,
    BusinessCapabilityUpdate,
    BusinessContextResponse,
    BusinessDomain,
    BusinessDomainCreate,
    BusinessDomainUpdate,
    CapabilityDomainAssign,
    CapabilityRef,
    DesignRef,
    DomainDetail,
    DomainListResponse,
    DomainSummary,
    DuplicateLinkError,
    DuplicateStageCapError,
    LinkNotFoundError,
    StageCapabilitiesResponse,
    StageCapabilityLinkCreate,
    StageCapabilityRef,
    StageCapNotFoundError,
    StageReorderItem,
    ValueStream,
    ValueStreamCreate,
    ValueStreamDetail,
    ValueStreamRef,
    ValueStreamStage,
    ValueStreamStageCreate,
    ValueStreamStageUpdate,
    ValueStreamUpdate,
)
from adp.search import (
    ENTITY_BUSINESS_CAPABILITY,
    build_text,
    index_entity,
    unindex_entity,
)

# ── Table definitions (SQLAlchemy Core — no ORM mapper needed) ────────────────

_metadata = sa.MetaData()

_capabilities = sa.Table(
    "business_capabilities",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("level", sa.Integer(), nullable=False),
    sa.Column("parent_id", sa.String(36), nullable=True),
    sa.Column("position", sa.Integer(), nullable=False, default=0),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    # ADP-SPEC-035: ON DELETE SET NULL at DB level (migration 009)
    sa.Column("domain_id", sa.String(36), nullable=True),
    # ADP-33v: strategic classification (migration 020)
    sa.Column("strategic_relevance", sa.SmallInteger(), nullable=True),
    # ADP-4ga: CMMI-style maturity assessment (migration 021)
    sa.Column("maturity_level", sa.SmallInteger(), nullable=True),
)

_value_streams = sa.Table(
    "value_streams",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("stakeholder", sa.String(255)),
    sa.Column("position", sa.Integer(), nullable=False, default=0),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_stages = sa.Table(
    "value_stream_stages",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("value_stream_id", sa.String(36), nullable=False),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("position", sa.Integer(), nullable=False, default=0),
)

# ── Traceability link tables (ADP-SPEC-034) ───────────────────────────────────

_cap_design_links = sa.Table(
    "capability_design_links",
    _metadata,
    sa.Column("capability_id", sa.String(36), nullable=False),
    sa.Column("design_id", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_vs_design_links = sa.Table(
    "value_stream_design_links",
    _metadata,
    sa.Column("value_stream_id", sa.String(36), nullable=False),
    sa.Column("design_id", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

# ── Domain and stage-capability tables (ADP-SPEC-035) ────────────────────────

_domains = sa.Table(
    "business_domains",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("scope_statement", sa.Text()),
    sa.Column("classification", sa.Text(), nullable=False),
    sa.Column("org_unit", sa.String(255)),
    sa.Column("risk_flags", sa.ARRAY(sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_stage_caps = sa.Table(
    "value_stream_stage_capabilities",
    _metadata,
    sa.Column("stage_id", sa.String(36), nullable=False),
    sa.Column("capability_id", sa.String(36), nullable=False),
)

# designs table reference for JOIN queries (read-only; managed by DesignStore migration 001)
_designs = sa.Table(
    "designs",
    _metadata,
    sa.Column("id", sa.Text(), primary_key=True),
    sa.Column("title", sa.Text(), nullable=False),
    sa.Column("lifecycle_status", sa.Text(), nullable=False, server_default="draft"),
)

# ── Module-level session factory (set by deps or tests) ───────────────────────

_engine: Any = None
_session_factory: Any = None


def _get_session_factory() -> async_sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        import os
        db_url = os.environ.get("ADP_DATABASE_URL", "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp")
        _engine = create_async_engine(db_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


def get_session() -> AsyncSession:
    return _get_session_factory()()


def _rowcount(result: Any) -> int:
    """DML executes return CursorResult at runtime; session.execute is typed
    as Result[Any], which lacks rowcount."""
    return cast("sa.CursorResult[Any]", result).rowcount


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_capability(row: Any) -> BusinessCapability:
    return BusinessCapability(
        id=row.id,
        name=row.name,
        description=row.description,
        level=row.level,
        parent_id=row.parent_id,
        position=row.position,
        created_at=row.created_at,
        updated_at=row.updated_at,
        domain_id=getattr(row, "domain_id", None),
        domain_name=getattr(row, "domain_name", None),
        strategic_relevance=getattr(row, "strategic_relevance", None),
        maturity_level=getattr(row, "maturity_level", None),
    )


def _cap_with_domain_stmt():
    """SELECT with LEFT JOIN to _domains so domain_name is always available."""
    return sa.select(
        _capabilities,
        _domains.c.name.label("domain_name"),
    ).outerjoin(_domains, _domains.c.id == _capabilities.c.domain_id)


def _row_to_vs(row: Any) -> ValueStream:
    return ValueStream(
        id=row.id,
        name=row.name,
        description=row.description,
        stakeholder=row.stakeholder,
        position=row.position,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_stage(row: Any) -> ValueStreamStage:
    return ValueStreamStage(
        id=row.id,
        value_stream_id=row.value_stream_id,
        name=row.name,
        description=row.description,
        position=row.position,
    )


# ── Capability CRUD ───────────────────────────────────────────────────────────

class ChildCapabilitiesExist(Exception):
    def __init__(self, parent_id: str, count: int) -> None:
        self.parent_id = parent_id
        self.count = count
        super().__init__(f"Capability {parent_id} has {count} child capabilities")


async def list_capabilities(session: AsyncSession) -> list[BusinessCapability]:
    result = await session.execute(
        _cap_with_domain_stmt().order_by(_capabilities.c.level, _capabilities.c.position)
    )
    return [_row_to_capability(row) for row in result.mappings().all()]


async def get_capability(cap_id: str, session: AsyncSession) -> BusinessCapability | None:
    result = await session.execute(
        _cap_with_domain_stmt().where(_capabilities.c.id == cap_id)
    )
    row = result.mappings().first()
    return _row_to_capability(row) if row else None


async def create_capability(
    data: BusinessCapabilityCreate, session: AsyncSession
) -> BusinessCapability:
    # Validate parent level matches expected level
    if data.parent_id:
        parent = await get_capability(data.parent_id, session)
        if parent is None:
            raise ValueError(f"Parent capability {data.parent_id!r} not found")
        if parent.level != data.level - 1:
            raise ValueError(
                f"Parent is level {parent.level} but new capability is level {data.level}; "
                f"parent must be level {data.level - 1}"
            )

    cap_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _capabilities.insert().values(
            id=cap_id,
            name=data.name.strip(),
            description=data.description,
            level=data.level,
            parent_id=data.parent_id,
            position=data.position,
            created_at=now,
            updated_at=now,
            strategic_relevance=data.strategic_relevance,
            maturity_level=data.maturity_level,
        )
    )
    await index_entity(
        ENTITY_BUSINESS_CAPABILITY, cap_id, build_text(data.name, data.description), session
    )
    return BusinessCapability(
        id=cap_id,
        name=data.name.strip(),
        description=data.description,
        level=data.level,
        parent_id=data.parent_id,
        position=data.position,
        created_at=now,
        updated_at=now,
        strategic_relevance=data.strategic_relevance,
        maturity_level=data.maturity_level,
    )


async def update_capability(
    cap_id: str, data: BusinessCapabilityUpdate, session: AsyncSession
) -> BusinessCapability | None:
    existing = await get_capability(cap_id, session)
    if existing is None:
        return None

    updates: dict[str, Any] = {"updated_at": _now()}
    if data.name is not None:
        updates["name"] = data.name.strip()
    if data.position is not None:
        updates["position"] = data.position
    # Nullable fields: an explicitly provided null clears the value;
    # an omitted field is left unchanged (model_fields_set distinguishes them).
    if "description" in data.model_fields_set:
        updates["description"] = data.description
    if "strategic_relevance" in data.model_fields_set:
        updates["strategic_relevance"] = data.strategic_relevance
    if "maturity_level" in data.model_fields_set:
        updates["maturity_level"] = data.maturity_level

    await session.execute(
        _capabilities.update().where(_capabilities.c.id == cap_id).values(**updates)
    )
    refreshed = await get_capability(cap_id, session)
    if refreshed is not None:
        await index_entity(
            ENTITY_BUSINESS_CAPABILITY, cap_id,
            build_text(refreshed.name, refreshed.description), session,
        )
    return refreshed


async def delete_capability(cap_id: str, session: AsyncSession) -> bool:
    """Delete a capability. Raises ChildCapabilitiesExist if it has children."""
    result = await session.execute(
        sa.select(sa.func.count())
        .select_from(_capabilities)
        .where(_capabilities.c.parent_id == cap_id)
    )
    child_count = result.scalar_one()
    if child_count > 0:
        raise ChildCapabilitiesExist(cap_id, child_count)

    result2 = await session.execute(
        _capabilities.delete().where(_capabilities.c.id == cap_id)
    )
    deleted = _rowcount(result2) > 0
    if deleted:
        await unindex_entity(ENTITY_BUSINESS_CAPABILITY, cap_id, session)
    return deleted


# ── Value Stream CRUD ─────────────────────────────────────────────────────────

async def list_value_streams(session: AsyncSession) -> list[ValueStream]:
    result = await session.execute(
        sa.select(_value_streams).order_by(_value_streams.c.position, _value_streams.c.created_at)
    )
    return [_row_to_vs(row) for row in result.mappings().all()]


async def get_value_stream(vs_id: str, session: AsyncSession) -> ValueStreamDetail | None:
    vs_result = await session.execute(
        sa.select(_value_streams).where(_value_streams.c.id == vs_id)
    )
    vs_row = vs_result.mappings().first()
    if vs_row is None:
        return None

    stages_result = await session.execute(
        sa.select(_stages).where(_stages.c.value_stream_id == vs_id).order_by(_stages.c.position)
    )
    stages = [_row_to_stage(row) for row in stages_result.mappings().all()]

    vs = _row_to_vs(vs_row)
    return ValueStreamDetail(**vs.model_dump(), stages=stages)


async def create_value_stream(data: ValueStreamCreate, session: AsyncSession) -> ValueStream:
    vs_id = str(uuid.uuid4())
    now = _now()
    # Position = count of existing streams
    count_result = await session.execute(sa.select(sa.func.count()).select_from(_value_streams))
    position = count_result.scalar_one()

    await session.execute(
        _value_streams.insert().values(
            id=vs_id,
            name=data.name.strip(),
            description=data.description,
            stakeholder=data.stakeholder,
            position=position,
            created_at=now,
            updated_at=now,
        )
    )
    return ValueStream(
        id=vs_id,
        name=data.name.strip(),
        description=data.description,
        stakeholder=data.stakeholder,
        position=position,
        created_at=now,
        updated_at=now,
    )


async def update_value_stream(
    vs_id: str, data: ValueStreamUpdate, session: AsyncSession
) -> ValueStream | None:
    result = await session.execute(sa.select(_value_streams).where(_value_streams.c.id == vs_id))
    if result.mappings().first() is None:
        return None

    updates: dict[str, Any] = {"updated_at": _now()}
    if data.name is not None:
        updates["name"] = data.name.strip()
    # Nullable fields: an explicitly provided null clears the value;
    # an omitted field is left unchanged (model_fields_set distinguishes them).
    if "description" in data.model_fields_set:
        updates["description"] = data.description
    if "stakeholder" in data.model_fields_set:
        updates["stakeholder"] = data.stakeholder

    await session.execute(
        _value_streams.update().where(_value_streams.c.id == vs_id).values(**updates)
    )

    result2 = await session.execute(sa.select(_value_streams).where(_value_streams.c.id == vs_id))
    return _row_to_vs(result2.mappings().first())


async def delete_value_stream(vs_id: str, session: AsyncSession) -> bool:
    # FK CASCADE handles stage deletion
    result = await session.execute(_value_streams.delete().where(_value_streams.c.id == vs_id))
    return _rowcount(result) > 0


# ── Value Stream Stage CRUD ───────────────────────────────────────────────────

async def add_stage(
    vs_id: str, data: ValueStreamStageCreate, session: AsyncSession
) -> ValueStreamStage:
    stage_id = str(uuid.uuid4())
    await session.execute(
        _stages.insert().values(
            id=stage_id,
            value_stream_id=vs_id,
            name=data.name.strip(),
            description=data.description,
            position=data.position,
        )
    )
    return ValueStreamStage(
        id=stage_id,
        value_stream_id=vs_id,
        name=data.name.strip(),
        description=data.description,
        position=data.position,
    )


async def update_stage(
    vs_id: str, stage_id: str, data: ValueStreamStageUpdate, session: AsyncSession
) -> ValueStreamStage | None:
    result = await session.execute(
        sa.select(_stages).where(_stages.c.id == stage_id, _stages.c.value_stream_id == vs_id)
    )
    if result.mappings().first() is None:
        return None

    updates: dict[str, Any] = {}
    if data.name is not None:
        updates["name"] = data.name.strip()
    if data.position is not None:
        updates["position"] = data.position
    # Nullable fields: an explicitly provided null clears the value;
    # an omitted field is left unchanged (model_fields_set distinguishes them).
    if "description" in data.model_fields_set:
        updates["description"] = data.description

    if updates:
        await session.execute(
            _stages.update().where(
                _stages.c.id == stage_id, _stages.c.value_stream_id == vs_id
            ).values(**updates)
        )

    result2 = await session.execute(
        sa.select(_stages).where(_stages.c.id == stage_id, _stages.c.value_stream_id == vs_id)
    )
    row = result2.mappings().first()
    return _row_to_stage(row) if row else None


async def delete_stage(vs_id: str, stage_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _stages.delete().where(_stages.c.id == stage_id, _stages.c.value_stream_id == vs_id)
    )
    return _rowcount(result) > 0


async def reorder_stages(
    vs_id: str, ordered_stages: list[StageReorderItem], session: AsyncSession
) -> list[ValueStreamStage]:
    """Replace the stage list for a value stream atomically.

    Deletes stages not in the list. Updates existing ones with new positions (0..n-1).
    """
    incoming_ids = {s.id for s in ordered_stages}

    # Delete stages not in the new list
    await session.execute(
        _stages.delete().where(
            _stages.c.value_stream_id == vs_id,
            _stages.c.id.not_in(incoming_ids),
        )
    )

    # Upsert each stage with its new position
    result_stages = []
    for position, stage_item in enumerate(ordered_stages):
        existing = await session.execute(
            sa.select(_stages).where(
                _stages.c.id == stage_item.id, _stages.c.value_stream_id == vs_id
            )
        )
        row = existing.mappings().first()
        if row is None:
            raise ValueError(f"Stage {stage_item.id!r} not found in value stream {vs_id!r}")

        await session.execute(
            _stages.update().where(
                _stages.c.id == stage_item.id, _stages.c.value_stream_id == vs_id
            ).values(name=stage_item.name, description=stage_item.description, position=position)
        )
        result_stages.append(
            ValueStreamStage(
                id=stage_item.id,
                value_stream_id=vs_id,
                name=stage_item.name,
                description=stage_item.description,
                position=position,
            )
        )

    return result_stages


# ── Traceability link store functions (ADP-SPEC-034) ─────────────────────────

async def list_capability_designs(capability_id: str, session: AsyncSession) -> list[DesignRef]:
    """Return designs linked to a capability, joined with designs table for metadata."""
    result = await session.execute(
        sa.select(
            _cap_design_links.c.design_id,
            _designs.c.title,
            _designs.c.lifecycle_status,
        ).join(
            _designs, _designs.c.id == _cap_design_links.c.design_id
        ).where(
            _cap_design_links.c.capability_id == capability_id
        ).order_by(_designs.c.title)
    )
    return [
        DesignRef(
            design_id=row.design_id, title=row.title, lifecycle_status=row.lifecycle_status
        )
        for row in result.mappings()
    ]


@dataclass(frozen=True)
class CapabilityStageRef:
    """A value-stream stage linked to a capability (ADP-SPEC-039 context assembly).

    Not a boundary payload (ART-XIII concerns external APIs) -- internal
    context data feeding the Agent Review toolkit, mirroring ReasoningRecord's
    dataclass precedent for non-boundary internal shapes.
    """

    stage_id: str
    stage_name: str
    value_stream_id: str
    value_stream_name: str


async def list_stages_for_capability(
    capability_id: str, session: AsyncSession
) -> list[CapabilityStageRef]:
    """Reverse of list_stage_caps: value-stream stages linked to a capability."""
    result = await session.execute(
        sa.select(
            _stage_caps.c.stage_id,
            _stages.c.name.label("stage_name"),
            _stages.c.value_stream_id,
            _value_streams.c.name.label("value_stream_name"),
        )
        .join(_stages, _stages.c.id == _stage_caps.c.stage_id)
        .join(_value_streams, _value_streams.c.id == _stages.c.value_stream_id)
        .where(_stage_caps.c.capability_id == capability_id)
        .order_by(_stages.c.position)
    )
    return [
        CapabilityStageRef(
            stage_id=row.stage_id,
            stage_name=row.stage_name,
            value_stream_id=row.value_stream_id,
            value_stream_name=row.value_stream_name,
        )
        for row in result.mappings()
    ]


async def link_design_to_capability(
    capability_id: str, design_id: str, session: AsyncSession
) -> None:
    """Link a design to a capability.

    Raises DuplicateLinkError on conflict, ValueError if the design is not found.
    """
    # Verify design exists
    des_row = await session.execute(sa.select(_designs.c.id).where(_designs.c.id == design_id))
    if des_row.first() is None:
        raise ValueError(f"Design {design_id!r} not found")
    try:
        await session.execute(
            _cap_design_links.insert().values(
                capability_id=capability_id,
                design_id=design_id,
                created_at=_now(),
            )
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateLinkError(
                f"Link ({capability_id!r}, {design_id!r}) already exists"
            ) from exc
        raise


async def unlink_design_from_capability(
    capability_id: str, design_id: str, session: AsyncSession
) -> None:
    """Remove a capability–design link. Raises LinkNotFoundError if it does not exist."""
    result = await session.execute(
        _cap_design_links.delete().where(
            _cap_design_links.c.capability_id == capability_id,
            _cap_design_links.c.design_id == design_id,
        )
    )
    if _rowcount(result) == 0:
        raise LinkNotFoundError(f"Link ({capability_id!r}, {design_id!r}) not found")


async def list_value_stream_designs(value_stream_id: str, session: AsyncSession) -> list[DesignRef]:
    """Return designs linked to a value stream."""
    result = await session.execute(
        sa.select(
            _vs_design_links.c.design_id,
            _designs.c.title,
            _designs.c.lifecycle_status,
        ).join(
            _designs, _designs.c.id == _vs_design_links.c.design_id
        ).where(
            _vs_design_links.c.value_stream_id == value_stream_id
        ).order_by(_designs.c.title)
    )
    return [
        DesignRef(
            design_id=row.design_id, title=row.title, lifecycle_status=row.lifecycle_status
        )
        for row in result.mappings()
    ]


async def link_design_to_value_stream(
    value_stream_id: str, design_id: str, session: AsyncSession
) -> None:
    """Link a design to a value stream.

    Raises DuplicateLinkError on conflict, ValueError if the design is not found.
    """
    des_row = await session.execute(sa.select(_designs.c.id).where(_designs.c.id == design_id))
    if des_row.first() is None:
        raise ValueError(f"Design {design_id!r} not found")
    try:
        await session.execute(
            _vs_design_links.insert().values(
                value_stream_id=value_stream_id,
                design_id=design_id,
                created_at=_now(),
            )
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateLinkError(
                f"Link ({value_stream_id!r}, {design_id!r}) already exists"
            ) from exc
        raise


async def unlink_design_from_value_stream(
    value_stream_id: str, design_id: str, session: AsyncSession
) -> None:
    """Remove a value-stream–design link. Raises LinkNotFoundError if it does not exist."""
    result = await session.execute(
        _vs_design_links.delete().where(
            _vs_design_links.c.value_stream_id == value_stream_id,
            _vs_design_links.c.design_id == design_id,
        )
    )
    if _rowcount(result) == 0:
        raise LinkNotFoundError(f"Link ({value_stream_id!r}, {design_id!r}) not found")


async def get_design_business_context(
    design_id: str, session: AsyncSession
) -> BusinessContextResponse:
    """Return all capabilities and value streams linked to a design (reverse lookup).

    Raises ValueError if the design does not exist.
    """
    des_row = await session.execute(sa.select(_designs.c.id).where(_designs.c.id == design_id))
    if des_row.first() is None:
        raise ValueError(f"Design {design_id!r} not found")

    cap_result = await session.execute(
        sa.select(
            _cap_design_links.c.capability_id,
            _capabilities.c.name,
            _capabilities.c.level,
        ).join(
            _capabilities, _capabilities.c.id == _cap_design_links.c.capability_id
        ).where(
            _cap_design_links.c.design_id == design_id
        ).order_by(_capabilities.c.name)
    )
    capabilities = [
        CapabilityRef(capability_id=row.capability_id, name=row.name, level=row.level)
        for row in cap_result.mappings()
    ]

    vs_result = await session.execute(
        sa.select(
            _vs_design_links.c.value_stream_id,
            _value_streams.c.name,
            _value_streams.c.stakeholder,
        ).join(
            _value_streams, _value_streams.c.id == _vs_design_links.c.value_stream_id
        ).where(
            _vs_design_links.c.design_id == design_id
        ).order_by(_value_streams.c.name)
    )
    value_streams = [
        ValueStreamRef(
            value_stream_id=row.value_stream_id, name=row.name, stakeholder=row.stakeholder
        )
        for row in vs_result.mappings()
    ]

    return BusinessContextResponse(
        design_id=design_id,
        capabilities=capabilities,
        value_streams=value_streams,
    )


# ── Domain CRUD (ADP-SPEC-035) ────────────────────────────────────────────────

def _row_to_domain(row: Any) -> BusinessDomain:
    return BusinessDomain(
        id=row.id,
        name=row.name,
        scope_statement=row.scope_statement,
        classification=row.classification,
        org_unit=row.org_unit,
        risk_flags=list(row.risk_flags or []),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_domains(session: AsyncSession) -> DomainListResponse:
    cap_count_subq = (
        sa.select(sa.func.count())
        .select_from(_capabilities)
        .where(_capabilities.c.domain_id == _domains.c.id)
        .correlate(_domains)
        .scalar_subquery()
    )
    result = await session.execute(
        sa.select(
            _domains,
            cap_count_subq.label("capability_count"),
        ).order_by(_domains.c.name)
    )
    items = [
        DomainSummary(
            id=row.id,
            name=row.name,
            classification=row.classification,
            org_unit=row.org_unit,
            risk_flags=list(row.risk_flags or []),
            capability_count=row.capability_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in result.mappings().all()
    ]
    return DomainListResponse(items=items, total=len(items))


async def get_domain(domain_id: str, session: AsyncSession) -> DomainDetail | None:
    result = await session.execute(
        sa.select(_domains).where(_domains.c.id == domain_id)
    )
    row = result.mappings().first()
    if row is None:
        return None

    caps_result = await session.execute(
        sa.select(
            _capabilities.c.id.label("capability_id"),
            _capabilities.c.name,
            _capabilities.c.level,
        ).where(
            _capabilities.c.domain_id == domain_id,
            _capabilities.c.level == 1,
        ).order_by(_capabilities.c.name)
    )
    capabilities = [
        CapabilityRef(capability_id=r.capability_id, name=r.name, level=r.level)
        for r in caps_result.mappings().all()
    ]

    return DomainDetail(
        **_row_to_domain(row).model_dump(),
        capabilities=capabilities,
    )


async def create_domain(data: BusinessDomainCreate, session: AsyncSession) -> BusinessDomain:
    domain_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _domains.insert().values(
            id=domain_id,
            name=data.name.strip(),
            scope_statement=data.scope_statement,
            classification=data.classification,
            org_unit=data.org_unit,
            risk_flags=data.risk_flags,
            created_at=now,
            updated_at=now,
        )
    )
    return BusinessDomain(
        id=domain_id,
        name=data.name.strip(),
        scope_statement=data.scope_statement,
        classification=data.classification,
        org_unit=data.org_unit,
        risk_flags=data.risk_flags,
        created_at=now,
        updated_at=now,
    )


async def update_domain(
    domain_id: str, data: BusinessDomainUpdate, session: AsyncSession
) -> BusinessDomain | None:
    result = await session.execute(
        sa.select(_domains).where(_domains.c.id == domain_id)
    )
    if result.mappings().first() is None:
        return None

    updates: dict[str, Any] = {"updated_at": _now()}
    if data.name is not None:
        updates["name"] = data.name.strip()
    if data.classification is not None:
        updates["classification"] = data.classification
    # Nullable fields: an explicitly provided null clears the value;
    # an omitted field is left unchanged (model_fields_set distinguishes them).
    if "scope_statement" in data.model_fields_set:
        updates["scope_statement"] = data.scope_statement
    if "org_unit" in data.model_fields_set:
        updates["org_unit"] = data.org_unit
    if data.risk_flags is not None:
        updates["risk_flags"] = data.risk_flags

    await session.execute(
        _domains.update().where(_domains.c.id == domain_id).values(**updates)
    )
    result2 = await session.execute(
        sa.select(_domains).where(_domains.c.id == domain_id)
    )
    return _row_to_domain(result2.mappings().first())


async def delete_domain(domain_id: str, session: AsyncSession) -> bool:
    """Delete a domain. DB ON DELETE SET NULL clears capability.domain_id references."""
    result = await session.execute(
        _domains.delete().where(_domains.c.id == domain_id)
    )
    return _rowcount(result) > 0


# ── Capability-Domain Assignment (ADP-SPEC-035 US2) ──────────────────────────

async def assign_capability_domain(
    cap_id: str, body: CapabilityDomainAssign, session: AsyncSession
) -> BusinessCapability | None:
    """Assign or clear a capability's domain. Enforces L1-only rule."""
    cap = await get_capability(cap_id, session)
    if cap is None:
        return None

    if body.domain_id is not None:
        if cap.level != 1:
            raise ValueError("Only level-1 capabilities can be assigned to a domain")
        # Verify domain exists
        dom_row = await session.execute(
            sa.select(_domains.c.id).where(_domains.c.id == body.domain_id)
        )
        if dom_row.first() is None:
            raise LookupError(f"Domain {body.domain_id!r} not found")

    await session.execute(
        _capabilities.update().where(_capabilities.c.id == cap_id).values(
            domain_id=body.domain_id,
            updated_at=_now(),
        )
    )
    return await get_capability(cap_id, session)


# ── Stage-Capability Mapping (ADP-SPEC-035 US3) ───────────────────────────────

async def list_stage_caps(
    vs_id: str, stage_id: str, session: AsyncSession
) -> StageCapabilitiesResponse | None:
    """Return capabilities linked to a stage. Returns None if stage not found."""
    stage_row = await session.execute(
        sa.select(_stages.c.id).where(
            _stages.c.id == stage_id, _stages.c.value_stream_id == vs_id
        )
    )
    if stage_row.first() is None:
        return None

    result = await session.execute(
        sa.select(
            _stage_caps.c.capability_id,
            _capabilities.c.name,
            _capabilities.c.level,
            _capabilities.c.domain_id,
            _domains.c.name.label("domain_name"),
        )
        .join(_capabilities, _capabilities.c.id == _stage_caps.c.capability_id)
        .outerjoin(_domains, _domains.c.id == _capabilities.c.domain_id)
        .where(_stage_caps.c.stage_id == stage_id)
        .order_by(_capabilities.c.name)
    )
    items = [
        StageCapabilityRef(
            capability_id=row.capability_id,
            name=row.name,
            level=row.level,
            domain_id=row.domain_id,
            domain_name=row.domain_name,
        )
        for row in result.mappings().all()
    ]
    return StageCapabilitiesResponse(items=items)


async def link_cap_to_stage(
    vs_id: str, stage_id: str, data: StageCapabilityLinkCreate, session: AsyncSession
) -> StageCapabilitiesResponse:
    """Link a capability to a stage. Raises DuplicateStageCapError on conflict."""
    stage_row = await session.execute(
        sa.select(_stages.c.id).where(
            _stages.c.id == stage_id, _stages.c.value_stream_id == vs_id
        )
    )
    if stage_row.first() is None:
        raise LookupError(f"Stage {stage_id!r} not found in value stream {vs_id!r}")

    cap_row = await session.execute(
        sa.select(_capabilities.c.id).where(_capabilities.c.id == data.capability_id)
    )
    if cap_row.first() is None:
        raise LookupError(f"Capability {data.capability_id!r} not found")

    try:
        await session.execute(
            _stage_caps.insert().values(stage_id=stage_id, capability_id=data.capability_id)
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateStageCapError(
                f"Link ({stage_id!r}, {data.capability_id!r}) already exists"
            ) from exc
        raise

    result = await list_stage_caps(vs_id, stage_id, session)
    assert result is not None
    return result


async def unlink_cap_from_stage(
    vs_id: str, stage_id: str, cap_id: str, session: AsyncSession
) -> None:
    """Remove a stage-capability link. Raises StageCapNotFoundError if not found."""
    stage_row = await session.execute(
        sa.select(_stages.c.id).where(
            _stages.c.id == stage_id, _stages.c.value_stream_id == vs_id
        )
    )
    if stage_row.first() is None:
        raise LookupError(f"Stage {stage_id!r} not found in value stream {vs_id!r}")

    result = await session.execute(
        _stage_caps.delete().where(
            _stage_caps.c.stage_id == stage_id,
            _stage_caps.c.capability_id == cap_id,
        )
    )
    if _rowcount(result) == 0:
        raise StageCapNotFoundError(f"Link ({stage_id!r}, {cap_id!r}) not found")
