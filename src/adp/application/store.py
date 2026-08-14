"""Application Registry store — async SQLAlchemy Core CRUD (ADP-SPEC-036).

All functions accept an AsyncSession and are called from the router inside
`async with session_factory() as session: ...` blocks.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.application.models import (
    TCO_BUCKET_NAMES,
    Application,
    ApplicationCapabilityLink,
    ApplicationCapabilityLinkCreate,
    ApplicationCapabilityLinksResponse,
    ApplicationCapabilityLinkUpdate,
    ApplicationCost,
    ApplicationCostUpdate,
    ApplicationCreate,
    ApplicationDesignLink,
    ApplicationDesignLinkCreate,
    ApplicationDesignLinksResponse,
    ApplicationDomainIntegration,
    ApplicationDomainIntegrationCreate,
    ApplicationDomainIntegrationsResponse,
    ApplicationGovernance,
    ApplicationGovernanceUpdate,
    ApplicationInitiativeLink,
    ApplicationInitiativeLinkCreate,
    ApplicationInitiativeLinksResponse,
    ApplicationInitiativeLinkUpdate,
    ApplicationIntegration,
    ApplicationIntegrationCreate,
    ApplicationIntegrationListResponse,
    ApplicationIntegrationUpdate,
    ApplicationListResponse,
    ApplicationQualityMetric,
    ApplicationQualityMetricUpdate,
    ApplicationRisk,
    ApplicationRiskUpdate,
    ApplicationStageLink,
    ApplicationStageLinkCreate,
    ApplicationStageLinksResponse,
    ApplicationTechCapLink,
    ApplicationTechCapLinkCreate,
    ApplicationTechCapLinksResponse,
    ApplicationUpdate,
    BusinessUnitCostRollup,
    CostBucket,
    CostRollupResponse,
    DuplicateAppCapLinkError,
    DuplicateAppDesignLinkError,
    DuplicateAppInitiativeLinkError,
    DuplicateAppStageLinkError,
    DuplicateAppTechCapLinkError,
    InitiativeMember,
    OutOfSupportEntry,
    OutOfSupportResponse,
    RationalizationResponse,
    RenewalSoonEntry,
    RenewalsSoonResponse,
    RoadmapEntry,
    RoadmapResponse,
    TechCapDepthError,
    TechCapHasChildrenError,
    TechCapListResponse,
    TechnicalCapability,
    TechnicalCapabilityCreate,
    TechnicalCapabilityUpdate,
    TransformationInitiative,
    TransformationInitiativeCreate,
    TransformationInitiativeDetail,
    TransformationInitiativeListResponse,
    TransformationInitiativeUpdate,
)
from adp.search import (
    ENTITY_APPLICATION,
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
    sa.Column("business_value", sa.SmallInteger()),
    sa.Column("business_criticality", sa.SmallInteger()),
    sa.Column("owning_business_unit", sa.String(255)),
    sa.Column("business_owner", sa.String(255)),
    sa.Column("technical_owner", sa.String(255)),
    sa.Column("lifecycle_status", sa.Text(), nullable=False, server_default="active"),
    sa.Column("hosting_model", sa.Text()),
    sa.Column("architecture_pattern", sa.Text()),
    sa.Column("tech_debt_flags", sa.JSON(), nullable=False),
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
    # ADP-33v: strategic classification (migration 020)
    sa.Column("strategic_relevance", sa.SmallInteger(), nullable=True),
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

# APM US3: risk & compliance register (1:1 with applications; cascade-deletes)
_application_risk = sa.Table(
    "application_risk",
    _metadata,
    sa.Column("app_id", sa.String(36), primary_key=True),
    sa.Column("security_posture", sa.Text()),
    sa.Column("vulnerability_status", sa.Text()),
    sa.Column("data_classification", sa.Text()),
    sa.Column("regulatory_tags", sa.JSON(), nullable=False),
    sa.Column("dr_bc_status", sa.Text()),
    sa.Column("end_of_life_date", sa.Date()),
    sa.Column("end_of_support_date", sa.Date()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

# APM US4: Total Cost of Ownership (1:1 with applications; cascade-deletes)
_cost_columns: list[sa.Column] = [
    sa.Column("app_id", sa.String(36), primary_key=True),
    sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
    sa.Column("horizon_years", sa.SmallInteger(), nullable=False, server_default="5"),
]
for _bucket in TCO_BUCKET_NAMES:
    _cost_columns.append(
        sa.Column(f"{_bucket}_one_time", sa.Numeric(14, 2), nullable=False, server_default="0")
    )
    _cost_columns.append(
        sa.Column(f"{_bucket}_annual", sa.Numeric(14, 2), nullable=False, server_default="0")
    )
_cost_columns.append(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))

_application_cost = sa.Table("application_cost", _metadata, *_cost_columns)

# APM US6: transformation initiatives + application links (many-to-many)
_transformation_initiatives = sa.Table(
    "transformation_initiatives",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("target_date", sa.Date()),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_app_initiative_links = sa.Table(
    "application_initiative_links",
    _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("initiative_id", sa.String(36), nullable=False),
    sa.Column("planned_disposition", sa.Text(), nullable=False),
)

# APM US7: ownership & governance (1:1 with applications; cascade-deletes)
_application_contracts = sa.Table(
    "application_contracts",
    _metadata,
    sa.Column("app_id", sa.String(36), primary_key=True),
    sa.Column("contract_terms", sa.Text()),
    sa.Column("renewal_date", sa.Date()),
    sa.Column("sla", sa.Text()),
    sa.Column("business_sponsor", sa.String(255)),
    sa.Column("it_owner", sa.String(255)),
    sa.Column("decision_rights", sa.Text()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

# APM US8: quality & performance signals (1:1 with applications; cascade-deletes)
_application_quality_metrics = sa.Table(
    "application_quality_metrics",
    _metadata,
    sa.Column("app_id", sa.String(36), primary_key=True),
    sa.Column("uptime_pct", sa.Numeric(5, 2)),
    sa.Column("incidents_ytd", sa.Integer()),
    sa.Column("satisfaction_score", sa.SmallInteger()),
    sa.Column("perf_note", sa.Text()),
    sa.Column("ticket_volume_30d", sa.Integer()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
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
        business_value=row.business_value,
        business_criticality=row.business_criticality,
        owning_business_unit=row.owning_business_unit,
        business_owner=row.business_owner,
        technical_owner=row.technical_owner,
        lifecycle_status=row.lifecycle_status,
        hosting_model=row.hosting_model,
        architecture_pattern=row.architecture_pattern,
        tech_debt_flags=list(row.tech_debt_flags or []),
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
        strategic_relevance=getattr(row, "strategic_relevance", None),
    )


def _is_duplicate_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "unique" in msg or "duplicate" in msg or "23505" in msg


# ── Application CRUD (US1) ────────────────────────────────────────────────────


async def list_applications(
    session: AsyncSession,
    business_unit: str | None = None,
    lifecycle_status: str | None = None,
    hosting_model: str | None = None,
    tech_debt_flag: str | None = None,
) -> ApplicationListResponse:
    stmt = sa.select(_applications)
    if business_unit is not None:
        stmt = stmt.where(_applications.c.owning_business_unit == business_unit)
    if lifecycle_status is not None:
        stmt = stmt.where(_applications.c.lifecycle_status == lifecycle_status)
    if hosting_model is not None:
        stmt = stmt.where(_applications.c.hosting_model == hosting_model)
    result = await session.execute(stmt.order_by(_applications.c.name))
    rows = result.mappings().all()
    if tech_debt_flag is not None:
        # JSON containment isn't portable across SQLite/Postgres in SQLAlchemy Core
        # without dialect-specific operators; filter in Python (small result sets).
        rows = [row for row in rows if tech_debt_flag in (row.tech_debt_flags or [])]
    items = [_row_to_application(row) for row in rows]
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
            business_value=body.business_value,
            business_criticality=body.business_criticality,
            owning_business_unit=body.owning_business_unit,
            business_owner=body.business_owner,
            technical_owner=body.technical_owner,
            lifecycle_status=body.lifecycle_status,
            hosting_model=body.hosting_model,
            architecture_pattern=body.architecture_pattern,
            tech_debt_flags=list(body.tech_debt_flags),
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
        business_value=body.business_value,
        business_criticality=body.business_criticality,
        owning_business_unit=body.owning_business_unit,
        business_owner=body.business_owner,
        technical_owner=body.technical_owner,
        lifecycle_status=body.lifecycle_status,
        hosting_model=body.hosting_model,
        architecture_pattern=body.architecture_pattern,
        tech_debt_flags=list(body.tech_debt_flags),
        created_at=now,
        updated_at=now,
    )
    await index_entity(ENTITY_APPLICATION, app_id, build_text(body.name, body.description), session)
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
        "business_value", "business_criticality",
        "owning_business_unit", "business_owner", "technical_owner", "lifecycle_status",
        "hosting_model", "architecture_pattern", "tech_debt_flags",
    ):
        if field in body.model_fields_set:
            updates[field] = getattr(body, field)

    await session.execute(
        _applications.update().where(_applications.c.id == app_id).values(**updates)
    )
    refreshed = await get_application(app_id, session)
    if refreshed is not None:
        await index_entity(
            ENTITY_APPLICATION, app_id, build_text(refreshed.name, refreshed.description), session
        )
    return refreshed


async def delete_application(app_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _applications.delete().where(_applications.c.id == app_id)
    )
    deleted = _rowcount(result) > 0
    if deleted:
        await unindex_entity(ENTITY_APPLICATION, app_id, session)
    return deleted


async def fetch_rationalization(session: AsyncSession) -> RationalizationResponse:
    """Build the TIME rationalization projection over all applications (APM US1)."""
    from adp.application.rationalization import build_projection

    result = await session.execute(
        sa.select(
            _applications.c.id,
            _applications.c.name,
            _applications.c.business_value,
            _applications.c.health_score,
        ).order_by(_applications.c.name)
    )
    return build_projection([dict(row) for row in result.mappings().all()])


# ── Application Risk & Compliance CRUD (US3) ──────────────────────────────────


def _row_to_risk(row: Any) -> ApplicationRisk:
    return ApplicationRisk(
        security_posture=row.security_posture,
        vulnerability_status=row.vulnerability_status,
        data_classification=row.data_classification,
        regulatory_tags=list(row.regulatory_tags or []),
        dr_bc_status=row.dr_bc_status,
        end_of_life_date=row.end_of_life_date,
        end_of_support_date=row.end_of_support_date,
        updated_at=row.updated_at,
    )


async def get_application_risk(app_id: str, session: AsyncSession) -> ApplicationRisk | None:
    result = await session.execute(
        sa.select(_application_risk).where(_application_risk.c.app_id == app_id)
    )
    row = result.mappings().first()
    return _row_to_risk(row) if row else None


async def upsert_application_risk(
    app_id: str, body: ApplicationRiskUpdate, session: AsyncSession
) -> ApplicationRisk:
    values: dict[str, Any] = {
        "security_posture": body.security_posture,
        "vulnerability_status": body.vulnerability_status,
        "data_classification": body.data_classification,
        "regulatory_tags": list(body.regulatory_tags),
        "dr_bc_status": body.dr_bc_status,
        "end_of_life_date": body.end_of_life_date,
        "end_of_support_date": body.end_of_support_date,
        "updated_at": _now(),
    }
    exists = (
        await session.execute(
            sa.select(_application_risk.c.app_id).where(_application_risk.c.app_id == app_id)
        )
    ).first() is not None
    if exists:
        await session.execute(
            _application_risk.update()
            .where(_application_risk.c.app_id == app_id)
            .values(**values)
        )
    else:
        await session.execute(_application_risk.insert().values(app_id=app_id, **values))
    risk = await get_application_risk(app_id, session)
    assert risk is not None  # just upserted
    return risk


async def list_out_of_support(session: AsyncSession, today: date) -> OutOfSupportResponse:
    stmt = (
        sa.select(
            _application_risk.c.app_id,
            _applications.c.name,
            _application_risk.c.end_of_support_date,
        )
        .join(_applications, _applications.c.id == _application_risk.c.app_id)
        .where(
            _application_risk.c.end_of_support_date.is_not(None),
            _application_risk.c.end_of_support_date < today,
        )
        .order_by(_applications.c.name)
    )
    result = await session.execute(stmt)
    items = [
        OutOfSupportEntry(
            app_id=r.app_id, name=r.name, end_of_support_date=r.end_of_support_date
        )
        for r in result.mappings().all()
    ]
    return OutOfSupportResponse(items=items, total=len(items))


# ── Application Cost / TCO CRUD (US4, ADP-9x6) ────────────────────────────────


def _row_to_cost(row: Any) -> ApplicationCost:
    buckets = {
        name: CostBucket(one_time=row[f"{name}_one_time"], annual=row[f"{name}_annual"])
        for name in TCO_BUCKET_NAMES
    }
    return ApplicationCost(
        currency=row["currency"],
        horizon_years=row["horizon_years"],
        updated_at=row["updated_at"],
        **buckets,
    )


async def get_application_cost(app_id: str, session: AsyncSession) -> ApplicationCost | None:
    result = await session.execute(
        sa.select(_application_cost).where(_application_cost.c.app_id == app_id)
    )
    row = result.mappings().first()
    return _row_to_cost(row) if row else None


async def upsert_application_cost(
    app_id: str, body: ApplicationCostUpdate, session: AsyncSession
) -> ApplicationCost:
    values: dict[str, Any] = {
        "currency": body.currency,
        "horizon_years": body.horizon_years,
        "updated_at": _now(),
    }
    for name in TCO_BUCKET_NAMES:
        bucket = getattr(body, name)
        values[f"{name}_one_time"] = bucket.one_time
        values[f"{name}_annual"] = bucket.annual

    exists = (
        await session.execute(
            sa.select(_application_cost.c.app_id).where(_application_cost.c.app_id == app_id)
        )
    ).first() is not None
    if exists:
        await session.execute(
            _application_cost.update()
            .where(_application_cost.c.app_id == app_id)
            .values(**values)
        )
    else:
        await session.execute(_application_cost.insert().values(app_id=app_id, **values))
    cost = await get_application_cost(app_id, session)
    assert cost is not None  # just upserted
    return cost


async def list_all_costs(session: AsyncSession) -> dict[str, Decimal]:
    """TCO per application, for every application with a cost record.

    919-insights-dashboard: a bulk read for the applications heat map's cost dimension --
    reuses ``_row_to_cost`` (TCO is derived, not stored) rather than duplicating the
    bucket-sum formula in raw SQL. Applications with no cost record are simply absent from
    the returned mapping (caller renders them "unclassified", mirroring health_score/
    business_criticality/time_classification's own null handling).
    """
    result = await session.execute(sa.select(_application_cost))
    return {row["app_id"]: _row_to_cost(row).tco for row in result.mappings().all()}


async def rollup_cost_by_business_unit(session: AsyncSession) -> CostRollupResponse:
    """TCO per business unit, computed in Python (TCO is derived, not stored)."""
    stmt = sa.select(_applications.c.owning_business_unit, _application_cost).select_from(
        _application_cost.join(_applications, _applications.c.id == _application_cost.c.app_id)
    )
    result = await session.execute(stmt)

    bu_totals: dict[str | None, list[Any]] = {}
    grand_total = Decimal("0")
    for row in result.mappings().all():
        cost = _row_to_cost(row)
        bu = row["owning_business_unit"]
        entry = bu_totals.setdefault(bu, [Decimal("0"), 0])
        entry[0] += cost.tco
        entry[1] += 1
        grand_total += cost.tco

    items = [
        BusinessUnitCostRollup(business_unit=bu, app_count=count, tco=total)
        for bu, (total, count) in sorted(
            bu_totals.items(), key=lambda kv: (kv[0] is None, kv[0] or "")
        )
    ]
    return CostRollupResponse(items=items, total_tco=grand_total)


# ── Transformation Initiatives & Roadmap (US6) ────────────────────────────────


def _row_to_initiative(row: Any) -> TransformationInitiative:
    return TransformationInitiative(
        id=row.id,
        name=row.name,
        description=row.description,
        target_date=row.target_date,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_initiatives(session: AsyncSession) -> TransformationInitiativeListResponse:
    result = await session.execute(
        sa.select(_transformation_initiatives).order_by(_transformation_initiatives.c.name)
    )
    items = [_row_to_initiative(row) for row in result.mappings().all()]
    return TransformationInitiativeListResponse(items=items, total=len(items))


async def get_initiative(
    initiative_id: str, session: AsyncSession
) -> TransformationInitiativeDetail | None:
    result = await session.execute(
        sa.select(_transformation_initiatives).where(
            _transformation_initiatives.c.id == initiative_id
        )
    )
    row = result.mappings().first()
    if row is None:
        return None

    members_result = await session.execute(
        sa.select(
            _app_initiative_links.c.app_id,
            _applications.c.name.label("app_name"),
            _app_initiative_links.c.planned_disposition,
        )
        .join(_applications, _applications.c.id == _app_initiative_links.c.app_id)
        .where(_app_initiative_links.c.initiative_id == initiative_id)
        .order_by(_applications.c.name)
    )
    members = [
        InitiativeMember(
            app_id=m.app_id, app_name=m.app_name, planned_disposition=m.planned_disposition
        )
        for m in members_result.mappings().all()
    ]
    return TransformationInitiativeDetail(**_row_to_initiative(row).model_dump(), members=members)


async def create_initiative(
    body: TransformationInitiativeCreate, session: AsyncSession
) -> TransformationInitiative:
    initiative_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _transformation_initiatives.insert().values(
            id=initiative_id,
            name=body.name.strip(),
            description=body.description,
            target_date=body.target_date,
            created_at=now,
            updated_at=now,
        )
    )
    return TransformationInitiative(
        id=initiative_id,
        name=body.name.strip(),
        description=body.description,
        target_date=body.target_date,
        created_at=now,
        updated_at=now,
    )


async def update_initiative(
    initiative_id: str, body: TransformationInitiativeUpdate, session: AsyncSession
) -> TransformationInitiative | None:
    result = await session.execute(
        sa.select(_transformation_initiatives).where(
            _transformation_initiatives.c.id == initiative_id
        )
    )
    if result.mappings().first() is None:
        return None

    updates: dict[str, Any] = {"updated_at": _now()}
    if body.name is not None:
        updates["name"] = body.name.strip()
    for field in ("description", "target_date"):
        if field in body.model_fields_set:
            updates[field] = getattr(body, field)

    await session.execute(
        _transformation_initiatives.update()
        .where(_transformation_initiatives.c.id == initiative_id)
        .values(**updates)
    )
    row = (
        await session.execute(
            sa.select(_transformation_initiatives).where(
                _transformation_initiatives.c.id == initiative_id
            )
        )
    ).mappings().first()
    assert row is not None  # just updated
    return _row_to_initiative(row)


async def delete_initiative(initiative_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _transformation_initiatives.delete().where(
            _transformation_initiatives.c.id == initiative_id
        )
    )
    return _rowcount(result) > 0


async def list_app_initiative_links(
    app_id: str, session: AsyncSession
) -> ApplicationInitiativeLinksResponse:
    result = await session.execute(
        sa.select(
            _app_initiative_links.c.app_id,
            _app_initiative_links.c.initiative_id,
            _transformation_initiatives.c.name.label("initiative_name"),
            _app_initiative_links.c.planned_disposition,
        )
        .join(
            _transformation_initiatives,
            _transformation_initiatives.c.id == _app_initiative_links.c.initiative_id,
        )
        .where(_app_initiative_links.c.app_id == app_id)
        .order_by(_transformation_initiatives.c.name)
    )
    items = [
        ApplicationInitiativeLink(
            app_id=row.app_id,
            initiative_id=row.initiative_id,
            initiative_name=row.initiative_name,
            planned_disposition=row.planned_disposition,
        )
        for row in result.mappings().all()
    ]
    return ApplicationInitiativeLinksResponse(items=items, total=len(items))


async def create_app_initiative_link(
    app_id: str, body: ApplicationInitiativeLinkCreate, session: AsyncSession
) -> ApplicationInitiativeLink:
    app = await get_application(app_id, session)
    if app is None:
        raise ValueError(f"Application {app_id!r} not found")

    initiative_row = await session.execute(
        sa.select(_transformation_initiatives.c.id, _transformation_initiatives.c.name).where(
            _transformation_initiatives.c.id == body.initiative_id
        )
    )
    initiative = initiative_row.mappings().first()
    if initiative is None:
        raise LookupError(f"Transformation initiative {body.initiative_id!r} not found")

    try:
        await session.execute(
            _app_initiative_links.insert().values(
                app_id=app_id,
                initiative_id=body.initiative_id,
                planned_disposition=body.planned_disposition,
            )
        )
    except Exception as exc:
        if _is_duplicate_error(exc):
            raise DuplicateAppInitiativeLinkError(
                f"Link ({app_id!r}, {body.initiative_id!r}) already exists"
            ) from exc
        raise

    return ApplicationInitiativeLink(
        app_id=app_id,
        initiative_id=body.initiative_id,
        initiative_name=initiative.name,
        planned_disposition=body.planned_disposition,
    )


async def update_app_initiative_link(
    app_id: str,
    initiative_id: str,
    body: ApplicationInitiativeLinkUpdate,
    session: AsyncSession,
) -> ApplicationInitiativeLink | None:
    existing = await session.execute(
        sa.select(_app_initiative_links).where(
            _app_initiative_links.c.app_id == app_id,
            _app_initiative_links.c.initiative_id == initiative_id,
        )
    )
    if existing.mappings().first() is None:
        return None

    await session.execute(
        _app_initiative_links.update()
        .where(
            _app_initiative_links.c.app_id == app_id,
            _app_initiative_links.c.initiative_id == initiative_id,
        )
        .values(planned_disposition=body.planned_disposition)
    )
    links = await list_app_initiative_links(app_id, session)
    for link in links.items:
        if link.initiative_id == initiative_id:
            return link
    return None  # pragma: no cover — link existed a moment ago


async def delete_app_initiative_link(
    app_id: str, initiative_id: str, session: AsyncSession
) -> bool:
    result = await session.execute(
        _app_initiative_links.delete().where(
            _app_initiative_links.c.app_id == app_id,
            _app_initiative_links.c.initiative_id == initiative_id,
        )
    )
    return _rowcount(result) > 0


async def get_roadmap(session: AsyncSession) -> RoadmapResponse:
    """Decommission/roadmap track: Eliminate-classified or sunset/retired apps,
    with their EOL date (US3, if recorded) and initiative links."""
    stmt = (
        sa.select(
            _applications.c.id,
            _applications.c.name,
            _applications.c.time_classification,
            _applications.c.lifecycle_status,
            _application_risk.c.end_of_life_date,
        )
        .select_from(
            _applications.outerjoin(
                _application_risk, _application_risk.c.app_id == _applications.c.id
            )
        )
        .where(
            sa.or_(
                _applications.c.time_classification == "Eliminate",
                _applications.c.lifecycle_status.in_(["sunset", "retired"]),
            )
        )
        .order_by(_applications.c.name)
    )
    rows = (await session.execute(stmt)).mappings().all()

    items = []
    for row in rows:
        links = await list_app_initiative_links(row["id"], session)
        items.append(
            RoadmapEntry(
                app_id=row["id"],
                name=row["name"],
                time_classification=row["time_classification"],
                lifecycle_status=row["lifecycle_status"],
                end_of_life_date=row["end_of_life_date"],
                initiative_links=links.items,
            )
        )
    return RoadmapResponse(items=items, total=len(items))


# ── Application Governance CRUD (US7) ─────────────────────────────────────────


def _row_to_governance(row: Any) -> ApplicationGovernance:
    return ApplicationGovernance(
        contract_terms=row.contract_terms,
        renewal_date=row.renewal_date,
        sla=row.sla,
        business_sponsor=row.business_sponsor,
        it_owner=row.it_owner,
        decision_rights=row.decision_rights,
        updated_at=row.updated_at,
    )


async def get_application_governance(
    app_id: str, session: AsyncSession
) -> ApplicationGovernance | None:
    result = await session.execute(
        sa.select(_application_contracts).where(_application_contracts.c.app_id == app_id)
    )
    row = result.mappings().first()
    return _row_to_governance(row) if row else None


async def upsert_application_governance(
    app_id: str, body: ApplicationGovernanceUpdate, session: AsyncSession
) -> ApplicationGovernance:
    values: dict[str, Any] = {
        "contract_terms": body.contract_terms,
        "renewal_date": body.renewal_date,
        "sla": body.sla,
        "business_sponsor": body.business_sponsor,
        "it_owner": body.it_owner,
        "decision_rights": body.decision_rights,
        "updated_at": _now(),
    }
    exists = (
        await session.execute(
            sa.select(_application_contracts.c.app_id).where(
                _application_contracts.c.app_id == app_id
            )
        )
    ).first() is not None
    if exists:
        await session.execute(
            _application_contracts.update()
            .where(_application_contracts.c.app_id == app_id)
            .values(**values)
        )
    else:
        await session.execute(_application_contracts.insert().values(app_id=app_id, **values))
    governance = await get_application_governance(app_id, session)
    assert governance is not None  # just upserted
    return governance


async def list_renewals_soon(
    session: AsyncSession, today: date, within_days: int = 90
) -> RenewalsSoonResponse:
    horizon = today + timedelta(days=within_days)
    stmt = (
        sa.select(
            _application_contracts.c.app_id,
            _applications.c.name,
            _application_contracts.c.renewal_date,
        )
        .join(_applications, _applications.c.id == _application_contracts.c.app_id)
        .where(
            _application_contracts.c.renewal_date.is_not(None),
            _application_contracts.c.renewal_date >= today,
            _application_contracts.c.renewal_date <= horizon,
        )
        .order_by(_application_contracts.c.renewal_date)
    )
    result = await session.execute(stmt)
    items = [
        RenewalSoonEntry(app_id=r.app_id, name=r.name, renewal_date=r.renewal_date)
        for r in result.mappings().all()
    ]
    return RenewalsSoonResponse(items=items, total=len(items))


# ── Application Quality & Performance CRUD (US8) ──────────────────────────────


def _row_to_quality(row: Any) -> ApplicationQualityMetric:
    return ApplicationQualityMetric(
        uptime_pct=row.uptime_pct,
        incidents_ytd=row.incidents_ytd,
        satisfaction_score=row.satisfaction_score,
        perf_note=row.perf_note,
        ticket_volume_30d=row.ticket_volume_30d,
        updated_at=row.updated_at,
    )


async def get_application_quality(
    app_id: str, session: AsyncSession
) -> ApplicationQualityMetric | None:
    result = await session.execute(
        sa.select(_application_quality_metrics).where(
            _application_quality_metrics.c.app_id == app_id
        )
    )
    row = result.mappings().first()
    return _row_to_quality(row) if row else None


async def upsert_application_quality(
    app_id: str, body: ApplicationQualityMetricUpdate, session: AsyncSession
) -> ApplicationQualityMetric:
    values: dict[str, Any] = {
        "uptime_pct": body.uptime_pct,
        "incidents_ytd": body.incidents_ytd,
        "satisfaction_score": body.satisfaction_score,
        "perf_note": body.perf_note,
        "ticket_volume_30d": body.ticket_volume_30d,
        "updated_at": _now(),
    }
    exists = (
        await session.execute(
            sa.select(_application_quality_metrics.c.app_id).where(
                _application_quality_metrics.c.app_id == app_id
            )
        )
    ).first() is not None
    if exists:
        await session.execute(
            _application_quality_metrics.update()
            .where(_application_quality_metrics.c.app_id == app_id)
            .values(**values)
        )
    else:
        await session.execute(
            _application_quality_metrics.insert().values(app_id=app_id, **values)
        )
    quality = await get_application_quality(app_id, session)
    assert quality is not None  # just upserted
    return quality


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
            strategic_relevance=body.strategic_relevance,
        )
    )
    tc = TechnicalCapability(
        id=tc_id,
        name=body.name.strip(),
        description=body.description,
        parent_id=body.parent_id,
        level=level,
        created_at=now,
        strategic_relevance=body.strategic_relevance,
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
    if "strategic_relevance" in body.model_fields_set:
        updates["strategic_relevance"] = body.strategic_relevance

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


async def list_all_capability_links(session: AsyncSession) -> list[ApplicationCapabilityLink]:
    """Every application-capability link across the whole registry, in one query.

    Application Portfolio pivot (ADP-8xo): a bulk read for the portfolio-wide
    "group by business capability" dimension -- reuses list_app_capability_links's
    own join shape, just without the app_id filter, mirroring 919-insights-dashboard's
    list_all_costs precedent for the same "one bulk query, not N+1" reasoning.
    Ordered by capability name then app name for a stable default grouping order.
    """
    result = await session.execute(
        sa.select(
            _app_cap_links.c.app_id,
            _app_cap_links.c.capability_id,
            _biz_caps.c.name.label("capability_name"),
            _app_cap_links.c.fit_score,
            _applications.c.name.label("app_name"),
        )
        .join(_biz_caps, _biz_caps.c.id == _app_cap_links.c.capability_id)
        .join(_applications, _applications.c.id == _app_cap_links.c.app_id)
        .order_by(_biz_caps.c.name, _applications.c.name)
    )
    return [
        ApplicationCapabilityLink(
            app_id=row.app_id,
            capability_id=row.capability_id,
            capability_name=row.capability_name,
            fit_score=row.fit_score,
        )
        for row in result.mappings().all()
    ]


@dataclass(frozen=True)
class CapabilityApplicationRef:
    """An application linked to a business capability, with non-sensitive APM
    fields only (ADP-SPEC-039 context assembly -- risk/cost/governance are
    deliberately excluded by construction, not by a permission check).

    Not a boundary payload (ART-XIII concerns external APIs) -- internal
    context data feeding the Agent Review toolkit.
    """

    app_id: str
    app_name: str
    fit_score: int
    time_classification: str | None
    r_strategy: str | None
    pace_layer: str | None
    health_score: int | None


async def list_applications_for_capability(
    capability_id: str, session: AsyncSession
) -> list[CapabilityApplicationRef]:
    """Reverse of list_app_capability_links: applications linked to a capability."""
    result = await session.execute(
        sa.select(
            _app_cap_links.c.app_id,
            _applications.c.name.label("app_name"),
            _app_cap_links.c.fit_score,
            _applications.c.time_classification,
            _applications.c.r_strategy,
            _applications.c.pace_layer,
            _applications.c.health_score,
        )
        .join(_applications, _applications.c.id == _app_cap_links.c.app_id)
        .where(_app_cap_links.c.capability_id == capability_id)
        .order_by(_applications.c.name)
    )
    return [
        CapabilityApplicationRef(
            app_id=row.app_id,
            app_name=row.app_name,
            fit_score=row.fit_score,
            time_classification=row.time_classification,
            r_strategy=row.r_strategy,
            pace_layer=row.pace_layer,
            health_score=row.health_score,
        )
        for row in result.mappings()
    ]


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
