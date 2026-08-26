"""Admin Scoring Rubric Management API (ADP-68z).

See specs/931-admin-ui-editing/contracts/scoring-rubrics-api.md for the full contract. Gated by
ActionType.MANAGE_SCORING_RUBRICS end-to-end (both reads and writes) via a single prefix rule in
adp.authz.enforcement -- mirrors admin_prompts_router.py's own FR-009-style precedent: this denies
access to "the admin screen and its underlying data", not just writes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from adp.admin import rubric_service
from adp.admin.rubric_models import (
    RubricChangeResult,
    RubricEditRequest,
    RubricHistoryResponse,
    RubricListResponse,
    RubricRestoreRequest,
)
from adp.authz.enforcement import require_action_dep
from adp.authz.roles import ActionType

router = APIRouter(prefix="/api/v1/admin/scoring-rubrics", tags=["admin"])

# GET routes are "safe methods" and exempt from the app-level enforcer, which only checks
# mutating methods -- so sensitive reads must gate themselves per-route, mirroring
# admin_prompts_router.py's own precedent.
_require_manage_rubrics = require_action_dep(ActionType.MANAGE_SCORING_RUBRICS)


async def _get_session():
    factory = rubric_service._get_session_factory()
    async with factory() as session:
        yield session


def _get_actor(request: Request) -> str:
    """Mirrors admin_prompts_router._get_actor exactly."""
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


@router.get(
    "", response_model=RubricListResponse, dependencies=[Depends(_require_manage_rubrics)]
)
async def list_scoring_rubrics(
    session: AsyncSession = Depends(_get_session),
) -> RubricListResponse:
    # session is unused by list_rubrics() today (rubric_registry is self-contained) but is
    # declared so this route participates in the same request-scoped-session shape as the
    # write endpoints below.
    del session
    return RubricListResponse(items=await rubric_service.list_rubrics())


@router.post("/{rubric_id}/confirm", response_model=RubricChangeResult)
async def confirm_rubric_edit(
    rubric_id: str,
    body: RubricEditRequest,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> RubricChangeResult:
    actor = _get_actor(request)
    try:
        result = await rubric_service.save_weights(
            rubric_id, body.weights, body.expected_version, actor, body.confirmation_id, session
        )
    except rubric_service.UnknownRubricError:
        raise HTTPException(status_code=404, detail=f"Unknown rubric_id {rubric_id!r}")
    except rubric_service.InvalidWeightsError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except rubric_service.RubricVersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "The rubric's weights changed since you loaded them.",
                "current_active_weights": exc.current_weights,
                "current_version": exc.current_version,
            },
        )
    await session.commit()
    return result


@router.get(
    "/{rubric_id}/history",
    response_model=RubricHistoryResponse,
    dependencies=[Depends(_require_manage_rubrics)],
)
async def get_rubric_history(
    rubric_id: str,
    session: AsyncSession = Depends(_get_session),
) -> RubricHistoryResponse:
    return RubricHistoryResponse(items=await rubric_service.get_history(rubric_id, session))


@router.post("/{rubric_id}/restore/{history_id}", response_model=RubricChangeResult)
async def restore_rubric_version(
    rubric_id: str,
    history_id: int,
    body: RubricRestoreRequest,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> RubricChangeResult:
    """Restore uses the IDENTICAL confirmation gate as confirm_rubric_edit above (mirrors
    ADP-SPEC-042's own Clarification Session 2026-07-24) -- RubricRestoreRequest requires the
    same non-empty confirmation_id, enforced by its own field_validator."""
    actor = _get_actor(request)
    try:
        result = await rubric_service.restore_weights(
            rubric_id, history_id, body.expected_version, actor, body.confirmation_id, session
        )
    except (rubric_service.UnknownRubricError, rubric_service.HistoryEntryNotFoundError):
        raise HTTPException(
            status_code=404,
            detail=f"history_id {history_id!r} not found for rubric {rubric_id!r}",
        )
    except rubric_service.RubricVersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "The rubric's weights changed since you loaded them.",
                "current_active_weights": exc.current_weights,
                "current_version": exc.current_version,
            },
        )
    await session.commit()
    return result
