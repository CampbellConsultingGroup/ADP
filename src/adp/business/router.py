"""Business Architecture API — ADP-SPEC-033/034.

GET/POST/PUT/DELETE /api/v1/business/capabilities   — 3-level capability hierarchy
GET/POST/PUT/DELETE /api/v1/business/value-streams  — value stream registry
POST/PUT/DELETE     /api/v1/business/value-streams/{id}/stages  — stage management
GET/POST/DELETE     /api/v1/business/capabilities/{id}/designs  — cap-design links
GET/POST/DELETE     /api/v1/business/value-streams/{id}/designs — vs-design links
GET                 /api/v1/business/designs/{id}/context       — reverse lookup

ART-V: write operations require authenticated actor.
ART-VI: mutations emit structured log entries (actor, entity, action).
ART-IX (SHOULD): structured logging used for business entities; design link mutations
         include the design_id for correlation but bypass the designs-table audit_entries
         to avoid creating spurious design versions (see research.md Decision 3).
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.agents.models import AgentSuggestionStatus
from adp.agents.provenance import write_suggestion_audit
from adp.business import store as bstore
from adp.business.models import (
    BusinessCapability,
    BusinessCapabilityCreate,
    BusinessCapabilityListResponse,
    BusinessCapabilityUpdate,
    BusinessContextResponse,
    CapabilityAgentReviewResponse,
    CapabilitySuggestion,
    DesignLinkCreate,
    DuplicateLinkError,
    LinkedDesignsResponse,
    LinkNotFoundError,
    SuggestionAcceptRequest,
    ValueStream,
    ValueStreamCreate,
    ValueStreamDetail,
    ValueStreamListResponse,
    ValueStreamStage,
    ValueStreamStageCreate,
    ValueStreamStagesReorder,
    ValueStreamStageUpdate,
    ValueStreamUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/business", tags=["business"])


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_actor(request: Request) -> str:
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


async def _get_session():
    factory = bstore._get_session_factory()
    async with factory() as session:
        yield session


async def _get_application_session():
    from adp.application import store as astore
    factory = astore._get_session_factory()
    async with factory() as session:
        yield session


async def _get_biz_session_factory():
    """Returns the session FACTORY (not a session) so a background task can
    open its own fresh session after the request-scoped one above has closed.
    A distinct dependency (not calling bstore._get_session_factory() directly
    inside the background closure) so tests can override it to a SQLite
    factory -- overriding _get_session alone would not reach the background
    task, since it isn't a request-scoped dependency."""
    return bstore._get_session_factory()


async def _get_application_session_factory():
    from adp.application import store as astore
    return astore._get_session_factory()


async def _get_op_store():
    from adp.api.deps import get_operation_store
    return await get_operation_store()


def _make_agent_review_llm_client():
    """Create an LLMClient for the Agent Review toolkit, or the shared stub
    when no API key is configured (mirrors _make_orchestrator in intake.py)."""
    from adp.agents.llm_stub import StubLLMClient
    from adp.api.routers.config import get_api_key, get_extraction_model
    from adp.llm.client import LLMClient

    endpoint = os.environ.get("ADP_LLM_ENDPOINT", "https://api.anthropic.com")
    api_key = get_api_key()
    if not api_key:
        return StubLLMClient(base_url="http://stub", api_key="stub", model="stub")
    return LLMClient(base_url=endpoint, api_key=api_key, model=get_extraction_model())


# ── Business Capabilities ─────────────────────────────────────────────────────

@router.get("/capabilities", response_model=BusinessCapabilityListResponse)
async def list_capabilities(session: AsyncSession = Depends(_get_session)):
    items = await bstore.list_capabilities(session)
    return BusinessCapabilityListResponse(items=items, total=len(items))


@router.post(
    "/capabilities", response_model=BusinessCapability, status_code=status.HTTP_201_CREATED
)
async def create_capability(
    body: BusinessCapabilityCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        cap = await bstore.create_capability(body, session)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    actor = _get_actor(request)
    logger.info(
        "business.capability.create id=%s name=%r level=%d actor=%s",
        cap.id, cap.name, cap.level, actor,
    )
    return cap


@router.get("/capabilities/{cap_id}", response_model=BusinessCapability)
async def get_capability(cap_id: str, session: AsyncSession = Depends(_get_session)):
    cap = await bstore.get_capability(cap_id, session)
    if cap is None:
        raise HTTPException(status_code=404, detail=f"Capability {cap_id!r} not found")
    return cap


@router.put("/capabilities/{cap_id}", response_model=BusinessCapability)
async def update_capability(
    cap_id: str,
    body: BusinessCapabilityUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    cap = await bstore.update_capability(cap_id, body, session)
    if cap is None:
        raise HTTPException(status_code=404, detail=f"Capability {cap_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("business.capability.update id=%s actor=%s", cap_id, actor)
    return cap


@router.delete("/capabilities/{cap_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capability(
    cap_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        deleted = await bstore.delete_capability(cap_id, session)
    except bstore.ChildCapabilitiesExist as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot delete capability: it has {exc.count} child capability(ies). "
                "Delete or reassign them first."
            ),
        )

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Capability {cap_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("business.capability.delete id=%s actor=%s", cap_id, actor)


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
        # FR-015: re-verify the supporting citation (the uncovered stage) still
        # exists before creating a record from this suggestion.
        citation = suggestion.citations[0] if suggestion.citations else None
        if citation is not None and not await bstore.stage_exists(citation.entity_id, session):
            raise HTTPException(
                status_code=409,
                detail=f"Supporting stage {citation.entity_id!r} no longer exists; "
                "re-run the review.",
            )

        # FR-016: re-check the write permission independent of trigger/confirm.
        _require_write_business_arch(get_current_user(request))

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


# ── Value Streams ─────────────────────────────────────────────────────────────

@router.get("/value-streams", response_model=ValueStreamListResponse)
async def list_value_streams(session: AsyncSession = Depends(_get_session)):
    items = await bstore.list_value_streams(session)
    return ValueStreamListResponse(items=items, total=len(items))


@router.post("/value-streams", response_model=ValueStream, status_code=status.HTTP_201_CREATED)
async def create_value_stream(
    body: ValueStreamCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    vs = await bstore.create_value_stream(body, session)
    await session.commit()

    actor = _get_actor(request)
    logger.info("business.value_stream.create id=%s name=%r actor=%s", vs.id, vs.name, actor)
    return vs


@router.get("/value-streams/{vs_id}", response_model=ValueStreamDetail)
async def get_value_stream(vs_id: str, session: AsyncSession = Depends(_get_session)):
    vs = await bstore.get_value_stream(vs_id, session)
    if vs is None:
        raise HTTPException(status_code=404, detail=f"Value stream {vs_id!r} not found")
    return vs


@router.put("/value-streams/{vs_id}", response_model=ValueStream)
async def update_value_stream(
    vs_id: str,
    body: ValueStreamUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    vs = await bstore.update_value_stream(vs_id, body, session)
    if vs is None:
        raise HTTPException(status_code=404, detail=f"Value stream {vs_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("business.value_stream.update id=%s actor=%s", vs_id, actor)
    return vs


@router.delete("/value-streams/{vs_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_value_stream(
    vs_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await bstore.delete_value_stream(vs_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Value stream {vs_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("business.value_stream.delete id=%s actor=%s", vs_id, actor)


# ── Value Stream Stages ───────────────────────────────────────────────────────

@router.post(
    "/value-streams/{vs_id}/stages",
    response_model=ValueStreamStage,
    status_code=status.HTTP_201_CREATED,
)
async def add_stage(
    vs_id: str,
    body: ValueStreamStageCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    vs = await bstore.get_value_stream(vs_id, session)
    if vs is None:
        raise HTTPException(status_code=404, detail=f"Value stream {vs_id!r} not found")

    stage = await bstore.add_stage(vs_id, body, session)
    await session.commit()

    actor = _get_actor(request)
    logger.info("business.stage.add vs_id=%s stage_id=%s actor=%s", vs_id, stage.id, actor)
    return stage


@router.put("/value-streams/{vs_id}/stages/{stage_id}", response_model=ValueStreamStage)
async def update_stage(
    vs_id: str,
    stage_id: str,
    body: ValueStreamStageUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    vs = await bstore.get_value_stream(vs_id, session)
    if vs is None:
        raise HTTPException(status_code=404, detail=f"Value stream {vs_id!r} not found")

    stage = await bstore.update_stage(vs_id, stage_id, body, session)
    if stage is None:
        raise HTTPException(status_code=404, detail=f"Stage {stage_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("business.stage.update vs_id=%s stage_id=%s actor=%s", vs_id, stage_id, actor)
    return stage


@router.delete("/value-streams/{vs_id}/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stage(
    vs_id: str,
    stage_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    vs = await bstore.get_value_stream(vs_id, session)
    if vs is None:
        raise HTTPException(status_code=404, detail=f"Value stream {vs_id!r} not found")

    deleted = await bstore.delete_stage(vs_id, stage_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Stage {stage_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("business.stage.delete vs_id=%s stage_id=%s actor=%s", vs_id, stage_id, actor)


@router.put("/value-streams/{vs_id}/stages", response_model=ValueStreamDetail)
async def reorder_stages(
    vs_id: str,
    body: ValueStreamStagesReorder,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    vs = await bstore.get_value_stream(vs_id, session)
    if vs is None:
        raise HTTPException(status_code=404, detail=f"Value stream {vs_id!r} not found")

    try:
        stages = await bstore.reorder_stages(vs_id, body.stages, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await session.commit()

    actor = _get_actor(request)
    logger.info("business.stage.reorder vs_id=%s count=%d actor=%s", vs_id, len(stages), actor)

    # Return full detail
    vs_refreshed = await bstore.get_value_stream(vs_id, session)
    return vs_refreshed


# ── Capability–Design Links (ADP-SPEC-034) ────────────────────────────────────

@router.get("/capabilities/{cap_id}/designs", response_model=LinkedDesignsResponse)
async def list_capability_designs(
    cap_id: str,
    session: AsyncSession = Depends(_get_session),
):
    cap = await bstore.get_capability(cap_id, session)
    if cap is None:
        raise HTTPException(status_code=404, detail=f"Capability {cap_id!r} not found")
    items = await bstore.list_capability_designs(cap_id, session)
    return LinkedDesignsResponse(items=items)


@router.post(
    "/capabilities/{cap_id}/designs",
    response_model=LinkedDesignsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def link_design_to_capability(
    cap_id: str,
    body: DesignLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    cap = await bstore.get_capability(cap_id, session)
    if cap is None:
        raise HTTPException(status_code=404, detail=f"Capability {cap_id!r} not found")
    try:
        await bstore.link_design_to_capability(cap_id, body.design_id, session)
    except DuplicateLinkError:
        raise HTTPException(status_code=409, detail="Design is already linked to this capability")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()

    actor = _get_actor(request)
    logger.info(
        "business.capability.link_design cap_id=%s design_id=%s actor=%s",
        cap_id, body.design_id, actor,
    )
    items = await bstore.list_capability_designs(cap_id, session)
    return LinkedDesignsResponse(items=items)


@router.delete(
    "/capabilities/{cap_id}/designs/{design_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_design_from_capability(
    cap_id: str,
    design_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    cap = await bstore.get_capability(cap_id, session)
    if cap is None:
        raise HTTPException(status_code=404, detail=f"Capability {cap_id!r} not found")
    try:
        await bstore.unlink_design_from_capability(cap_id, design_id, session)
    except LinkNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Design {design_id!r} is not linked to capability {cap_id!r}",
        )
    await session.commit()

    actor = _get_actor(request)
    logger.info(
        "business.capability.unlink_design cap_id=%s design_id=%s actor=%s",
        cap_id, design_id, actor,
    )


# ── Value-Stream–Design Links (ADP-SPEC-034) ──────────────────────────────────

@router.get("/value-streams/{vs_id}/designs", response_model=LinkedDesignsResponse)
async def list_value_stream_designs(
    vs_id: str,
    session: AsyncSession = Depends(_get_session),
):
    vs = await bstore.get_value_stream(vs_id, session)
    if vs is None:
        raise HTTPException(status_code=404, detail=f"Value stream {vs_id!r} not found")
    items = await bstore.list_value_stream_designs(vs_id, session)
    return LinkedDesignsResponse(items=items)


@router.post(
    "/value-streams/{vs_id}/designs",
    response_model=LinkedDesignsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def link_design_to_value_stream(
    vs_id: str,
    body: DesignLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    vs = await bstore.get_value_stream(vs_id, session)
    if vs is None:
        raise HTTPException(status_code=404, detail=f"Value stream {vs_id!r} not found")
    try:
        await bstore.link_design_to_value_stream(vs_id, body.design_id, session)
    except DuplicateLinkError:
        raise HTTPException(status_code=409, detail="Design is already linked to this value stream")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()

    actor = _get_actor(request)
    logger.info(
        "business.value_stream.link_design vs_id=%s design_id=%s actor=%s",
        vs_id, body.design_id, actor,
    )
    items = await bstore.list_value_stream_designs(vs_id, session)
    return LinkedDesignsResponse(items=items)


@router.delete(
    "/value-streams/{vs_id}/designs/{design_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_design_from_value_stream(
    vs_id: str,
    design_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    vs = await bstore.get_value_stream(vs_id, session)
    if vs is None:
        raise HTTPException(status_code=404, detail=f"Value stream {vs_id!r} not found")
    try:
        await bstore.unlink_design_from_value_stream(vs_id, design_id, session)
    except LinkNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Design {design_id!r} is not linked to value stream {vs_id!r}",
        )
    await session.commit()

    actor = _get_actor(request)
    logger.info(
        "business.value_stream.unlink_design vs_id=%s design_id=%s actor=%s",
        vs_id, design_id, actor,
    )


# ── Design Business Context (ADP-SPEC-034) ────────────────────────────────────

@router.get("/designs/{design_id}/context", response_model=BusinessContextResponse)
async def get_design_business_context(
    design_id: str,
    session: AsyncSession = Depends(_get_session),
):
    try:
        return await bstore.get_design_business_context(design_id, session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Business Domains (ADP-SPEC-035 US1) ──────────────────────────────────────

from adp.business.models import (  # noqa: E402 — appended block
    BusinessDomain,
    BusinessDomainCreate,
    BusinessDomainUpdate,
    CapabilityDomainAssign,
    DomainDetail,
    DomainListResponse,
    DuplicateStageCapError,
    StageCapabilitiesResponse,
    StageCapabilityLinkCreate,
    StageCapNotFoundError,
)


@router.get("/domains", response_model=DomainListResponse)
async def list_domains(session: AsyncSession = Depends(_get_session)):
    return await bstore.list_domains(session)


@router.post("/domains", response_model=BusinessDomain, status_code=status.HTTP_201_CREATED)
async def create_domain(
    body: BusinessDomainCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    domain = await bstore.create_domain(body, session)
    await session.commit()
    actor = _get_actor(request)
    logger.info("business.domain.create id=%s name=%r actor=%s", domain.id, domain.name, actor)
    return domain


@router.get("/domains/{domain_id}", response_model=DomainDetail)
async def get_domain(domain_id: str, session: AsyncSession = Depends(_get_session)):
    domain = await bstore.get_domain(domain_id, session)
    if domain is None:
        raise HTTPException(status_code=404, detail=f"Domain {domain_id!r} not found")
    return domain


@router.put("/domains/{domain_id}", response_model=BusinessDomain)
async def update_domain(
    domain_id: str,
    body: BusinessDomainUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    domain = await bstore.update_domain(domain_id, body, session)
    if domain is None:
        raise HTTPException(status_code=404, detail=f"Domain {domain_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("business.domain.update id=%s actor=%s", domain_id, actor)
    return domain


@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(
    domain_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await bstore.delete_domain(domain_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Domain {domain_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("business.domain.delete id=%s actor=%s", domain_id, actor)


# ── Capability-Domain Assignment (ADP-SPEC-035 US2) ──────────────────────────

@router.patch("/capabilities/{cap_id}/domain", response_model=BusinessCapability)
async def assign_capability_domain(
    cap_id: str,
    body: CapabilityDomainAssign,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        cap = await bstore.assign_capability_domain(cap_id, body, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if cap is None:
        raise HTTPException(status_code=404, detail=f"Capability {cap_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "business.capability.assign_domain cap_id=%s domain_id=%s actor=%s",
        cap_id, body.domain_id, actor,
    )
    return cap


# ── Stage-Capability Mapping (ADP-SPEC-035 US3) ───────────────────────────────

@router.get(
    "/value-streams/{vs_id}/stages/{stage_id}/capabilities",
    response_model=StageCapabilitiesResponse,
)
async def list_stage_capabilities(
    vs_id: str,
    stage_id: str,
    session: AsyncSession = Depends(_get_session),
):
    result = await bstore.list_stage_caps(vs_id, stage_id, session)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Stage {stage_id!r} not found")
    return result


@router.post(
    "/value-streams/{vs_id}/stages/{stage_id}/capabilities",
    response_model=StageCapabilitiesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def link_capability_to_stage(
    vs_id: str,
    stage_id: str,
    body: StageCapabilityLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        result = await bstore.link_cap_to_stage(vs_id, stage_id, body, session)
    except DuplicateStageCapError:
        raise HTTPException(status_code=409, detail="Capability is already linked to this stage")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "business.stage.link_capability stage_id=%s cap_id=%s actor=%s",
        stage_id, body.capability_id, actor,
    )
    return result


@router.delete(
    "/value-streams/{vs_id}/stages/{stage_id}/capabilities/{cap_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_capability_from_stage(
    vs_id: str,
    stage_id: str,
    cap_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        await bstore.unlink_cap_from_stage(vs_id, stage_id, cap_id, session)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except StageCapNotFoundError:
        raise HTTPException(status_code=404, detail=f"Link ({stage_id!r}, {cap_id!r}) not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "business.stage.unlink_capability stage_id=%s cap_id=%s actor=%s",
        stage_id, cap_id, actor,
    )
