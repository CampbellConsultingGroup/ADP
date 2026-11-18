"""Transformation initiatives and the roadmap (split out of ``adp.application.store``, which
re-exports every name here; ADP-blp.27).
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.application.models import (
    ApplicationInitiativeLink,
    ApplicationInitiativeLinkCreate,
    ApplicationInitiativeLinksResponse,
    ApplicationInitiativeLinkUpdate,
    DuplicateAppInitiativeLinkError,
    InitiativeMember,
    RoadmapEntry,
    RoadmapResponse,
    TransformationInitiative,
    TransformationInitiativeCreate,
    TransformationInitiativeDetail,
    TransformationInitiativeListResponse,
    TransformationInitiativeUpdate,
)
from adp.application.store_base import (
    _is_duplicate_error,
    _now,
    _rowcount,
    get_application,
)
from adp.application.tables import (
    _app_initiative_links,
    _application_risk,
    _applications,
    _transformation_initiatives,
)

# ── Transformation Initiatives & Roadmap (US6) ────────────────────────────────


def _row_to_initiative(row: Any) -> TransformationInitiative:
    return TransformationInitiative(
        id=row.id,
        name=row.name,
        description=row.description,
        target_date=row.target_date,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_initiatives(session: AsyncSession) -> TransformationInitiativeListResponse:
    result = await session.execute(
        sa.select(_transformation_initiatives).order_by(_transformation_initiatives.c.name)
    )
    items = [_row_to_initiative(row) for row in result.mappings().all()]
    return TransformationInitiativeListResponse(items=items, total=len(items))


async def get_initiative(
    initiative_id: str, session: AsyncSession
) -> TransformationInitiativeDetail | None:
    result = await session.execute(
        sa.select(_transformation_initiatives).where(
            _transformation_initiatives.c.id == initiative_id
        )
    )
    row = result.mappings().first()
    if row is None:
        return None

    members_result = await session.execute(
        sa.select(
            _app_initiative_links.c.app_id,
            _applications.c.name.label("app_name"),
            _app_initiative_links.c.planned_disposition,
        )
        .join(_applications, _applications.c.id == _app_initiative_links.c.app_id)
        .where(_app_initiative_links.c.initiative_id == initiative_id)
        .order_by(_applications.c.name)
    )
    members = [
        InitiativeMember(
            app_id=m.app_id, app_name=m.app_name, planned_disposition=m.planned_disposition
        )
        for m in members_result.mappings().all()
    ]
    return TransformationInitiativeDetail(**_row_to_initiative(row).model_dump(), members=members)


async def create_initiative(
    body: TransformationInitiativeCreate, session: AsyncSession
) -> TransformationInitiative:
    initiative_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _transformation_initiatives.insert().values(
            id=initiative_id,
            name=body.name.strip(),
            description=body.description,
            target_date=body.target_date,
            created_at=now,
            updated_at=now,
        )
    )
    return TransformationInitiative(
        id=initiative_id,
        name=body.name.strip(),
        description=body.description,
        target_date=body.target_date,
        created_at=now,
        updated_at=now,
    )


async def update_initiative(
    initiative_id: str, body: TransformationInitiativeUpdate, session: AsyncSession
) -> TransformationInitiative | None:
    result = await session.execute(
        sa.select(_transformation_initiatives).where(
            _transformation_initiatives.c.id == initiative_id
        )
    )
    if result.mappings().first() is None:
        return None

    updates: dict[str, Any] = {"updated_at": _now()}
    if body.name is not None:
        updates["name"] = body.name.strip()
    for field in ("description", "target_date"):
        if field in body.model_fields_set:
            updates[field] = getattr(body, field)

    await session.execute(
        _transformation_initiatives.update()
        .where(_transformation_initiatives.c.id == initiative_id)
        .values(**updates)
    )
    row = (
        await session.execute(
            sa.select(_transformation_initiatives).where(
                _transformation_initiatives.c.id == initiative_id
            )
        )
    ).mappings().first()
    assert row is not None  # just updated
    return _row_to_initiative(row)


async def delete_initiative(initiative_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _transformation_initiatives.delete().where(
            _transformation_initiatives.c.id == initiative_id
        )
    )
    return _rowcount(result) > 0


async def list_app_initiative_links(
    app_id: str, session: AsyncSession
) -> ApplicationInitiativeLinksResponse:
    result = await session.execute(
        sa.select(
            _app_initiative_links.c.app_id,
            _app_initiative_links.c.initiative_id,
            _transformation_initiatives.c.name.label("initiative_name"),
            _app_initiative_links.c.planned_disposition,
        )
        .join(
            _transformation_initiatives,
            _transformation_initiatives.c.id == _app_initiative_links.c.initiative_id,
        )
        .where(_app_initiative_links.c.app_id == app_id)
        .order_by(_transformation_initiatives.c.name)
    )
    items = [
        ApplicationInitiativeLink(
            app_id=row.app_id,
            initiative_id=row.initiative_id,
            initiative_name=row.initiative_name,
            planned_disposition=row.planned_disposition,
        )
        for row in result.mappings().all()
    ]
    return ApplicationInitiativeLinksResponse(items=items, total=len(items))


async def create_app_initiative_link(
    app_id: str, body: ApplicationInitiativeLinkCreate, session: AsyncSession
) -> ApplicationInitiativeLink:
    app = await get_application(app_id, session)
    if app is None:
        raise ValueError(f"Application {app_id!r} not found")

    initiative_row = await session.execute(
        sa.select(_transformation_initiatives.c.id, _transformation_initiatives.c.name).where(
            _transformation_initiatives.c.id == body.initiative_id
        )
    )
    initiative = initiative_row.mappings().first()
    if initiative is None:
        raise LookupError(f"Transformation initiative {body.initiative_id!r} not found")

    try:
        await session.execute(
            _app_initiative_links.insert().values(
                app_id=app_id,
                initiative_id=body.initiative_id,
                planned_disposition=body.planned_disposition,
            )
        )
    except Exception as exc:
        if _is_duplicate_error(exc):
            raise DuplicateAppInitiativeLinkError(
                f"Link ({app_id!r}, {body.initiative_id!r}) already exists"
            ) from exc
        raise

    return ApplicationInitiativeLink(
        app_id=app_id,
        initiative_id=body.initiative_id,
        initiative_name=initiative.name,
        planned_disposition=body.planned_disposition,
    )


async def update_app_initiative_link(
    app_id: str,
    initiative_id: str,
    body: ApplicationInitiativeLinkUpdate,
    session: AsyncSession,
) -> ApplicationInitiativeLink | None:
    existing = await session.execute(
        sa.select(_app_initiative_links).where(
            _app_initiative_links.c.app_id == app_id,
            _app_initiative_links.c.initiative_id == initiative_id,
        )
    )
    if existing.mappings().first() is None:
        return None

    await session.execute(
        _app_initiative_links.update()
        .where(
            _app_initiative_links.c.app_id == app_id,
            _app_initiative_links.c.initiative_id == initiative_id,
        )
        .values(planned_disposition=body.planned_disposition)
    )
    links = await list_app_initiative_links(app_id, session)
    for link in links.items:
        if link.initiative_id == initiative_id:
            return link
    return None  # pragma: no cover — link existed a moment ago


async def delete_app_initiative_link(
    app_id: str, initiative_id: str, session: AsyncSession
) -> bool:
    result = await session.execute(
        _app_initiative_links.delete().where(
            _app_initiative_links.c.app_id == app_id,
            _app_initiative_links.c.initiative_id == initiative_id,
        )
    )
    return _rowcount(result) > 0


async def get_roadmap(session: AsyncSession) -> RoadmapResponse:
    """Decommission/roadmap track: Eliminate-classified or sunset/retired apps,
    with their EOL date (US3, if recorded) and initiative links."""
    stmt = (
        sa.select(
            _applications.c.id,
            _applications.c.name,
            _applications.c.time_classification,
            _applications.c.lifecycle_status,
            _application_risk.c.end_of_life_date,
        )
        .select_from(
            _applications.outerjoin(
                _application_risk, _application_risk.c.app_id == _applications.c.id
            )
        )
        .where(
            sa.or_(
                _applications.c.time_classification == "Eliminate",
                _applications.c.lifecycle_status.in_(["sunset", "retired"]),
            )
        )
        .order_by(_applications.c.name)
    )
    rows = (await session.execute(stmt)).mappings().all()

    # ADP-blp.23: one query for every application's initiative links (was one per application).
    links_by_app: dict[str, list[ApplicationInitiativeLink]] = {}
    app_ids = [row["id"] for row in rows]
    if app_ids:
        link_rows = await session.execute(
            sa.select(
                _app_initiative_links.c.app_id,
                _app_initiative_links.c.initiative_id,
                _transformation_initiatives.c.name.label("initiative_name"),
                _app_initiative_links.c.planned_disposition,
            )
            .join(
                _transformation_initiatives,
                _transformation_initiatives.c.id == _app_initiative_links.c.initiative_id,
            )
            .where(_app_initiative_links.c.app_id.in_(app_ids))
            .order_by(_transformation_initiatives.c.name)
        )
        for link in link_rows.mappings().all():
            links_by_app.setdefault(link["app_id"], []).append(
                ApplicationInitiativeLink(
                    app_id=link["app_id"],
                    initiative_id=link["initiative_id"],
                    initiative_name=link["initiative_name"],
                    planned_disposition=link["planned_disposition"],
                )
            )

    items = [
        RoadmapEntry(
            app_id=row["id"],
            name=row["name"],
            time_classification=row["time_classification"],
            lifecycle_status=row["lifecycle_status"],
            end_of_life_date=row["end_of_life_date"],
            initiative_links=links_by_app.get(row["id"], []),
        )
        for row in rows
    ]
    return RoadmapResponse(items=items, total=len(items))
