"""Legal entity and typed geography link routes (947 GEO-02, ADP-bo1.2).

Two routers, both registered in ``adp.api.app`` (never nested -- a nested router reports its
path without the outer prefix and the permission lookup misses it):

* ``router`` under ``/api/v1/business``: legal entities, their org unit links, the geography
  links of legal entities and org units, and the relation matrix. Writes ride the
  ``/api/v1/business/`` prefix rule (WRITE_BUSINESS_ARCH).
* ``applications_router`` under ``/api/v1/applications``: an application's legal entities and
  geography links, so writes ride WRITE_APPLICATION (R5).

The session dependency, error mapping and audit log are the organization router's, so a test
overriding ``orouter._get_session`` covers these routes too.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.organization import geo_links, legal_entities
from adp.organization.models import (
    GeoLink,
    GeoLinkCreate,
    GeoLinkListResponse,
    GeoLinkRelations,
    GeoLinkSubject,
    GeoLinkUpdate,
    LegalEntity,
    LegalEntityCreate,
    LegalEntityDetail,
    LegalEntityListResponse,
    LegalEntityUpdate,
    LinkLegalEntity,
    LinkOrgUnit,
    OrganizationError,
)
from adp.organization.router import _get_session, _http, _log

router = APIRouter(prefix="/api/v1/business", tags=["organization"])
applications_router = APIRouter(prefix="/api/v1/applications", tags=["organization"])


async def _run(fn: Callable[[], Awaitable[Any]]) -> Any:
    try:
        return await fn()
    except OrganizationError as exc:
        raise _http(exc) from exc


# ── Relation matrix (FR-006) ──────────────────────────────────────────────────


@router.get("/geo-link-relations", response_model=GeoLinkRelations)
async def get_relations() -> GeoLinkRelations:
    return geo_links.relations()


# ── Legal entities (US1) ──────────────────────────────────────────────────────


@router.get("/legal-entities", response_model=LegalEntityListResponse)
async def list_legal_entities(
    session: AsyncSession = Depends(_get_session),
) -> LegalEntityListResponse:
    return await legal_entities.list_legal_entities(session)


@router.post("/legal-entities", response_model=LegalEntity, status_code=status.HTTP_201_CREATED)
async def create_legal_entity(
    body: LegalEntityCreate, request: Request, session: AsyncSession = Depends(_get_session)
) -> LegalEntity:
    le = await _run(lambda: legal_entities.create_legal_entity(body, session))
    await session.commit()
    _log("legal_entity.create", request, id=le.id, name=le.name)
    return le  # type: ignore[no-any-return]


@router.get("/legal-entities/{le_id}", response_model=LegalEntityDetail)
async def get_legal_entity(
    le_id: str, session: AsyncSession = Depends(_get_session)
) -> LegalEntityDetail:
    return await _run(lambda: legal_entities.get_legal_entity(le_id, session))  # type: ignore[no-any-return]


@router.patch("/legal-entities/{le_id}", response_model=LegalEntity)
async def update_legal_entity(
    le_id: str,
    body: LegalEntityUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> LegalEntity:
    le = await _run(lambda: legal_entities.update_legal_entity(le_id, body, session))
    await session.commit()
    _log("legal_entity.update", request, id=le_id, fields=",".join(body.model_fields_set))
    return le  # type: ignore[no-any-return]


@router.delete("/legal-entities/{le_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_legal_entity(
    le_id: str, request: Request, session: AsyncSession = Depends(_get_session)
) -> Response:
    await _run(lambda: legal_entities.delete_legal_entity(le_id, session))
    await session.commit()
    _log("legal_entity.delete", request, id=le_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/legal-entities/{le_id}/org-units",
    response_model=LegalEntityDetail,
    status_code=status.HTTP_201_CREATED,
)
async def link_org_unit(
    le_id: str, body: LinkOrgUnit, request: Request, session: AsyncSession = Depends(_get_session)
) -> LegalEntityDetail:
    le = await _run(lambda: legal_entities.link_org_unit(le_id, body.org_unit_id, session))
    await session.commit()
    _log("legal_entity.link_org_unit", request, id=le_id, org_unit=body.org_unit_id)
    return le  # type: ignore[no-any-return]


@router.delete(
    "/legal-entities/{le_id}/org-units/{ou_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def unlink_org_unit(
    le_id: str, ou_id: str, request: Request, session: AsyncSession = Depends(_get_session)
) -> Response:
    await _run(lambda: legal_entities.unlink_org_unit(le_id, ou_id, session))
    await session.commit()
    _log("legal_entity.unlink_org_unit", request, id=le_id, org_unit=ou_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/org-units/{ou_id}/legal-entities", response_model=list[LegalEntity])
async def org_unit_legal_entities(
    ou_id: str, session: AsyncSession = Depends(_get_session)
) -> list[LegalEntity]:
    return await legal_entities.legal_entities_for_org_unit(ou_id, session)


# ── An application's legal entities (FR-002) ──────────────────────────────────


@applications_router.get("/{app_id}/legal-entities", response_model=list[LegalEntity])
async def application_legal_entities(
    app_id: str, session: AsyncSession = Depends(_get_session)
) -> list[LegalEntity]:
    return await _run(lambda: legal_entities.legal_entities_for_application(app_id, session))  # type: ignore[no-any-return]


@applications_router.post(
    "/{app_id}/legal-entities", response_model=list[LegalEntity], status_code=201
)
async def link_application_legal_entity(
    app_id: str,
    body: LinkLegalEntity,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> list[LegalEntity]:
    out = await _run(
        lambda: legal_entities.link_application(app_id, body.legal_entity_id, session)
    )
    await session.commit()
    _log("application.link_legal_entity", request, id=app_id, legal_entity=body.legal_entity_id)
    return out  # type: ignore[no-any-return]


@applications_router.delete(
    "/{app_id}/legal-entities/{le_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def unlink_application_legal_entity(
    app_id: str, le_id: str, request: Request, session: AsyncSession = Depends(_get_session)
) -> Response:
    await _run(lambda: legal_entities.unlink_application(app_id, le_id, session))
    await session.commit()
    _log("application.unlink_legal_entity", request, id=app_id, legal_entity=le_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Typed geography links (US2), one set of handlers per subject ──────────────


def _register_geo_links(r: APIRouter, base: str, subject: GeoLinkSubject) -> None:
    async def list_(
        subject_id: str,
        as_of: date | None = None,
        all: bool = False,  # noqa: A002 -- the query parameter's public name
        session: AsyncSession = Depends(_get_session),
    ) -> GeoLinkListResponse:
        return await _run(  # type: ignore[no-any-return]
            lambda: geo_links.list_links(subject, subject_id, session, as_of, include_inactive=all)
        )

    async def add(
        subject_id: str,
        body: GeoLinkCreate,
        request: Request,
        session: AsyncSession = Depends(_get_session),
    ) -> GeoLink:
        link = await _run(lambda: geo_links.add_link(subject, subject_id, body, session))
        await session.commit()
        _log(
            f"{subject}.geo_link.add", request, id=subject_id, relation=body.relation,
            geography=body.geography_id, valid_from=body.valid_from, valid_to=body.valid_to,
        )
        return link  # type: ignore[no-any-return]

    async def update(
        subject_id: str,
        link_id: str,
        body: GeoLinkUpdate,
        request: Request,
        session: AsyncSession = Depends(_get_session),
    ) -> GeoLink:
        link = await _run(
            lambda: geo_links.update_link(subject, subject_id, link_id, body, session)
        )
        await session.commit()
        _log(
            f"{subject}.geo_link.update", request, id=subject_id, link=link_id,
            valid_from=body.valid_from, valid_to=body.valid_to,
        )
        return link  # type: ignore[no-any-return]

    async def delete(
        subject_id: str,
        link_id: str,
        request: Request,
        session: AsyncSession = Depends(_get_session),
    ) -> Response:
        gone = await _run(lambda: geo_links.delete_link(subject, subject_id, link_id, session))
        await session.commit()
        _log(
            f"{subject}.geo_link.delete", request, id=subject_id, link=link_id,
            relation=gone.relation, geography=gone.geography.id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    path = f"{base}/{{subject_id}}/geo-links"
    name = subject.replace("_", "-")
    r.add_api_route(
        path, list_, methods=["GET"], response_model=GeoLinkListResponse,
        name=f"list_{subject}_geo_links", operation_id=f"list_{subject}_geo_links",
    )
    r.add_api_route(
        path, add, methods=["POST"], response_model=GeoLink, status_code=201,
        name=f"add_{subject}_geo_link", operation_id=f"add_{subject}_geo_link",
    )
    r.add_api_route(
        f"{path}/{{link_id}}", update, methods=["PATCH"], response_model=GeoLink,
        name=f"update_{subject}_geo_link", operation_id=f"update_{subject}_geo_link",
    )
    r.add_api_route(
        f"{path}/{{link_id}}", delete, methods=["DELETE"], status_code=204,
        name=f"delete_{subject}_geo_link", operation_id=f"delete_{subject}_geo_link",
        summary=f"Remove a {name} geography link",
    )


_register_geo_links(router, "/legal-entities", "legal_entity")
_register_geo_links(router, "/org-units", "org_unit")
_register_geo_links(applications_router, "", "application")
