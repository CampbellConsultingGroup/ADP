"""Application Registry store — async SQLAlchemy Core CRUD (ADP-SPEC-036).

All functions accept an AsyncSession and are called from the router inside
`async with session_factory() as session: ...` blocks.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.application.models import (
    Application,
    ApplicationCapabilityLink,
    ApplicationCapabilityLinkCreate,
    ApplicationCapabilityLinksResponse,
    ApplicationCapabilityLinkUpdate,
    ApplicationCreate,
    ApplicationDesignLink,
    ApplicationDesignLinkCreate,
    ApplicationDesignLinksResponse,
    ApplicationDomainIntegration,
    ApplicationDomainIntegrationCreate,
    ApplicationDomainIntegrationsResponse,
    ApplicationIntegration,
    ApplicationIntegrationCreate,
    ApplicationIntegrationListResponse,
    ApplicationIntegrationUpdate,
    ApplicationListResponse,
    ApplicationStageLink,
    ApplicationStageLinkCreate,
    ApplicationStageLinksResponse,
    ApplicationTechCapLink,
    ApplicationTechCapLinkCreate,
    ApplicationTechCapLinksResponse,
    ApplicationUpdate,
    DuplicateAppCapLinkError,
    DuplicateAppDesignLinkError,
    DuplicateAppStageLinkError,
    DuplicateAppTechCapLinkError,
    TechCapDepthError,
    TechCapHasChildrenError,
    TechCapListResponse,
    TechnicalCapability,
    TechnicalCapabilityCreate,
    TechnicalCapabilityUpdate,
)
from adp.search import (
    ENTITY_TECHNICAL_CAPABILITY,
    build_text,
    index_entity,
    unindex_entity,
)

# ── Table definitions (SQLAlchemy Core — no ORM mapper) ──────────────────────

_metadata = sa.MetaData()

_applications = sa.Table(
    "applications",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("vendor", sa.String(255)),
    sa.Column("primary_owner", sa.String(255)),
    sa.Column("time_classification", sa.Text()),
    sa.Column("r_strategy", sa.Text()),
    sa.Column("pace_layer", sa.Text()),
    sa.Column("health_score", sa.Integer()),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_tech_caps = sa.Table(
    "technical_capabilities",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("parent_id", sa.String(36)),
    sa.Column("level", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_app_cap_links = sa.Table(
    "application_capability_links",
    _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("capability_id", sa.String(36), nullable=False),
    sa.Column("fit_score", sa.Integer(), nullable=False),
)

# business_capabilities reference for JOIN queries
_biz_caps = sa.Table(
    "business_capabilities",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
)

_app_tech_cap_links = sa.Table(
    "application_tech_cap_links",
    _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("tech_cap_id", sa.String(36), nullable=False),
    sa.Column("usage_type", sa.Text(), nullable=False),
)

_app_stage_links = sa.Table(
    "application_stage_links",
    _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("stage_id", sa.String(36), nullable=False),
)

# value_stream_stages reference for JOIN queries
_stages = sa.Table(
    "value_stream_stages",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
)

_app_domain_integrations = sa.Table(
    "application_domain_integrations",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("domain_id", sa.String(36)),
    sa.Column("integration_type", sa.String(255), nullable=False),
    sa.Column("direction", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

# business_domains reference for JOIN queries
_domains = sa.Table(
    "business_domains",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
)

_app_integrations = sa.Table(
    "application_integrations",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("source_app_id", sa.String(36), nullable=False),
    sa.Column("target_app_id", sa.String(36), nullable=False),
    sa.Column("integration_type", sa.Text(), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_app_design_links = sa.Table(
    "application_design_links",
    _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("design_id", sa.String(36), nullable=False),
)

# designs reference for existence checks (ADP-SPEC-002)
_designs = sa.Table(
    "designs",
    _metadata,
    sa.Column("id", sa.Text(), primary_key=True),
)

# ── Session factory ───────────────────────────────────────────────────────────

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


def _row_to_application(row: Any) -> Application:
    return Application(
        id=row.id,
        name=row.name,
        description=row.description,
        vendor=row.vendor,
        primary_owner=row.primary_owner,
        time_classification=row.time_classification,
        r_strategy=row.r_strategy,
        pace_layer=row.pace_layer,
        health_score=row.health_score,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_tech_cap(row: Any) -> TechnicalCapability:
    return TechnicalCapability(
        id=row.id,
        name=row.name,
        description=row.description,
        parent_id=row.parent_id,
        level=row.level,
        created_at=row.created_at,
    )


def _is_duplicate_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "unique" in msg or "duplicate" in msg or "23505" in msg


# ── Application CRUD (US1) ────────────────────────────────────────────────────


async def list_applications(session: AsyncSession) -> ApplicationListResponse:
    result = await session.execute(
        sa.select(_applications).order_by(_applications.c.name)
    )
    items = [_row_to_application(row) for row in result.mappings().all()]
    return ApplicationListResponse(items=items, total=len(items))


async def get_application(app_id: str, session: AsyncSession) -> Application | None:
    result = await session.execute(
        sa.select(_applications).where(_applications.c.id == app_id)
    )
    row = result.mappings().first()
    return _row_to_application(row) if row else None


async def create_application(body: ApplicationCreate, session: AsyncSession) -> Application:
    app_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _applications.insert().values(
            id=app_id,
            name=body.name.strip(),
            description=body.description,
            vendor=body.vendor,
            primary_owner=body.primary_owner,
            time_classification=body.time_classification,
            r_strategy=body.r_strategy,
            pace_layer=body.pace_layer,
            health_score=body.health_score,
            created_at=now,
            updated_at=now,
        )
    )
    app = Application(
        id=app_id,
        name=body.name.strip(),
        description=body.description,
        vendor=body.vendor,
        primary_owner=body.primary_owner,
        time_classification=body.time_classification,
        r_strategy=body.r_strategy,
        pace_layer=body.pace_layer,
        health_score=body.health_score,
        created_at=now,
        updated_at=now,
    )
    return app


async def update_application(
    app_id: str, body: ApplicationUpdate, session: AsyncSession
) -> Application | None:
    existing = await get_application(app_id, session)
    if existing is None:
        return None

    updates: dict[str, Any] = {"updated_at": _now()}
    if body.name is not None:
        updates["name"] = body.name.strip()
    # Nullable fields: an explicitly provided null clears the value;
    # an omitted field is left unchanged (model_fields_set distinguishes them).
    for field in (
        "description", "vendor", "primary_owner", "time_classification",
        "r_strategy", "pace_layer", "health_score",
    ):
        if field in body.model_fields_set:
            updates[field] = getattr(body, field)

    await session.execute(
        _applications.update().where(_applications.c.id == app_id).values(**updates)
    )
    return await get_application(app_id, session)


async def delete_application(app_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _applications.delete().where(_applications.c.id == app_id)
    )
    return _rowcount(result) > 0


# ── Technical Capability CRUD (US3) ──────────────────────────────────────────

async def list_technical_capabilities(session: AsyncSession) -> TechCapListResponse:
    result = await session.execute(
        sa.select(_tech_caps).order_by(_tech_caps.c.level, _tech_caps.c.name)
    )
    items = [_row_to_tech_cap(row) for row in result.mappings().all()]
    return TechCapListResponse(items=items, total=len(items))


async def get_technical_capability(tc_id: str, session: AsyncSession) -> TechnicalCapability | None:
    result = await session.execute(
        sa.select(_tech_caps).where(_tech_caps.c.id == tc_id)
    )
    row = result.mappings().first()
    return _row_to_tech_cap(row) if row else None


async def create_technical_capability(
    body: TechnicalCapabilityCreate, session: AsyncSession
) -> TechnicalCapability:
    level = 1
    if body.parent_id is not None:
        parent = await get_technical_capability(body.parent_id, session)
        if parent is None:
            raise ValueError(f"Parent technical capability {body.parent_id!r} not found")
        if parent.level >= 3:
            raise TechCapDepthError(
                f"Parent is level {parent.level}; maximum depth is 3"
            )
        level = parent.level + 1

    tc_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _tech_caps.insert().values(
            id=tc_id,
            name=body.name.strip(),
            description=body.description,
            parent_id=body.parent_id,
            level=level,
            created_at=now,
        )
    )
    tc = TechnicalCapability(
        id=tc_id,
        name=body.name.strip(),
        description=body.description,
        parent_id=body.parent_id,
        level=level,
        created_at=now,
    )
    await index_entity(
        ENTITY_TECHNICAL_CAPABILITY, tc_id, build_text(body.name, body.description), session
    )
    return tc


async def update_technical_capability(
    tc_id: str, body: TechnicalCapabilityUpdate, session: AsyncSession
) -> TechnicalCapability | None:
    existing = await get_technical_capability(tc_id, session)
    if existing is None:
        return None

    updates: dict[str, Any] = {}
    if body.name is not None:
        updates["name"] = body.name.strip()
    # Nullable fields: an explicitly provided null clears the value;
    # an omitted field is left unchanged (model_fields_set distinguishes them).
    if "description" in body.model_fields_set:
        updates["description"] = body.description

    if updates:
        await session.execute(
            _tech_caps.update().where(_tech_caps.c.id == tc_id).values(**updates)
        )
    refreshed = await get_technical_capability(tc_id, session)
    if refreshed is not None:
        await index_entity(
            ENTITY_TECHNICAL_CAPABILITY, tc_id,
            build_text(refreshed.name, refreshed.description), session,
        )
    return refreshed


async def delete_technical_capability(tc_id: str, session: AsyncSession) -> bool:
    child_count_result = await session.execute(
        sa.select(sa.func.count()).select_from(_tech_caps).where(_tech_caps.c.parent_id == tc_id)
    )
    child_count = child_count_result.scalar_one()
    if child_count > 0:
        raise TechCapHasChildrenError(
            f"Technical capability {tc_id!r} has {child_count} child capability(ies). "
            "Delete children first."
        )

    result = await session.execute(
        _tech_caps.delete().where(_tech_caps.c.id == tc_id)
    )
    deleted = _rowcount(result) > 0
    if deleted:
        await unindex_entity(ENTITY_TECHNICAL_CAPABILITY, tc_id, session)
    return deleted


# ── Application–Business Capability Links (US2) ───────────────────────────────

async def list_app_capability_links(
    app_id: str, session: AsyncSession
) -> ApplicationCapabilityLinksResponse:
    result = await session.execute(
        sa.select(
            _app_cap_links.c.app_id,
            _app_cap_links.c.capability_id,
            _biz_caps.c.name.label("capability_name"),
            _app_cap_links.c.fit_score,
        )
        .join(_biz_caps, _biz_caps.c.id == _app_cap_links.c.capability_id)
        .where(_app_cap_links.c.app_id == app_id)
        .order_by(_biz_caps.c.name)
    )
    items = [
        ApplicationCapabilityLink(
            app_id=row.app_id,
            capability_id=row.capability_id,
            capability_name=row.capability_name,
            fit_score=row.fit_score,
        )
        for row in result.mappings().all()
    ]
    return ApplicationCapabilityLinksResponse(items=items)


async def create_app_capability_link(
    app_id: str, body: ApplicationCapabilityLinkCreate, session: AsyncSession
) -> ApplicationCapabilityLink:
    # Verify application exists
    app = await get_application(app_id, session)
    if app is None:
        raise ValueError(f"Application {app_id!r} not found")

    # Verify business capability exists
    cap_row = await session.execute(
        sa.select(_biz_caps.c.id, _biz_caps.c.name).where(_biz_caps.c.id == body.capability_id)
    )
    cap = cap_row.mappings().first()
    if cap is None:
        raise LookupError(f"Business capability {body.capability_id!r} not found")

    try:
        await session.execute(
            _app_cap_links.insert().values(
                app_id=app_id,
                capability_id=body.capability_id,
                fit_score=body.fit_score,
            )
        )
    except Exception as exc:
        if _is_duplicate_error(exc):
            raise DuplicateAppCapLinkError(
                f"Link ({app_id!r}, {body.capability_id!r}) already exists"
            ) from exc
        raise

    return ApplicationCapabilityLink(
        app_id=app_id,
        capability_id=body.capability_id,
        capability_name=cap.name,
        fit_score=body.fit_score,
    )


async def update_app_capability_link(
    app_id: str, cap_id: str, body: ApplicationCapabilityLinkUpdate, session: AsyncSession
) -> ApplicationCapabilityLink | None:
    existing = await session.execute(
        sa.select(_app_cap_links).where(
            _app_cap_links.c.app_id == app_id,
            _app_cap_links.c.capability_id == cap_id,
        )
    )
    if existing.mappings().first() is None:
        return None

    await session.execute(
        _app_cap_links.update()
        .where(_app_cap_links.c.app_id == app_id, _app_cap_links.c.capability_id == cap_id)
        .values(fit_score=body.fit_score)
    )
    links = await list_app_capability_links(app_id, session)
    for link in links.items:
        if link.capability_id == cap_id:
            return link
    return None


async def delete_app_capability_link(app_id: str, cap_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _app_cap_links.delete().where(
            _app_cap_links.c.app_id == app_id,
            _app_cap_links.c.capability_id == cap_id,
        )
    )
    return _rowcount(result) > 0


# ── Application–Technical Capability Links (US4) ──────────────────────────────

async def list_app_tech_cap_links(
    app_id: str, session: AsyncSession
) -> ApplicationTechCapLinksResponse:
    result = await session.execute(
        sa.select(
            _app_tech_cap_links.c.app_id,
            _app_tech_cap_links.c.tech_cap_id,
            _tech_caps.c.name.label("tech_cap_name"),
            _app_tech_cap_links.c.usage_type,
        )
        .join(_tech_caps, _tech_caps.c.id == _app_tech_cap_links.c.tech_cap_id)
        .where(_app_tech_cap_links.c.app_id == app_id)
        .order_by(_tech_caps.c.name, _app_tech_cap_links.c.usage_type)
    )
    items = [
        ApplicationTechCapLink(
            app_id=row.app_id,
            tech_cap_id=row.tech_cap_id,
            tech_cap_name=row.tech_cap_name,
            usage_type=row.usage_type,
        )
        for row in result.mappings().all()
    ]
    return ApplicationTechCapLinksResponse(items=items)


async def create_app_tech_cap_link(
    app_id: str, body: ApplicationTechCapLinkCreate, session: AsyncSession
) -> ApplicationTechCapLink:
    app = await get_application(app_id, session)
    if app is None:
        raise ValueError(f"Application {app_id!r} not found")

    tc = await get_technical_capability(body.tech_cap_id, session)
    if tc is None:
        raise LookupError(f"Technical capability {body.tech_cap_id!r} not found")

    try:
        await session.execute(
            _app_tech_cap_links.insert().values(
                app_id=app_id,
                tech_cap_id=body.tech_cap_id,
                usage_type=body.usage_type,
            )
        )
    except Exception as exc:
        if _is_duplicate_error(exc):
            raise DuplicateAppTechCapLinkError(
                f"Link ({app_id!r}, {body.tech_cap_id!r}, {body.usage_type!r}) already exists"
            ) from exc
        raise

    return ApplicationTechCapLink(
        app_id=app_id,
        tech_cap_id=body.tech_cap_id,
        tech_cap_name=tc.name,
        usage_type=body.usage_type,
    )


async def delete_app_tech_cap_link(
    app_id: str, tc_id: str, usage_type: str, session: AsyncSession
) -> bool:
    result = await session.execute(
        _app_tech_cap_links.delete().where(
            _app_tech_cap_links.c.app_id == app_id,
            _app_tech_cap_links.c.tech_cap_id == tc_id,
            _app_tech_cap_links.c.usage_type == usage_type,
        )
    )
    return _rowcount(result) > 0


# ── Application–Value Stream Stage Links (US5) ────────────────────────────────

async def list_app_stage_links(
    app_id: str, session: AsyncSession
) -> ApplicationStageLinksResponse:
    result = await session.execute(
        sa.select(
            _app_stage_links.c.app_id,
            _app_stage_links.c.stage_id,
            _stages.c.name.label("stage_name"),
        )
        .join(_stages, _stages.c.id == _app_stage_links.c.stage_id)
        .where(_app_stage_links.c.app_id == app_id)
        .order_by(_stages.c.name)
    )
    items = [
        ApplicationStageLink(
            app_id=row.app_id,
            stage_id=row.stage_id,
            stage_name=row.stage_name,
        )
        for row in result.mappings().all()
    ]
    return ApplicationStageLinksResponse(items=items)


async def create_app_stage_link(
    app_id: str, body: ApplicationStageLinkCreate, session: AsyncSession
) -> ApplicationStageLink:
    app = await get_application(app_id, session)
    if app is None:
        raise ValueError(f"Application {app_id!r} not found")

    stage_row = await session.execute(
        sa.select(_stages.c.id, _stages.c.name).where(_stages.c.id == body.stage_id)
    )
    stage = stage_row.mappings().first()
    if stage is None:
        raise LookupError(f"Value stream stage {body.stage_id!r} not found")

    try:
        await session.execute(
            _app_stage_links.insert().values(app_id=app_id, stage_id=body.stage_id)
        )
    except Exception as exc:
        if _is_duplicate_error(exc):
            raise DuplicateAppStageLinkError(
                f"Link ({app_id!r}, {body.stage_id!r}) already exists"
            ) from exc
        raise

    return ApplicationStageLink(
        app_id=app_id,
        stage_id=body.stage_id,
        stage_name=stage.name,
    )


async def delete_app_stage_link(app_id: str, stage_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _app_stage_links.delete().where(
            _app_stage_links.c.app_id == app_id,
            _app_stage_links.c.stage_id == stage_id,
        )
    )
    return _rowcount(result) > 0


# ── Application–Domain Integrations (US5) ─────────────────────────────────────

async def list_app_domain_integrations(
    app_id: str, session: AsyncSession
) -> ApplicationDomainIntegrationsResponse:
    result = await session.execute(
        sa.select(
            _app_domain_integrations,
            _domains.c.name.label("domain_name"),
        )
        .outerjoin(_domains, _domains.c.id == _app_domain_integrations.c.domain_id)
        .where(_app_domain_integrations.c.app_id == app_id)
        .order_by(_app_domain_integrations.c.created_at)
    )
    items = [
        ApplicationDomainIntegration(
            id=row.id,
            app_id=row.app_id,
            domain_id=row.domain_id,
            domain_name=row.domain_name,
            integration_type=row.integration_type,
            direction=row.direction,
            created_at=row.created_at,
        )
        for row in result.mappings().all()
    ]
    return ApplicationDomainIntegrationsResponse(items=items)


async def create_app_domain_integration(
    app_id: str, body: ApplicationDomainIntegrationCreate, session: AsyncSession
) -> ApplicationDomainIntegration:
    app = await get_application(app_id, session)
    if app is None:
        raise ValueError(f"Application {app_id!r} not found")

    domain_name: str | None = None
    if body.domain_id is not None:
        dom_row = await session.execute(
            sa.select(_domains.c.id, _domains.c.name).where(_domains.c.id == body.domain_id)
        )
        dom = dom_row.mappings().first()
        if dom is None:
            raise LookupError(f"Business domain {body.domain_id!r} not found")
        domain_name = dom.name

    link_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _app_domain_integrations.insert().values(
            id=link_id,
            app_id=app_id,
            domain_id=body.domain_id,
            integration_type=body.integration_type.strip(),
            direction=body.direction,
            created_at=now,
        )
    )
    return ApplicationDomainIntegration(
        id=link_id,
        app_id=app_id,
        domain_id=body.domain_id,
        domain_name=domain_name,
        integration_type=body.integration_type.strip(),
        direction=body.direction,
        created_at=now,
    )


async def delete_app_domain_integration(app_id: str, link_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _app_domain_integrations.delete().where(
            _app_domain_integrations.c.id == link_id,
            _app_domain_integrations.c.app_id == app_id,
        )
    )
    return _rowcount(result) > 0


# ── Application Integrations (US6) ────────────────────────────────────────────

_src_apps = _applications.alias("src_apps")
_tgt_apps = _applications.alias("tgt_apps")


def _row_to_integration(row: Any) -> ApplicationIntegration:
    return ApplicationIntegration(
        id=row.id,
        source_app_id=row.source_app_id,
        source_app_name=row.source_app_name,
        target_app_id=row.target_app_id,
        target_app_name=row.target_app_name,
        integration_type=row.integration_type,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _integration_select():
    return (
        sa.select(
            _app_integrations,
            _src_apps.c.name.label("source_app_name"),
            _tgt_apps.c.name.label("target_app_name"),
        )
        .join(_src_apps, _src_apps.c.id == _app_integrations.c.source_app_id)
        .join(_tgt_apps, _tgt_apps.c.id == _app_integrations.c.target_app_id)
    )


async def list_integrations(
    app_id: str | None, session: AsyncSession
) -> ApplicationIntegrationListResponse:
    stmt = _integration_select()
    if app_id is not None:
        stmt = stmt.where(
            sa.or_(
                _app_integrations.c.source_app_id == app_id,
                _app_integrations.c.target_app_id == app_id,
            )
        )
    stmt = stmt.order_by(_app_integrations.c.created_at)
    result = await session.execute(stmt)
    items = [_row_to_integration(row) for row in result.mappings().all()]
    return ApplicationIntegrationListResponse(items=items, total=len(items))


async def get_integration(int_id: str, session: AsyncSession) -> ApplicationIntegration | None:
    result = await session.execute(
        _integration_select().where(_app_integrations.c.id == int_id)
    )
    row = result.mappings().first()
    return _row_to_integration(row) if row else None


async def create_integration(
    body: ApplicationIntegrationCreate, session: AsyncSession
) -> ApplicationIntegration:
    src = await get_application(body.source_app_id, session)
    if src is None:
        raise LookupError(f"Source application {body.source_app_id!r} not found")

    tgt = await get_application(body.target_app_id, session)
    if tgt is None:
        raise LookupError(f"Target application {body.target_app_id!r} not found")

    int_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _app_integrations.insert().values(
            id=int_id,
            source_app_id=body.source_app_id,
            target_app_id=body.target_app_id,
            integration_type=body.integration_type,
            description=body.description,
            created_at=now,
            updated_at=now,
        )
    )
    return ApplicationIntegration(
        id=int_id,
        source_app_id=body.source_app_id,
        source_app_name=src.name,
        target_app_id=body.target_app_id,
        target_app_name=tgt.name,
        integration_type=body.integration_type,
        description=body.description,
        created_at=now,
        updated_at=now,
    )


async def update_integration(
    int_id: str, body: ApplicationIntegrationUpdate, session: AsyncSession
) -> ApplicationIntegration | None:
    existing = await get_integration(int_id, session)
    if existing is None:
        return None

    updates: dict[str, Any] = {"updated_at": _now()}
    # Nullable fields: an explicitly provided null clears the value;
    # an omitted field is left unchanged (model_fields_set distinguishes them).
    if "description" in body.model_fields_set:
        updates["description"] = body.description

    await session.execute(
        _app_integrations.update().where(_app_integrations.c.id == int_id).values(**updates)
    )
    return await get_integration(int_id, session)


async def delete_integration(int_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _app_integrations.delete().where(_app_integrations.c.id == int_id)
    )
    return _rowcount(result) > 0


# ── Application–Design Links (US7) ────────────────────────────────────────────

async def list_app_design_links(
    app_id: str, session: AsyncSession
) -> ApplicationDesignLinksResponse:
    result = await session.execute(
        sa.select(_app_design_links).where(_app_design_links.c.app_id == app_id)
    )
    items = [
        ApplicationDesignLink(app_id=row.app_id, design_id=row.design_id)
        for row in result.mappings().all()
    ]
    return ApplicationDesignLinksResponse(items=items)


async def create_app_design_link(
    app_id: str, body: ApplicationDesignLinkCreate, session: AsyncSession
) -> ApplicationDesignLink:
    app = await get_application(app_id, session)
    if app is None:
        raise ValueError(f"Application {app_id!r} not found")

    design_row = await session.execute(
        sa.select(_designs.c.id).where(_designs.c.id == body.design_id)
    )
    if design_row.first() is None:
        raise LookupError(f"Design {body.design_id!r} not found")

    try:
        await session.execute(
            _app_design_links.insert().values(app_id=app_id, design_id=body.design_id)
        )
    except Exception as exc:
        if _is_duplicate_error(exc):
            raise DuplicateAppDesignLinkError(
                f"Link ({app_id!r}, {body.design_id!r}) already exists"
            ) from exc
        raise

    return ApplicationDesignLink(app_id=app_id, design_id=body.design_id)


async def delete_app_design_link(app_id: str, design_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _app_design_links.delete().where(
            _app_design_links.c.app_id == app_id,
            _app_design_links.c.design_id == design_id,
        )
    )
    return _rowcount(result) > 0
