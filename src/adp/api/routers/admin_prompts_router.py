"""Admin Agent Prompt Management API (ADP-SPEC-042).

See specs/042-admin-prompt-management/contracts/agent-prompts-api.md for the
full contract. Gated by ActionType.MANAGE_AGENT_PROMPTS end-to-end (both
reads and writes) via a single prefix rule in adp.authz.enforcement -- FR-009
denies access to "the admin screen and its underlying data", not just writes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from adp.admin import service as admin_service
from adp.admin.models import (
    AgentPromptListResponse,
    PromptChangeResult,
    PromptEditRequest,
    PromptHistoryResponse,
    PromptRestoreRequest,
)
from adp.authz.enforcement import require_action_dep
from adp.authz.roles import ActionType

router = APIRouter(prefix="/api/v1/admin/agent-prompts", tags=["admin"])

# GET routes are "safe methods" and exempt from the app-level enforcer, which
# only checks mutating methods -- so sensitive reads must gate themselves
# per-route, mirroring adp.application.router's READ_APPLICATION_{RISK,COST,
# GOVERNANCE} precedent. FR-009 denies access to "the admin screen and its
# underlying data", not just writes, so this applies to every route here.
_require_manage_prompts = require_action_dep(ActionType.MANAGE_AGENT_PROMPTS)


async def _get_session():
    factory = admin_service._get_session_factory()
    async with factory() as session:
        yield session


def _get_actor(request: Request) -> str:
    """Mirrors adp.business.router._get_actor exactly."""
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


@router.get(
    "", response_model=AgentPromptListResponse, dependencies=[Depends(_require_manage_prompts)]
)
async def list_agent_prompts(
    session: AsyncSession = Depends(_get_session),
) -> AgentPromptListResponse:
    # session is unused by list_agents() today (prompt_registry is
    # self-contained) but is declared so this route participates in the
    # same request-scoped-session shape as the write endpoints below.
    del session
    return AgentPromptListResponse(items=await admin_service.list_agents())


@router.post("/{agent_id}/confirm", response_model=PromptChangeResult)
async def confirm_prompt_edit(
    agent_id: str,
    body: PromptEditRequest,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> PromptChangeResult:
    actor = _get_actor(request)
    try:
        result = await admin_service.save_prompt(
            agent_id, body.new_text, body.expected_version, actor, body.confirmation_id, session
        )
    except admin_service.UnknownAgentError:
        raise HTTPException(status_code=404, detail=f"Unknown agent_id {agent_id!r}")
    except admin_service.PromptVersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "The prompt changed since you loaded it.",
                "current_active_text": exc.current_text,
                "current_version": exc.current_version,
            },
        )
    await session.commit()
    return result


@router.get(
    "/{agent_id}/history",
    response_model=PromptHistoryResponse,
    dependencies=[Depends(_require_manage_prompts)],
)
async def get_prompt_history(
    agent_id: str,
    session: AsyncSession = Depends(_get_session),
) -> PromptHistoryResponse:
    return PromptHistoryResponse(items=await admin_service.get_history(agent_id, session))


@router.post("/{agent_id}/restore/{history_id}", response_model=PromptChangeResult)
async def restore_prompt_version(
    agent_id: str,
    history_id: int,
    body: PromptRestoreRequest,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> PromptChangeResult:
    """Restore uses the IDENTICAL confirmation gate as confirm_prompt_edit
    above (Clarification Session 2026-07-24) -- PromptRestoreRequest requires
    the same non-empty confirmation_id, enforced by its own field_validator."""
    actor = _get_actor(request)
    try:
        result = await admin_service.restore_prompt(
            agent_id, history_id, body.expected_version, actor, body.confirmation_id, session
        )
    except (admin_service.UnknownAgentError, admin_service.HistoryEntryNotFoundError):
        raise HTTPException(
            status_code=404,
            detail=f"history_id {history_id!r} not found for agent {agent_id!r}",
        )
    except admin_service.PromptVersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "The prompt changed since you loaded it.",
                "current_active_text": exc.current_text,
                "current_version": exc.current_version,
            },
        )
    await session.commit()
    return result
