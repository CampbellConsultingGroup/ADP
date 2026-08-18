"""Application Registry API — ADP-SPEC-036.

GET/POST/PATCH/DELETE /api/v1/applications           — application CRUD
GET/POST/PATCH/DELETE /api/v1/applications/{id}/capability-links
GET/POST/DELETE       /api/v1/applications/{id}/technical-capability-links
GET/POST/DELETE       /api/v1/applications/{id}/stage-links
GET/POST/DELETE       /api/v1/applications/{id}/domain-integrations
GET/POST/DELETE       /api/v1/applications/{id}/design-links
GET/PUT               /api/v1/applications/{id}/health-assessment
GET/PUT               /api/v1/applications/{id}/business-value-assessment
GET/POST/PATCH/DELETE /api/v1/technical-capabilities
GET/POST/PATCH/DELETE /api/v1/integrations

ART-IX (SHOULD): structured logging used for all mutations.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.application import store as astore
from adp.application.models import (
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
    BusinessValueAssessmentResponse,
    BusinessValueAssessmentSubmit,
    CostRollupResponse,
    DuplicateAppCapLinkError,
    DuplicateAppDesignLinkError,
    DuplicateAppInitiativeLinkError,
    DuplicateAppStageLinkError,
    DuplicateAppTechCapLinkError,
    HealthAssessmentResponse,
    HealthAssessmentSubmit,
    OutOfSupportResponse,
    RationalizationResponse,
    RenewalsSoonResponse,
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
from adp.authz.enforcement import require_action_dep
from adp.authz.roles import ActionType
from adp.compliance.models import ControlMappingListResponse
from adp.strategy.models import StrategicObjectiveListResponse

logger = logging.getLogger(__name__)

applications_router = APIRouter(prefix="/api/v1/applications", tags=["applications"])
tech_caps_router = APIRouter(
    prefix="/api/v1/technical-capabilities", tags=["technical-capabilities"]
)
integrations_router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
initiatives_router = APIRouter(
    prefix="/api/v1/transformation-initiatives", tags=["transformation-initiatives"]
)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_actor(request: Request) -> str:
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


async def _get_session():
    factory = astore._get_session_factory()
    async with factory() as session:
        yield session


async def _get_strategy_session():
    """A strategy-scoped session (ADP-d8u.2), used only by the reverse-lookup
    GET /applications/{id}/objectives endpoint below."""
    from adp.strategy import store as sstore

    factory = sstore._get_session_factory()
    async with factory() as session:
        yield session


async def _get_compliance_session():
    """A compliance-scoped session (COMPLY-02 research.md D7), used only by the
    reverse-lookup GET /applications/{id}/compliance-mappings endpoint below."""
    from adp.compliance import store as cstore

    factory = cstore._get_session_factory()
    async with factory() as session:
        yield session


# Sensitive-read gate (APM US3): risk & compliance fields are not open to every
# reader. The app-level enforcer exempts GETs, so gate these reads per-route.
_require_risk_read = require_action_dep(ActionType.READ_APPLICATION_RISK)
_require_cost_read = require_action_dep(ActionType.READ_APPLICATION_COST)
_require_governance_read = require_action_dep(ActionType.READ_APPLICATION_GOVERNANCE)


# ── Applications CRUD ─────────────────────────────────────────────────────────

@applications_router.get("", response_model=ApplicationListResponse)
async def list_applications(
    business_unit: Optional[str] = Query(default=None),
    lifecycle_status: Optional[str] = Query(default=None),
    hosting_model: Optional[str] = Query(default=None),
    tech_debt_flag: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(_get_session),
):
    return await astore.list_applications(
        session,
        business_unit=business_unit,
        lifecycle_status=lifecycle_status,
        hosting_model=hosting_model,
        tech_debt_flag=tech_debt_flag,
    )


@applications_router.post("", response_model=Application, status_code=status.HTTP_201_CREATED)
async def create_application(
    body: ApplicationCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    app = await astore.create_application(body, session)
    await session.commit()
    actor = _get_actor(request)
    logger.info("application.create id=%s name=%r actor=%s", app.id, app.name, actor)
    return app


@applications_router.get("/rationalization", response_model=RationalizationResponse)
async def get_rationalization(session: AsyncSession = Depends(_get_session)):
    """TIME rationalization projection: business_value × health_score (APM US1).

    Registered before ``/{app_id}`` so the literal path is not shadowed.
    """
    return await astore.fetch_rationalization(session)


@applications_router.get("/roadmap", response_model=RoadmapResponse)
async def get_roadmap(session: AsyncSession = Depends(_get_session)):
    """Decommission track: Eliminate-classified or sunset/retired applications
    (APM US6). Registered before ``/{app_id}`` so the literal path is not shadowed.
    """
    return await astore.get_roadmap(session)


@applications_router.get("/{app_id}", response_model=Application)
async def get_application(app_id: str, session: AsyncSession = Depends(_get_session)):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return app


@applications_router.get(
    "/{app_id}/objectives", response_model=StrategicObjectiveListResponse
)
async def get_application_objectives(
    app_id: str,
    session: AsyncSession = Depends(_get_session),
    strategy_session: AsyncSession = Depends(_get_strategy_session),
):
    """ADP-d8u.2: reverse lookup -- every strategic objective this
    application realizes."""
    if await astore.get_application(app_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")

    from adp.strategy import store as sstore

    return await sstore.list_objectives_for_application(app_id, strategy_session)


@applications_router.get(
    "/{app_id}/compliance-mappings",
    response_model=ControlMappingListResponse,
    dependencies=[Depends(_require_governance_read)],
)
async def get_application_compliance_mappings(
    app_id: str,
    session: AsyncSession = Depends(_get_session),
    compliance_session: AsyncSession = Depends(_get_compliance_session),
):
    """Reverse lookup (FR-012): every Control mapped to this Application. Gated by
    READ_APPLICATION_GOVERNANCE (Clarification Session 2026-08-18; research.md D2) -- the
    same permission that already protects this Application's other governance data."""
    if await astore.get_application(app_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")

    from adp.compliance import store as cstore

    items = await cstore.list_mappings_for_application(app_id, compliance_session)
    return ControlMappingListResponse(items=items, total=len(items))


@applications_router.patch("/{app_id}", response_model=Application)
async def update_application(
    app_id: str,
    body: ApplicationUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    app = await astore.update_application(app_id, body, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("application.update id=%s actor=%s", app_id, actor)
    return app


@applications_router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_application(app_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("application.delete id=%s actor=%s", app_id, actor)


# ── Application Risk & Compliance (APM US3, sensitive) ────────────────────────

@applications_router.get(
    "/risk/out-of-support",
    response_model=OutOfSupportResponse,
    dependencies=[Depends(_require_risk_read)],
)
async def list_out_of_support(session: AsyncSession = Depends(_get_session)):
    """Applications whose end-of-support date is in the past."""
    return await astore.list_out_of_support(session, date.today())


@applications_router.get(
    "/{app_id}/risk",
    response_model=ApplicationRisk,
    dependencies=[Depends(_require_risk_read)],
)
async def get_application_risk(app_id: str, session: AsyncSession = Depends(_get_session)):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    risk = await astore.get_application_risk(app_id, session)
    return risk or ApplicationRisk()


@applications_router.put("/{app_id}/risk", response_model=ApplicationRisk)
async def put_application_risk(
    app_id: str,
    body: ApplicationRiskUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    risk = await astore.upsert_application_risk(app_id, body, session)
    await session.commit()
    logger.info("application.risk.update id=%s actor=%s", app_id, _get_actor(request))
    return risk


# ── Application Health Assessment (docs/application-health-assessment-spec.md,
#    not sensitive -- ungated read, matching every other non-Risk/Cost/
#    Governance Application sub-resource) ──────────────────────────────────────

@applications_router.get(
    "/{app_id}/health-assessment", response_model=HealthAssessmentResponse
)
async def get_health_assessment(app_id: str, session: AsyncSession = Depends(_get_session)):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.get_health_assessment(app_id, session)


@applications_router.put(
    "/{app_id}/health-assessment", response_model=HealthAssessmentResponse
)
async def put_health_assessment(
    app_id: str,
    body: HealthAssessmentSubmit,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    actor = _get_actor(request)
    result = await astore.upsert_health_assessment(app_id, body, actor, session)
    await session.commit()
    logger.info(
        "application.health_assessment.update id=%s health_score=%s actor=%s",
        app_id, result.health_score, actor,
    )
    return result


# ── Application Business Value Assessment
#    (docs/application-business-value-assessment-spec.md, not sensitive --
#    ungated read, same treatment as Health Assessment above) ────────────────

@applications_router.get(
    "/{app_id}/business-value-assessment", response_model=BusinessValueAssessmentResponse
)
async def get_business_value_assessment(
    app_id: str, session: AsyncSession = Depends(_get_session)
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.get_business_value_assessment(app_id, session)


@applications_router.put(
    "/{app_id}/business-value-assessment", response_model=BusinessValueAssessmentResponse
)
async def put_business_value_assessment(
    app_id: str,
    body: BusinessValueAssessmentSubmit,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    actor = _get_actor(request)
    result = await astore.upsert_business_value_assessment(app_id, body, actor, session)
    await session.commit()
    logger.info(
        "application.business_value_assessment.update id=%s business_value=%s actor=%s",
        app_id, result.result.business_value if result.result else None, actor,
    )
    return result


# ── Application Cost / TCO (APM US4, sensitive) ───────────────────────────────

@applications_router.get(
    "/cost/rollup",
    response_model=CostRollupResponse,
    dependencies=[Depends(_require_cost_read)],
)
async def get_cost_rollup(session: AsyncSession = Depends(_get_session)):
    """TCO rolled up by owning business unit. Sensitive aggregate — same gate as
    the per-application read, so it cannot leak cost data around the field-level
    permission (FR-013)."""
    return await astore.rollup_cost_by_business_unit(session)


@applications_router.get(
    "/{app_id}/cost",
    response_model=ApplicationCost,
    dependencies=[Depends(_require_cost_read)],
)
async def get_application_cost(app_id: str, session: AsyncSession = Depends(_get_session)):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    cost = await astore.get_application_cost(app_id, session)
    return cost or ApplicationCost()


@applications_router.put("/{app_id}/cost", response_model=ApplicationCost)
async def put_application_cost(
    app_id: str,
    body: ApplicationCostUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    cost = await astore.upsert_application_cost(app_id, body, session)
    await session.commit()
    logger.info("application.cost.update id=%s actor=%s", app_id, _get_actor(request))
    return cost


# ── Lifecycle & Roadmap (APM US6, links) ───────────────────────────────────────

@applications_router.get(
    "/{app_id}/initiative-links", response_model=ApplicationInitiativeLinksResponse
)
async def list_initiative_links(app_id: str, session: AsyncSession = Depends(_get_session)):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.list_app_initiative_links(app_id, session)


@applications_router.post(
    "/{app_id}/initiative-links",
    response_model=ApplicationInitiativeLink,
    status_code=status.HTTP_201_CREATED,
)
async def create_initiative_link(
    app_id: str,
    body: ApplicationInitiativeLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        link = await astore.create_app_initiative_link(app_id, body, session)
    except DuplicateAppInitiativeLinkError:
        raise HTTPException(status_code=409, detail="Link already exists")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    logger.info(
        "app.initiative_link.create app_id=%s initiative_id=%s actor=%s",
        app_id, body.initiative_id, _get_actor(request),
    )
    return link


@applications_router.patch(
    "/{app_id}/initiative-links/{initiative_id}",
    response_model=ApplicationInitiativeLink,
)
async def update_initiative_link(
    app_id: str,
    initiative_id: str,
    body: ApplicationInitiativeLinkUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    link = await astore.update_app_initiative_link(app_id, initiative_id, body, session)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    logger.info(
        "app.initiative_link.update app_id=%s initiative_id=%s actor=%s",
        app_id, initiative_id, _get_actor(request),
    )
    return link


@applications_router.delete(
    "/{app_id}/initiative-links/{initiative_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_initiative_link(
    app_id: str,
    initiative_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_app_initiative_link(app_id, initiative_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    logger.info(
        "app.initiative_link.delete app_id=%s initiative_id=%s actor=%s",
        app_id, initiative_id, _get_actor(request),
    )


# ── Application Ownership & Governance (APM US7, sensitive) ───────────────────

@applications_router.get(
    "/governance/renewals-soon",
    response_model=RenewalsSoonResponse,
    dependencies=[Depends(_require_governance_read)],
)
async def list_renewals_soon(
    within_days: int = Query(default=90, ge=1),
    session: AsyncSession = Depends(_get_session),
):
    """Contracts renewing within the given window (default 90 days)."""
    return await astore.list_renewals_soon(session, date.today(), within_days=within_days)


@applications_router.get(
    "/{app_id}/governance",
    response_model=ApplicationGovernance,
    dependencies=[Depends(_require_governance_read)],
)
async def get_application_governance(app_id: str, session: AsyncSession = Depends(_get_session)):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    governance = await astore.get_application_governance(app_id, session)
    return governance or ApplicationGovernance()


@applications_router.put("/{app_id}/governance", response_model=ApplicationGovernance)
async def put_application_governance(
    app_id: str,
    body: ApplicationGovernanceUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    governance = await astore.upsert_application_governance(app_id, body, session)
    await session.commit()
    logger.info("application.governance.update id=%s actor=%s", app_id, _get_actor(request))
    return governance


# ── Application Quality & Performance Signals (APM US8) ───────────────────────
# Manual/advisory in v1 — not a sensitive category, no new authz (like US5/US6).

@applications_router.get("/{app_id}/quality", response_model=ApplicationQualityMetric)
async def get_application_quality(app_id: str, session: AsyncSession = Depends(_get_session)):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    quality = await astore.get_application_quality(app_id, session)
    return quality or ApplicationQualityMetric()


@applications_router.put("/{app_id}/quality", response_model=ApplicationQualityMetric)
async def put_application_quality(
    app_id: str,
    body: ApplicationQualityMetricUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    quality = await astore.upsert_application_quality(app_id, body, session)
    await session.commit()
    logger.info("application.quality.update id=%s actor=%s", app_id, _get_actor(request))
    return quality


# ── Application–Business Capability Links ─────────────────────────────────────

@applications_router.get(
    "/{app_id}/capability-links", response_model=ApplicationCapabilityLinksResponse
)
async def list_capability_links(
    app_id: str, session: AsyncSession = Depends(_get_session)
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.list_app_capability_links(app_id, session)


@applications_router.post(
    "/{app_id}/capability-links",
    response_model=ApplicationCapabilityLink,
    status_code=status.HTTP_201_CREATED,
)
async def create_capability_link(
    app_id: str,
    body: ApplicationCapabilityLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        link = await astore.create_app_capability_link(app_id, body, session)
    except DuplicateAppCapLinkError:
        raise HTTPException(status_code=409, detail="Link already exists")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.capability_link.create app_id=%s cap_id=%s actor=%s",
        app_id, body.capability_id, actor,
    )
    return link


@applications_router.patch(
    "/{app_id}/capability-links/{capability_id}",
    response_model=ApplicationCapabilityLink,
)
async def update_capability_link(
    app_id: str,
    capability_id: str,
    body: ApplicationCapabilityLinkUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    link = await astore.update_app_capability_link(app_id, capability_id, body, session)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.capability_link.update app_id=%s cap_id=%s actor=%s",
        app_id, capability_id, actor,
    )
    return link


@applications_router.delete(
    "/{app_id}/capability-links/{capability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_capability_link(
    app_id: str,
    capability_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_app_capability_link(app_id, capability_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.capability_link.delete app_id=%s cap_id=%s actor=%s",
        app_id, capability_id, actor,
    )


# ── Application–Technical Capability Links ────────────────────────────────────

@applications_router.get(
    "/{app_id}/technical-capability-links",
    response_model=ApplicationTechCapLinksResponse,
)
async def list_tech_cap_links(
    app_id: str, session: AsyncSession = Depends(_get_session)
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.list_app_tech_cap_links(app_id, session)


@applications_router.post(
    "/{app_id}/technical-capability-links",
    response_model=ApplicationTechCapLink,
    status_code=status.HTTP_201_CREATED,
)
async def create_tech_cap_link(
    app_id: str,
    body: ApplicationTechCapLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        link = await astore.create_app_tech_cap_link(app_id, body, session)
    except DuplicateAppTechCapLinkError:
        raise HTTPException(status_code=409, detail="Link already exists")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.tech_cap_link.create app_id=%s tc_id=%s usage=%s actor=%s",
        app_id, body.tech_cap_id, body.usage_type, actor,
    )
    return link


@applications_router.delete(
    "/{app_id}/technical-capability-links/{tc_id}/{usage_type}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_tech_cap_link(
    app_id: str,
    tc_id: str,
    usage_type: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_app_tech_cap_link(app_id, tc_id, usage_type, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.tech_cap_link.delete app_id=%s tc_id=%s usage=%s actor=%s",
        app_id, tc_id, usage_type, actor,
    )


# ── Application–Value Stream Stage Links ──────────────────────────────────────

@applications_router.get(
    "/{app_id}/stage-links", response_model=ApplicationStageLinksResponse
)
async def list_stage_links(
    app_id: str, session: AsyncSession = Depends(_get_session)
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.list_app_stage_links(app_id, session)


@applications_router.post(
    "/{app_id}/stage-links",
    response_model=ApplicationStageLink,
    status_code=status.HTTP_201_CREATED,
)
async def create_stage_link(
    app_id: str,
    body: ApplicationStageLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        link = await astore.create_app_stage_link(app_id, body, session)
    except DuplicateAppStageLinkError:
        raise HTTPException(status_code=409, detail="Link already exists")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.stage_link.create app_id=%s stage_id=%s actor=%s",
        app_id, body.stage_id, actor,
    )
    return link


@applications_router.delete(
    "/{app_id}/stage-links/{stage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_stage_link(
    app_id: str,
    stage_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_app_stage_link(app_id, stage_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.stage_link.delete app_id=%s stage_id=%s actor=%s",
        app_id, stage_id, actor,
    )


# ── Application–Domain Integrations ──────────────────────────────────────────

@applications_router.get(
    "/{app_id}/domain-integrations",
    response_model=ApplicationDomainIntegrationsResponse,
)
async def list_domain_integrations(
    app_id: str, session: AsyncSession = Depends(_get_session)
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.list_app_domain_integrations(app_id, session)


@applications_router.post(
    "/{app_id}/domain-integrations",
    response_model=ApplicationDomainIntegration,
    status_code=status.HTTP_201_CREATED,
)
async def create_domain_integration(
    app_id: str,
    body: ApplicationDomainIntegrationCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        link = await astore.create_app_domain_integration(app_id, body, session)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.domain_integration.create app_id=%s id=%s actor=%s",
        app_id, link.id, actor,
    )
    return link


@applications_router.delete(
    "/{app_id}/domain-integrations/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_domain_integration(
    app_id: str,
    link_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_app_domain_integration(app_id, link_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Domain integration not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.domain_integration.delete app_id=%s link_id=%s actor=%s",
        app_id, link_id, actor,
    )


# ── Application–Design Links ──────────────────────────────────────────────────

@applications_router.get(
    "/{app_id}/design-links", response_model=ApplicationDesignLinksResponse
)
async def list_design_links(
    app_id: str, session: AsyncSession = Depends(_get_session)
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.list_app_design_links(app_id, session)


@applications_router.post(
    "/{app_id}/design-links",
    response_model=ApplicationDesignLink,
    status_code=status.HTTP_201_CREATED,
)
async def create_design_link(
    app_id: str,
    body: ApplicationDesignLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        link = await astore.create_app_design_link(app_id, body, session)
    except DuplicateAppDesignLinkError:
        raise HTTPException(status_code=409, detail="Link already exists")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.design_link.create app_id=%s design_id=%s actor=%s",
        app_id, body.design_id, actor,
    )
    return link


@applications_router.delete(
    "/{app_id}/design-links/{design_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_design_link(
    app_id: str,
    design_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_app_design_link(app_id, design_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.design_link.delete app_id=%s design_id=%s actor=%s",
        app_id, design_id, actor,
    )


# ── Technical Capabilities ────────────────────────────────────────────────────

@tech_caps_router.get("", response_model=TechCapListResponse)
async def list_tech_caps(session: AsyncSession = Depends(_get_session)):
    return await astore.list_technical_capabilities(session)


@tech_caps_router.post(
    "", response_model=TechnicalCapability, status_code=status.HTTP_201_CREATED
)
async def create_tech_cap(
    body: TechnicalCapabilityCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        tc = await astore.create_technical_capability(body, session)
    except TechCapDepthError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "technical_capability.create id=%s name=%r level=%d actor=%s",
        tc.id, tc.name, tc.level, actor,
    )
    return tc


@tech_caps_router.get("/{tc_id}", response_model=TechnicalCapability)
async def get_tech_cap(tc_id: str, session: AsyncSession = Depends(_get_session)):
    tc = await astore.get_technical_capability(tc_id, session)
    if tc is None:
        raise HTTPException(status_code=404, detail=f"Technical capability {tc_id!r} not found")
    return tc


@tech_caps_router.patch("/{tc_id}", response_model=TechnicalCapability)
async def update_tech_cap(
    tc_id: str,
    body: TechnicalCapabilityUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    tc = await astore.update_technical_capability(tc_id, body, session)
    if tc is None:
        raise HTTPException(status_code=404, detail=f"Technical capability {tc_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("technical_capability.update id=%s actor=%s", tc_id, actor)
    return tc


@tech_caps_router.delete("/{tc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tech_cap(
    tc_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        deleted = await astore.delete_technical_capability(tc_id, session)
    except TechCapHasChildrenError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Technical capability {tc_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("technical_capability.delete id=%s actor=%s", tc_id, actor)


# ── Application Integrations ──────────────────────────────────────────────────

@integrations_router.get("", response_model=ApplicationIntegrationListResponse)
async def list_integrations(
    app_id: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(_get_session),
):
    return await astore.list_integrations(app_id, session)


@integrations_router.post(
    "", response_model=ApplicationIntegration, status_code=status.HTTP_201_CREATED
)
async def create_integration(
    body: ApplicationIntegrationCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        intg = await astore.create_integration(body, session)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "integration.create id=%s src=%s tgt=%s actor=%s",
        intg.id, body.source_app_id, body.target_app_id, actor,
    )
    return intg


@integrations_router.get("/{int_id}", response_model=ApplicationIntegration)
async def get_integration(int_id: str, session: AsyncSession = Depends(_get_session)):
    intg = await astore.get_integration(int_id, session)
    if intg is None:
        raise HTTPException(status_code=404, detail=f"Integration {int_id!r} not found")
    return intg


@integrations_router.patch("/{int_id}", response_model=ApplicationIntegration)
async def update_integration(
    int_id: str,
    body: ApplicationIntegrationUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    intg = await astore.update_integration(int_id, body, session)
    if intg is None:
        raise HTTPException(status_code=404, detail=f"Integration {int_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("integration.update id=%s actor=%s", int_id, actor)
    return intg


@integrations_router.delete("/{int_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    int_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_integration(int_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Integration {int_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("integration.delete id=%s actor=%s", int_id, actor)


# ── Transformation Initiatives (APM US6) ───────────────────────────────────────

@initiatives_router.get("", response_model=TransformationInitiativeListResponse)
async def list_initiatives(session: AsyncSession = Depends(_get_session)):
    return await astore.list_initiatives(session)


@initiatives_router.post(
    "", response_model=TransformationInitiative, status_code=status.HTTP_201_CREATED
)
async def create_initiative(
    body: TransformationInitiativeCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    initiative = await astore.create_initiative(body, session)
    await session.commit()
    logger.info(
        "initiative.create id=%s name=%r actor=%s",
        initiative.id, initiative.name, _get_actor(request),
    )
    return initiative


@initiatives_router.get("/{initiative_id}", response_model=TransformationInitiativeDetail)
async def get_initiative(initiative_id: str, session: AsyncSession = Depends(_get_session)):
    initiative = await astore.get_initiative(initiative_id, session)
    if initiative is None:
        raise HTTPException(
            status_code=404, detail=f"Transformation initiative {initiative_id!r} not found"
        )
    return initiative


@initiatives_router.patch("/{initiative_id}", response_model=TransformationInitiative)
async def update_initiative(
    initiative_id: str,
    body: TransformationInitiativeUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    initiative = await astore.update_initiative(initiative_id, body, session)
    if initiative is None:
        raise HTTPException(
            status_code=404, detail=f"Transformation initiative {initiative_id!r} not found"
        )
    await session.commit()
    logger.info("initiative.update id=%s actor=%s", initiative_id, _get_actor(request))
    return initiative


@initiatives_router.delete("/{initiative_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_initiative(
    initiative_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_initiative(initiative_id, session)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Transformation initiative {initiative_id!r} not found"
        )
    await session.commit()
    logger.info("initiative.delete id=%s actor=%s", initiative_id, _get_actor(request))
