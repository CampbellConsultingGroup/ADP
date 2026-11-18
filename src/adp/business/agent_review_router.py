"""Agent Review routes for business capabilities: per capability (ADP-SPEC-039) and the whole
portfolio (ADP-SPEC-040). Split out of ``adp.business.router`` (ADP-blp.27); registered in
``adp.api.app``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.agents.models import AgentSuggestionStatus
from adp.agents.provenance import write_suggestion_audit
from adp.business import store as bstore
from adp.business.models import (
    BusinessCapability,
    BusinessCapabilityCreate,
    BusinessCapabilityUpdate,
    CapabilityAgentReviewResponse,
    CapabilityDomainAssign,
    CapabilitySuggestion,
    SuggestionAcceptRequest,
)
from adp.business.router_deps import (
    _get_actor,
    _get_application_session_factory,
    _get_biz_session_factory,
    _get_op_store,
    _get_session,
    _make_agent_review_llm_client,
    logger,
)

# Same prefix and tag as adp.business.router. Registered on the app directly (not nested in
# that router): a nested router reports the matched route without the prefix, and the
# permission and metrics code read that.
router = APIRouter(prefix="/api/v1/business", tags=["business"])


# ── Agent Review: Business Capabilities adapter (ADP-SPEC-039) ────────────────
# Trigger uses the shared SUBMIT_AI_OPERATION action (reused, not duplicated --
# research.md D3); accept/reject use the new CONFIRM_AGENT_SUGGESTION action,
# distinct from WRITE_BUSINESS_ARCH (the action gating the underlying write).
# Both are registered as explicit route->action overrides in enforcement.py.

@router.post(
    "/capabilities/{cap_id}/agent-review",
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_capability_agent_review(
    cap_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    session: AsyncSession = Depends(_get_session),
    op_store=Depends(_get_op_store),
    biz_session_factory=Depends(_get_biz_session_factory),
    app_session_factory=Depends(_get_application_session_factory),
):
    """Trigger an Agent Review of one capability (FR-007). Returns 202 + operation_id."""
    capability = await bstore.get_capability(cap_id, session)
    if capability is None:
        raise HTTPException(status_code=404, detail=f"Capability {cap_id!r} not found")

    operation_id = str(uuid.uuid4())
    actor = _get_actor(request)
    await op_store.create(operation_id, "agent_review", cap_id, actor, {"suggestions": {}})

    llm_client = _make_agent_review_llm_client()

    async def _run() -> None:
        # Fresh sessions for the background task -- the request-scoped `session`
        # dependency above is closed once this endpoint returns its response.
        # Uses the injected factories (test-overridable), not a direct call to
        # bstore/astore._get_session_factory(), so tests can point the
        # background task at a SQLite engine instead of real Postgres.
        from adp.business.agent_review import run_review

        async with biz_session_factory() as biz_session, app_session_factory() as app_session:
            await run_review(
                operation_id=operation_id,
                capability_id=cap_id,
                biz_session=biz_session,
                app_session=app_session,
                llm_client=llm_client,
                op_store=op_store,
            )

    background_tasks.add_task(_run)
    logger.info("business.capability.agent_review.submit id=%s actor=%s", cap_id, actor)
    return {"operation_id": operation_id}


@router.get(
    "/capabilities/{cap_id}/agent-review/{operation_id}",
    response_model=CapabilityAgentReviewResponse,
)
async def get_capability_agent_review(
    cap_id: str,
    operation_id: str,
    op_store=Depends(_get_op_store),
):
    """Poll an Agent Review operation (FR-007)."""
    op = await op_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")

    suggestions = [
        CapabilitySuggestion.model_validate(raw)
        for raw in (op.get("suggestions") or {}).values()
    ]
    return CapabilityAgentReviewResponse(
        operation_id=operation_id,
        capability_id=cap_id,
        status=op["status"],
        suggestions=suggestions,
        error_description=op.get("error_description"),
    )


async def _get_pending_suggestion(
    op_store, operation_id: str, suggestion_id: str
) -> tuple[dict, CapabilitySuggestion]:
    op = await op_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")
    suggestions = op.get("suggestions") or {}
    raw = suggestions.get(suggestion_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Suggestion {suggestion_id!r} not found")
    suggestion = CapabilitySuggestion.model_validate(raw)
    if suggestion.status != AgentSuggestionStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Suggestion {suggestion_id!r} has already been actioned "
            f"(status={suggestion.status})",
        )
    return suggestions, suggestion


def _require_write_business_arch(user) -> None:
    """FR-016: accept re-checks the underlying write permission for the target
    entity, independent of whether the caller was permitted to trigger the
    review or confirm suggestions in general."""
    from adp.authz.permissions import is_permitted
    from adp.authz.roles import ActionType

    if not is_permitted(user.role, ActionType.WRITE_BUSINESS_ARCH):
        raise HTTPException(
            status_code=403,
            detail=f"Role '{user.role.value}' is not permitted to write_business_arch.",
        )


async def _create_capability_from_suggestion(
    suggestion: CapabilitySuggestion, session: AsyncSession
) -> BusinessCapability:
    """Shared propose_new_capability accept logic -- used by both the
    per-capability review's accept endpoint and the portfolio review's
    (ADP-SPEC-040): re-verify the supporting citation still exists (FR-015),
    then create via the existing create_capability path (FR-014),
    translating its hierarchy-consistency ValueError into a 422. Caller is
    responsible for the FR-016 permission check beforehand."""
    citation = suggestion.citations[0] if suggestion.citations else None
    if citation is not None and not await bstore.stage_exists(citation.entity_id, session):
        raise HTTPException(
            status_code=409,
            detail=f"Supporting stage {citation.entity_id!r} no longer exists; "
            "re-run the review.",
        )

    if suggestion.proposed_name is None or suggestion.proposed_level is None:
        # Unreachable in practice -- _build_propose_new_capability_suggestion
        # always sets both -- but satisfies the type checker's Optional
        # fields (shared across all suggestion types) without a cast.
        raise HTTPException(
            status_code=422, detail="Suggestion is missing proposed_name/proposed_level"
        )

    try:
        new_capability = await bstore.create_capability(
            BusinessCapabilityCreate(
                name=suggestion.proposed_name,
                description=suggestion.proposed_description,
                level=suggestion.proposed_level,
                parent_id=suggestion.proposed_parent_id,
            ),
            session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await session.commit()
    return new_capability


async def _remove_capability_from_suggestion(
    suggestion: CapabilitySuggestion, session: AsyncSession
) -> str:
    """flag_capability_for_removal accept logic (ADP-SPEC-040, portfolio
    scope only): re-verify the target capability still exists, then delete
    via the existing delete_capability path (FR-014) -- which itself already
    guards against removing a capability that still has children, exactly
    like the manual delete button. Caller is responsible for the FR-016
    permission check beforehand. Returns the removed capability's id."""
    target_id = suggestion.capability_id
    if target_id is None:  # pragma: no cover -- always set by the builder
        raise HTTPException(status_code=422, detail="Suggestion is missing capability_id")

    current = await bstore.get_capability(target_id, session)
    if current is None:
        raise HTTPException(status_code=404, detail=f"Capability {target_id!r} not found")

    try:
        deleted = await bstore.delete_capability(target_id, session)
    except bstore.ChildCapabilitiesExist as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot remove capability: it has {exc.count} child capability(ies). "
                "Delete or reassign them first."
            ),
        )
    if not deleted:  # pragma: no cover -- current-check above already guards this
        raise HTTPException(status_code=404, detail=f"Capability {target_id!r} not found")
    await session.commit()
    return target_id


@router.post(
    "/capabilities/{cap_id}/agent-review/{operation_id}/suggestions/{suggestion_id}/accept",
    response_model=CapabilitySuggestion,
)
async def accept_capability_suggestion(
    cap_id: str,
    operation_id: str,
    suggestion_id: str,
    body: SuggestionAcceptRequest,
    request: Request,
    session: AsyncSession = Depends(_get_session),
    op_store=Depends(_get_op_store),
):
    """Accept a suggestion (FR-014/FR-015/FR-016). Dispatches by type to the
    same store functions the manual edit UI already calls -- no new write path.
    """
    from adp.auth.deps import get_current_user

    suggestions, suggestion = await _get_pending_suggestion(op_store, operation_id, suggestion_id)

    if suggestion.advisory and not body.advisory_acknowledged:
        raise HTTPException(
            status_code=422,
            detail="This suggestion is advisory (an unverified citation); set "
            "advisory_acknowledged=true to accept it anyway.",
        )

    # Overridden below for propose_new_capability, whose write targets a
    # brand-new capability, not the one under review.
    affected_entity = cap_id

    if suggestion.type == "flag_duplicate":
        # US1: no store write, acknowledgment only.
        pass
    elif suggestion.type in ("reclassify_strategic_relevance", "set_maturity_level"):
        current = await bstore.get_capability(cap_id, session)
        if current is None:
            raise HTTPException(status_code=404, detail=f"Capability {cap_id!r} not found")

        is_relevance = suggestion.type == "reclassify_strategic_relevance"

        # FR-015: field-scoped stale check -- compare only the one field this
        # suggestion targets against its generation-time snapshot. A change to
        # an unrelated field does not block acceptance.
        current_value = current.strategic_relevance if is_relevance else current.maturity_level
        previous_value = (
            suggestion.previous_strategic_relevance if is_relevance
            else suggestion.previous_maturity_level
        )
        if current_value != previous_value:
            field_name = "strategic_relevance" if is_relevance else "maturity_level"
            raise HTTPException(
                status_code=409,
                detail=f"{field_name} has changed since this suggestion was generated; "
                "re-run the review.",
            )

        # FR-016: re-check the write permission independent of trigger/confirm.
        _require_write_business_arch(get_current_user(request))

        update = (
            BusinessCapabilityUpdate(strategic_relevance=suggestion.strategic_relevance)
            if is_relevance
            else BusinessCapabilityUpdate(maturity_level=suggestion.maturity_level)
        )
        await bstore.update_capability(cap_id, update, session)
        await session.commit()
    elif suggestion.type == "assign_domain":
        current = await bstore.get_capability(cap_id, session)
        if current is None:
            raise HTTPException(status_code=404, detail=f"Capability {cap_id!r} not found")

        # FR-015's degenerate case (research D8): assign_domain has no
        # previous_* snapshot field -- it's scoped to domain_id IS NULL
        # capabilities by construction, so the stale check degenerates to "is
        # it still unassigned."
        if current.domain_id is not None:
            raise HTTPException(
                status_code=409,
                detail="Capability has already been assigned a domain since this "
                "suggestion was generated; re-run the review.",
            )

        # FR-016: re-check the write permission independent of trigger/confirm.
        _require_write_business_arch(get_current_user(request))

        try:
            await bstore.assign_capability_domain(
                cap_id, CapabilityDomainAssign(domain_id=suggestion.domain_id), session
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        await session.commit()
    elif suggestion.type == "propose_new_capability":
        # FR-016: re-check the write permission independent of trigger/confirm.
        _require_write_business_arch(get_current_user(request))
        new_capability = await _create_capability_from_suggestion(suggestion, session)
        affected_entity = new_capability.id
    else:  # pragma: no cover -- unreachable, all five suggestion types handled above
        raise HTTPException(
            status_code=501, detail=f"Suggestion type {suggestion.type!r} not yet supported"
        )

    suggestion.status = AgentSuggestionStatus.ACCEPTED
    suggestions[suggestion_id] = suggestion.model_dump(mode="json")
    await op_store.update(operation_id, payload_patch={"suggestions": suggestions})

    actor = _get_actor(request)
    write_suggestion_audit(
        logger,
        actor=actor,
        action="business.capability.agent_review_accept",
        affected_entity=affected_entity,
        summary=f"accepted {suggestion.type} suggestion",
        operation_id=operation_id,
        suggestion_id=suggestion_id,
    )
    return suggestion


@router.post(
    "/capabilities/{cap_id}/agent-review/{operation_id}/suggestions/{suggestion_id}/reject",
    response_model=CapabilitySuggestion,
)
async def reject_capability_suggestion(
    cap_id: str,
    operation_id: str,
    suggestion_id: str,
    request: Request,
    op_store=Depends(_get_op_store),
):
    """Reject a suggestion (FR-017). No database write occurs."""
    suggestions, suggestion = await _get_pending_suggestion(op_store, operation_id, suggestion_id)

    suggestion.status = AgentSuggestionStatus.REJECTED
    suggestions[suggestion_id] = suggestion.model_dump(mode="json")
    await op_store.update(operation_id, payload_patch={"suggestions": suggestions})

    actor = _get_actor(request)
    logger.info(
        "business.capability.agent_review_reject id=%s actor=%s origin=ai "
        "operation_id=%s suggestion_id=%s",
        cap_id, actor, operation_id, suggestion_id,
    )
    return suggestion


# ── Agent Review: Portfolio scope (ADP-SPEC-040) ──────────────────────────────
# Reviews the WHOLE capability tree at once rather than one capability's
# direct links (contrast the per-capability endpoints above). Distinct route
# shape (no {cap_id} segment) -- no path collision with the per-capability
# routes, since FastAPI/Starlette match on segment shape and these differ in
# segment count/structure. Only two suggestion types are ever produced at
# this scope: propose_new_capability and flag_capability_for_removal (see
# agent_review.py's "Portfolio-scope review" section for why the other four
# don't apply here).

# operations.design_id is NOT NULL (no single reviewed entity at this scope).
_PORTFOLIO_OPERATION_SLOT = "PORTFOLIO"


@router.post(
    "/capabilities/agent-review",
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_portfolio_agent_review(
    background_tasks: BackgroundTasks,
    request: Request,
    op_store=Depends(_get_op_store),
    biz_session_factory=Depends(_get_biz_session_factory),
):
    """Trigger a whole-portfolio Agent Review. Returns 202 + operation_id."""
    operation_id = str(uuid.uuid4())
    actor = _get_actor(request)
    await op_store.create(
        operation_id, "agent_review", _PORTFOLIO_OPERATION_SLOT, actor, {"suggestions": {}}
    )

    llm_client = _make_agent_review_llm_client()

    async def _run() -> None:
        # See submit_capability_agent_review's identical comment: fresh
        # session from the injected (test-overridable) factory, since the
        # request-scoped session above closes once this endpoint returns.
        from adp.business.agent_review import run_portfolio_review

        async with biz_session_factory() as biz_session:
            await run_portfolio_review(
                operation_id=operation_id,
                biz_session=biz_session,
                llm_client=llm_client,
                op_store=op_store,
            )

    background_tasks.add_task(_run)
    logger.info("business.capability.agent_review.submit_portfolio actor=%s", actor)
    return {"operation_id": operation_id}


@router.get(
    "/capabilities/agent-review/{operation_id}",
    response_model=CapabilityAgentReviewResponse,
)
async def get_portfolio_agent_review(
    operation_id: str,
    op_store=Depends(_get_op_store),
):
    """Poll a portfolio Agent Review operation."""
    op = await op_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")

    suggestions = [
        CapabilitySuggestion.model_validate(raw)
        for raw in (op.get("suggestions") or {}).values()
    ]
    return CapabilityAgentReviewResponse(
        operation_id=operation_id,
        capability_id=None,
        status=op["status"],
        suggestions=suggestions,
        error_description=op.get("error_description"),
    )


@router.post(
    "/capabilities/agent-review/{operation_id}/suggestions/{suggestion_id}/accept",
    response_model=CapabilitySuggestion,
)
async def accept_portfolio_suggestion(
    operation_id: str,
    suggestion_id: str,
    body: SuggestionAcceptRequest,
    request: Request,
    session: AsyncSession = Depends(_get_session),
    op_store=Depends(_get_op_store),
):
    """Accept a portfolio-scope suggestion (FR-014/015/016)."""
    from adp.auth.deps import get_current_user

    suggestions, suggestion = await _get_pending_suggestion(op_store, operation_id, suggestion_id)

    if suggestion.advisory and not body.advisory_acknowledged:
        raise HTTPException(
            status_code=422,
            detail="This suggestion is advisory (an unverified citation); set "
            "advisory_acknowledged=true to accept it anyway.",
        )

    # FR-016: re-check the write permission independent of trigger/confirm.
    _require_write_business_arch(get_current_user(request))

    if suggestion.type == "propose_new_capability":
        new_capability = await _create_capability_from_suggestion(suggestion, session)
        affected_entity = new_capability.id
    elif suggestion.type == "flag_capability_for_removal":
        affected_entity = await _remove_capability_from_suggestion(suggestion, session)
    else:  # pragma: no cover -- unreachable, only two types ever produced at this scope
        raise HTTPException(
            status_code=501,
            detail=f"Suggestion type {suggestion.type!r} not supported at portfolio scope",
        )

    suggestion.status = AgentSuggestionStatus.ACCEPTED
    suggestions[suggestion_id] = suggestion.model_dump(mode="json")
    await op_store.update(operation_id, payload_patch={"suggestions": suggestions})

    actor = _get_actor(request)
    write_suggestion_audit(
        logger,
        actor=actor,
        action="business.capability.agent_review_accept",
        affected_entity=affected_entity,
        summary=f"accepted {suggestion.type} suggestion (portfolio review)",
        operation_id=operation_id,
        suggestion_id=suggestion_id,
    )
    return suggestion


@router.post(
    "/capabilities/agent-review/{operation_id}/suggestions/{suggestion_id}/reject",
    response_model=CapabilitySuggestion,
)
async def reject_portfolio_suggestion(
    operation_id: str,
    suggestion_id: str,
    request: Request,
    op_store=Depends(_get_op_store),
):
    """Reject a portfolio-scope suggestion (FR-017). No database write occurs."""
    suggestions, suggestion = await _get_pending_suggestion(op_store, operation_id, suggestion_id)

    suggestion.status = AgentSuggestionStatus.REJECTED
    suggestions[suggestion_id] = suggestion.model_dump(mode="json")
    await op_store.update(operation_id, payload_patch={"suggestions": suggestions})

    actor = _get_actor(request)
    logger.info(
        "business.capability.agent_review_reject actor=%s origin=ai "
        "operation_id=%s suggestion_id=%s (portfolio review)",
        actor, operation_id, suggestion_id,
    )
    return suggestion
