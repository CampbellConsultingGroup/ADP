"""Framework jurisdiction and applicability routes (948 GEO-03, ADP-bo1.3).

Under ``/api/v1/compliance`` so the jurisdiction PUT rides the ``/api/v1/compliance/`` prefix rule
(WRITE_COMPLIANCE). Reads are open. Registered in ``adp.api.app`` beside the compliance router
(never nested in it). Shares that router's session dependency, so a test overriding
``crouter._get_session`` covers these routes too.
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from adp.compliance import jurisdiction
from adp.compliance.models import (
    FrameworkApplicabilityResponse,
    FrameworkJurisdiction,
    SetFrameworkJurisdiction,
    SubjectApplicabilityResponse,
)
from adp.compliance.router import _get_actor, _get_session

logger = logging.getLogger("adp.compliance.router")

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/frameworks/{framework_id}/jurisdiction", response_model=FrameworkJurisdiction)
async def get_jurisdiction(
    framework_id: str, session: AsyncSession = Depends(_get_session)
) -> FrameworkJurisdiction:
    try:
        return await jurisdiction.get_jurisdiction(framework_id, session)
    except jurisdiction.FrameworkNotFound as exc:
        raise _not_found(exc) from exc


@router.put("/frameworks/{framework_id}/jurisdiction", response_model=FrameworkJurisdiction)
async def set_jurisdiction(
    framework_id: str,
    body: SetFrameworkJurisdiction,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> FrameworkJurisdiction:
    try:
        out = await jurisdiction.set_jurisdiction(framework_id, body, session)
    except jurisdiction.FrameworkNotFound as exc:
        raise _not_found(exc) from exc
    except jurisdiction.JurisdictionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    logger.info(
        "compliance.framework.jurisdiction id=%s geographies=%s triggers=%s actor=%s",
        framework_id,
        ",".join(g.id for g in out.geographies),
        ",".join(f"{t.subject_type}:{t.relation}" for t in out.triggers),
        _get_actor(request),
    )
    return out


@router.get(
    "/frameworks/{framework_id}/applicability", response_model=FrameworkApplicabilityResponse
)
async def get_framework_applicability(
    framework_id: str,
    as_of: date | None = None,
    session: AsyncSession = Depends(_get_session),
) -> FrameworkApplicabilityResponse:
    try:
        return await jurisdiction.framework_applicability(framework_id, session, as_of)
    except jurisdiction.FrameworkNotFound as exc:
        raise _not_found(exc) from exc


async def _subject(
    subject_type: str, subject_id: str, as_of: date | None, session: AsyncSession
) -> SubjectApplicabilityResponse:
    try:
        return await jurisdiction.subject_applicability(subject_type, subject_id, session, as_of)
    except jurisdiction.SubjectNotFound as exc:
        raise _not_found(exc) from exc


@router.get(
    "/applications/{application_id}/applicability", response_model=SubjectApplicabilityResponse
)
async def get_application_applicability(
    application_id: str,
    as_of: date | None = None,
    session: AsyncSession = Depends(_get_session),
) -> SubjectApplicabilityResponse:
    return await _subject("application", application_id, as_of, session)


@router.get(
    "/legal-entities/{legal_entity_id}/applicability", response_model=SubjectApplicabilityResponse
)
async def get_legal_entity_applicability(
    legal_entity_id: str,
    as_of: date | None = None,
    session: AsyncSession = Depends(_get_session),
) -> SubjectApplicabilityResponse:
    return await _subject("legal_entity", legal_entity_id, as_of, session)
