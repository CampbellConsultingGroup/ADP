"""Application capability routes (937-application-capabilities, ADP-6et.1).

``/api/v1/application-capabilities``. Writes are gated by the
``("/api/v1/application-capabilities", WRITE_APPLICATION)`` prefix rule (no new ActionType);
reads need platform read access only. The literal ``by-*`` reverse-lookup routes are declared
before ``/{ac_id}`` so they are never captured as an id.
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.application import app_capabilities as acstore
from adp.application import cap_analysis as analysis
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
from adp.application.cap_analysis_models import (
    CapabilityFindings,
    CapabilityRollupResponse,
    ImpactResult,
    TechnologyDependenciesResponse,
)
from adp.application.cap_analysis_store import build_snapshot
from adp.application.router import _get_actor, _get_session
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.permissions import is_permitted
from adp.authz.roles import ActionType

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


# ── Analysis (938-capability-model-analysis, ADP-6et.2) ────────────────────────
# All derived on read, never stored. GETs are open reads; cost and risk content is gated inline
# (research R3) and never even queried for a caller without READ_APPLICATION_COST/_RISK.


@router.get("/analysis/business-rollup", response_model=CapabilityRollupResponse)
async def business_rollup(
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> CapabilityRollupResponse:
    snapshot = await build_snapshot(
        session,
        risk_visible=is_permitted(user.role, ActionType.READ_APPLICATION_RISK),
        cost_visible=is_permitted(user.role, ActionType.READ_APPLICATION_COST),
    )
    return analysis.business_rollup(snapshot, date.today())


@router.get("/analysis/technical-capabilities/{tc_id}/impact", response_model=ImpactResult)
async def technical_capability_impact(
    tc_id: str, session: AsyncSession = Depends(_get_session)
) -> ImpactResult:
    snapshot = await build_snapshot(session, risk_visible=False, cost_visible=False)
    result = analysis.impact(snapshot, tc_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Technical capability {tc_id!r} not found")
    return result


@router.get(
    "/analysis/business-capabilities/{cap_id}/technology",
    response_model=TechnologyDependenciesResponse,
)
async def business_capability_technology(
    cap_id: str, session: AsyncSession = Depends(_get_session)
) -> TechnologyDependenciesResponse:
    snapshot = await build_snapshot(session, risk_visible=False, cost_visible=False)
    today = date.today()
    items = analysis.technology_dependencies(snapshot, cap_id, today)
    if items is None:
        raise HTTPException(status_code=404, detail=f"Business capability {cap_id!r} not found")
    return TechnologyDependenciesResponse(as_of=today, items=items)


@router.get("/analysis/findings", response_model=CapabilityFindings)
async def capability_findings(session: AsyncSession = Depends(_get_session)) -> CapabilityFindings:
    snapshot = await build_snapshot(session, risk_visible=False, cost_visible=False)
    return analysis.findings(snapshot)


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
