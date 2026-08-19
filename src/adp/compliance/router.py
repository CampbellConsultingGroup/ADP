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

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.enforcement import require_action_dep
from adp.authz.permissions import is_permitted
from adp.authz.roles import ActionType
from adp.compliance import store as cstore
from adp.compliance.models import (
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
from adp.strategy.models import StrategicObjectiveListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_actor(request: Request) -> str:
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


async def _get_session():
    factory = cstore._get_session_factory()
    async with factory() as session:
        yield session


async def _get_strategy_session():
    """A strategy-scoped session (925-strategy-compliance-linkage, COMPLY-05 research.md D2),
    used only by the reverse-lookup GET .../objectives and GET .../initiatives routes below --
    mirrors adp/api/routers/designs.py's own _get_strategy_session() verbatim (ADP-d8u.2)."""
    from adp.strategy import store as sstore

    factory = sstore._get_session_factory()
    async with factory() as session:
        yield session


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


@router.put(
    "/controls/{control_id}/mappings/capabilities/{capability_id}", response_model=ControlMapping
)
async def upsert_capability_mapping(
    control_id: str,
    capability_id: str,
    body: ControlMappingWrite,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    mapping = await _translate_mapping_write_errors(
        cstore.upsert_capability_mapping(control_id, capability_id, body, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.upsert control_id=%s target_type=capability target_id=%s actor=%s",
        control_id, capability_id, actor,
    )
    return mapping


@router.delete(
    "/controls/{control_id}/mappings/capabilities/{capability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_capability_mapping(
    control_id: str,
    capability_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    await _translate_mapping_delete_errors(
        cstore.delete_capability_mapping(control_id, capability_id, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.delete control_id=%s target_type=capability target_id=%s actor=%s",
        control_id, capability_id, actor,
    )


@router.put(
    "/controls/{control_id}/mappings/applications/{application_id}", response_model=ControlMapping
)
async def upsert_application_mapping(
    control_id: str,
    application_id: str,
    body: ControlMappingWrite,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    mapping = await _translate_mapping_write_errors(
        cstore.upsert_application_mapping(control_id, application_id, body, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.upsert control_id=%s target_type=application target_id=%s actor=%s",
        control_id, application_id, actor,
    )
    return mapping


@router.delete(
    "/controls/{control_id}/mappings/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_application_mapping(
    control_id: str,
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    await _translate_mapping_delete_errors(
        cstore.delete_application_mapping(control_id, application_id, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.delete control_id=%s target_type=application target_id=%s actor=%s",
        control_id, application_id, actor,
    )


@router.put(
    "/controls/{control_id}/mappings/designs/{design_id}", response_model=ControlMapping
)
async def upsert_design_mapping(
    control_id: str,
    design_id: str,
    body: ControlMappingWrite,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    mapping = await _translate_mapping_write_errors(
        cstore.upsert_design_mapping(control_id, design_id, body, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.upsert control_id=%s target_type=design target_id=%s actor=%s",
        control_id, design_id, actor,
    )
    return mapping


@router.delete(
    "/controls/{control_id}/mappings/designs/{design_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_design_mapping(
    control_id: str,
    design_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    await _translate_mapping_delete_errors(
        cstore.delete_design_mapping(control_id, design_id, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.delete control_id=%s target_type=design target_id=%s actor=%s",
        control_id, design_id, actor,
    )


@router.put(
    "/controls/{control_id}/mappings/patterns/{pattern_id}", response_model=ControlMapping
)
async def upsert_pattern_mapping(
    control_id: str,
    pattern_id: str,
    body: ControlMappingWrite,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    mapping = await _translate_mapping_write_errors(
        cstore.upsert_pattern_mapping(control_id, pattern_id, body, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.upsert control_id=%s target_type=pattern target_id=%s actor=%s",
        control_id, pattern_id, actor,
    )
    return mapping


@router.delete(
    "/controls/{control_id}/mappings/patterns/{pattern_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_pattern_mapping(
    control_id: str,
    pattern_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    await _translate_mapping_delete_errors(
        cstore.delete_pattern_mapping(control_id, pattern_id, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.delete control_id=%s target_type=pattern target_id=%s actor=%s",
        control_id, pattern_id, actor,
    )


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
) -> StrategyInitiativeListResponse:
    """Shared handler body for the five GET routes below (spec.md FR-007 reverse direction)."""
    from adp.strategy import store as sstore

    if not await sstore.control_exists(control_id, strategy_session):
        raise HTTPException(status_code=404, detail=f"Control {control_id!r} not found")

    from adp.strategy import initiatives as sinit

    return await sinit.list_initiatives_for_control_mapping(
        control_id, target_type, target_id, strategy_session
    )


@router.get(
    "/controls/{control_id}/mappings/capabilities/{capability_id}/initiatives",
    response_model=StrategyInitiativeListResponse,
)
async def list_capability_mapping_initiatives(
    control_id: str,
    capability_id: str,
    strategy_session: AsyncSession = Depends(_get_strategy_session),
):
    return await _list_control_mapping_initiatives(
        control_id, MappingTargetType.CAPABILITY, capability_id, strategy_session
    )


@router.get(
    "/controls/{control_id}/mappings/applications/{application_id}/initiatives",
    response_model=StrategyInitiativeListResponse,
    dependencies=[Depends(_require_governance_read)],
)
async def list_application_mapping_initiatives(
    control_id: str,
    application_id: str,
    strategy_session: AsyncSession = Depends(_get_strategy_session),
):
    return await _list_control_mapping_initiatives(
        control_id, MappingTargetType.APPLICATION, application_id, strategy_session
    )


@router.get(
    "/controls/{control_id}/mappings/designs/{design_id}/initiatives",
    response_model=StrategyInitiativeListResponse,
)
async def list_design_mapping_initiatives(
    control_id: str,
    design_id: str,
    strategy_session: AsyncSession = Depends(_get_strategy_session),
):
    return await _list_control_mapping_initiatives(
        control_id, MappingTargetType.DESIGN, design_id, strategy_session
    )


@router.get(
    "/controls/{control_id}/mappings/patterns/{pattern_id}/initiatives",
    response_model=StrategyInitiativeListResponse,
)
async def list_pattern_mapping_initiatives(
    control_id: str,
    pattern_id: str,
    strategy_session: AsyncSession = Depends(_get_strategy_session),
):
    return await _list_control_mapping_initiatives(
        control_id, MappingTargetType.PATTERN, pattern_id, strategy_session
    )


@router.get(
    "/controls/{control_id}/mappings/organization/initiatives",
    response_model=StrategyInitiativeListResponse,
)
async def list_organization_mapping_initiatives(
    control_id: str,
    strategy_session: AsyncSession = Depends(_get_strategy_session),
):
    return await _list_control_mapping_initiatives(
        control_id, MappingTargetType.ORGANIZATION, None, strategy_session
    )
