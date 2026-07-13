"""Application Registry API — ADP-SPEC-036.

GET/POST/PATCH/DELETE /api/v1/applications           — application CRUD
GET/POST/PATCH/DELETE /api/v1/applications/{id}/capability-links
GET/POST/DELETE       /api/v1/applications/{id}/technical-capability-links
GET/POST/DELETE       /api/v1/applications/{id}/stage-links
GET/POST/DELETE       /api/v1/applications/{id}/domain-integrations
GET/POST/DELETE       /api/v1/applications/{id}/design-links
GET/POST/PATCH/DELETE /api/v1/technical-capabilities
GET/POST/PATCH/DELETE /api/v1/integrations

ART-IX (SHOULD): structured logging used for all mutations.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.application import store as astore
from adp.application.models import (
    Application,
    ApplicationCapabilityLink,
    ApplicationCapabilityLinkCreate,
    ApplicationCapabilityLinksResponse,
    ApplicationCapabilityLinkUpdate,
    ApplicationCreate,
    ApplicationDesignLink,
    ApplicationDesignLinkCreate,
    ApplicationDesignLinksResponse,
    ApplicationDomainIntegration,
    ApplicationDomainIntegrationCreate,
    ApplicationDomainIntegrationsResponse,
    ApplicationIntegration,
    ApplicationIntegrationCreate,
    ApplicationIntegrationListResponse,
    ApplicationIntegrationUpdate,
    ApplicationListResponse,
    ApplicationStageLink,
    ApplicationStageLinkCreate,
    ApplicationStageLinksResponse,
    ApplicationTechCapLink,
    ApplicationTechCapLinkCreate,
    ApplicationTechCapLinksResponse,
    ApplicationUpdate,
    DuplicateAppCapLinkError,
    DuplicateAppDesignLinkError,
    DuplicateAppStageLinkError,
    DuplicateAppTechCapLinkError,
    TechCapDepthError,
    TechCapHasChildrenError,
    TechCapListResponse,
    TechnicalCapability,
    TechnicalCapabilityCreate,
    TechnicalCapabilityUpdate,
)

logger = logging.getLogger(__name__)

applications_router = APIRouter(prefix="/api/v1/applications", tags=["applications"])
tech_caps_router = APIRouter(
    prefix="/api/v1/technical-capabilities", tags=["technical-capabilities"]
)
integrations_router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_actor(request: Request) -> str:
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


async def _get_session():
    factory = astore._get_session_factory()
    async with factory() as session:
        yield session


# ── Applications CRUD ─────────────────────────────────────────────────────────

@applications_router.get("", response_model=ApplicationListResponse)
async def list_applications(session: AsyncSession = Depends(_get_session)):
    return await astore.list_applications(session)


@applications_router.post("", response_model=Application, status_code=status.HTTP_201_CREATED)
async def create_application(
    body: ApplicationCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    app = await astore.create_application(body, session)
    await session.commit()
    actor = _get_actor(request)
    logger.info("application.create id=%s name=%r actor=%s", app.id, app.name, actor)
    return app


@applications_router.get("/{app_id}", response_model=Application)
async def get_application(app_id: str, session: AsyncSession = Depends(_get_session)):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return app


@applications_router.patch("/{app_id}", response_model=Application)
async def update_application(
    app_id: str,
    body: ApplicationUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    app = await astore.update_application(app_id, body, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("application.update id=%s actor=%s", app_id, actor)
    return app


@applications_router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_application(app_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("application.delete id=%s actor=%s", app_id, actor)


# ── Application–Business Capability Links ─────────────────────────────────────

@applications_router.get(
    "/{app_id}/capability-links", response_model=ApplicationCapabilityLinksResponse
)
async def list_capability_links(
    app_id: str, session: AsyncSession = Depends(_get_session)
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.list_app_capability_links(app_id, session)


@applications_router.post(
    "/{app_id}/capability-links",
    response_model=ApplicationCapabilityLink,
    status_code=status.HTTP_201_CREATED,
)
async def create_capability_link(
    app_id: str,
    body: ApplicationCapabilityLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        link = await astore.create_app_capability_link(app_id, body, session)
    except DuplicateAppCapLinkError:
        raise HTTPException(status_code=409, detail="Link already exists")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.capability_link.create app_id=%s cap_id=%s actor=%s",
        app_id, body.capability_id, actor,
    )
    return link


@applications_router.patch(
    "/{app_id}/capability-links/{capability_id}",
    response_model=ApplicationCapabilityLink,
)
async def update_capability_link(
    app_id: str,
    capability_id: str,
    body: ApplicationCapabilityLinkUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    link = await astore.update_app_capability_link(app_id, capability_id, body, session)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.capability_link.update app_id=%s cap_id=%s actor=%s",
        app_id, capability_id, actor,
    )
    return link


@applications_router.delete(
    "/{app_id}/capability-links/{capability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_capability_link(
    app_id: str,
    capability_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_app_capability_link(app_id, capability_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.capability_link.delete app_id=%s cap_id=%s actor=%s",
        app_id, capability_id, actor,
    )


# ── Application–Technical Capability Links ────────────────────────────────────

@applications_router.get(
    "/{app_id}/technical-capability-links",
    response_model=ApplicationTechCapLinksResponse,
)
async def list_tech_cap_links(
    app_id: str, session: AsyncSession = Depends(_get_session)
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.list_app_tech_cap_links(app_id, session)


@applications_router.post(
    "/{app_id}/technical-capability-links",
    response_model=ApplicationTechCapLink,
    status_code=status.HTTP_201_CREATED,
)
async def create_tech_cap_link(
    app_id: str,
    body: ApplicationTechCapLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        link = await astore.create_app_tech_cap_link(app_id, body, session)
    except DuplicateAppTechCapLinkError:
        raise HTTPException(status_code=409, detail="Link already exists")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.tech_cap_link.create app_id=%s tc_id=%s usage=%s actor=%s",
        app_id, body.tech_cap_id, body.usage_type, actor,
    )
    return link


@applications_router.delete(
    "/{app_id}/technical-capability-links/{tc_id}/{usage_type}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_tech_cap_link(
    app_id: str,
    tc_id: str,
    usage_type: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_app_tech_cap_link(app_id, tc_id, usage_type, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.tech_cap_link.delete app_id=%s tc_id=%s usage=%s actor=%s",
        app_id, tc_id, usage_type, actor,
    )


# ── Application–Value Stream Stage Links ──────────────────────────────────────

@applications_router.get(
    "/{app_id}/stage-links", response_model=ApplicationStageLinksResponse
)
async def list_stage_links(
    app_id: str, session: AsyncSession = Depends(_get_session)
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.list_app_stage_links(app_id, session)


@applications_router.post(
    "/{app_id}/stage-links",
    response_model=ApplicationStageLink,
    status_code=status.HTTP_201_CREATED,
)
async def create_stage_link(
    app_id: str,
    body: ApplicationStageLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        link = await astore.create_app_stage_link(app_id, body, session)
    except DuplicateAppStageLinkError:
        raise HTTPException(status_code=409, detail="Link already exists")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.stage_link.create app_id=%s stage_id=%s actor=%s",
        app_id, body.stage_id, actor,
    )
    return link


@applications_router.delete(
    "/{app_id}/stage-links/{stage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_stage_link(
    app_id: str,
    stage_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_app_stage_link(app_id, stage_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.stage_link.delete app_id=%s stage_id=%s actor=%s",
        app_id, stage_id, actor,
    )


# ── Application–Domain Integrations ──────────────────────────────────────────

@applications_router.get(
    "/{app_id}/domain-integrations",
    response_model=ApplicationDomainIntegrationsResponse,
)
async def list_domain_integrations(
    app_id: str, session: AsyncSession = Depends(_get_session)
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.list_app_domain_integrations(app_id, session)


@applications_router.post(
    "/{app_id}/domain-integrations",
    response_model=ApplicationDomainIntegration,
    status_code=status.HTTP_201_CREATED,
)
async def create_domain_integration(
    app_id: str,
    body: ApplicationDomainIntegrationCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        link = await astore.create_app_domain_integration(app_id, body, session)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.domain_integration.create app_id=%s id=%s actor=%s",
        app_id, link.id, actor,
    )
    return link


@applications_router.delete(
    "/{app_id}/domain-integrations/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_domain_integration(
    app_id: str,
    link_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_app_domain_integration(app_id, link_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Domain integration not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.domain_integration.delete app_id=%s link_id=%s actor=%s",
        app_id, link_id, actor,
    )


# ── Application–Design Links ──────────────────────────────────────────────────

@applications_router.get(
    "/{app_id}/design-links", response_model=ApplicationDesignLinksResponse
)
async def list_design_links(
    app_id: str, session: AsyncSession = Depends(_get_session)
):
    app = await astore.get_application(app_id, session)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return await astore.list_app_design_links(app_id, session)


@applications_router.post(
    "/{app_id}/design-links",
    response_model=ApplicationDesignLink,
    status_code=status.HTTP_201_CREATED,
)
async def create_design_link(
    app_id: str,
    body: ApplicationDesignLinkCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        link = await astore.create_app_design_link(app_id, body, session)
    except DuplicateAppDesignLinkError:
        raise HTTPException(status_code=409, detail="Link already exists")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.design_link.create app_id=%s design_id=%s actor=%s",
        app_id, body.design_id, actor,
    )
    return link


@applications_router.delete(
    "/{app_id}/design-links/{design_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_design_link(
    app_id: str,
    design_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_app_design_link(app_id, design_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "app.design_link.delete app_id=%s design_id=%s actor=%s",
        app_id, design_id, actor,
    )


# ── Technical Capabilities ────────────────────────────────────────────────────

@tech_caps_router.get("", response_model=TechCapListResponse)
async def list_tech_caps(session: AsyncSession = Depends(_get_session)):
    return await astore.list_technical_capabilities(session)


@tech_caps_router.post(
    "", response_model=TechnicalCapability, status_code=status.HTTP_201_CREATED
)
async def create_tech_cap(
    body: TechnicalCapabilityCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        tc = await astore.create_technical_capability(body, session)
    except TechCapDepthError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "technical_capability.create id=%s name=%r level=%d actor=%s",
        tc.id, tc.name, tc.level, actor,
    )
    return tc


@tech_caps_router.get("/{tc_id}", response_model=TechnicalCapability)
async def get_tech_cap(tc_id: str, session: AsyncSession = Depends(_get_session)):
    tc = await astore.get_technical_capability(tc_id, session)
    if tc is None:
        raise HTTPException(status_code=404, detail=f"Technical capability {tc_id!r} not found")
    return tc


@tech_caps_router.patch("/{tc_id}", response_model=TechnicalCapability)
async def update_tech_cap(
    tc_id: str,
    body: TechnicalCapabilityUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    tc = await astore.update_technical_capability(tc_id, body, session)
    if tc is None:
        raise HTTPException(status_code=404, detail=f"Technical capability {tc_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("technical_capability.update id=%s actor=%s", tc_id, actor)
    return tc


@tech_caps_router.delete("/{tc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tech_cap(
    tc_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        deleted = await astore.delete_technical_capability(tc_id, session)
    except TechCapHasChildrenError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Technical capability {tc_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("technical_capability.delete id=%s actor=%s", tc_id, actor)


# ── Application Integrations ──────────────────────────────────────────────────

@integrations_router.get("", response_model=ApplicationIntegrationListResponse)
async def list_integrations(
    app_id: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(_get_session),
):
    return await astore.list_integrations(app_id, session)


@integrations_router.post(
    "", response_model=ApplicationIntegration, status_code=status.HTTP_201_CREATED
)
async def create_integration(
    body: ApplicationIntegrationCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    try:
        intg = await astore.create_integration(body, session)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    actor = _get_actor(request)
    logger.info(
        "integration.create id=%s src=%s tgt=%s actor=%s",
        intg.id, body.source_app_id, body.target_app_id, actor,
    )
    return intg


@integrations_router.get("/{int_id}", response_model=ApplicationIntegration)
async def get_integration(int_id: str, session: AsyncSession = Depends(_get_session)):
    intg = await astore.get_integration(int_id, session)
    if intg is None:
        raise HTTPException(status_code=404, detail=f"Integration {int_id!r} not found")
    return intg


@integrations_router.patch("/{int_id}", response_model=ApplicationIntegration)
async def update_integration(
    int_id: str,
    body: ApplicationIntegrationUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    intg = await astore.update_integration(int_id, body, session)
    if intg is None:
        raise HTTPException(status_code=404, detail=f"Integration {int_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("integration.update id=%s actor=%s", int_id, actor)
    return intg


@integrations_router.delete("/{int_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    int_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    deleted = await astore.delete_integration(int_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Integration {int_id!r} not found")
    await session.commit()
    actor = _get_actor(request)
    logger.info("integration.delete id=%s actor=%s", int_id, actor)
