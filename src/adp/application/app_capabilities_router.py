"""Application capability routes (937-application-capabilities, ADP-6et.1).

``/api/v1/application-capabilities``. Writes are gated by the
``("/api/v1/application-capabilities", WRITE_APPLICATION)`` prefix rule (no new ActionType);
reads need platform read access only. The literal ``by-*`` reverse-lookup routes are declared
before ``/{ac_id}`` so they are never captured as an id.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.application import app_capabilities as acstore
from adp.application.app_capability_models import (
    AppCapDepthError,
    AppCapError,
    AppCapHasChildrenError,
    AppCapNotFoundError,
    AppCapSummary,
    AppCapWarning,
    ApplicationCapability,
    ApplicationCapabilityCreate,
    ApplicationCapabilityDetail,
    ApplicationCapabilityListResponse,
    ApplicationCapabilityUpdate,
    BusinessCapabilityLinkCreate,
    CapabilityLevelError,
    DuplicateAppCapLinkError,
    DuplicateSiblingNameError,
    RealizationCreate,
    TechCapabilityLinkCreate,
)
from adp.application.router import _get_actor, _get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/application-capabilities", tags=["application-capabilities"])

_STATUS: list[tuple[type[AppCapError], int]] = [
    (AppCapNotFoundError, status.HTTP_404_NOT_FOUND),
    (AppCapDepthError, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (CapabilityLevelError, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (AppCapHasChildrenError, status.HTTP_409_CONFLICT),
    (DuplicateSiblingNameError, status.HTTP_409_CONFLICT),
    (DuplicateAppCapLinkError, status.HTTP_409_CONFLICT),
]


def _http(exc: AppCapError) -> HTTPException:
    for cls, code in _STATUS:
        if isinstance(exc, cls):
            return HTTPException(status_code=code, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))  # pragma: no cover


async def _detail_or_404(ac_id: str, session: AsyncSession) -> ApplicationCapabilityDetail:
    detail = await acstore.get_app_capability_detail(ac_id, session)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Application capability {ac_id!r} not found")
    return detail


# ── Catalog ───────────────────────────────────────────────────────────────────


@router.get("", response_model=ApplicationCapabilityListResponse)
async def list_app_capabilities(
    warning: AppCapWarning | None = Query(default=None),
    session: AsyncSession = Depends(_get_session),
) -> ApplicationCapabilityListResponse:
    return await acstore.list_app_capabilities(session, warning=warning)


@router.post("", response_model=ApplicationCapability, status_code=status.HTTP_201_CREATED)
async def create_app_capability(
    body: ApplicationCapabilityCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> ApplicationCapability:
    try:
        created = await acstore.create_app_capability(body, session)
    except AppCapError as exc:
        raise _http(exc) from exc
    await session.commit()
    logger.info(
        "app_capability.create id=%s name=%r level=%d actor=%s",
        created.id,
        created.name,
        created.level,
        _get_actor(request),
    )
    return created


# Reverse lookups: declared before /{ac_id}.


@router.get("/by-business-capability/{cap_id}", response_model=list[AppCapSummary])
async def list_by_business_capability(
    cap_id: str, session: AsyncSession = Depends(_get_session)
) -> list[AppCapSummary]:
    return await acstore.list_by_business_capability(cap_id, session)


@router.get("/by-technical-capability/{tc_id}", response_model=list[AppCapSummary])
async def list_by_technical_capability(
    tc_id: str, session: AsyncSession = Depends(_get_session)
) -> list[AppCapSummary]:
    return await acstore.list_by_technical_capability(tc_id, session)


@router.get("/by-application/{app_id}", response_model=list[AppCapSummary])
async def list_by_application(
    app_id: str, session: AsyncSession = Depends(_get_session)
) -> list[AppCapSummary]:
    return await acstore.list_by_application(app_id, session)


@router.get("/{ac_id}", response_model=ApplicationCapabilityDetail)
async def get_app_capability(
    ac_id: str, session: AsyncSession = Depends(_get_session)
) -> ApplicationCapabilityDetail:
    return await _detail_or_404(ac_id, session)


@router.patch("/{ac_id}", response_model=ApplicationCapability)
async def update_app_capability(
    ac_id: str,
    body: ApplicationCapabilityUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> ApplicationCapability:
    try:
        updated = await acstore.update_app_capability(ac_id, body, session)
    except AppCapError as exc:
        raise _http(exc) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Application capability {ac_id!r} not found")
    await session.commit()
    logger.info("app_capability.update id=%s actor=%s", ac_id, _get_actor(request))
    return updated


@router.delete("/{ac_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app_capability(
    ac_id: str, request: Request, session: AsyncSession = Depends(_get_session)
) -> None:
    try:
        deleted = await acstore.delete_app_capability(ac_id, session)
    except AppCapError as exc:
        raise _http(exc) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Application capability {ac_id!r} not found")
    await session.commit()
    logger.info("app_capability.delete id=%s actor=%s", ac_id, _get_actor(request))


# ── Links ─────────────────────────────────────────────────────────────────────


def _log_link(action: str, kind: str, ac_id: str, target: str, request: Request) -> None:
    logger.info(
        "app_capability.link.%s kind=%s id=%s target=%s actor=%s",
        action,
        kind,
        ac_id,
        target,
        _get_actor(request),
    )


@router.post(
    "/{ac_id}/business-capabilities",
    response_model=ApplicationCapabilityDetail,
    status_code=status.HTTP_201_CREATED,
)
async def add_business_link(
    ac_id: str,
    body: BusinessCapabilityLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> ApplicationCapabilityDetail:
    try:
        await acstore.add_business_link(ac_id, body.business_capability_id, session)
    except AppCapError as exc:
        raise _http(exc) from exc
    await session.commit()
    _log_link("create", "business", ac_id, body.business_capability_id, request)
    return await _detail_or_404(ac_id, session)


@router.delete("/{ac_id}/business-capabilities/{cap_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_business_link(
    ac_id: str, cap_id: str, request: Request, session: AsyncSession = Depends(_get_session)
) -> None:
    if not await acstore.remove_business_link(ac_id, cap_id, session):
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    _log_link("delete", "business", ac_id, cap_id, request)


@router.post(
    "/{ac_id}/technical-capabilities",
    response_model=ApplicationCapabilityDetail,
    status_code=status.HTTP_201_CREATED,
)
async def add_tech_link(
    ac_id: str,
    body: TechCapabilityLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> ApplicationCapabilityDetail:
    try:
        await acstore.add_tech_link(ac_id, body.tech_cap_id, session)
    except AppCapError as exc:
        raise _http(exc) from exc
    await session.commit()
    _log_link("create", "technical", ac_id, body.tech_cap_id, request)
    return await _detail_or_404(ac_id, session)


@router.delete("/{ac_id}/technical-capabilities/{tc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_tech_link(
    ac_id: str, tc_id: str, request: Request, session: AsyncSession = Depends(_get_session)
) -> None:
    if not await acstore.remove_tech_link(ac_id, tc_id, session):
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    _log_link("delete", "technical", ac_id, tc_id, request)


@router.post(
    "/{ac_id}/applications",
    response_model=ApplicationCapabilityDetail,
    status_code=status.HTTP_201_CREATED,
)
async def add_realization(
    ac_id: str,
    body: RealizationCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> ApplicationCapabilityDetail:
    try:
        await acstore.add_realization(ac_id, body.app_id, session)
    except AppCapError as exc:
        raise _http(exc) from exc
    await session.commit()
    _log_link("create", "application", ac_id, body.app_id, request)
    return await _detail_or_404(ac_id, session)


@router.delete("/{ac_id}/applications/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_realization(
    ac_id: str, app_id: str, request: Request, session: AsyncSession = Depends(_get_session)
) -> None:
    if not await acstore.remove_realization(ac_id, app_id, session):
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    _log_link("delete", "application", ac_id, app_id, request)
