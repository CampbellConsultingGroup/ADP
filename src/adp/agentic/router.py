"""Agent registry API (933-agent-registry, ADP-hii).

GET/POST                 /api/v1/agentic/agents                          — registry list/create
GET/PATCH/DELETE         /api/v1/agentic/agents/{agent_id}               — one agent (+ solutions)
GET/POST                 /api/v1/agentic/solutions/{app_id}/agents       — a solution's members
PATCH/DELETE             /api/v1/agentic/solutions/{app_id}/agents/{agent_id} — role / remove
PUT                      /api/v1/agentic/solutions/{app_id}/agents/order — reorder
GET                      /api/v1/agentic/agents/{agent_id}/automates     — what it automates (944)
POST/DELETE              /api/v1/agentic/agents/{agent_id}/automates/{kind}[/{target_id}]
                         kind = capabilities | stages | activities
GET                      /api/v1/agentic/{target}/{id}/agents — reverse lookups (944); target =
                         capabilities | value-stream-stages | value-chain-activities

ART-V: mutations require WRITE_APPLICATION via the `/api/v1/agentic/` prefix rule. Cost estimates
        (Clarification Q2) mirror application cost: reads redact them inline for a caller lacking
        READ_APPLICATION_COST (cost_visible=false) rather than hiding the whole agent; a write that
        sets either cost field additionally requires WRITE_APPLICATION_COST (403 otherwise).
ART-VI/IX: every mutation emits an actor-attributed structured log line; no audit_entries write,
        matching adp.application/adp.compliance's established precedent (research.md D6).
"""

from __future__ import annotations

import logging
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.agentic import store as agstore
from adp.agentic.models import (
    COST_FIELDS,
    ActivityLinkCreate,
    Agent,
    AgentAutomates,
    AgentCreate,
    AgentDetail,
    AgentLifecycle,
    AgentListResponse,
    AgentNotFoundError,
    AgentSummaryListResponse,
    AgentUpdate,
    AutomatesKind,
    CapabilityLinkCreate,
    DuplicateLinkError,
    DuplicateSolutionAgentError,
    LevelRuleError,
    LinkNotFoundError,
    MembershipNotFoundError,
    NotAgenticSolutionError,
    OrderMismatchError,
    SolutionAgent,
    SolutionAgentCreate,
    SolutionAgentListResponse,
    SolutionAgentOrder,
    SolutionAgentUpdate,
    SolutionNotFoundError,
    StageLinkCreate,
    TargetNotFoundError,
)
from adp.agentic.risk import solution_risk
from adp.api.common import session_dependency
from adp.auth.actor import actor_of
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.permissions import is_permitted
from adp.authz.roles import ActionType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agentic", tags=["agentic"])

_A = TypeVar("_A", bound=Agent)


def _get_actor(request: Request) -> str:
    return actor_of(request)


_get_session = session_dependency("adp.agentic.store")


# ── Cost gating (Clarification Q2) ────────────────────────────────────────────


def _cost_readable(user: AuthenticatedUser) -> bool:
    return is_permitted(user.role, ActionType.READ_APPLICATION_COST)


def _redact(agent: _A, readable: bool) -> _A:
    if readable:
        return agent
    return agent.model_copy(
        update={"est_cost_per_run": None, "runs_per_month": None, "cost_visible": False}
    )


def _require_cost_write(fields_set: set[str], user: AuthenticatedUser) -> None:
    if fields_set & COST_FIELDS and not is_permitted(
        user.role, ActionType.WRITE_APPLICATION_COST
    ):
        raise HTTPException(
            status_code=403,
            detail="Setting agent cost estimates requires the WRITE_APPLICATION_COST permission",
        )


def _redact_members(items: list[SolutionAgent], readable: bool) -> SolutionAgentListResponse:
    redacted = [m.model_copy(update={"agent": _redact(m.agent, readable)}) for m in items]
    risk = solution_risk(
        (m.agent.id, m.agent.name, m.agent.lifecycle_status, m.agent.agentic_risk) for m in items
    )
    return SolutionAgentListResponse(items=redacted, total=len(redacted), solution_risk=risk)


# ── Agents ────────────────────────────────────────────────────────────────────


@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    autonomy_level: Annotated[int | None, Query(ge=0, le=4)] = None,
    autonomy_min: Annotated[int | None, Query(ge=0, le=4)] = None,
    model_provider: str | None = None,
    owner: str | None = None,
    lifecycle_status: AgentLifecycle | None = None,
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    items = await agstore.list_agents(
        session,
        autonomy_level=autonomy_level,
        autonomy_min=autonomy_min,
        model_provider=model_provider,
        owner=owner,
        lifecycle_status=lifecycle_status,
    )
    readable = _cost_readable(user)
    return AgentListResponse(items=[_redact(a, readable) for a in items], total=len(items))


@router.post("/agents", response_model=Agent, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    _require_cost_write(body.model_fields_set, user)
    agent = await agstore.create_agent(body, session)
    await session.commit()
    logger.info(
        "agentic.agent.create id=%s name=%r actor=%s", agent.id, agent.name, _get_actor(request)
    )
    return _redact(agent, _cost_readable(user))


@router.get("/agents/{agent_id}", response_model=AgentDetail)
async def get_agent(
    agent_id: str,
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    agent = await agstore.get_agent(agent_id, session)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    return _redact(agent, _cost_readable(user))


@router.patch("/agents/{agent_id}", response_model=Agent)
async def update_agent(
    agent_id: str,
    body: AgentUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    _require_cost_write(body.model_fields_set, user)
    agent = await agstore.update_agent(agent_id, body, session)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    await session.commit()
    logger.info(
        "agentic.agent.update id=%s fields=%s actor=%s",
        agent_id,
        sorted(body.model_fields_set),
        _get_actor(request),
    )
    return _redact(agent, _cost_readable(user))


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    if not await agstore.delete_agent(agent_id, session):
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    await session.commit()
    logger.info("agentic.agent.delete id=%s actor=%s", agent_id, _get_actor(request))


# ── Solution membership ───────────────────────────────────────────────────────

_MEMBERSHIP_ERRORS: dict[type[Exception], int] = {
    SolutionNotFoundError: 404,
    AgentNotFoundError: 404,
    MembershipNotFoundError: 404,
    NotAgenticSolutionError: 422,
    OrderMismatchError: 422,
    DuplicateSolutionAgentError: 409,
}


def _http_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=_MEMBERSHIP_ERRORS[type(exc)], detail=str(exc))


_MembershipError = (
    SolutionNotFoundError,
    AgentNotFoundError,
    MembershipNotFoundError,
    NotAgenticSolutionError,
    OrderMismatchError,
    DuplicateSolutionAgentError,
)


@router.get("/solutions/{app_id}/agents", response_model=SolutionAgentListResponse)
async def list_solution_agents(
    app_id: str,
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        items = await agstore.list_solution_agents(app_id, session)
    except _MembershipError as exc:
        raise _http_error(exc) from exc
    return _redact_members(items, _cost_readable(user))


@router.post(
    "/solutions/{app_id}/agents",
    response_model=SolutionAgentListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_solution_agent(
    app_id: str,
    body: SolutionAgentCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        items = await agstore.add_solution_agent(app_id, body.agent_id, body.role, session)
    except _MembershipError as exc:
        raise _http_error(exc) from exc
    await session.commit()
    logger.info(
        "agentic.solution_agent.add app_id=%s agent_id=%s role=%s actor=%s",
        app_id,
        body.agent_id,
        body.role,
        _get_actor(request),
    )
    return _redact_members(items, _cost_readable(user))


# Registered before the {agent_id} routes so "order" is never captured as an agent id.
@router.put("/solutions/{app_id}/agents/order", response_model=SolutionAgentListResponse)
async def reorder_solution_agents(
    app_id: str,
    body: SolutionAgentOrder,
    request: Request,
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        items = await agstore.reorder_solution_agents(app_id, body.agent_ids, session)
    except _MembershipError as exc:
        raise _http_error(exc) from exc
    await session.commit()
    logger.info("agentic.solution_agent.reorder app_id=%s actor=%s", app_id, _get_actor(request))
    return _redact_members(items, _cost_readable(user))


@router.patch("/solutions/{app_id}/agents/{agent_id}", response_model=SolutionAgent)
async def update_solution_agent(
    app_id: str,
    agent_id: str,
    body: SolutionAgentUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        member = await agstore.update_solution_agent_role(app_id, agent_id, body.role, session)
    except _MembershipError as exc:
        raise _http_error(exc) from exc
    await session.commit()
    logger.info(
        "agentic.solution_agent.update app_id=%s agent_id=%s role=%s actor=%s",
        app_id,
        agent_id,
        body.role,
        _get_actor(request),
    )
    return member.model_copy(update={"agent": _redact(member.agent, _cost_readable(user))})


@router.delete(
    "/solutions/{app_id}/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_solution_agent(
    app_id: str,
    agent_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        await agstore.remove_solution_agent(app_id, agent_id, session)
    except _MembershipError as exc:
        raise _http_error(exc) from exc
    await session.commit()
    logger.info(
        "agentic.solution_agent.remove app_id=%s agent_id=%s actor=%s",
        app_id,
        agent_id,
        _get_actor(request),
    )


# ── Automates links (944-agent-traceability, US1) ─────────────────────────────

_LINK_ERRORS: dict[type[Exception], int] = {
    AgentNotFoundError: 404,
    TargetNotFoundError: 404,
    LinkNotFoundError: 404,
    DuplicateLinkError: 409,
    LevelRuleError: 422,
}
_LinkError = tuple(_LINK_ERRORS)


def _link_http_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=_LINK_ERRORS[type(exc)], detail=str(exc))


@router.get("/agents/{agent_id}/automates", response_model=AgentAutomates)
async def get_automates(agent_id: str, session: AsyncSession = Depends(_get_session)):
    try:
        return await agstore.get_automates(agent_id, session)
    except _LinkError as exc:
        raise _link_http_error(exc) from exc


async def _add_link(
    kind: AutomatesKind, agent_id: str, target_id: str, request: Request, session: AsyncSession
) -> AgentAutomates:
    try:
        out = await agstore.add_link(kind, agent_id, target_id, session)
    except _LinkError as exc:
        raise _link_http_error(exc) from exc
    await session.commit()
    logger.info(
        "agentic.automates.create agent=%s kind=%s target=%s actor=%s",
        agent_id, kind, target_id, _get_actor(request),
    )
    return out


async def _remove_link(
    kind: AutomatesKind, agent_id: str, target_id: str, request: Request, session: AsyncSession
) -> None:
    try:
        await agstore.remove_link(kind, agent_id, target_id, session)
    except _LinkError as exc:
        raise _link_http_error(exc) from exc
    await session.commit()
    logger.info(
        "agentic.automates.delete agent=%s kind=%s target=%s actor=%s",
        agent_id, kind, target_id, _get_actor(request),
    )


@router.post(
    "/agents/{agent_id}/automates/capabilities",
    response_model=AgentAutomates,
    status_code=status.HTTP_201_CREATED,
)
async def add_capability_link(
    agent_id: str,
    body: CapabilityLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    return await _add_link("capability", agent_id, body.capability_id, request, session)


@router.post(
    "/agents/{agent_id}/automates/stages",
    response_model=AgentAutomates,
    status_code=status.HTTP_201_CREATED,
)
async def add_stage_link(
    agent_id: str,
    body: StageLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    return await _add_link("stage", agent_id, body.stage_id, request, session)


@router.post(
    "/agents/{agent_id}/automates/activities",
    response_model=AgentAutomates,
    status_code=status.HTTP_201_CREATED,
)
async def add_activity_link(
    agent_id: str,
    body: ActivityLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    return await _add_link("activity", agent_id, body.activity_id, request, session)


@router.delete(
    "/agents/{agent_id}/automates/capabilities/{target_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_capability_link(
    agent_id: str, target_id: str, request: Request, session: AsyncSession = Depends(_get_session)
):
    await _remove_link("capability", agent_id, target_id, request, session)


@router.delete(
    "/agents/{agent_id}/automates/stages/{target_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_stage_link(
    agent_id: str, target_id: str, request: Request, session: AsyncSession = Depends(_get_session)
):
    await _remove_link("stage", agent_id, target_id, request, session)


@router.delete(
    "/agents/{agent_id}/automates/activities/{target_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_activity_link(
    agent_id: str, target_id: str, request: Request, session: AsyncSession = Depends(_get_session)
):
    await _remove_link("activity", agent_id, target_id, request, session)


async def _agents_for(
    kind: AutomatesKind, target_id: str, session: AsyncSession
) -> AgentSummaryListResponse:
    try:
        items = await agstore.list_agents_for(kind, target_id, session)
    except _LinkError as exc:
        raise _link_http_error(exc) from exc
    return AgentSummaryListResponse(items=items, total=len(items))


@router.get("/capabilities/{target_id}/agents", response_model=AgentSummaryListResponse)
async def capability_agents(target_id: str, session: AsyncSession = Depends(_get_session)):
    return await _agents_for("capability", target_id, session)


@router.get("/value-stream-stages/{target_id}/agents", response_model=AgentSummaryListResponse)
async def stage_agents(target_id: str, session: AsyncSession = Depends(_get_session)):
    return await _agents_for("stage", target_id, session)


@router.get(
    "/value-chain-activities/{target_id}/agents", response_model=AgentSummaryListResponse
)
async def activity_agents(target_id: str, session: AsyncSession = Depends(_get_session)):
    return await _agents_for("activity", target_id, session)
