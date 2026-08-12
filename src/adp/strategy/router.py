"""Strategic Objective Capture API — ADP-d8u.1.

POST/GET /api/v1/strategy/themes
POST/GET /api/v1/strategy/objectives
GET/PUT/DELETE /api/v1/strategy/objectives/{id}
POST/DELETE /api/v1/strategy/objectives/{id}/capabilities[/{capability_id}]
POST/DELETE /api/v1/strategy/objectives/{id}/value-streams[/{value_stream_id}]

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
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.strategy import store as sstore
from adp.strategy.models import (
    ObjectiveCapabilityLinkCreate,
    ObjectiveValueStreamLinkCreate,
    StrategicObjective,
    StrategicObjectiveCreate,
    StrategicObjectiveListResponse,
    StrategicObjectiveUpdate,
    StrategicSummaryResponse,
    StrategicTheme,
    StrategicThemeCreate,
    StrategicThemeListResponse,
)

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
