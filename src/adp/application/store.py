"""Application Registry store — async SQLAlchemy Core CRUD (ADP-SPEC-036).

All functions accept an AsyncSession and are called from the router inside
`async with session_factory() as session: ...` blocks.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adp.application.assessments import (  # noqa: F401
    _framework_record,
    _linked_framework_ids,
    _row_to_cost,
    _row_to_governance,
    _row_to_quality,
    _row_to_risk,
    compute_business_value_score,
    get_application_cost,
    get_application_governance,
    get_application_quality,
    get_application_risk,
    get_business_value_assessment,
    get_health_assessment,
    list_all_costs,
    list_out_of_support,
    list_renewals_soon,
    rollup_cost_by_business_unit,
    upsert_application_cost,
    upsert_application_governance,
    upsert_application_quality,
    upsert_application_risk,
    upsert_business_value_assessment,
    upsert_health_assessment,
)
from adp.application.links import (  # noqa: F401
    CapabilityApplicationRef,
    _integration_select,
    _row_to_integration,
    _src_apps,
    _tgt_apps,
    create_app_capability_link,
    create_app_design_link,
    create_app_domain_integration,
    create_app_stage_link,
    create_app_tech_cap_link,
    create_integration,
    delete_app_capability_link,
    delete_app_design_link,
    delete_app_domain_integration,
    delete_app_stage_link,
    delete_app_tech_cap_link,
    delete_integration,
    get_integration,
    list_all_capability_links,
    list_app_capability_links,
    list_app_design_links,
    list_app_domain_integrations,
    list_app_stage_links,
    list_app_tech_cap_links,
    list_applications_for_capability,
    list_integrations,
    update_app_capability_link,
    update_integration,
)
from adp.application.models import (
    AgenticSolutionHasAgentsError,
    Application,
    ApplicationCreate,
    ApplicationListResponse,
    ApplicationUpdate,
    RationalizationResponse,
    TechCapDepthError,
    TechCapHasChildrenError,
    TechCapListResponse,
    TechnicalCapability,
    TechnicalCapabilityCreate,
    TechnicalCapabilityUpdate,
)
from adp.application.roadmap import (  # noqa: F401
    _row_to_initiative,
    create_app_initiative_link,
    create_initiative,
    delete_app_initiative_link,
    delete_initiative,
    get_initiative,
    get_roadmap,
    list_app_initiative_links,
    list_initiatives,
    update_app_initiative_link,
    update_initiative,
)
from adp.application.store_base import (  # noqa: F401
    _is_duplicate_error,
    _now,
    _row_to_application,
    _row_to_tech_cap,
    _rowcount,
    get_application,
    get_technical_capability,
)
from adp.application.tables import (  # noqa: F401
    _app_cap_links,
    _app_cap_realizations,
    _app_cap_tech_links,
    _app_caps,
    _app_design_links,
    _app_domain_integrations,
    _app_initiative_links,
    _app_integrations,
    _app_stage_links,
    _app_tech_cap_links,
    _application_contracts,
    _application_cost,
    _application_framework_tags,
    _application_quality_metrics,
    _application_risk,
    _applications,
    _biz_app_cap_links,
    _biz_caps,
    _business_value_assessment,
    _cost_columns,
    _designs,
    _domains,
    _health_assessment,
    _metadata,
    _regulatory_frameworks,
    _solution_agents,
    _stages,
    _tech_caps,
    _transformation_initiatives,
)
from adp.search import (
    ENTITY_APPLICATION,
    ENTITY_TECHNICAL_CAPABILITY,
    build_text,
    index_entity,
    unindex_entity,
)

# The tables, shared helpers and the assessment, roadmap and link functions live in sibling
# modules (ADP-blp.27) and are re-exported above: callers and tests use this module's names.

# ── Session factory ───────────────────────────────────────────────────────────

_engine: Any = None
_session_factory: Any = None


def _get_session_factory() -> async_sessionmaker:
    """Every store shares adp.db's single engine (ADP-blp.15). A test may set this module's
    _session_factory to point it at its own database instead."""
    if _session_factory is not None:
        return _session_factory
    from adp.db import get_session_factory

    return get_session_factory()


def get_session() -> AsyncSession:
    return _get_session_factory()()




# ── Helpers ───────────────────────────────────────────────────────────────────









# ── Application CRUD (US1) ────────────────────────────────────────────────────


async def list_applications(
    session: AsyncSession,
    business_unit: str | None = None,
    lifecycle_status: str | None = None,
    hosting_model: str | None = None,
    application_type: str | None = None,
    tech_debt_flag: str | None = None,
) -> ApplicationListResponse:
    stmt = sa.select(_applications)
    if business_unit is not None:
        stmt = stmt.where(_applications.c.owning_business_unit == business_unit)
    if lifecycle_status is not None:
        stmt = stmt.where(_applications.c.lifecycle_status == lifecycle_status)
    if hosting_model is not None:
        stmt = stmt.where(_applications.c.hosting_model == hosting_model)
    if application_type is not None:
        stmt = stmt.where(_applications.c.application_type == application_type)
    result = await session.execute(stmt.order_by(_applications.c.name))
    rows = result.mappings().all()
    if tech_debt_flag is not None:
        # JSON containment isn't portable across SQLite/Postgres in SQLAlchemy Core
        # without dialect-specific operators; filter in Python (small result sets).
        rows = [row for row in rows if tech_debt_flag in (row.tech_debt_flags or [])]
    items = [_row_to_application(row) for row in rows]
    return ApplicationListResponse(items=items, total=len(items))




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
            # health_score/business_value always start unset -- only ever
            # written by upsert_health_assessment/upsert_business_value_assessment,
            # and there's no application_id yet to assess against until this
            # insert commits.
            health_score=None,
            business_value=None,
            business_criticality=body.business_criticality,
            owning_business_unit=body.owning_business_unit,
            owning_org_unit_id=body.owning_org_unit_id,
            business_owner=body.business_owner,
            technical_owner=body.technical_owner,
            lifecycle_status=body.lifecycle_status,
            hosting_model=body.hosting_model,
            application_type=body.application_type,
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
        health_score=None,
        business_value=None,
        business_criticality=body.business_criticality,
        owning_business_unit=body.owning_business_unit,
        owning_org_unit_id=body.owning_org_unit_id,
        business_owner=body.business_owner,
        technical_owner=body.technical_owner,
        lifecycle_status=body.lifecycle_status,
        hosting_model=body.hosting_model,
        application_type=body.application_type,
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

    # 933-agent-registry (Clarification Q1): an agentic solution with agents cannot be
    # reclassified until its agents are removed.
    if (
        "application_type" in body.model_fields_set
        and existing.application_type == "agentic"
        and body.application_type != "agentic"
    ):
        agent_count = (
            await session.execute(
                sa.select(sa.func.count())
                .select_from(_solution_agents)
                .where(_solution_agents.c.solution_app_id == app_id)
            )
        ).scalar_one()
        if agent_count:
            raise AgenticSolutionHasAgentsError(app_id, agent_count)

    updates: dict[str, Any] = {"updated_at": _now()}
    if body.name is not None:
        updates["name"] = body.name.strip()
    # Nullable fields: an explicitly provided null clears the value;
    # an omitted field is left unchanged (model_fields_set distinguishes them).
    for field in (
        # health_score/business_value are deliberately absent --
        # ApplicationUpdate no longer carries either (docs/application-
        # health-assessment-spec.md §6 Q5; docs/application-business-value-
        # assessment-spec.md §7); each is only ever written by its own
        # upsert_*_assessment function below.
        "description", "vendor", "primary_owner", "time_classification",
        "r_strategy", "pace_layer",
        "business_criticality",
        "owning_business_unit", "business_owner", "technical_owner", "lifecycle_status",
        "hosting_model", "application_type", "architecture_pattern", "tech_debt_flags",
        "owning_org_unit_id",
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
    # 933-agent-registry: remove agent memberships explicitly (never the agents themselves) so
    # SQLite fixtures behave like Postgres, where migration 043's CASCADE is the safety net.
    await session.execute(
        _solution_agents.delete().where(_solution_agents.c.solution_app_id == app_id)
    )
    # 937: same for application capability realizations (the capabilities themselves stay).
    await session.execute(
        _app_cap_realizations.delete().where(_app_cap_realizations.c.app_id == app_id)
    )
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


# ── Technical Capability CRUD (US3) ──────────────────────────────────────────

async def list_technical_capabilities(session: AsyncSession) -> TechCapListResponse:
    result = await session.execute(
        sa.select(_tech_caps).order_by(_tech_caps.c.level, _tech_caps.c.name)
    )
    items = [_row_to_tech_cap(row) for row in result.mappings().all()]
    return TechCapListResponse(items=items, total=len(items))




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
            lifecycle_status=body.lifecycle_status,
            end_of_life_date=body.end_of_life_date,
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
        lifecycle_status=body.lifecycle_status,
        end_of_life_date=body.end_of_life_date,
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
    if body.lifecycle_status is not None:
        updates["lifecycle_status"] = body.lifecycle_status
    if "end_of_life_date" in body.model_fields_set:
        updates["end_of_life_date"] = body.end_of_life_date

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

    # 937: remove application capability -> technical links explicitly (SQLite parity; migration
    # 046's CASCADE is the safety net). An L3 left with no technical link starts showing the
    # derived missing-technical-capability warning.
    await session.execute(
        _app_cap_tech_links.delete().where(_app_cap_tech_links.c.tech_cap_id == tc_id)
    )
    result = await session.execute(
        _tech_caps.delete().where(_tech_caps.c.id == tc_id)
    )
    deleted = _rowcount(result) > 0
    if deleted:
        await unindex_entity(ENTITY_TECHNICAL_CAPABILITY, tc_id, session)
    return deleted

