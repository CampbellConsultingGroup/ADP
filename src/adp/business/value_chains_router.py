"""Value chain routes (ADP-nag). Store functions live in ``adp.business.value_chains``.
Split out of ``adp.business.router`` (ADP-blp.27); registered in ``adp.api.app``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.business import value_chains as vcstore
from adp.business.models import (
    DuplicateStageCapError,
    StageCapabilitiesResponse,
    StageCapabilityLinkCreate,
    StageCapNotFoundError,
    ValueChain,
    ValueChainActivitiesReorder,
    ValueChainActivity,
    ValueChainActivityCreate,
    ValueChainActivityUpdate,
    ValueChainCreate,
    ValueChainDetail,
    ValueChainListResponse,
    ValueChainUpdate,
)
from adp.business.router_deps import (
    _get_actor,
    _get_session,
    logger,
)

# Same prefix and tag as adp.business.router. Registered on the app directly (not nested in
# that router): a nested router reports the matched route without the prefix, and the
# permission and metrics code read that.
router = APIRouter(prefix="/api/v1/business", tags=["business"])


# ── Value Chains (ADP-nag) ────────────────────────────────────────────────────
# Porter value chains: primary + support activities and the capabilities each
# depends on. Store functions live in adp.business.value_chains. Writes are
# authorised by the existing ("/api/v1/business/", WRITE_BUSINESS_ARCH) rule.


def _chain_not_found(chain_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Value chain {chain_id!r} not found")


def _activity_not_found(activity_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Activity {activity_id!r} not found")


@router.get("/value-chains", response_model=ValueChainListResponse)
async def list_value_chains(session: AsyncSession = Depends(_get_session)):
    items = await vcstore.list_value_chains(session)
    return ValueChainListResponse(items=items, total=len(items))


@router.post("/value-chains", response_model=ValueChain, status_code=status.HTTP_201_CREATED)
async def create_value_chain(
    body: ValueChainCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    chain = await vcstore.create_value_chain(body, session)
    await session.commit()
    logger.info(
        "business.value_chain.create id=%s name=%r actor=%s",
        chain.id, chain.name, _get_actor(request),
    )
    return chain


@router.get("/value-chains/{chain_id}", response_model=ValueChainDetail)
async def get_value_chain(chain_id: str, session: AsyncSession = Depends(_get_session)):
    chain = await vcstore.get_value_chain(chain_id, session)
    if chain is None:
        raise _chain_not_found(chain_id)
    return chain


@router.put("/value-chains/{chain_id}", response_model=ValueChain)
async def update_value_chain(
    chain_id: str,
    body: ValueChainUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    chain = await vcstore.update_value_chain(chain_id, body, session)
    if chain is None:
        raise _chain_not_found(chain_id)
    await session.commit()
    logger.info("business.value_chain.update id=%s actor=%s", chain_id, _get_actor(request))
    return chain


@router.delete("/value-chains/{chain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_value_chain(
    chain_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    if not await vcstore.delete_value_chain(chain_id, session):
        raise _chain_not_found(chain_id)
    await session.commit()
    logger.info("business.value_chain.delete id=%s actor=%s", chain_id, _get_actor(request))


@router.post(
    "/value-chains/{chain_id}/activities",
    response_model=ValueChainActivity,
    status_code=status.HTTP_201_CREATED,
)
async def add_value_chain_activity(
    chain_id: str,
    body: ValueChainActivityCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        activity = await vcstore.add_activity(chain_id, body, session)
    except LookupError:
        raise _chain_not_found(chain_id)
    await session.commit()
    logger.info(
        "business.value_chain.activity.add chain_id=%s activity_id=%s category=%s actor=%s",
        chain_id, activity.id, activity.category, _get_actor(request),
    )
    return activity


@router.put("/value-chains/{chain_id}/activities", response_model=ValueChainDetail)
async def reorder_value_chain_activities(
    chain_id: str,
    body: ValueChainActivitiesReorder,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        await vcstore.reorder_activities(chain_id, body.category, body.activity_ids, session)
    except LookupError:
        raise _chain_not_found(chain_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await session.commit()
    logger.info(
        "business.value_chain.activity.reorder chain_id=%s category=%s count=%d actor=%s",
        chain_id, body.category, len(body.activity_ids), _get_actor(request),
    )
    return await vcstore.get_value_chain(chain_id, session)


@router.put("/value-chains/{chain_id}/activities/{activity_id}", response_model=ValueChainActivity)
async def update_value_chain_activity(
    chain_id: str,
    activity_id: str,
    body: ValueChainActivityUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    activity = await vcstore.update_activity(chain_id, activity_id, body, session)
    if activity is None:
        raise _activity_not_found(activity_id)
    await session.commit()
    logger.info(
        "business.value_chain.activity.update chain_id=%s activity_id=%s actor=%s",
        chain_id, activity_id, _get_actor(request),
    )
    return activity


@router.delete(
    "/value-chains/{chain_id}/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_value_chain_activity(
    chain_id: str,
    activity_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    if not await vcstore.delete_activity(chain_id, activity_id, session):
        raise _activity_not_found(activity_id)
    await session.commit()
    logger.info(
        "business.value_chain.activity.delete chain_id=%s activity_id=%s actor=%s",
        chain_id, activity_id, _get_actor(request),
    )


@router.get(
    "/value-chains/{chain_id}/activities/{activity_id}/capabilities",
    response_model=StageCapabilitiesResponse,
)
async def list_value_chain_activity_capabilities(
    chain_id: str,
    activity_id: str,
    session: AsyncSession = Depends(_get_session),
):
    result = await vcstore.list_activity_caps(chain_id, activity_id, session)
    if result is None:
        raise _activity_not_found(activity_id)
    return result


@router.post(
    "/value-chains/{chain_id}/activities/{activity_id}/capabilities",
    response_model=StageCapabilitiesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def link_capability_to_value_chain_activity(
    chain_id: str,
    activity_id: str,
    body: StageCapabilityLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        result = await vcstore.link_cap_to_activity(chain_id, activity_id, body, session)
    except DuplicateStageCapError:
        raise HTTPException(status_code=409, detail="Capability is already linked to this activity")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    logger.info(
        "business.value_chain.activity.link_capability activity_id=%s cap_id=%s actor=%s",
        activity_id, body.capability_id, _get_actor(request),
    )
    return result


@router.delete(
    "/value-chains/{chain_id}/activities/{activity_id}/capabilities/{cap_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_capability_from_value_chain_activity(
    chain_id: str,
    activity_id: str,
    cap_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        await vcstore.unlink_cap_from_activity(chain_id, activity_id, cap_id, session)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except StageCapNotFoundError:
        raise HTTPException(status_code=404, detail=f"Link ({activity_id!r}, {cap_id!r}) not found")
    await session.commit()
    logger.info(
        "business.value_chain.activity.unlink_capability activity_id=%s cap_id=%s actor=%s",
        activity_id, cap_id, _get_actor(request),
    )
