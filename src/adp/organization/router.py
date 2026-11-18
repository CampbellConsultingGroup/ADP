"""Org Units and Geography routes (940-org-units-geography, ADP-55k.1).

Under ``/api/v1/business/`` so writes ride the existing
``("/api/v1/business/", WRITE_BUSINESS_ARCH)`` prefix rule (no new permission). Reads are
open. The literal ``/org-units/unmatched...`` routes are declared before
``/org-units/{ou_id}`` so they are never captured as an id. Registered in ``adp.api.app``
before the business router.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.api.common import session_dependency
from adp.organization import cap_mappings, regional
from adp.organization import store as ostore
from adp.organization.models import (
    AddMapping,
    CapabilityOrgFindings,
    CapabilityOrgMapping,
    CapabilityOrgMappingsResponse,
    CapabilityOrgView,
    DepthError,
    DuplicateCodeError,
    DuplicateLinkError,
    DuplicateSiblingError,
    Geography,
    GeographyCreate,
    GeographyLinkCreate,
    GeographyListResponse,
    GeographyUpdate,
    HasChildrenError,
    InvalidCodeError,
    LevelRuleError,
    OrganizationError,
    OrgNotFoundError,
    OrgUnit,
    OrgUnitCreate,
    OrgUnitDetail,
    OrgUnitFootprint,
    OrgUnitListResponse,
    OrgUnitUpdate,
    RegionalAssessment,
    RegionalAssessmentListResponse,
    RegionalHeatmap,
    RegionScope,
    ResolveResult,
    ResolveUnmatched,
    SetOwner,
    SetRegionalAssessment,
    SetRegionScope,
    UnknownReferenceError,
    UnmatchedListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/business", tags=["organization"])

_STATUS: list[tuple[type[OrganizationError], int]] = [
    (OrgNotFoundError, status.HTTP_404_NOT_FOUND),
    (DepthError, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (InvalidCodeError, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (LevelRuleError, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (UnknownReferenceError, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (HasChildrenError, status.HTTP_409_CONFLICT),
    (DuplicateSiblingError, status.HTTP_409_CONFLICT),
    (DuplicateCodeError, status.HTTP_409_CONFLICT),
    (DuplicateLinkError, status.HTTP_409_CONFLICT),
]


def _http(exc: OrganizationError) -> HTTPException:
    for cls, code in _STATUS:
        if isinstance(exc, cls):
            return HTTPException(status_code=code, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))  # pragma: no cover


_get_session = session_dependency("adp.organization.store")


def _actor(request: Request) -> str:
    from adp.auth.models import UNAUTHENTICATED_USER

    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return str(user.username)
    return request.headers.get("X-Actor", "architect")


def _log(event: str, request: Request, **fields: object) -> None:
    detail = " ".join(f"{k}={v}" for k, v in fields.items())
    logger.info("organization.%s %s actor=%s", event, detail, _actor(request))


# ── Review queue (US4) -- literal routes before /org-units/{ou_id} ─────────────


@router.get("/org-units/unmatched", response_model=UnmatchedListResponse)
async def list_unmatched(session: AsyncSession = Depends(_get_session)) -> UnmatchedListResponse:
    return await ostore.list_unmatched(session)


@router.post("/org-units/unmatched/resolve", response_model=ResolveResult)
async def resolve_unmatched(
    body: ResolveUnmatched, request: Request, session: AsyncSession = Depends(_get_session)
) -> ResolveResult:
    try:
        result = await ostore.resolve_unmatched(body, session)
    except OrganizationError as exc:
        await session.rollback()
        raise _http(exc) from exc
    await session.commit()
    _log(
        "unmatched.resolve",
        request,
        value=repr(body.value),
        org_unit=result.org_unit.id,
        created=body.create is not None,
        count=result.updated_count,
    )
    return result


# ── Org units (US1, US3) ──────────────────────────────────────────────────────


@router.get("/org-units", response_model=OrgUnitListResponse)
async def list_org_units(session: AsyncSession = Depends(_get_session)) -> OrgUnitListResponse:
    return await ostore.list_org_units(session)


@router.post("/org-units", response_model=OrgUnit, status_code=status.HTTP_201_CREATED)
async def create_org_unit(
    body: OrgUnitCreate, request: Request, session: AsyncSession = Depends(_get_session)
) -> OrgUnit:
    try:
        ou = await ostore.create_org_unit(body, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    await session.commit()
    _log("org_unit.create", request, id=ou.id, parent=ou.parent_id)
    return ou


@router.get("/org-units/{ou_id}", response_model=OrgUnitDetail)
async def get_org_unit(ou_id: str, session: AsyncSession = Depends(_get_session)) -> OrgUnitDetail:
    ou = await ostore.get_org_unit(ou_id, session)
    if ou is None:
        raise HTTPException(status_code=404, detail=f"Org unit {ou_id!r} not found")
    return ou


@router.patch("/org-units/{ou_id}", response_model=OrgUnit)
async def update_org_unit(
    ou_id: str, body: OrgUnitUpdate, request: Request, session: AsyncSession = Depends(_get_session)
) -> OrgUnit:
    try:
        ou = await ostore.update_org_unit(ou_id, body, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    if ou is None:
        raise HTTPException(status_code=404, detail=f"Org unit {ou_id!r} not found")
    await session.commit()
    _log("org_unit.update", request, id=ou_id)
    return ou


@router.delete("/org-units/{ou_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org_unit(
    ou_id: str, request: Request, session: AsyncSession = Depends(_get_session)
) -> Response:
    try:
        deleted = await ostore.delete_org_unit(ou_id, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Org unit {ou_id!r} not found")
    await session.commit()
    _log("org_unit.delete", request, id=ou_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/org-units/{ou_id}/geographies", response_model=OrgUnit, status_code=status.HTTP_201_CREATED
)
async def link_geography(
    ou_id: str,
    body: GeographyLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> OrgUnit:
    try:
        ou = await ostore.link_geography(ou_id, body.geography_id, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    await session.commit()
    _log("org_unit.link_geography", request, id=ou_id, geography=body.geography_id)
    return ou


@router.delete("/org-units/{ou_id}/geographies/{geo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_geography(
    ou_id: str, geo_id: str, request: Request, session: AsyncSession = Depends(_get_session)
) -> Response:
    if not await ostore.unlink_geography(ou_id, geo_id, session):
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    _log("org_unit.unlink_geography", request, id=ou_id, geography=geo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Geography (US2, US3) ──────────────────────────────────────────────────────


@router.get("/geographies", response_model=GeographyListResponse)
async def list_geographies(session: AsyncSession = Depends(_get_session)) -> GeographyListResponse:
    return await ostore.list_geographies(session)


@router.post("/geographies", response_model=Geography, status_code=status.HTTP_201_CREATED)
async def create_geography(
    body: GeographyCreate, request: Request, session: AsyncSession = Depends(_get_session)
) -> Geography:
    try:
        geo = await ostore.create_geography(body, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    await session.commit()
    _log("geography.create", request, id=geo.id, parent=geo.parent_id)
    return geo


@router.patch("/geographies/{geo_id}", response_model=Geography)
async def update_geography(
    geo_id: str,
    body: GeographyUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> Geography:
    try:
        geo = await ostore.update_geography(geo_id, body, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    if geo is None:
        raise HTTPException(status_code=404, detail=f"Geography {geo_id!r} not found")
    await session.commit()
    _log("geography.update", request, id=geo_id)
    return geo


@router.delete("/geographies/{geo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_geography(
    geo_id: str, request: Request, session: AsyncSession = Depends(_get_session)
) -> Response:
    try:
        deleted = await ostore.delete_geography(geo_id, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Geography {geo_id!r} not found")
    await session.commit()
    _log("geography.delete", request, id=geo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/geographies/{geo_id}/org-units", response_model=list[OrgUnit])
async def geography_org_units(
    geo_id: str, session: AsyncSession = Depends(_get_session)
) -> list[OrgUnit]:
    items = await ostore.org_units_for_geography(geo_id, session)
    if items is None:
        raise HTTPException(status_code=404, detail=f"Geography {geo_id!r} not found")
    return items


# ── Capability <-> org unit mappings (941-capability-org-mappings, ADP-55k.2) ──
#
# A distinct ``capability-org-mappings`` prefix (research R5) so nothing overlaps the business
# router's ``/capabilities/{cap_id}``. Findings and footprints are derived per request.


@router.get("/capability-org-mappings", response_model=CapabilityOrgMappingsResponse)
async def list_capability_org_mappings(
    session: AsyncSession = Depends(_get_session),
) -> CapabilityOrgMappingsResponse:
    return await cap_mappings.list_views(session)


@router.get("/capability-org-mappings/findings", response_model=CapabilityOrgFindings)
async def capability_org_findings(
    session: AsyncSession = Depends(_get_session),
) -> CapabilityOrgFindings:
    return await cap_mappings.get_findings(session)


@router.put("/capability-org-mappings/{cap_id}/owner", response_model=CapabilityOrgView)
async def set_capability_owner(
    cap_id: str,
    body: SetOwner,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> CapabilityOrgView:
    try:
        view, previous = await cap_mappings.set_owner(cap_id, body.org_unit_id, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    await session.commit()
    if body.org_unit_id is None:
        if previous is not None:
            _log("capability_mapping.clear_owner", request, capability=cap_id, previous=previous)
    elif previous != body.org_unit_id:
        _log(
            "capability_mapping.set_owner",
            request,
            capability=cap_id,
            org_unit=body.org_unit_id,
            previous=previous,
        )
    return view


@router.post(
    "/capability-org-mappings",
    response_model=CapabilityOrgMapping,
    status_code=status.HTTP_201_CREATED,
)
async def add_capability_mapping(
    body: AddMapping,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> CapabilityOrgMapping:
    try:
        mapping = await cap_mappings.add_mapping(body, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    await session.commit()
    _log(
        "capability_mapping.add",
        request,
        capability=body.capability_id,
        org_unit=body.org_unit_id,
        role=body.role,
        geography=body.geography_id,
    )
    return mapping


@router.delete(
    "/capability-org-mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_capability_mapping(
    mapping_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> Response:
    try:
        row = await cap_mappings.remove_mapping(mapping_id, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    await session.commit()
    _log(
        "capability_mapping.remove",
        request,
        mapping=mapping_id,
        capability=row.capability_id,
        org_unit=row.org_unit_id,
        role=row.role,
        geography=row.geography_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/org-units/{ou_id}/footprint", response_model=OrgUnitFootprint)
async def org_unit_footprint(
    ou_id: str, session: AsyncSession = Depends(_get_session)
) -> OrgUnitFootprint:
    try:
        return await cap_mappings.get_footprint(ou_id, session)
    except OrganizationError as exc:
        raise _http(exc) from exc


# ── Regional assessments (942-regional-assessments, ADP-55k.3) ─────────────────
#
# Distinct prefixes (research R4): /regional-assessments/{cap_id}/{geo_id}, /regional-heatmap and
# /capability-region-scope/{cap_id}, so no path can be taken for another. The capability's own
# maturity_level (the baseline) is never written here.


@router.get("/regional-assessments", response_model=RegionalAssessmentListResponse)
async def list_regional_assessments(
    capability_id: str | None = None, session: AsyncSession = Depends(_get_session)
) -> RegionalAssessmentListResponse:
    return await regional.list_assessments(session, capability_id=capability_id)


@router.put("/regional-assessments/{cap_id}/{geo_id}", response_model=RegionalAssessment)
async def set_regional_assessment(
    cap_id: str,
    geo_id: str,
    body: SetRegionalAssessment,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> RegionalAssessment:
    try:
        assessment, created = await regional.set_assessment(cap_id, geo_id, body, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    await session.commit()
    _log(
        "regional_assessment.set",
        request,
        capability=cap_id,
        geography=geo_id,
        maturity=body.maturity_level,
        note_chars=len(body.note or ""),
        created=created,
    )
    return assessment


@router.delete(
    "/regional-assessments/{cap_id}/{geo_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_regional_assessment(
    cap_id: str, geo_id: str, request: Request, session: AsyncSession = Depends(_get_session)
) -> Response:
    try:
        await regional.remove_assessment(cap_id, geo_id, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    await session.commit()
    _log("regional_assessment.remove", request, capability=cap_id, geography=geo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/regional-heatmap", response_model=RegionalHeatmap)
async def regional_heatmap(
    geography_ids: str | None = None, session: AsyncSession = Depends(_get_session)
) -> RegionalHeatmap:
    requested = (
        [g.strip() for g in geography_ids.split(",") if g.strip()] if geography_ids else None
    )
    try:
        return await regional.get_heatmap(requested, session)
    except OrganizationError as exc:
        raise _http(exc) from exc


@router.get("/capability-region-scope/{cap_id}", response_model=RegionScope)
async def get_region_scope(
    cap_id: str, session: AsyncSession = Depends(_get_session)
) -> RegionScope:
    try:
        return await regional.get_scope(cap_id, session)
    except OrganizationError as exc:
        raise _http(exc) from exc


@router.put("/capability-region-scope/{cap_id}", response_model=RegionScope)
async def set_region_scope(
    cap_id: str,
    body: SetRegionScope,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> RegionScope:
    try:
        scope = await regional.set_scope(cap_id, body, session)
    except OrganizationError as exc:
        raise _http(exc) from exc
    await session.commit()
    _log(
        "region_scope.set",
        request,
        capability=cap_id,
        region_specific=body.region_specific,
        geographies=",".join(body.geography_ids) or None,
    )
    return scope
