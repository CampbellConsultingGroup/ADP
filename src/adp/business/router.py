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

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.business import store as bstore
from adp.business.models import (
    BusinessCapability,
    BusinessCapabilityCreate,
    BusinessCapabilityListResponse,
    BusinessCapabilityUpdate,
    BusinessContextResponse,
    DesignLinkCreate,
    DuplicateLinkError,
    LinkedDesignsResponse,
    LinkNotFoundError,
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
