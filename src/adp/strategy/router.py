"""Strategic Objective Capture API — ADP-d8u.1, extended by ADP-d8u.5.

POST/GET /api/v1/strategy/themes
GET/PATCH/DELETE /api/v1/strategy/themes/{id}
POST/GET /api/v1/strategy/objectives
GET/PUT/DELETE /api/v1/strategy/objectives/{id}
POST/DELETE /api/v1/strategy/objectives/{id}/capabilities[/{capability_id}]
POST/DELETE /api/v1/strategy/objectives/{id}/value-streams[/{value_stream_id}]
POST/GET /api/v1/strategy/objectives/{id}/progress
PATCH /api/v1/strategy/objectives/{id}/progress/{as_of_date}
PATCH /api/v1/strategy/objectives/{id}/abandon
POST/DELETE /api/v1/strategy/objectives/{id}/controls[/{control_id}]
    (925-strategy-compliance-linkage)
POST/DELETE /api/v1/strategy/initiatives/{id}/control-mappings/{capabilities|applications|
    designs|patterns}/{control_id}/{target_id}, .../organization/{control_id}
    (925-strategy-compliance-linkage, COMPLY-05)

Write endpoints are gated by ActionType.WRITE_BUSINESS_ARCH via the app-level
`/api/v1/strategy/` prefix rule in adp.authz.enforcement (research.md
Decision 3) -- mirroring adp.diagrams.router, no inline permission-check
helper is needed here (unlike adp.business.router's `_require_write_
business_arch`, which exists only for a defense-in-depth re-check inside
the agent-review confirm flow, not as a general per-route pattern).

Cross-package validation (research.md Decision 2): the link endpoints take a
*second*, adp.business-scoped session (mirrors adp.business.router's own
`_get_application_session` and adp.chat.router's `_get_biz_session_factory`)
and call adp.business.store.get_capability/get_value_stream directly before
writing a link row -- never a duplicated or bypassed existence check.

ADP-d8u.5 plan.md Ground-Truth Correction 4: there is no design_id/design_
version here for a real AuditEntry row (audit_entries is tightly coupled to
those). Consistent with adp.business/adp.application's own established
precedent (adp.agents.provenance's documented rationale), ART-IX here is
satisfied by structured logger.info(...) calls -- this module's first.
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.compliance.models import MappingTargetType
from adp.strategy import initiatives as sinit
from adp.strategy import store as sstore
from adp.strategy.initiatives import (
    ObjectiveDependenciesResponse,
    ObjectiveDependencyCreate,
    StrategyInitiative,
    StrategyInitiativeCreate,
    StrategyInitiativeListResponse,
    StrategyInitiativeUpdate,
)
from adp.strategy.models import (
    AbandonRequest,
    ObjectiveApplicationLinkCreate,
    ObjectiveCapabilityLinkCreate,
    ObjectiveControlLinkCreate,
    ObjectiveDesignLinkCreate,
    ObjectiveProgressCreate,
    ObjectiveProgressEntry,
    ObjectiveProgressListResponse,
    ObjectiveProgressUpdate,
    ObjectiveValueStreamLinkCreate,
    StrategicObjective,
    StrategicObjectiveCreate,
    StrategicObjectiveListResponse,
    StrategicObjectiveUpdate,
    StrategicSummaryResponse,
    StrategicTheme,
    StrategicThemeCreate,
    StrategicThemeListResponse,
    StrategicThemeUpdate,
    StrategyHeatMapResponse,
    ThemeFrameworkLinkCreate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/strategy", tags=["strategy"])


# ── Shared helpers (mirrors adp.business.router's _get_actor exactly) ────────


def _get_actor(request: Request) -> str:
    from adp.auth.models import UNAUTHENTICATED_USER

    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


async def _get_session():
    factory = sstore._get_session_factory()
    async with factory() as session:
        yield session


async def _get_business_session():
    """A second, adp.business-scoped session for link-target existence
    checks (research.md Decision 2). Mirrors adp.business.router's own
    `_get_application_session`."""
    from adp.business import store as bstore

    factory = bstore._get_session_factory()
    async with factory() as session:
        yield session


# ── Themes ────────────────────────────────────────────────────────────────────


@router.post("/themes", response_model=StrategicTheme, status_code=status.HTTP_201_CREATED)
async def create_theme(
    body: StrategicThemeCreate, session: AsyncSession = Depends(_get_session)
):
    try:
        theme = await sstore.create_theme(body, session)
    except sstore.DuplicateThemeNameError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    return theme


@router.get("/themes", response_model=StrategicThemeListResponse)
async def list_themes(session: AsyncSession = Depends(_get_session)):
    return await sstore.list_themes(session)


@router.get("/themes/{theme_id}", response_model=StrategicTheme)
async def get_theme(theme_id: str, session: AsyncSession = Depends(_get_session)):
    theme = await sstore.get_theme(theme_id, session)
    if theme is None:
        raise HTTPException(status_code=404, detail=f"Theme {theme_id!r} not found")
    return theme


@router.patch("/themes/{theme_id}", response_model=StrategicTheme)
async def update_theme(
    theme_id: str, body: StrategicThemeUpdate, session: AsyncSession = Depends(_get_session)
):
    theme = await sstore.update_theme(theme_id, body, session)
    if theme is None:
        raise HTTPException(status_code=404, detail=f"Theme {theme_id!r} not found")
    await session.commit()
    return theme


@router.delete("/themes/{theme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_theme(
    theme_id: str, raw_request: Request, session: AsyncSession = Depends(_get_session)
):
    if await sstore.get_theme(theme_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Theme {theme_id!r} not found")
    try:
        await sstore.delete_theme(theme_id, session)
    except sstore.ThemeInUseError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    actor = _get_actor(raw_request)
    logger.info("strategy.theme.delete theme_id=%s actor=%s", theme_id, actor)


# ── Theme <-> Framework links (927-theme-framework-mapping, COMPLY-05 link #3) ──────────────────


@router.post("/themes/{theme_id}/frameworks", status_code=status.HTTP_201_CREATED)
async def link_theme_framework(
    theme_id: str,
    body: ThemeFrameworkLinkCreate,
    session: AsyncSession = Depends(_get_session),
):
    framework_id = body.framework_id
    if not await sstore.theme_exists(theme_id, session):
        raise HTTPException(status_code=404, detail=f"Theme {theme_id!r} not found")
    if not await sstore.framework_exists(framework_id, session):
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    try:
        await sstore.link_theme_framework(theme_id, framework_id, session)
    except sstore.DuplicateLinkError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    logger.info(
        "strategy.theme.framework.link theme_id=%s framework_id=%s", theme_id, framework_id
    )
    return await sstore.list_framework_ids_for_theme(theme_id, session)


@router.delete(
    "/themes/{theme_id}/frameworks/{framework_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_theme_framework(
    theme_id: str, framework_id: str, session: AsyncSession = Depends(_get_session)
):
    try:
        await sstore.unlink_theme_framework(theme_id, framework_id, session)
    except sstore.LinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    logger.info(
        "strategy.theme.framework.unlink theme_id=%s framework_id=%s", theme_id, framework_id
    )


# ── Objectives ────────────────────────────────────────────────────────────────


@router.post(
    "/objectives", response_model=StrategicObjective, status_code=status.HTTP_201_CREATED
)
async def create_objective(
    body: StrategicObjectiveCreate, session: AsyncSession = Depends(_get_session)
):
    if not await sstore.theme_exists(body.theme_id, session):
        raise HTTPException(status_code=404, detail=f"Theme {body.theme_id!r} not found")
    objective = await sstore.create_objective(body, session)
    await session.commit()
    return objective


@router.get("/objectives", response_model=StrategicObjectiveListResponse)
async def list_objectives(session: AsyncSession = Depends(_get_session)):
    return await sstore.list_objectives(session)


@router.get("/objectives/{objective_id}", response_model=StrategicObjective)
async def get_objective(objective_id: str, session: AsyncSession = Depends(_get_session)):
    objective = await sstore.get_objective(objective_id, session)
    if objective is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    return objective


@router.put("/objectives/{objective_id}", response_model=StrategicObjective)
async def update_objective(
    objective_id: str,
    body: StrategicObjectiveUpdate,
    session: AsyncSession = Depends(_get_session),
):
    if body.theme_id is not None and not await sstore.theme_exists(body.theme_id, session):
        raise HTTPException(status_code=404, detail=f"Theme {body.theme_id!r} not found")
    objective = await sstore.update_objective(objective_id, body, session)
    if objective is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    await session.commit()
    return objective


@router.delete("/objectives/{objective_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_objective(objective_id: str, session: AsyncSession = Depends(_get_session)):
    deleted = await sstore.delete_objective(objective_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    await session.commit()


# ── Progress (ADP-d8u.5) ─────────────────────────────────────────────────────


@router.post(
    "/objectives/{objective_id}/progress",
    response_model=ObjectiveProgressEntry,
    status_code=status.HTTP_201_CREATED,
)
async def create_progress_entry(
    objective_id: str,
    body: ObjectiveProgressCreate,
    raw_request: Request,
    session: AsyncSession = Depends(_get_session),
):
    if await sstore.get_objective(objective_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    actor = _get_actor(raw_request)
    try:
        entry = await sstore.create_progress_entry(objective_id, body, actor, session)
    except sstore.DuplicateProgressEntryError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    return entry


@router.get("/objectives/{objective_id}/progress", response_model=ObjectiveProgressListResponse)
async def list_progress_entries(
    objective_id: str, session: AsyncSession = Depends(_get_session)
):
    if await sstore.get_objective(objective_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    return await sstore.list_progress_entries(objective_id, session)


@router.patch(
    "/objectives/{objective_id}/progress/{as_of_date}", response_model=ObjectiveProgressEntry
)
async def update_progress_entry(
    objective_id: str,
    as_of_date: date,
    body: ObjectiveProgressUpdate,
    raw_request: Request,
    session: AsyncSession = Depends(_get_session),
):
    """FR-002a: the correction path -- date is fixed once recorded, only
    actual_value/note are editable."""
    entry = await sstore.update_progress_entry(objective_id, as_of_date, body, session)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"No progress entry for {as_of_date} on objective {objective_id!r}",
        )
    await session.commit()
    actor = _get_actor(raw_request)
    logger.info(
        "strategy.objective.progress.update objective_id=%s as_of_date=%s actor=%s",
        objective_id, as_of_date, actor,
    )
    return entry


@router.patch("/objectives/{objective_id}/abandon", response_model=StrategicObjective)
async def abandon_objective(
    objective_id: str,
    body: AbandonRequest,
    raw_request: Request,
    session: AsyncSession = Depends(_get_session),
):
    """FR-009/FR-010/FR-011: named /abandon, not a generic /status, since
    it's the only settable transition -- the URL itself communicates that
    on-track/at-risk/achieved aren't reachable this way."""
    objective = await sstore.abandon_objective(objective_id, body, session)
    if objective is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    await session.commit()
    actor = _get_actor(raw_request)
    logger.info(
        "strategy.objective.abandon objective_id=%s actor=%s reason=%r",
        objective_id, actor, body.status_reason,
    )
    return objective


# ── Links: capabilities ────────────────────────────────────────────────────────


@router.post("/objectives/{objective_id}/capabilities", status_code=status.HTTP_201_CREATED)
async def link_objective_capability(
    objective_id: str,
    body: ObjectiveCapabilityLinkCreate,
    session: AsyncSession = Depends(_get_session),
    business_session: AsyncSession = Depends(_get_business_session),
):
    from adp.business import store as bstore

    capability_id = body.capability_id
    if await sstore.get_objective(objective_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    if await bstore.get_capability(capability_id, business_session) is None:
        raise HTTPException(status_code=404, detail=f"Capability {capability_id!r} not found")
    try:
        await sstore.link_objective_capability(objective_id, capability_id, session)
    except sstore.DuplicateLinkError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    objective = await sstore.get_objective(objective_id, session)
    assert objective is not None
    return objective.capability_ids


@router.delete(
    "/objectives/{objective_id}/capabilities/{capability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_objective_capability(
    objective_id: str, capability_id: str, session: AsyncSession = Depends(_get_session)
):
    try:
        await sstore.unlink_objective_capability(objective_id, capability_id, session)
    except sstore.LinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()


# ── Links: value streams ───────────────────────────────────────────────────────


@router.post("/objectives/{objective_id}/value-streams", status_code=status.HTTP_201_CREATED)
async def link_objective_value_stream(
    objective_id: str,
    body: ObjectiveValueStreamLinkCreate,
    session: AsyncSession = Depends(_get_session),
    business_session: AsyncSession = Depends(_get_business_session),
):
    from adp.business import store as bstore

    value_stream_id = body.value_stream_id
    if await sstore.get_objective(objective_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    if await bstore.get_value_stream(value_stream_id, business_session) is None:
        raise HTTPException(
            status_code=404, detail=f"Value stream {value_stream_id!r} not found"
        )
    try:
        await sstore.link_objective_value_stream(objective_id, value_stream_id, session)
    except sstore.DuplicateLinkError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    objective = await sstore.get_objective(objective_id, session)
    assert objective is not None
    return objective.value_stream_ids


@router.delete(
    "/objectives/{objective_id}/value-streams/{value_stream_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_objective_value_stream(
    objective_id: str, value_stream_id: str, session: AsyncSession = Depends(_get_session)
):
    try:
        await sstore.unlink_objective_value_stream(objective_id, value_stream_id, session)
    except sstore.LinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()


# ── Links: designs / applications (ADP-d8u.2) ──────────────────────────────────
#
# Unlike the capability/value-stream links above, design_id/application_id
# existence is checked via sstore.design_exists/application_exists using the
# SAME session -- no second, cross-package session is needed here (research.md
# Decision 2: designs/applications are validated through adp.strategy.store's
# own lightweight read-only mirror tables, which live in this module's own
# _metadata against the same physical database, unlike capability_id/
# value_stream_id which genuinely go through adp.business.store's own
# higher-level functions via a separate session).


@router.post("/objectives/{objective_id}/designs", status_code=status.HTTP_201_CREATED)
async def link_objective_design(
    objective_id: str,
    body: ObjectiveDesignLinkCreate,
    session: AsyncSession = Depends(_get_session),
):
    design_id = body.design_id
    if await sstore.get_objective(objective_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    if not await sstore.design_exists(design_id, session):
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")
    try:
        await sstore.link_objective_design(objective_id, design_id, session)
    except sstore.DuplicateLinkError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    logger.info(
        "strategy.objective.design.link objective_id=%s design_id=%s", objective_id, design_id
    )
    objective = await sstore.get_objective(objective_id, session)
    assert objective is not None
    return objective.design_ids


@router.delete(
    "/objectives/{objective_id}/designs/{design_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_objective_design(
    objective_id: str, design_id: str, session: AsyncSession = Depends(_get_session)
):
    try:
        await sstore.unlink_objective_design(objective_id, design_id, session)
    except sstore.LinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    logger.info(
        "strategy.objective.design.unlink objective_id=%s design_id=%s", objective_id, design_id
    )


@router.post("/objectives/{objective_id}/applications", status_code=status.HTTP_201_CREATED)
async def link_objective_application(
    objective_id: str,
    body: ObjectiveApplicationLinkCreate,
    session: AsyncSession = Depends(_get_session),
):
    application_id = body.application_id
    if await sstore.get_objective(objective_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    if not await sstore.application_exists(application_id, session):
        raise HTTPException(status_code=404, detail=f"Application {application_id!r} not found")
    try:
        await sstore.link_objective_application(objective_id, application_id, session)
    except sstore.DuplicateLinkError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    logger.info(
        "strategy.objective.application.link objective_id=%s application_id=%s",
        objective_id, application_id,
    )
    objective = await sstore.get_objective(objective_id, session)
    assert objective is not None
    return objective.application_ids


@router.delete(
    "/objectives/{objective_id}/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_objective_application(
    objective_id: str, application_id: str, session: AsyncSession = Depends(_get_session)
):
    try:
        await sstore.unlink_objective_application(objective_id, application_id, session)
    except sstore.LinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    logger.info(
        "strategy.objective.application.unlink objective_id=%s application_id=%s",
        objective_id, application_id,
    )


# ── Links: Controls — Objective side (925-strategy-compliance-linkage, COMPLY-05) ───────────────


@router.post("/objectives/{objective_id}/controls", status_code=status.HTTP_201_CREATED)
async def link_objective_control(
    objective_id: str,
    body: ObjectiveControlLinkCreate,
    session: AsyncSession = Depends(_get_session),
):
    control_id = body.control_id
    if await sstore.get_objective(objective_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    if not await sstore.control_exists(control_id, session):
        raise HTTPException(status_code=404, detail=f"Control {control_id!r} not found")
    try:
        await sstore.link_objective_control(objective_id, control_id, session)
    except sstore.DuplicateLinkError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    logger.info(
        "strategy.objective.control.link objective_id=%s control_id=%s", objective_id, control_id
    )
    objective = await sstore.get_objective(objective_id, session)
    assert objective is not None
    return objective.control_ids


@router.delete(
    "/objectives/{objective_id}/controls/{control_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_objective_control(
    objective_id: str, control_id: str, session: AsyncSession = Depends(_get_session)
):
    try:
        await sstore.unlink_objective_control(objective_id, control_id, session)
    except sstore.LinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    logger.info(
        "strategy.objective.control.unlink objective_id=%s control_id=%s",
        objective_id, control_id,
    )


# ── Strategy Initiatives (ADP-d8u.6) ───────────────────────────────────────────


@router.post(
    "/initiatives", response_model=StrategyInitiative, status_code=status.HTTP_201_CREATED
)
async def create_initiative(
    body: StrategyInitiativeCreate, session: AsyncSession = Depends(_get_session)
):
    initiative = await sinit.create_initiative(body, session)
    await session.commit()
    return initiative


@router.get("/initiatives", response_model=StrategyInitiativeListResponse)
async def list_initiatives(session: AsyncSession = Depends(_get_session)):
    return await sinit.list_initiatives(session)


@router.get("/initiatives/{initiative_id}", response_model=StrategyInitiative)
async def get_initiative(initiative_id: str, session: AsyncSession = Depends(_get_session)):
    initiative = await sinit.get_initiative(initiative_id, session)
    if initiative is None:
        raise HTTPException(status_code=404, detail=f"Initiative {initiative_id!r} not found")
    return initiative


@router.patch("/initiatives/{initiative_id}", response_model=StrategyInitiative)
async def update_initiative(
    initiative_id: str,
    body: StrategyInitiativeUpdate,
    raw_request: Request,
    session: AsyncSession = Depends(_get_session),
):
    initiative = await sinit.update_initiative(initiative_id, body, session)
    if initiative is None:
        raise HTTPException(status_code=404, detail=f"Initiative {initiative_id!r} not found")
    await session.commit()
    actor = _get_actor(raw_request)
    logger.info("strategy.initiative.update initiative_id=%s actor=%s", initiative_id, actor)
    return initiative


@router.delete("/initiatives/{initiative_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_initiative(
    initiative_id: str, raw_request: Request, session: AsyncSession = Depends(_get_session)
):
    """FR-011: unconditional -- never blocked by existing links."""
    deleted = await sinit.delete_initiative(initiative_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Initiative {initiative_id!r} not found")
    await session.commit()
    actor = _get_actor(raw_request)
    logger.info("strategy.initiative.delete initiative_id=%s actor=%s", initiative_id, actor)


@router.post(
    "/initiatives/{initiative_id}/objectives/{objective_id}",
    response_model=StrategyInitiative,
    status_code=status.HTTP_201_CREATED,
)
async def link_initiative_objective(
    initiative_id: str, objective_id: str, session: AsyncSession = Depends(_get_session)
):
    if await sinit.get_initiative(initiative_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Initiative {initiative_id!r} not found")
    if await sstore.get_objective(objective_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    try:
        await sinit.link_initiative_objective(initiative_id, objective_id, session)
    except sinit.DuplicateLinkError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    initiative = await sinit.get_initiative(initiative_id, session)
    assert initiative is not None
    return initiative


@router.delete(
    "/initiatives/{initiative_id}/objectives/{objective_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_initiative_objective(
    initiative_id: str, objective_id: str, session: AsyncSession = Depends(_get_session)
):
    try:
        await sinit.unlink_initiative_objective(initiative_id, objective_id, session)
    except sinit.LinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()


@router.get("/objectives/{objective_id}/initiatives", response_model=StrategyInitiativeListResponse)
async def list_objective_initiatives(
    objective_id: str, session: AsyncSession = Depends(_get_session)
):
    """Reverse lookup (FR-005)."""
    if await sstore.get_objective(objective_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    initiative_ids = await sinit.list_objective_initiative_ids(objective_id, session)
    items = []
    for initiative_id in initiative_ids:
        initiative = await sinit.get_initiative(initiative_id, session)
        assert initiative is not None
        items.append(initiative)
    return StrategyInitiativeListResponse(items=items, total=len(items))


# ── Links: Control Mappings — Initiative side (925-strategy-compliance-linkage, COMPLY-05) ──────
# One POST/DELETE pair per ControlMapping target shape (research.md D1 -- ControlMapping itself
# has no single addressable row, so this mirrors adp.compliance.router's own literal-route-per-
# target-type style rather than one dynamic {target_type} segment), sharing one internal helper
# each (avoids duplicating the exception->HTTP-status translation five times, mirroring
# adp.compliance.router's own _translate_mapping_write_errors precedent).


async def _link_initiative_control_mapping(
    initiative_id: str,
    control_id: str,
    target_type: MappingTargetType,
    target_id: str | None,
    session: AsyncSession,
) -> StrategyInitiative:
    if await sinit.get_initiative(initiative_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Initiative {initiative_id!r} not found")
    try:
        await sinit.link_initiative_control_mapping(
            initiative_id, control_id, target_type, target_id, session
        )
    except sinit.ControlMappingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except sinit.DuplicateLinkError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    logger.info(
        "strategy.initiative.control_mapping.link initiative_id=%s control_id=%s "
        "target_type=%s target_id=%s",
        initiative_id, control_id, target_type.value, target_id,
    )
    initiative = await sinit.get_initiative(initiative_id, session)
    assert initiative is not None
    return initiative


async def _unlink_initiative_control_mapping(
    initiative_id: str,
    control_id: str,
    target_type: MappingTargetType,
    target_id: str | None,
    session: AsyncSession,
) -> None:
    try:
        await sinit.unlink_initiative_control_mapping(
            initiative_id, control_id, target_type, target_id, session
        )
    except sinit.LinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    logger.info(
        "strategy.initiative.control_mapping.unlink initiative_id=%s control_id=%s "
        "target_type=%s target_id=%s",
        initiative_id, control_id, target_type.value, target_id,
    )


@router.post(
    "/initiatives/{initiative_id}/control-mappings/capabilities/{control_id}/{capability_id}",
    response_model=StrategyInitiative,
    status_code=status.HTTP_201_CREATED,
)
async def link_initiative_capability_mapping(
    initiative_id: str, control_id: str, capability_id: str,
    session: AsyncSession = Depends(_get_session),
):
    return await _link_initiative_control_mapping(
        initiative_id, control_id, MappingTargetType.CAPABILITY, capability_id, session
    )


@router.delete(
    "/initiatives/{initiative_id}/control-mappings/capabilities/{control_id}/{capability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_initiative_capability_mapping(
    initiative_id: str, control_id: str, capability_id: str,
    session: AsyncSession = Depends(_get_session),
):
    await _unlink_initiative_control_mapping(
        initiative_id, control_id, MappingTargetType.CAPABILITY, capability_id, session
    )


@router.post(
    "/initiatives/{initiative_id}/control-mappings/applications/{control_id}/{application_id}",
    response_model=StrategyInitiative,
    status_code=status.HTTP_201_CREATED,
)
async def link_initiative_application_mapping(
    initiative_id: str, control_id: str, application_id: str,
    session: AsyncSession = Depends(_get_session),
):
    return await _link_initiative_control_mapping(
        initiative_id, control_id, MappingTargetType.APPLICATION, application_id, session
    )


@router.delete(
    "/initiatives/{initiative_id}/control-mappings/applications/{control_id}/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_initiative_application_mapping(
    initiative_id: str, control_id: str, application_id: str,
    session: AsyncSession = Depends(_get_session),
):
    await _unlink_initiative_control_mapping(
        initiative_id, control_id, MappingTargetType.APPLICATION, application_id, session
    )


@router.post(
    "/initiatives/{initiative_id}/control-mappings/designs/{control_id}/{design_id}",
    response_model=StrategyInitiative,
    status_code=status.HTTP_201_CREATED,
)
async def link_initiative_design_mapping(
    initiative_id: str, control_id: str, design_id: str,
    session: AsyncSession = Depends(_get_session),
):
    return await _link_initiative_control_mapping(
        initiative_id, control_id, MappingTargetType.DESIGN, design_id, session
    )


@router.delete(
    "/initiatives/{initiative_id}/control-mappings/designs/{control_id}/{design_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_initiative_design_mapping(
    initiative_id: str, control_id: str, design_id: str,
    session: AsyncSession = Depends(_get_session),
):
    await _unlink_initiative_control_mapping(
        initiative_id, control_id, MappingTargetType.DESIGN, design_id, session
    )


@router.post(
    "/initiatives/{initiative_id}/control-mappings/patterns/{control_id}/{pattern_id}",
    response_model=StrategyInitiative,
    status_code=status.HTTP_201_CREATED,
)
async def link_initiative_pattern_mapping(
    initiative_id: str, control_id: str, pattern_id: str,
    session: AsyncSession = Depends(_get_session),
):
    return await _link_initiative_control_mapping(
        initiative_id, control_id, MappingTargetType.PATTERN, pattern_id, session
    )


@router.delete(
    "/initiatives/{initiative_id}/control-mappings/patterns/{control_id}/{pattern_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_initiative_pattern_mapping(
    initiative_id: str, control_id: str, pattern_id: str,
    session: AsyncSession = Depends(_get_session),
):
    await _unlink_initiative_control_mapping(
        initiative_id, control_id, MappingTargetType.PATTERN, pattern_id, session
    )


@router.post(
    "/initiatives/{initiative_id}/control-mappings/organization/{control_id}",
    response_model=StrategyInitiative,
    status_code=status.HTTP_201_CREATED,
)
async def link_initiative_organization_mapping(
    initiative_id: str, control_id: str, session: AsyncSession = Depends(_get_session),
):
    return await _link_initiative_control_mapping(
        initiative_id, control_id, MappingTargetType.ORGANIZATION, None, session
    )


@router.delete(
    "/initiatives/{initiative_id}/control-mappings/organization/{control_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_initiative_organization_mapping(
    initiative_id: str, control_id: str, session: AsyncSession = Depends(_get_session),
):
    await _unlink_initiative_control_mapping(
        initiative_id, control_id, MappingTargetType.ORGANIZATION, None, session
    )


# ── Objective Dependencies (ADP-d8u.6) ─────────────────────────────────────────


@router.post(
    "/objectives/{objective_id}/depends-on",
    response_model=ObjectiveDependenciesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_objective_dependency(
    objective_id: str,
    body: ObjectiveDependencyCreate,
    raw_request: Request,
    session: AsyncSession = Depends(_get_session),
):
    depends_on_objective_id = body.depends_on_objective_id
    if await sstore.get_objective(objective_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    if await sstore.get_objective(depends_on_objective_id, session) is None:
        raise HTTPException(
            status_code=404, detail=f"Objective {depends_on_objective_id!r} not found"
        )
    try:
        await sinit.add_objective_dependency(objective_id, depends_on_objective_id, session)
    except sinit.CycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except sinit.DuplicateLinkError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    actor = _get_actor(raw_request)
    logger.info(
        "strategy.objective.dependency.add objective_id=%s depends_on_objective_id=%s actor=%s",
        objective_id, depends_on_objective_id, actor,
    )
    return await sinit.get_objective_dependencies(objective_id, session)


@router.delete(
    "/objectives/{objective_id}/depends-on/{depends_on_objective_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_objective_dependency(
    objective_id: str,
    depends_on_objective_id: str,
    raw_request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        await sinit.remove_objective_dependency(objective_id, depends_on_objective_id, session)
    except sinit.LinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(raw_request)
    logger.info(
        "strategy.objective.dependency.remove objective_id=%s depends_on_objective_id=%s "
        "actor=%s",
        objective_id, depends_on_objective_id, actor,
    )


@router.get(
    "/objectives/{objective_id}/dependencies", response_model=ObjectiveDependenciesResponse
)
async def get_objective_dependencies(
    objective_id: str, session: AsyncSession = Depends(_get_session)
):
    if await sstore.get_objective(objective_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Objective {objective_id!r} not found")
    return await sinit.get_objective_dependencies(objective_id, session)


# ── Overview dashboard summary (051-strategy-landing-card) ────────────────────


@router.get("/summary", response_model=StrategicSummaryResponse)
async def get_summary(session: AsyncSession = Depends(_get_session)):
    """Read-only; no ActionType gate (enforce_route_permission is a no-op
    for GET; spec.md FR-012) -- normal authentication still applies via
    AuthMiddleware, same as every other route."""
    return await sstore.get_summary_stats(session)


@router.get("/heatmap", response_model=StrategyHeatMapResponse)
async def get_heatmap(
    theme_id: str | None = None, session: AsyncSession = Depends(_get_session)
):
    """918-strategy-rollups: theme x status matrix, optionally narrowed to
    one theme. Read-only, ungated, same as /summary above (spec.md FR-008)."""
    return await sstore.get_strategy_heatmap(session, theme_id=theme_id)
