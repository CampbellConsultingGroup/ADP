"""Compliance Framework & Control Registry API (COMPLY-01) + Control Mappings API (COMPLY-02).

GET/POST/PATCH/DELETE /api/v1/compliance/frameworks               — framework registry
POST/GET/DELETE       /api/v1/compliance/frameworks/{id}/application-phases[/{phase_id}]
                         — staged application dates (COMPLY-01a)
POST/GET/DELETE       /api/v1/compliance/frameworks/{id}/amendments[/{amendment_id}]
                         — amending legal instruments (COMPLY-01a)
POST/PATCH/DELETE     /api/v1/compliance/frameworks/{id}/controls — control catalog
PATCH/DELETE          /api/v1/compliance/controls/{id}            — individual control edit/delete
PUT/DELETE            /api/v1/compliance/controls/{id}/mappings/{capabilities|applications|
                         designs|patterns}/{target_id} — entity-targeted mapping upsert/remove
PUT/DELETE            /api/v1/compliance/controls/{id}/mappings/organization — estate-wide mapping
GET                   /api/v1/compliance/controls/{id}/mappings   — forward lookup (all 5 target
                         shapes; Application-targeted rows filtered per D2 — see below)

ART-V: write operations require ActionType.WRITE_COMPLIANCE (Clarification Session 2026-08-17,
        research.md D4); already covers every mapping route below via the existing
        `/api/v1/compliance/` prefix rule in enforcement.py -- no new rule needed for COMPLY-02.
        Reads are open EXCEPT Application-targeted mappings, which require
        READ_APPLICATION_GOVERNANCE (Clarification Session 2026-08-18; research.md D2): the
        forward lookup filters those rows out inline for a caller lacking the permission rather
        than 403ing the whole response, since a Control's other mappings must stay visible.
ART-VI: mutations emit structured log entries (actor, entity, action), matching
        adp.business.router's existing convention.
ART-IX: created_at recorded on every mapping (no updated_at -- spec.md 922 User Story 2
        Acceptance Scenario 1: the prior status is not separately preserved); no audit_entries
        write, matching COMPLY-01's own confirmed precedent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from adp.api.common import named_path_param, session_dependency
from adp.auth.actor import actor_of
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.enforcement import require_action_dep
from adp.authz.permissions import is_permitted
from adp.authz.roles import ActionType
from adp.compliance import store as cstore
from adp.compliance.models import (
    AgentComplianceMappings,
    AgentComplianceStatus,
    AgentComplianceStatuses,
    AmendmentNotFoundError,
    ApplicationPhaseNotFoundError,
    ComplianceSummaryResponse,
    Control,
    ControlCreate,
    ControlMapping,
    ControlMappingListResponse,
    ControlMappingWrite,
    ControlNotFoundError,
    ControlUpdate,
    CrossFrameworkParentError,
    CyclicParentError,
    DuplicateControlCodeError,
    DuplicateRegulationNumberError,
    FrameworkAmendment,
    FrameworkAmendmentCreate,
    FrameworkAmendmentListResponse,
    FrameworkApplicationPhase,
    FrameworkApplicationPhaseCreate,
    FrameworkApplicationPhaseListResponse,
    FrameworkCoverageRollup,
    InvalidPatternTargetError,
    MappingNotFoundError,
    MappingTargetNotFoundError,
    MappingTargetType,
    ParentNotFoundError,
    RegulatoryFramework,
    RegulatoryFrameworkCreate,
    RegulatoryFrameworkDetail,
    RegulatoryFrameworkListResponse,
    RegulatoryFrameworkUpdate,
)
from adp.strategy.initiatives import StrategyInitiativeListResponse
from adp.strategy.models import StrategicObjectiveListResponse, StrategicThemeListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_actor(request: Request) -> str:
    return actor_of(request)


_get_session = session_dependency("adp.compliance.store")


# A strategy-scoped session (925-strategy-compliance-linkage, COMPLY-05 research.md D2), used only
# by the reverse-lookup GET .../objectives and GET .../initiatives routes below -- mirrors
# adp/api/routers/designs.py's own _get_strategy_session() verbatim (ADP-d8u.2).
_get_strategy_session = session_dependency("adp.strategy.store")


# ── Regulatory Frameworks ─────────────────────────────────────────────────────

@router.get("/frameworks", response_model=RegulatoryFrameworkListResponse)
async def list_frameworks(session: AsyncSession = Depends(_get_session)):
    items = await cstore.list_frameworks(session)
    return RegulatoryFrameworkListResponse(items=items, total=len(items))


@router.post(
    "/frameworks", response_model=RegulatoryFramework, status_code=status.HTTP_201_CREATED
)
async def create_framework(
    body: RegulatoryFrameworkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        fw = await cstore.create_framework(body, session)
    except DuplicateRegulationNumberError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()

    actor = _get_actor(request)
    logger.info("compliance.framework.create id=%s name=%r actor=%s", fw.id, fw.name, actor)
    return fw


@router.get("/frameworks/{framework_id}", response_model=RegulatoryFrameworkDetail)
async def get_framework_detail(framework_id: str, session: AsyncSession = Depends(_get_session)):
    detail = await cstore.get_framework_detail(framework_id, session)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    return detail


@router.get("/frameworks/{framework_id}/rollup", response_model=FrameworkCoverageRollup)
async def get_framework_rollup(
    framework_id: str,
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Framework coverage rollup (COMPLY-04 US1, FR-001/002/003): a live count of entities at
    each compliance status, scoped to this framework's own controls, plus its estate-wide
    obligation status as a separate line if one exists. Application-targeted entities are
    excluded from the counts for a caller lacking READ_APPLICATION_GOVERNANCE (FR-007) --
    never a 403, unlike GET /applications/{id}/compliance-mappings's own route-level gate
    (research.md D2 deliberately mirrors list_control_mappings' filtering precedent instead)."""
    include_application = is_permitted(user.role, ActionType.READ_APPLICATION_GOVERNANCE)
    rollup = await cstore.get_framework_coverage_rollup(framework_id, include_application, session)
    if rollup is None:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    return rollup


@router.patch("/frameworks/{framework_id}", response_model=RegulatoryFramework)
async def update_framework(
    framework_id: str,
    body: RegulatoryFrameworkUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        fw = await cstore.update_framework(framework_id, body, session)
    except DuplicateRegulationNumberError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if fw is None:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("compliance.framework.update id=%s actor=%s", framework_id, actor)
    return fw


@router.delete("/frameworks/{framework_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_framework(
    framework_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await cstore.delete_framework(framework_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("compliance.framework.delete id=%s actor=%s", framework_id, actor)


# ── Framework Application Phases & Amendments (COMPLY-01a) ──────────────────────

@router.post(
    "/frameworks/{framework_id}/application-phases",
    response_model=FrameworkApplicationPhase,
    status_code=status.HTTP_201_CREATED,
)
async def create_application_phase(
    framework_id: str,
    body: FrameworkApplicationPhaseCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    if await cstore.get_framework(framework_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    phase = await cstore.add_application_phase(framework_id, body, session)
    await session.commit()

    actor = _get_actor(request)
    logger.info(
        "compliance.framework.application_phase.create framework_id=%s id=%s actor=%s",
        framework_id, phase.id, actor,
    )
    return phase


@router.get(
    "/frameworks/{framework_id}/application-phases",
    response_model=FrameworkApplicationPhaseListResponse,
)
async def list_application_phases(
    framework_id: str, session: AsyncSession = Depends(_get_session)
):
    if await cstore.get_framework(framework_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    items = await cstore.list_application_phases(framework_id, session)
    return FrameworkApplicationPhaseListResponse(items=items, total=len(items))


@router.delete(
    "/frameworks/{framework_id}/application-phases/{phase_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_application_phase(
    framework_id: str,
    phase_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        await cstore.delete_application_phase(framework_id, phase_id, session)
    except ApplicationPhaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()

    actor = _get_actor(request)
    logger.info(
        "compliance.framework.application_phase.delete framework_id=%s id=%s actor=%s",
        framework_id, phase_id, actor,
    )


@router.post(
    "/frameworks/{framework_id}/amendments",
    response_model=FrameworkAmendment,
    status_code=status.HTTP_201_CREATED,
)
async def create_amendment(
    framework_id: str,
    body: FrameworkAmendmentCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    if await cstore.get_framework(framework_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    amendment = await cstore.add_amendment(framework_id, body, session)
    await session.commit()

    actor = _get_actor(request)
    logger.info(
        "compliance.framework.amendment.create framework_id=%s id=%s actor=%s",
        framework_id, amendment.id, actor,
    )
    return amendment


@router.get(
    "/frameworks/{framework_id}/amendments", response_model=FrameworkAmendmentListResponse
)
async def list_amendments(framework_id: str, session: AsyncSession = Depends(_get_session)):
    if await cstore.get_framework(framework_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    items = await cstore.list_amendments(framework_id, session)
    return FrameworkAmendmentListResponse(items=items, total=len(items))


@router.delete(
    "/frameworks/{framework_id}/amendments/{amendment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_amendment(
    framework_id: str,
    amendment_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        await cstore.delete_amendment(framework_id, amendment_id, session)
    except AmendmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()

    actor = _get_actor(request)
    logger.info(
        "compliance.framework.amendment.delete framework_id=%s id=%s actor=%s",
        framework_id, amendment_id, actor,
    )


# ── Compliance Rollup Reporting (COMPLY-04 US2) ──────────────────────────────

@router.get("/summary", response_model=ComplianceSummaryResponse)
async def get_compliance_summary(
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Platform-wide compliance summary, backing the Overview dashboard's Compliance domain
    card (FR-004/005). Same Application-exclusion rule as the framework rollup above (FR-007)."""
    include_application = is_permitted(user.role, ActionType.READ_APPLICATION_GOVERNANCE)
    return await cstore.get_compliance_summary(include_application, session)


# ── Controls ──────────────────────────────────────────────────────────────────

@router.post(
    "/frameworks/{framework_id}/controls",
    response_model=Control,
    status_code=status.HTTP_201_CREATED,
)
async def create_control(
    framework_id: str,
    body: ControlCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    if await cstore.get_framework(framework_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    try:
        ctrl = await cstore.create_control(framework_id, body, session)
        await session.commit()
    except ParentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (CrossFrameworkParentError, CyclicParentError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DuplicateControlCodeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    actor = _get_actor(request)
    logger.info(
        "compliance.control.create id=%s framework_id=%s code=%r actor=%s",
        ctrl.id, framework_id, ctrl.code, actor,
    )
    return ctrl


@router.patch("/controls/{control_id}", response_model=Control)
async def update_control(
    control_id: str,
    body: ControlUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        ctrl = await cstore.update_control(control_id, body, session)
    except ParentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (CrossFrameworkParentError, CyclicParentError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DuplicateControlCodeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if ctrl is None:
        raise HTTPException(status_code=404, detail=f"Control {control_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("compliance.control.update id=%s actor=%s", control_id, actor)
    return ctrl


@router.delete("/controls/{control_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_control(
    control_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await cstore.delete_control(control_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Control {control_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("compliance.control.delete id=%s actor=%s", control_id, actor)


# ── Control Mappings (COMPLY-02) ────────────────────────────────────────────
# Writes/forward-lookup live here (Control's own package -- research.md D7, mirrors
# adp.strategy.router owning Objective-side link writes); reverse-lookups (given a target
# entity, list its mapped controls) live on each target's own router instead
# (business/application/designs/knowledge -- see those routers' own compliance-mappings routes).

async def _translate_mapping_write_errors(coro):
    """Shared exception -> HTTP translation for every upsert route below, avoiding five
    near-identical try/except blocks (research.md D7's own "shared internal helper" note)."""
    try:
        return await coro
    except ControlNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MappingTargetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidPatternTargetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _translate_mapping_delete_errors(coro) -> None:
    try:
        await coro
    except MappingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ADP-blp.27: the five entity targets share one pair of handlers. Each used to have its own
# PUT and DELETE (and, further down, its own "initiatives" GET), identical but for the noun,
# so a new target meant another three near-copies here. A target is now one line in
# _ENTITY_MAPPING_ROUTES. The estate-wide (organization) routes stay separate: no target id.

@dataclass(frozen=True)
class _EntityMappingRoute:
    target_type: MappingTargetType
    segment: str
    """The plural path segment, e.g. "capabilities"."""
    param: str
    """The target's path parameter name, e.g. "capability_id"."""
    initiatives_description: str | None = None
    initiatives_dependencies: tuple[Any, ...] = ()
    """Extra dependencies on the reverse "initiatives" route (application: governance read)."""


def _register_entity_mapping_writes(spec: _EntityMappingRoute) -> None:
    noun = spec.target_type.value
    path = f"/controls/{{control_id}}/mappings/{spec.segment}/{{{spec.param}}}"

    async def upsert_mapping(
        control_id: str,
        target_id: str,
        body: ControlMappingWrite,
        request: Request,
        session: AsyncSession = Depends(_get_session),
    ):
        mapping = await _translate_mapping_write_errors(
            cstore.upsert_entity_mapping(spec.target_type, control_id, target_id, body, session)
        )
        await session.commit()
        logger.info(
            "compliance.mapping.upsert control_id=%s target_type=%s target_id=%s actor=%s",
            control_id, noun, target_id, _get_actor(request),
        )
        return mapping

    async def delete_mapping(
        control_id: str,
        target_id: str,
        request: Request,
        session: AsyncSession = Depends(_get_session),
    ):
        await _translate_mapping_delete_errors(
            cstore.delete_entity_mapping(spec.target_type, control_id, target_id, session)
        )
        await session.commit()
        logger.info(
            "compliance.mapping.delete control_id=%s target_type=%s target_id=%s actor=%s",
            control_id, noun, target_id, _get_actor(request),
        )

    router.add_api_route(
        path, named_path_param(upsert_mapping, "target_id", spec.param), methods=["PUT"],
        response_model=ControlMapping,
        name=f"upsert_{noun}_mapping",
    )
    router.add_api_route(
        path, named_path_param(delete_mapping, "target_id", spec.param), methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
        name=f"delete_{noun}_mapping",
    )


# ── Agent mappings (944-agent-traceability, ADP-12x, US2) ────────────────────
# The sixth target. Agents are not Applications, so READ_APPLICATION_GOVERNANCE never applies.
# The agent-side read lives here rather than on the agentic router, which imports no other
# domain package (research.md R5).

_MAX_STATUS_IDS = 200


@router.get("/agents/statuses", response_model=AgentComplianceStatuses)
async def agent_compliance_statuses(
    ids: str = "",
    session: AsyncSession = Depends(_get_session),
):
    """Each agent's derived status in one call (FR-009a), for a solution's Agents tab."""
    agent_ids = list(dict.fromkeys(i.strip() for i in ids.split(",") if i.strip()))
    if len(agent_ids) > _MAX_STATUS_IDS:
        raise HTTPException(
            status_code=422, detail=f"At most {_MAX_STATUS_IDS} agent ids per request"
        )
    statuses = await cstore.get_agent_statuses(agent_ids, session)
    return AgentComplianceStatuses(
        items=[AgentComplianceStatus(agent_id=a, status=statuses[a]) for a in agent_ids]
    )


@router.get("/agents/{agent_id}/mappings", response_model=AgentComplianceMappings)
async def agent_compliance_mappings(
    agent_id: str,
    session: AsyncSession = Depends(_get_session),
):
    if not await cstore.agent_exists(agent_id, session):
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    items = await cstore.list_mappings_for_agent(agent_id, session)
    status_ = cstore.compute_compliance_status([m.compliance_status for m in items])
    return AgentComplianceMappings(items=items, total=len(items), status=status_)


@router.put("/controls/{control_id}/mappings/organization", response_model=ControlMapping)
async def upsert_organization_mapping(
    control_id: str,
    body: ControlMappingWrite,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    mapping = await _translate_mapping_write_errors(
        cstore.upsert_organization_mapping(control_id, body, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.upsert control_id=%s target_type=organization actor=%s",
        control_id, actor,
    )
    return mapping


@router.delete(
    "/controls/{control_id}/mappings/organization", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_organization_mapping(
    control_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    await _translate_mapping_delete_errors(
        cstore.delete_organization_mapping(control_id, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.delete control_id=%s target_type=organization actor=%s",
        control_id, actor,
    )


@router.get("/controls/{control_id}/mappings", response_model=ControlMappingListResponse)
async def list_control_mappings(
    control_id: str,
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Forward lookup (FR-011): every mapping for this Control, across all five target
    shapes. Application-targeted rows are filtered out inline for a caller lacking
    READ_APPLICATION_GOVERNANCE (research.md D2) -- NOT a blanket require_action_dep on the
    whole route, since Capability/Design/Pattern/organization rows must stay visible
    regardless (spec.md 922 User Story 3 Acceptance Scenario 3; SC-006)."""
    try:
        mappings = await cstore.list_mappings_for_control(control_id, session)
    except ControlNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not is_permitted(user.role, ActionType.READ_APPLICATION_GOVERNANCE):
        mappings = [m for m in mappings if m.target_type != MappingTargetType.APPLICATION]

    return ControlMappingListResponse(items=mappings, total=len(mappings))


# ── Reverse lookups — Strategy domain (925-strategy-compliance-linkage, COMPLY-05) ──────────────
# Mirrors adp/api/routers/designs.py's own cross-package reverse-lookup precedent (ADP-d8u.2):
# store/list functions live in adp.strategy (research.md D2), called here via _get_strategy_session
# rather than duplicated. control_exists() is checked against adp.strategy.store's own mirror of
# the controls table, not cstore -- these routes never touch adp.compliance.store at all.


class _ObjectiveRef(BaseModel):
    id: str
    statement: str


class _ControlObjectives(BaseModel):
    control_id: str
    objectives: list[_ObjectiveRef]


class FrameworkControlObjectivesResponse(BaseModel):
    items: list[_ControlObjectives]


@router.get(
    "/frameworks/{framework_id}/control-objectives",
    response_model=FrameworkControlObjectivesResponse,
)
async def list_framework_control_objectives(
    framework_id: str,
    strategy_session: AsyncSession = Depends(_get_strategy_session),
):
    """The objectives linked to each control of a framework, in one request (ADP-blp.35).

    The bulk form of GET /controls/{control_id}/objectives below, for the control tree, which
    otherwise asks once per control. Controls with no linked objective are left out."""
    from adp.strategy import store as sstore

    if not await sstore.framework_exists(framework_id, strategy_session):
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    by_control = await sstore.list_control_objectives_for_framework(framework_id, strategy_session)
    return FrameworkControlObjectivesResponse(
        items=[
            _ControlObjectives(
                control_id=control_id,
                objectives=[_ObjectiveRef(id=oid, statement=text) for oid, text in objectives],
            )
            for control_id, objectives in by_control.items()
        ]
    )


@router.get("/controls/{control_id}/objectives", response_model=StrategicObjectiveListResponse)
async def list_control_objectives(
    control_id: str,
    strategy_session: AsyncSession = Depends(_get_strategy_session),
):
    """Reverse lookup (spec.md FR-003): every Strategic Objective linked to this Control.
    Ungated beyond general platform read access -- an abstract Control carries no
    target-entity sensitivity of its own, unlike the ControlMapping-scoped routes below."""
    from adp.strategy import store as sstore

    if not await sstore.control_exists(control_id, strategy_session):
        raise HTTPException(status_code=404, detail=f"Control {control_id!r} not found")
    return await sstore.list_objectives_for_control(control_id, strategy_session)


# ── Reverse lookup — 927-theme-framework-mapping (COMPLY-05, link #3) ────────────────────────────


@router.get("/frameworks/{framework_id}/themes", response_model=StrategicThemeListResponse)
async def list_framework_themes(
    framework_id: str,
    strategy_session: AsyncSession = Depends(_get_strategy_session),
):
    """Reverse lookup (spec.md FR-005): every Strategic Theme tagged onto this Framework.
    Ungated beyond general platform read access -- a RegulatoryFramework carries no
    target-entity sensitivity of its own, mirroring list_control_objectives above."""
    from adp.strategy import store as sstore

    if not await sstore.framework_exists(framework_id, strategy_session):
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    return await sstore.list_themes_for_framework(framework_id, strategy_session)


# Decorator-level dependency, applied only to the Application-targeted route below (spec.md
# FR-013) -- mirrors adp.application.router's own `_require_governance_read` precedent exactly.
# This runs (and can 403) BEFORE the route's own strategy_session dependency is ever asked to do
# anything beyond construct a lazy SQLAlchemy engine (no real query, no live DB required to test
# the denial path -- tests/authz/test_enforcement.py's own no-DB-required design).
_require_governance_read = require_action_dep(ActionType.READ_APPLICATION_GOVERNANCE)


async def _list_control_mapping_initiatives(
    control_id: str,
    target_type: MappingTargetType,
    target_id: str | None,
    strategy_session: AsyncSession,
    user: AuthenticatedUser,
) -> StrategyInitiativeListResponse:
    """Shared handler body for the six GET routes below (spec.md FR-007 reverse direction).

    ADP-blp.4: each returned initiative embeds all of its linked control mappings, so a caller
    without READ_APPLICATION_GOVERNANCE gets them with the Application-targeted rows removed.
    """
    from adp.strategy import store as sstore

    if not await sstore.control_exists(control_id, strategy_session):
        raise HTTPException(status_code=404, detail=f"Control {control_id!r} not found")

    from adp.strategy import initiatives as sinit

    listing = await sinit.list_initiatives_for_control_mapping(
        control_id, target_type, target_id, strategy_session
    )
    if is_permitted(user.role, ActionType.READ_APPLICATION_GOVERNANCE):
        return listing
    return listing.model_copy(
        update={"items": [sinit.without_application_mappings(i) for i in listing.items]}
    )


def _register_entity_mapping_initiatives(spec: _EntityMappingRoute) -> None:
    async def list_mapping_initiatives(
        control_id: str,
        target_id: str,
        strategy_session: AsyncSession = Depends(_get_strategy_session),
        user: AuthenticatedUser = Depends(get_current_user),
    ):
        return await _list_control_mapping_initiatives(
            control_id, spec.target_type, target_id, strategy_session, user
        )

    router.add_api_route(
        f"/controls/{{control_id}}/mappings/{spec.segment}/{{{spec.param}}}/initiatives",
        named_path_param(list_mapping_initiatives, "target_id", spec.param),
        methods=["GET"],
        description=spec.initiatives_description,
        response_model=StrategyInitiativeListResponse,
        dependencies=list(spec.initiatives_dependencies),
        name=f"list_{spec.target_type.value}_mapping_initiatives",
    )


# Agent mappings (and the initiatives remediating them, ADP-321) are never filtered by
# READ_APPLICATION_GOVERNANCE: agents are not Applications. Only the application target's
# reverse lookup carries that gate.
_ENTITY_MAPPING_ROUTES = (
    _EntityMappingRoute(MappingTargetType.CAPABILITY, "capabilities", "capability_id"),
    _EntityMappingRoute(
        MappingTargetType.APPLICATION, "applications", "application_id",
        initiatives_dependencies=(Depends(_require_governance_read),),
    ),
    _EntityMappingRoute(MappingTargetType.DESIGN, "designs", "design_id"),
    _EntityMappingRoute(MappingTargetType.PATTERN, "patterns", "pattern_id"),
    _EntityMappingRoute(
        MappingTargetType.AGENT, "agents", "agent_id",
        initiatives_description=(
            "ADP-321: initiatives remediating an agent's mapping. Like the agent mapping itself, "
            "never\nfiltered by READ_APPLICATION_GOVERNANCE."
        ),
    ),
)

for _spec in _ENTITY_MAPPING_ROUTES:
    _register_entity_mapping_writes(_spec)
    _register_entity_mapping_initiatives(_spec)


@router.get(
    "/controls/{control_id}/mappings/organization/initiatives",
    response_model=StrategyInitiativeListResponse,
)
async def list_organization_mapping_initiatives(
    control_id: str,
    strategy_session: AsyncSession = Depends(_get_strategy_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    return await _list_control_mapping_initiatives(
        control_id, MappingTargetType.ORGANIZATION, None, strategy_session, user
    )
