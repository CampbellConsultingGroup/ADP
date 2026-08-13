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

from adp.strategy import store as sstore
from adp.strategy.models import (
    AbandonRequest,
    ObjectiveCapabilityLinkCreate,
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


# ── Overview dashboard summary (051-strategy-landing-card) ────────────────────


@router.get("/summary", response_model=StrategicSummaryResponse)
async def get_summary(session: AsyncSession = Depends(_get_session)):
    """Read-only; no ActionType gate (enforce_route_permission is a no-op
    for GET; spec.md FR-012) -- normal authentication still applies via
    AuthMiddleware, same as every other route."""
    return await sstore.get_summary_stats(session)
