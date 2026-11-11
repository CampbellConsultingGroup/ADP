"""Value chain store (ADP-nag) -- Porter value chains and their activities.

A sibling of adp.business.store, split out the way adp.strategy.initiatives was: the tables
are defined on store's own _metadata (so the activity -> business_capabilities foreign key
resolves and test fixtures' create_all() includes them), the functions live here, and
adp.business.router registers the endpoints.

Activity positions are kept normalised to 0..n-1 within each category (primary / support) on
every add, move, delete and reorder. Deletes remove child rows explicitly rather than relying
on the database's ON DELETE CASCADE alone, so they behave the same on SQLite (where foreign
keys aren't enforced by default) as on PostgreSQL; the cascade in migration 042 stays as the
safety net.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.business.models import (
    ActivityCategory,
    DuplicateStageCapError,
    StageCapabilitiesResponse,
    StageCapabilityLinkCreate,
    StageCapabilityRef,
    StageCapNotFoundError,
    ValueChain,
    ValueChainActivity,
    ValueChainActivityCreate,
    ValueChainActivityUpdate,
    ValueChainCreate,
    ValueChainDetail,
    ValueChainUpdate,
)
from adp.business.store import (
    _capabilities,
    _domains,
    _now,
    _rowcount,
    _value_chain_activities,
    _value_chain_activity_caps,
    _value_chains,
)
from adp.search import (
    ENTITY_VALUE_CHAIN,
    ENTITY_VALUE_CHAIN_ACTIVITY,
    build_text,
    index_entity,
    unindex_entity,
)

_chains = _value_chains
_activities = _value_chain_activities
_activity_caps = _value_chain_activity_caps


def _row_to_chain(row: Any) -> ValueChain:
    return ValueChain(
        id=row.id,
        name=row.name,
        description=row.description,
        margin_label=row.margin_label,
        position=row.position,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_activity(
    row: Any, capabilities: list[StageCapabilityRef] | None = None
) -> ValueChainActivity:
    return ValueChainActivity(
        id=row.id,
        value_chain_id=row.value_chain_id,
        name=row.name,
        description=row.description,
        category=row.category,
        position=row.position,
        capabilities=capabilities or [],
    )


def _caps_select() -> Any:
    return (
        sa.select(
            _activity_caps.c.activity_id,
            _activity_caps.c.capability_id,
            _capabilities.c.name,
            _capabilities.c.level,
            _capabilities.c.domain_id,
            _domains.c.name.label("domain_name"),
        )
        .join(_capabilities, _capabilities.c.id == _activity_caps.c.capability_id)
        .outerjoin(_domains, _domains.c.id == _capabilities.c.domain_id)
        .order_by(_capabilities.c.name)
    )


def _cap_ref(row: Any) -> StageCapabilityRef:
    return StageCapabilityRef(
        capability_id=row.capability_id,
        name=row.name,
        level=row.level,
        domain_id=row.domain_id,
        domain_name=row.domain_name,
    )


async def _chain_exists(chain_id: str, session: AsyncSession) -> bool:
    result = await session.execute(sa.select(_chains.c.id).where(_chains.c.id == chain_id))
    return result.first() is not None


async def _get_activity_row(chain_id: str, activity_id: str, session: AsyncSession) -> Any:
    result = await session.execute(
        sa.select(_activities).where(
            _activities.c.id == activity_id, _activities.c.value_chain_id == chain_id
        )
    )
    return result.mappings().first()


async def _lane_ids(
    chain_id: str, category: ActivityCategory, session: AsyncSession, *, exclude: str | None = None
) -> list[str]:
    """The ids of one category's activities, in position order."""
    stmt = (
        sa.select(_activities.c.id)
        .where(_activities.c.value_chain_id == chain_id, _activities.c.category == category)
        .order_by(_activities.c.position, _activities.c.id)
    )
    if exclude is not None:
        stmt = stmt.where(_activities.c.id != exclude)
    return [row.id for row in await session.execute(stmt)]


async def _write_lane(
    chain_id: str, category: ActivityCategory, ordered_ids: list[str], session: AsyncSession
) -> None:
    """Give one category's activities positions 0..n-1 in the given order."""
    for position, activity_id in enumerate(ordered_ids):
        await session.execute(
            _activities.update()
            .where(_activities.c.id == activity_id, _activities.c.value_chain_id == chain_id)
            .values(category=category, position=position)
        )


async def _touch(chain_id: str, session: AsyncSession) -> None:
    await session.execute(
        _chains.update().where(_chains.c.id == chain_id).values(updated_at=_now())
    )


# ── Value chain CRUD ──────────────────────────────────────────────────────────


async def list_value_chains(session: AsyncSession) -> list[ValueChain]:
    result = await session.execute(
        sa.select(_chains).order_by(_chains.c.position, _chains.c.created_at)
    )
    return [_row_to_chain(row) for row in result.mappings().all()]


async def get_value_chain(chain_id: str, session: AsyncSession) -> ValueChainDetail | None:
    chain_row = (
        (await session.execute(sa.select(_chains).where(_chains.c.id == chain_id)))
        .mappings()
        .first()
    )
    if chain_row is None:
        return None

    activity_rows = (
        (
            await session.execute(
                sa.select(_activities)
                .where(_activities.c.value_chain_id == chain_id)
                .order_by(_activities.c.category, _activities.c.position, _activities.c.id)
            )
        )
        .mappings()
        .all()
    )

    # One query for every activity's capabilities, not one per activity.
    caps_by_activity: dict[str, list[StageCapabilityRef]] = defaultdict(list)
    if activity_rows:
        cap_rows = await session.execute(
            _caps_select().where(
                _activity_caps.c.activity_id.in_([row.id for row in activity_rows])
            )
        )
        for cap_row in cap_rows.mappings().all():
            caps_by_activity[cap_row.activity_id].append(_cap_ref(cap_row))

    activities = [_row_to_activity(row, caps_by_activity[row.id]) for row in activity_rows]
    return ValueChainDetail(
        **_row_to_chain(chain_row).model_dump(),
        primary_activities=[a for a in activities if a.category == "primary"],
        support_activities=[a for a in activities if a.category == "support"],
    )


async def create_value_chain(data: ValueChainCreate, session: AsyncSession) -> ValueChain:
    chain_id = str(uuid.uuid4())
    now = _now()
    position = (await session.execute(sa.select(sa.func.count()).select_from(_chains))).scalar_one()
    chain = ValueChain(
        id=chain_id,
        name=data.name.strip(),
        description=data.description,
        margin_label=data.margin_label.strip(),
        position=position,
        created_at=now,
        updated_at=now,
    )
    await session.execute(_chains.insert().values(**chain.model_dump()))
    await index_entity(
        ENTITY_VALUE_CHAIN, chain_id, build_text(chain.name, chain.description), session
    )
    return chain


async def update_value_chain(
    chain_id: str, data: ValueChainUpdate, session: AsyncSession
) -> ValueChain | None:
    if not await _chain_exists(chain_id, session):
        return None

    updates: dict[str, Any] = {"updated_at": _now()}
    if data.name is not None:
        updates["name"] = data.name.strip()
    if data.margin_label is not None:
        updates["margin_label"] = data.margin_label.strip()
    # description is nullable: an explicit null clears it, an omitted field is left alone.
    if "description" in data.model_fields_set:
        updates["description"] = data.description

    await session.execute(_chains.update().where(_chains.c.id == chain_id).values(**updates))
    row = (
        (await session.execute(sa.select(_chains).where(_chains.c.id == chain_id)))
        .mappings()
        .first()
    )
    refreshed = _row_to_chain(row)
    await index_entity(
        ENTITY_VALUE_CHAIN, chain_id, build_text(refreshed.name, refreshed.description), session
    )
    return refreshed


async def delete_value_chain(chain_id: str, session: AsyncSession) -> bool:
    if not await _chain_exists(chain_id, session):
        return False
    activity_ids = [
        row.id
        for row in await session.execute(
            sa.select(_activities.c.id).where(_activities.c.value_chain_id == chain_id)
        )
    ]
    if activity_ids:
        await session.execute(
            _activity_caps.delete().where(_activity_caps.c.activity_id.in_(activity_ids))
        )
        await session.execute(_activities.delete().where(_activities.c.value_chain_id == chain_id))
    await session.execute(_chains.delete().where(_chains.c.id == chain_id))

    await unindex_entity(ENTITY_VALUE_CHAIN, chain_id, session)
    for activity_id in activity_ids:
        await unindex_entity(ENTITY_VALUE_CHAIN_ACTIVITY, activity_id, session)
    return True


# ── Activities ────────────────────────────────────────────────────────────────


async def add_activity(
    chain_id: str, data: ValueChainActivityCreate, session: AsyncSession
) -> ValueChainActivity:
    """Add an activity at `position` within its category (appended when None).

    Raises LookupError if the chain doesn't exist."""
    if not await _chain_exists(chain_id, session):
        raise LookupError(f"Value chain {chain_id!r} not found")

    activity_id = str(uuid.uuid4())
    await session.execute(
        _activities.insert().values(
            id=activity_id,
            value_chain_id=chain_id,
            name=data.name.strip(),
            description=data.description,
            category=data.category,
            position=0,
        )
    )
    lane = await _lane_ids(chain_id, data.category, session, exclude=activity_id)
    index = len(lane) if data.position is None else max(0, min(data.position, len(lane)))
    lane.insert(index, activity_id)
    await _write_lane(chain_id, data.category, lane, session)
    await _touch(chain_id, session)

    await index_entity(
        ENTITY_VALUE_CHAIN_ACTIVITY, activity_id, build_text(data.name, data.description), session
    )
    row = await _get_activity_row(chain_id, activity_id, session)
    return _row_to_activity(row)


async def update_activity(
    chain_id: str, activity_id: str, data: ValueChainActivityUpdate, session: AsyncSession
) -> ValueChainActivity | None:
    """Rename / re-describe an activity, and move it between or within categories.

    Returns None if the activity isn't part of the chain."""
    row = await _get_activity_row(chain_id, activity_id, session)
    if row is None:
        return None

    updates: dict[str, Any] = {}
    if data.name is not None:
        updates["name"] = data.name.strip()
    if "description" in data.model_fields_set:
        updates["description"] = data.description
    if updates:
        await session.execute(
            _activities.update()
            .where(_activities.c.id == activity_id, _activities.c.value_chain_id == chain_id)
            .values(**updates)
        )

    old_category: ActivityCategory = row.category
    new_category: ActivityCategory = data.category or old_category
    if new_category != old_category or data.position is not None:
        target = await _lane_ids(chain_id, new_category, session, exclude=activity_id)
        if data.position is not None:
            index = max(0, min(data.position, len(target)))
        else:
            # Moved to the other category with no position given: append there.
            index = len(target)
        target.insert(index, activity_id)
        await _write_lane(chain_id, new_category, target, session)
        if new_category != old_category:
            await _write_lane(
                chain_id, old_category, await _lane_ids(chain_id, old_category, session), session
            )

    await _touch(chain_id, session)
    refreshed = await _get_activity_row(chain_id, activity_id, session)
    await index_entity(
        ENTITY_VALUE_CHAIN_ACTIVITY,
        activity_id,
        build_text(refreshed.name, refreshed.description),
        session,
    )
    caps = await list_activity_caps(chain_id, activity_id, session)
    return _row_to_activity(refreshed, caps.items if caps else [])


async def delete_activity(chain_id: str, activity_id: str, session: AsyncSession) -> bool:
    row = await _get_activity_row(chain_id, activity_id, session)
    if row is None:
        return False
    await session.execute(
        _activity_caps.delete().where(_activity_caps.c.activity_id == activity_id)
    )
    await session.execute(
        _activities.delete().where(
            _activities.c.id == activity_id, _activities.c.value_chain_id == chain_id
        )
    )
    category: ActivityCategory = row.category
    await _write_lane(chain_id, category, await _lane_ids(chain_id, category, session), session)
    await _touch(chain_id, session)
    await unindex_entity(ENTITY_VALUE_CHAIN_ACTIVITY, activity_id, session)
    return True


async def reorder_activities(
    chain_id: str, category: ActivityCategory, activity_ids: list[str], session: AsyncSession
) -> list[ValueChainActivity]:
    """Reorder one category. `activity_ids` must be exactly that category's current activities (a
    reorder never adds, removes or re-categorises). Raises LookupError for a missing chain and
    ValueError for a mismatched id list."""
    if not await _chain_exists(chain_id, session):
        raise LookupError(f"Value chain {chain_id!r} not found")
    current = await _lane_ids(chain_id, category, session)
    if len(activity_ids) != len(set(activity_ids)) or set(activity_ids) != set(current):
        raise ValueError(
            f"activity_ids must list each of the chain's {category} activities exactly once"
        )
    await _write_lane(chain_id, category, activity_ids, session)
    await _touch(chain_id, session)
    detail = await get_value_chain(chain_id, session)
    assert detail is not None
    return detail.primary_activities if category == "primary" else detail.support_activities


# ── Activity capabilities ─────────────────────────────────────────────────────


async def list_activity_caps(
    chain_id: str, activity_id: str, session: AsyncSession
) -> StageCapabilitiesResponse | None:
    """Capabilities linked to an activity. None if the activity isn't part of the chain."""
    if await _get_activity_row(chain_id, activity_id, session) is None:
        return None
    result = await session.execute(
        _caps_select().where(_activity_caps.c.activity_id == activity_id)
    )
    return StageCapabilitiesResponse(items=[_cap_ref(row) for row in result.mappings().all()])


async def link_cap_to_activity(
    chain_id: str, activity_id: str, data: StageCapabilityLinkCreate, session: AsyncSession
) -> StageCapabilitiesResponse:
    """Raises LookupError if the activity or capability doesn't exist, and
    DuplicateStageCapError if the link already does."""
    if await _get_activity_row(chain_id, activity_id, session) is None:
        raise LookupError(f"Activity {activity_id!r} not found in value chain {chain_id!r}")
    cap = await session.execute(
        sa.select(_capabilities.c.id).where(_capabilities.c.id == data.capability_id)
    )
    if cap.first() is None:
        raise LookupError(f"Capability {data.capability_id!r} not found")

    existing = await session.execute(
        sa.select(_activity_caps.c.activity_id).where(
            _activity_caps.c.activity_id == activity_id,
            _activity_caps.c.capability_id == data.capability_id,
        )
    )
    if existing.first() is not None:
        raise DuplicateStageCapError(
            f"Link ({activity_id!r}, {data.capability_id!r}) already exists"
        )

    await session.execute(
        _activity_caps.insert().values(activity_id=activity_id, capability_id=data.capability_id)
    )
    result = await list_activity_caps(chain_id, activity_id, session)
    assert result is not None
    return result


async def unlink_cap_from_activity(
    chain_id: str, activity_id: str, cap_id: str, session: AsyncSession
) -> None:
    """Raises LookupError if the activity doesn't exist, StageCapNotFoundError if the link
    doesn't."""
    if await _get_activity_row(chain_id, activity_id, session) is None:
        raise LookupError(f"Activity {activity_id!r} not found in value chain {chain_id!r}")
    result = await session.execute(
        _activity_caps.delete().where(
            _activity_caps.c.activity_id == activity_id, _activity_caps.c.capability_id == cap_id
        )
    )
    if _rowcount(result) == 0:
        raise StageCapNotFoundError(f"Link ({activity_id!r}, {cap_id!r}) not found")
