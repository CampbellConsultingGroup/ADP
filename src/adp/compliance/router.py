"""Compliance Framework & Control Registry API (COMPLY-01) + Control Mappings API (COMPLY-02).

GET/POST/PATCH/DELETE /api/v1/compliance/frameworks               — framework registry
POST/PATCH/DELETE     /api/v1/compliance/frameworks/{id}/controls — control catalog
PATCH/DELETE          /api/v1/compliance/controls/{id}            — individual control edit/delete
PUT/DELETE            /api/v1/compliance/controls/{id}/mappings/{capabilities|applications|
                         designs|patterns}/{target_id} — entity-targeted mapping upsert/remove
PUT/DELETE            /api/v1/compliance/controls/{id}/mappings/organization — estate-wide mapping
GET                   /api/v1/compliance/controls/{id}/mappings   — forward lookup (all 5 target
                         shapes; Application-targeted rows filtered per D2 — see below)

ART-V: write operations require ActionType.WRITE_COMPLIANCE (Clarification Session 2026-08-17,
        research.md D4); already covers every mapping route below via the existing
        `/api/v1/compliance/` prefix rule in enforcement.py -- no new rule needed for COMPLY-02.
        Reads are open EXCEPT Application-targeted mappings, which require
        READ_APPLICATION_GOVERNANCE (Clarification Session 2026-08-18; research.md D2): the
        forward lookup filters those rows out inline for a caller lacking the permission rather
        than 403ing the whole response, since a Control's other mappings must stay visible.
ART-VI: mutations emit structured log entries (actor, entity, action), matching
        adp.business.router's existing convention.
ART-IX: created_at recorded on every mapping (no updated_at -- spec.md 922 User Story 2
        Acceptance Scenario 1: the prior status is not separately preserved); no audit_entries
        write, matching COMPLY-01's own confirmed precedent.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.permissions import is_permitted
from adp.authz.roles import ActionType
from adp.compliance import store as cstore
from adp.compliance.models import (
    Control,
    ControlCreate,
    ControlMapping,
    ControlMappingListResponse,
    ControlMappingWrite,
    ControlNotFoundError,
    ControlUpdate,
    CrossFrameworkParentError,
    CyclicParentError,
    DuplicateControlCodeError,
    InvalidPatternTargetError,
    MappingNotFoundError,
    MappingTargetNotFoundError,
    MappingTargetType,
    ParentNotFoundError,
    RegulatoryFramework,
    RegulatoryFrameworkCreate,
    RegulatoryFrameworkDetail,
    RegulatoryFrameworkListResponse,
    RegulatoryFrameworkUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_actor(request: Request) -> str:
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


async def _get_session():
    factory = cstore._get_session_factory()
    async with factory() as session:
        yield session


# ── Regulatory Frameworks ─────────────────────────────────────────────────────

@router.get("/frameworks", response_model=RegulatoryFrameworkListResponse)
async def list_frameworks(session: AsyncSession = Depends(_get_session)):
    items = await cstore.list_frameworks(session)
    return RegulatoryFrameworkListResponse(items=items, total=len(items))


@router.post(
    "/frameworks", response_model=RegulatoryFramework, status_code=status.HTTP_201_CREATED
)
async def create_framework(
    body: RegulatoryFrameworkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    fw = await cstore.create_framework(body, session)
    await session.commit()

    actor = _get_actor(request)
    logger.info("compliance.framework.create id=%s name=%r actor=%s", fw.id, fw.name, actor)
    return fw


@router.get("/frameworks/{framework_id}", response_model=RegulatoryFrameworkDetail)
async def get_framework_detail(framework_id: str, session: AsyncSession = Depends(_get_session)):
    detail = await cstore.get_framework_detail(framework_id, session)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    return detail


@router.patch("/frameworks/{framework_id}", response_model=RegulatoryFramework)
async def update_framework(
    framework_id: str,
    body: RegulatoryFrameworkUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    fw = await cstore.update_framework(framework_id, body, session)
    if fw is None:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("compliance.framework.update id=%s actor=%s", framework_id, actor)
    return fw


@router.delete("/frameworks/{framework_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_framework(
    framework_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await cstore.delete_framework(framework_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("compliance.framework.delete id=%s actor=%s", framework_id, actor)


# ── Controls ──────────────────────────────────────────────────────────────────

@router.post(
    "/frameworks/{framework_id}/controls",
    response_model=Control,
    status_code=status.HTTP_201_CREATED,
)
async def create_control(
    framework_id: str,
    body: ControlCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    if await cstore.get_framework(framework_id, session) is None:
        raise HTTPException(status_code=404, detail=f"Framework {framework_id!r} not found")
    try:
        ctrl = await cstore.create_control(framework_id, body, session)
        await session.commit()
    except ParentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (CrossFrameworkParentError, CyclicParentError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DuplicateControlCodeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    actor = _get_actor(request)
    logger.info(
        "compliance.control.create id=%s framework_id=%s code=%r actor=%s",
        ctrl.id, framework_id, ctrl.code, actor,
    )
    return ctrl


@router.patch("/controls/{control_id}", response_model=Control)
async def update_control(
    control_id: str,
    body: ControlUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        ctrl = await cstore.update_control(control_id, body, session)
    except ParentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (CrossFrameworkParentError, CyclicParentError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DuplicateControlCodeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if ctrl is None:
        raise HTTPException(status_code=404, detail=f"Control {control_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("compliance.control.update id=%s actor=%s", control_id, actor)
    return ctrl


@router.delete("/controls/{control_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_control(
    control_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await cstore.delete_control(control_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Control {control_id!r} not found")
    await session.commit()

    actor = _get_actor(request)
    logger.info("compliance.control.delete id=%s actor=%s", control_id, actor)


# ── Control Mappings (COMPLY-02) ────────────────────────────────────────────
# Writes/forward-lookup live here (Control's own package -- research.md D7, mirrors
# adp.strategy.router owning Objective-side link writes); reverse-lookups (given a target
# entity, list its mapped controls) live on each target's own router instead
# (business/application/designs/knowledge -- see those routers' own compliance-mappings routes).

async def _translate_mapping_write_errors(coro):
    """Shared exception -> HTTP translation for every upsert route below, avoiding five
    near-identical try/except blocks (research.md D7's own "shared internal helper" note)."""
    try:
        return await coro
    except ControlNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MappingTargetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidPatternTargetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _translate_mapping_delete_errors(coro) -> None:
    try:
        await coro
    except MappingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put(
    "/controls/{control_id}/mappings/capabilities/{capability_id}", response_model=ControlMapping
)
async def upsert_capability_mapping(
    control_id: str,
    capability_id: str,
    body: ControlMappingWrite,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    mapping = await _translate_mapping_write_errors(
        cstore.upsert_capability_mapping(control_id, capability_id, body, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.upsert control_id=%s target_type=capability target_id=%s actor=%s",
        control_id, capability_id, actor,
    )
    return mapping


@router.delete(
    "/controls/{control_id}/mappings/capabilities/{capability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_capability_mapping(
    control_id: str,
    capability_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    await _translate_mapping_delete_errors(
        cstore.delete_capability_mapping(control_id, capability_id, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.delete control_id=%s target_type=capability target_id=%s actor=%s",
        control_id, capability_id, actor,
    )


@router.put(
    "/controls/{control_id}/mappings/applications/{application_id}", response_model=ControlMapping
)
async def upsert_application_mapping(
    control_id: str,
    application_id: str,
    body: ControlMappingWrite,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    mapping = await _translate_mapping_write_errors(
        cstore.upsert_application_mapping(control_id, application_id, body, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.upsert control_id=%s target_type=application target_id=%s actor=%s",
        control_id, application_id, actor,
    )
    return mapping


@router.delete(
    "/controls/{control_id}/mappings/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_application_mapping(
    control_id: str,
    application_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    await _translate_mapping_delete_errors(
        cstore.delete_application_mapping(control_id, application_id, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.delete control_id=%s target_type=application target_id=%s actor=%s",
        control_id, application_id, actor,
    )


@router.put(
    "/controls/{control_id}/mappings/designs/{design_id}", response_model=ControlMapping
)
async def upsert_design_mapping(
    control_id: str,
    design_id: str,
    body: ControlMappingWrite,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    mapping = await _translate_mapping_write_errors(
        cstore.upsert_design_mapping(control_id, design_id, body, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.upsert control_id=%s target_type=design target_id=%s actor=%s",
        control_id, design_id, actor,
    )
    return mapping


@router.delete(
    "/controls/{control_id}/mappings/designs/{design_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_design_mapping(
    control_id: str,
    design_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    await _translate_mapping_delete_errors(
        cstore.delete_design_mapping(control_id, design_id, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.delete control_id=%s target_type=design target_id=%s actor=%s",
        control_id, design_id, actor,
    )


@router.put(
    "/controls/{control_id}/mappings/patterns/{pattern_id}", response_model=ControlMapping
)
async def upsert_pattern_mapping(
    control_id: str,
    pattern_id: str,
    body: ControlMappingWrite,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    mapping = await _translate_mapping_write_errors(
        cstore.upsert_pattern_mapping(control_id, pattern_id, body, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.upsert control_id=%s target_type=pattern target_id=%s actor=%s",
        control_id, pattern_id, actor,
    )
    return mapping


@router.delete(
    "/controls/{control_id}/mappings/patterns/{pattern_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_pattern_mapping(
    control_id: str,
    pattern_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    await _translate_mapping_delete_errors(
        cstore.delete_pattern_mapping(control_id, pattern_id, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.delete control_id=%s target_type=pattern target_id=%s actor=%s",
        control_id, pattern_id, actor,
    )


@router.put("/controls/{control_id}/mappings/organization", response_model=ControlMapping)
async def upsert_organization_mapping(
    control_id: str,
    body: ControlMappingWrite,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    mapping = await _translate_mapping_write_errors(
        cstore.upsert_organization_mapping(control_id, body, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.upsert control_id=%s target_type=organization actor=%s",
        control_id, actor,
    )
    return mapping


@router.delete(
    "/controls/{control_id}/mappings/organization", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_organization_mapping(
    control_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    await _translate_mapping_delete_errors(
        cstore.delete_organization_mapping(control_id, session)
    )
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "compliance.mapping.delete control_id=%s target_type=organization actor=%s",
        control_id, actor,
    )


@router.get("/controls/{control_id}/mappings", response_model=ControlMappingListResponse)
async def list_control_mappings(
    control_id: str,
    session: AsyncSession = Depends(_get_session),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Forward lookup (FR-011): every mapping for this Control, across all five target
    shapes. Application-targeted rows are filtered out inline for a caller lacking
    READ_APPLICATION_GOVERNANCE (research.md D2) -- NOT a blanket require_action_dep on the
    whole route, since Capability/Design/Pattern/organization rows must stay visible
    regardless (spec.md 922 User Story 3 Acceptance Scenario 3; SC-006)."""
    try:
        mappings = await cstore.list_mappings_for_control(control_id, session)
    except ControlNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not is_permitted(user.role, ActionType.READ_APPLICATION_GOVERNANCE):
        mappings = [m for m in mappings if m.target_type != MappingTargetType.APPLICATION]

    return ControlMappingListResponse(items=mappings, total=len(mappings))
