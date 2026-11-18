"""Application links: business and technical capabilities, value stream stages, domain
integrations, application integrations, designs (split out of ``adp.application.store``,
which re-exports every name here; ADP-blp.27).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.application.models import (
    ApplicationCapabilityLink,
    ApplicationCapabilityLinkCreate,
    ApplicationCapabilityLinksResponse,
    ApplicationCapabilityLinkUpdate,
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
    ApplicationStageLink,
    ApplicationStageLinkCreate,
    ApplicationStageLinksResponse,
    ApplicationTechCapLink,
    ApplicationTechCapLinkCreate,
    ApplicationTechCapLinksResponse,
    DuplicateAppCapLinkError,
    DuplicateAppDesignLinkError,
    DuplicateAppStageLinkError,
    DuplicateAppTechCapLinkError,
)
from adp.application.store_base import (
    _is_duplicate_error,
    _now,
    _rowcount,
    get_application,
    get_technical_capability,
)
from adp.application.tables import (
    _app_cap_links,
    _app_design_links,
    _app_domain_integrations,
    _app_integrations,
    _app_stage_links,
    _app_tech_cap_links,
    _applications,
    _biz_caps,
    _designs,
    _domains,
    _stages,
    _tech_caps,
)

# ── Application–Business Capability Links (US2) ───────────────────────────────

async def list_app_capability_links(
    app_id: str, session: AsyncSession
) -> ApplicationCapabilityLinksResponse:
    result = await session.execute(
        sa.select(
            _app_cap_links.c.app_id,
            _app_cap_links.c.capability_id,
            _biz_caps.c.name.label("capability_name"),
            _app_cap_links.c.fit_score,
        )
        .join(_biz_caps, _biz_caps.c.id == _app_cap_links.c.capability_id)
        .where(_app_cap_links.c.app_id == app_id)
        .order_by(_biz_caps.c.name)
    )
    items = [
        ApplicationCapabilityLink(
            app_id=row.app_id,
            capability_id=row.capability_id,
            capability_name=row.capability_name,
            fit_score=row.fit_score,
        )
        for row in result.mappings().all()
    ]
    return ApplicationCapabilityLinksResponse(items=items)


async def list_all_capability_links(session: AsyncSession) -> list[ApplicationCapabilityLink]:
    """Every application-capability link across the whole registry, in one query.

    Application Portfolio pivot (ADP-8xo): a bulk read for the portfolio-wide
    "group by business capability" dimension -- reuses list_app_capability_links's
    own join shape, just without the app_id filter, mirroring 919-insights-dashboard's
    list_all_costs precedent for the same "one bulk query, not N+1" reasoning.
    Ordered by capability name then app name for a stable default grouping order.
    """
    result = await session.execute(
        sa.select(
            _app_cap_links.c.app_id,
            _app_cap_links.c.capability_id,
            _biz_caps.c.name.label("capability_name"),
            _app_cap_links.c.fit_score,
            _applications.c.name.label("app_name"),
        )
        .join(_biz_caps, _biz_caps.c.id == _app_cap_links.c.capability_id)
        .join(_applications, _applications.c.id == _app_cap_links.c.app_id)
        .order_by(_biz_caps.c.name, _applications.c.name)
    )
    return [
        ApplicationCapabilityLink(
            app_id=row.app_id,
            capability_id=row.capability_id,
            capability_name=row.capability_name,
            fit_score=row.fit_score,
        )
        for row in result.mappings().all()
    ]


@dataclass(frozen=True)
class CapabilityApplicationRef:
    """An application linked to a business capability, with non-sensitive APM
    fields only (ADP-SPEC-039 context assembly -- risk/cost/governance are
    deliberately excluded by construction, not by a permission check).

    Not a boundary payload (ART-XIII concerns external APIs) -- internal
    context data feeding the Agent Review toolkit.
    """

    app_id: str
    app_name: str
    fit_score: int
    time_classification: str | None
    r_strategy: str | None
    pace_layer: str | None
    health_score: int | None


async def list_applications_for_capability(
    capability_id: str, session: AsyncSession
) -> list[CapabilityApplicationRef]:
    """Reverse of list_app_capability_links: applications linked to a capability."""
    result = await session.execute(
        sa.select(
            _app_cap_links.c.app_id,
            _applications.c.name.label("app_name"),
            _app_cap_links.c.fit_score,
            _applications.c.time_classification,
            _applications.c.r_strategy,
            _applications.c.pace_layer,
            _applications.c.health_score,
        )
        .join(_applications, _applications.c.id == _app_cap_links.c.app_id)
        .where(_app_cap_links.c.capability_id == capability_id)
        .order_by(_applications.c.name)
    )
    return [
        CapabilityApplicationRef(
            app_id=row.app_id,
            app_name=row.app_name,
            fit_score=row.fit_score,
            time_classification=row.time_classification,
            r_strategy=row.r_strategy,
            pace_layer=row.pace_layer,
            health_score=row.health_score,
        )
        for row in result.mappings()
    ]


async def create_app_capability_link(
    app_id: str, body: ApplicationCapabilityLinkCreate, session: AsyncSession
) -> ApplicationCapabilityLink:
    # Verify application exists
    app = await get_application(app_id, session)
    if app is None:
        raise ValueError(f"Application {app_id!r} not found")

    # Verify business capability exists
    cap_row = await session.execute(
        sa.select(_biz_caps.c.id, _biz_caps.c.name).where(_biz_caps.c.id == body.capability_id)
    )
    cap = cap_row.mappings().first()
    if cap is None:
        raise LookupError(f"Business capability {body.capability_id!r} not found")

    try:
        await session.execute(
            _app_cap_links.insert().values(
                app_id=app_id,
                capability_id=body.capability_id,
                fit_score=body.fit_score,
            )
        )
    except Exception as exc:
        if _is_duplicate_error(exc):
            raise DuplicateAppCapLinkError(
                f"Link ({app_id!r}, {body.capability_id!r}) already exists"
            ) from exc
        raise

    return ApplicationCapabilityLink(
        app_id=app_id,
        capability_id=body.capability_id,
        capability_name=cap.name,
        fit_score=body.fit_score,
    )


async def update_app_capability_link(
    app_id: str, cap_id: str, body: ApplicationCapabilityLinkUpdate, session: AsyncSession
) -> ApplicationCapabilityLink | None:
    existing = await session.execute(
        sa.select(_app_cap_links).where(
            _app_cap_links.c.app_id == app_id,
            _app_cap_links.c.capability_id == cap_id,
        )
    )
    if existing.mappings().first() is None:
        return None

    await session.execute(
        _app_cap_links.update()
        .where(_app_cap_links.c.app_id == app_id, _app_cap_links.c.capability_id == cap_id)
        .values(fit_score=body.fit_score)
    )
    links = await list_app_capability_links(app_id, session)
    for link in links.items:
        if link.capability_id == cap_id:
            return link
    return None


async def delete_app_capability_link(app_id: str, cap_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _app_cap_links.delete().where(
            _app_cap_links.c.app_id == app_id,
            _app_cap_links.c.capability_id == cap_id,
        )
    )
    return _rowcount(result) > 0


# ── Application–Technical Capability Links (US4) ──────────────────────────────

async def list_app_tech_cap_links(
    app_id: str, session: AsyncSession
) -> ApplicationTechCapLinksResponse:
    result = await session.execute(
        sa.select(
            _app_tech_cap_links.c.app_id,
            _app_tech_cap_links.c.tech_cap_id,
            _tech_caps.c.name.label("tech_cap_name"),
            _app_tech_cap_links.c.usage_type,
        )
        .join(_tech_caps, _tech_caps.c.id == _app_tech_cap_links.c.tech_cap_id)
        .where(_app_tech_cap_links.c.app_id == app_id)
        .order_by(_tech_caps.c.name, _app_tech_cap_links.c.usage_type)
    )
    items = [
        ApplicationTechCapLink(
            app_id=row.app_id,
            tech_cap_id=row.tech_cap_id,
            tech_cap_name=row.tech_cap_name,
            usage_type=row.usage_type,
        )
        for row in result.mappings().all()
    ]
    return ApplicationTechCapLinksResponse(items=items)


async def create_app_tech_cap_link(
    app_id: str, body: ApplicationTechCapLinkCreate, session: AsyncSession
) -> ApplicationTechCapLink:
    app = await get_application(app_id, session)
    if app is None:
        raise ValueError(f"Application {app_id!r} not found")

    tc = await get_technical_capability(body.tech_cap_id, session)
    if tc is None:
        raise LookupError(f"Technical capability {body.tech_cap_id!r} not found")

    try:
        await session.execute(
            _app_tech_cap_links.insert().values(
                app_id=app_id,
                tech_cap_id=body.tech_cap_id,
                usage_type=body.usage_type,
            )
        )
    except Exception as exc:
        if _is_duplicate_error(exc):
            raise DuplicateAppTechCapLinkError(
                f"Link ({app_id!r}, {body.tech_cap_id!r}, {body.usage_type!r}) already exists"
            ) from exc
        raise

    return ApplicationTechCapLink(
        app_id=app_id,
        tech_cap_id=body.tech_cap_id,
        tech_cap_name=tc.name,
        usage_type=body.usage_type,
    )


async def delete_app_tech_cap_link(
    app_id: str, tc_id: str, usage_type: str, session: AsyncSession
) -> bool:
    result = await session.execute(
        _app_tech_cap_links.delete().where(
            _app_tech_cap_links.c.app_id == app_id,
            _app_tech_cap_links.c.tech_cap_id == tc_id,
            _app_tech_cap_links.c.usage_type == usage_type,
        )
    )
    return _rowcount(result) > 0


# ── Application–Value Stream Stage Links (US5) ────────────────────────────────

async def list_app_stage_links(
    app_id: str, session: AsyncSession
) -> ApplicationStageLinksResponse:
    result = await session.execute(
        sa.select(
            _app_stage_links.c.app_id,
            _app_stage_links.c.stage_id,
            _stages.c.name.label("stage_name"),
        )
        .join(_stages, _stages.c.id == _app_stage_links.c.stage_id)
        .where(_app_stage_links.c.app_id == app_id)
        .order_by(_stages.c.name)
    )
    items = [
        ApplicationStageLink(
            app_id=row.app_id,
            stage_id=row.stage_id,
            stage_name=row.stage_name,
        )
        for row in result.mappings().all()
    ]
    return ApplicationStageLinksResponse(items=items)


async def create_app_stage_link(
    app_id: str, body: ApplicationStageLinkCreate, session: AsyncSession
) -> ApplicationStageLink:
    app = await get_application(app_id, session)
    if app is None:
        raise ValueError(f"Application {app_id!r} not found")

    stage_row = await session.execute(
        sa.select(_stages.c.id, _stages.c.name).where(_stages.c.id == body.stage_id)
    )
    stage = stage_row.mappings().first()
    if stage is None:
        raise LookupError(f"Value stream stage {body.stage_id!r} not found")

    try:
        await session.execute(
            _app_stage_links.insert().values(app_id=app_id, stage_id=body.stage_id)
        )
    except Exception as exc:
        if _is_duplicate_error(exc):
            raise DuplicateAppStageLinkError(
                f"Link ({app_id!r}, {body.stage_id!r}) already exists"
            ) from exc
        raise

    return ApplicationStageLink(
        app_id=app_id,
        stage_id=body.stage_id,
        stage_name=stage.name,
    )


async def delete_app_stage_link(app_id: str, stage_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _app_stage_links.delete().where(
            _app_stage_links.c.app_id == app_id,
            _app_stage_links.c.stage_id == stage_id,
        )
    )
    return _rowcount(result) > 0


# ── Application–Domain Integrations (US5) ─────────────────────────────────────

async def list_app_domain_integrations(
    app_id: str, session: AsyncSession
) -> ApplicationDomainIntegrationsResponse:
    result = await session.execute(
        sa.select(
            _app_domain_integrations,
            _domains.c.name.label("domain_name"),
        )
        .outerjoin(_domains, _domains.c.id == _app_domain_integrations.c.domain_id)
        .where(_app_domain_integrations.c.app_id == app_id)
        .order_by(_app_domain_integrations.c.created_at)
    )
    items = [
        ApplicationDomainIntegration(
            id=row.id,
            app_id=row.app_id,
            domain_id=row.domain_id,
            domain_name=row.domain_name,
            integration_type=row.integration_type,
            direction=row.direction,
            created_at=row.created_at,
        )
        for row in result.mappings().all()
    ]
    return ApplicationDomainIntegrationsResponse(items=items)


async def create_app_domain_integration(
    app_id: str, body: ApplicationDomainIntegrationCreate, session: AsyncSession
) -> ApplicationDomainIntegration:
    app = await get_application(app_id, session)
    if app is None:
        raise ValueError(f"Application {app_id!r} not found")

    domain_name: str | None = None
    if body.domain_id is not None:
        dom_row = await session.execute(
            sa.select(_domains.c.id, _domains.c.name).where(_domains.c.id == body.domain_id)
        )
        dom = dom_row.mappings().first()
        if dom is None:
            raise LookupError(f"Business domain {body.domain_id!r} not found")
        domain_name = dom.name

    link_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _app_domain_integrations.insert().values(
            id=link_id,
            app_id=app_id,
            domain_id=body.domain_id,
            integration_type=body.integration_type.strip(),
            direction=body.direction,
            created_at=now,
        )
    )
    return ApplicationDomainIntegration(
        id=link_id,
        app_id=app_id,
        domain_id=body.domain_id,
        domain_name=domain_name,
        integration_type=body.integration_type.strip(),
        direction=body.direction,
        created_at=now,
    )


async def delete_app_domain_integration(app_id: str, link_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _app_domain_integrations.delete().where(
            _app_domain_integrations.c.id == link_id,
            _app_domain_integrations.c.app_id == app_id,
        )
    )
    return _rowcount(result) > 0


# ── Application Integrations (US6) ────────────────────────────────────────────

_src_apps = _applications.alias("src_apps")
_tgt_apps = _applications.alias("tgt_apps")


def _row_to_integration(row: Any) -> ApplicationIntegration:
    return ApplicationIntegration(
        id=row.id,
        source_app_id=row.source_app_id,
        source_app_name=row.source_app_name,
        target_app_id=row.target_app_id,
        target_app_name=row.target_app_name,
        integration_type=row.integration_type,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _integration_select():
    return (
        sa.select(
            _app_integrations,
            _src_apps.c.name.label("source_app_name"),
            _tgt_apps.c.name.label("target_app_name"),
        )
        .join(_src_apps, _src_apps.c.id == _app_integrations.c.source_app_id)
        .join(_tgt_apps, _tgt_apps.c.id == _app_integrations.c.target_app_id)
    )


async def list_integrations(
    app_id: str | None, session: AsyncSession
) -> ApplicationIntegrationListResponse:
    stmt = _integration_select()
    if app_id is not None:
        stmt = stmt.where(
            sa.or_(
                _app_integrations.c.source_app_id == app_id,
                _app_integrations.c.target_app_id == app_id,
            )
        )
    stmt = stmt.order_by(_app_integrations.c.created_at)
    result = await session.execute(stmt)
    items = [_row_to_integration(row) for row in result.mappings().all()]
    return ApplicationIntegrationListResponse(items=items, total=len(items))


async def get_integration(int_id: str, session: AsyncSession) -> ApplicationIntegration | None:
    result = await session.execute(
        _integration_select().where(_app_integrations.c.id == int_id)
    )
    row = result.mappings().first()
    return _row_to_integration(row) if row else None


async def create_integration(
    body: ApplicationIntegrationCreate, session: AsyncSession
) -> ApplicationIntegration:
    src = await get_application(body.source_app_id, session)
    if src is None:
        raise LookupError(f"Source application {body.source_app_id!r} not found")

    tgt = await get_application(body.target_app_id, session)
    if tgt is None:
        raise LookupError(f"Target application {body.target_app_id!r} not found")

    int_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _app_integrations.insert().values(
            id=int_id,
            source_app_id=body.source_app_id,
            target_app_id=body.target_app_id,
            integration_type=body.integration_type,
            description=body.description,
            created_at=now,
            updated_at=now,
        )
    )
    return ApplicationIntegration(
        id=int_id,
        source_app_id=body.source_app_id,
        source_app_name=src.name,
        target_app_id=body.target_app_id,
        target_app_name=tgt.name,
        integration_type=body.integration_type,
        description=body.description,
        created_at=now,
        updated_at=now,
    )


async def update_integration(
    int_id: str, body: ApplicationIntegrationUpdate, session: AsyncSession
) -> ApplicationIntegration | None:
    existing = await get_integration(int_id, session)
    if existing is None:
        return None

    updates: dict[str, Any] = {"updated_at": _now()}
    # Nullable fields: an explicitly provided null clears the value;
    # an omitted field is left unchanged (model_fields_set distinguishes them).
    if "description" in body.model_fields_set:
        updates["description"] = body.description

    await session.execute(
        _app_integrations.update().where(_app_integrations.c.id == int_id).values(**updates)
    )
    return await get_integration(int_id, session)


async def delete_integration(int_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _app_integrations.delete().where(_app_integrations.c.id == int_id)
    )
    return _rowcount(result) > 0


# ── Application–Design Links (US7) ────────────────────────────────────────────

async def list_app_design_links(
    app_id: str, session: AsyncSession
) -> ApplicationDesignLinksResponse:
    result = await session.execute(
        sa.select(_app_design_links).where(_app_design_links.c.app_id == app_id)
    )
    items = [
        ApplicationDesignLink(app_id=row.app_id, design_id=row.design_id)
        for row in result.mappings().all()
    ]
    return ApplicationDesignLinksResponse(items=items)


async def create_app_design_link(
    app_id: str, body: ApplicationDesignLinkCreate, session: AsyncSession
) -> ApplicationDesignLink:
    app = await get_application(app_id, session)
    if app is None:
        raise ValueError(f"Application {app_id!r} not found")

    design_row = await session.execute(
        sa.select(_designs.c.id).where(_designs.c.id == body.design_id)
    )
    if design_row.first() is None:
        raise LookupError(f"Design {body.design_id!r} not found")

    try:
        await session.execute(
            _app_design_links.insert().values(app_id=app_id, design_id=body.design_id)
        )
    except Exception as exc:
        if _is_duplicate_error(exc):
            raise DuplicateAppDesignLinkError(
                f"Link ({app_id!r}, {body.design_id!r}) already exists"
            ) from exc
        raise

    return ApplicationDesignLink(app_id=app_id, design_id=body.design_id)


async def delete_app_design_link(app_id: str, design_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _app_design_links.delete().where(
            _app_design_links.c.app_id == app_id,
            _app_design_links.c.design_id == design_id,
        )
    )
    return _rowcount(result) > 0
