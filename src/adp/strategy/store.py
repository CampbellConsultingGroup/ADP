"""Strategy store — async SQLAlchemy CRUD (ADP-d8u.1).

Persists strategic themes/objectives + their capability/value-stream links
via migration 025. All functions accept an AsyncSession and are called from
the router inside `async with session_factory() as session: ...` blocks,
mirroring every other domain store in this codebase (adp.business.store,
adp.diagrams.store, adp.chat.store).

Cross-package validation (research.md Decision 2): link functions here do
NOT duplicate capability/value-stream existence checks -- the router passes
in a *separate* adp.business-scoped session and calls
adp.business.store.get_capability/get_value_stream directly before calling
into this module, the same way adp.business.store.link_design_to_capability
checks `_designs` for an existing design id in-package. This module only
ever touches its own four tables plus (read-only, for existence checks
during unlink -- none needed) nothing else.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.strategy.models import (
    StrategicObjective,
    StrategicObjectiveCreate,
    StrategicObjectiveListResponse,
    StrategicObjectiveSummary,
    StrategicObjectiveUpdate,
    StrategicTheme,
    StrategicThemeCreate,
    StrategicThemeListResponse,
)

_metadata = sa.MetaData()

_themes = sa.Table(
    "strategic_themes",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_objectives = sa.Table(
    "strategic_objectives",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("theme_id", sa.String(36), nullable=False),
    sa.Column("owner", sa.Text(), nullable=False),
    sa.Column("statement", sa.Text(), nullable=False),
    sa.Column("metric_name", sa.Text(), nullable=True),
    sa.Column("target_value", sa.Numeric(14, 2), nullable=True),
    sa.Column("target_unit", sa.Text(), nullable=True),
    sa.Column("direction", sa.Text(), nullable=True),
    sa.Column("fiscal_year", sa.SmallInteger(), nullable=False),
    sa.Column("period", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_objective_capabilities = sa.Table(
    "strategic_objective_capabilities",
    _metadata,
    sa.Column("objective_id", sa.String(36), nullable=False),
    sa.Column("capability_id", sa.String(36), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_objective_value_streams = sa.Table(
    "strategic_objective_value_streams",
    _metadata,
    sa.Column("objective_id", sa.String(36), nullable=False),
    sa.Column("value_stream_id", sa.String(36), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


class DuplicateLinkError(Exception):
    """Raised when a link already exists (mirrors adp.business.models's)."""


class LinkNotFoundError(Exception):
    """Raised when an unlink target does not exist."""


class DuplicateThemeNameError(Exception):
    """Raised when a theme with that exact name already exists (contracts/
    strategy-api.md: case-sensitive uniqueness, backed by the `unique=True`
    constraint on strategic_themes.name in migration 025)."""


# ── Module-level session factory (set by deps or tests) ──────────────────────

_engine: Any = None
_session_factory: Any = None


def _get_session_factory() -> async_sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        db_url = os.environ.get(
            "ADP_DATABASE_URL", "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
        )
        _engine = create_async_engine(db_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


def get_session() -> AsyncSession:
    return _get_session_factory()()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rowcount(result: Any) -> int:
    """DML executes return CursorResult at runtime; session.execute is typed
    as Result[Any], which lacks rowcount."""
    return cast("sa.CursorResult[Any]", result).rowcount


# ── Themes ────────────────────────────────────────────────────────────────────


def _row_to_theme(row: Any) -> StrategicTheme:
    return StrategicTheme(id=row.id, name=row.name, created_at=row.created_at)


async def create_theme(body: StrategicThemeCreate, session: AsyncSession) -> StrategicTheme:
    theme_id = str(uuid.uuid4())
    now = _now()
    try:
        await session.execute(
            _themes.insert().values(id=theme_id, name=body.name, created_at=now)
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateThemeNameError(
                f"Theme named {body.name!r} already exists"
            ) from exc
        raise
    return StrategicTheme(id=theme_id, name=body.name, created_at=now)


async def list_themes(session: AsyncSession) -> StrategicThemeListResponse:
    result = await session.execute(sa.select(_themes).order_by(_themes.c.name))
    items = [_row_to_theme(row) for row in result.mappings().all()]
    return StrategicThemeListResponse(items=items, total=len(items))


async def theme_exists(theme_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        sa.select(_themes.c.id).where(_themes.c.id == theme_id)
    )
    return result.first() is not None


# ── Objectives ────────────────────────────────────────────────────────────────


async def _linked_capability_ids(objective_id: str, session: AsyncSession) -> list[str]:
    result = await session.execute(
        sa.select(_objective_capabilities.c.capability_id)
        .where(_objective_capabilities.c.objective_id == objective_id)
        .order_by(_objective_capabilities.c.capability_id)
    )
    return [row.capability_id for row in result]


async def _linked_value_stream_ids(objective_id: str, session: AsyncSession) -> list[str]:
    result = await session.execute(
        sa.select(_objective_value_streams.c.value_stream_id)
        .where(_objective_value_streams.c.objective_id == objective_id)
        .order_by(_objective_value_streams.c.value_stream_id)
    )
    return [row.value_stream_id for row in result]


def _row_to_summary(row: Any) -> StrategicObjectiveSummary:
    return StrategicObjectiveSummary(
        id=row.id,
        theme_id=row.theme_id,
        owner=row.owner,
        statement=row.statement,
        fiscal_year=row.fiscal_year,
        period=row.period,
        updated_at=row.updated_at,
    )


async def create_objective(
    body: StrategicObjectiveCreate, session: AsyncSession
) -> StrategicObjective:
    objective_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _objectives.insert().values(
            id=objective_id,
            theme_id=body.theme_id,
            owner=body.owner,
            statement=body.statement,
            metric_name=body.metric_name,
            target_value=body.target_value,
            target_unit=body.target_unit,
            direction=body.direction,
            fiscal_year=body.fiscal_year,
            period=body.period,
            created_at=now,
            updated_at=now,
        )
    )
    objective = await get_objective(objective_id, session)
    assert objective is not None  # just inserted
    return objective


async def get_objective(objective_id: str, session: AsyncSession) -> StrategicObjective | None:
    result = await session.execute(
        sa.select(_objectives).where(_objectives.c.id == objective_id)
    )
    row = result.mappings().first()
    if row is None:
        return None
    return StrategicObjective(
        id=row["id"],
        theme_id=row["theme_id"],
        owner=row["owner"],
        statement=row["statement"],
        metric_name=row["metric_name"],
        target_value=row["target_value"],
        target_unit=row["target_unit"],
        direction=row["direction"],
        fiscal_year=row["fiscal_year"],
        period=row["period"],
        capability_ids=await _linked_capability_ids(objective_id, session),
        value_stream_ids=await _linked_value_stream_ids(objective_id, session),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def list_objectives(session: AsyncSession) -> StrategicObjectiveListResponse:
    result = await session.execute(
        sa.select(_objectives).order_by(_objectives.c.updated_at.desc())
    )
    items = [_row_to_summary(row) for row in result.mappings().all()]
    return StrategicObjectiveListResponse(items=items, total=len(items))


async def update_objective(
    objective_id: str, body: StrategicObjectiveUpdate, session: AsyncSession
) -> StrategicObjective | None:
    values: dict[str, Any] = {}
    for field in (
        "theme_id",
        "owner",
        "statement",
        "metric_name",
        "target_value",
        "target_unit",
        "direction",
        "fiscal_year",
        "period",
    ):
        value = getattr(body, field)
        if value is not None:
            values[field] = value
    if not values:
        return await get_objective(objective_id, session)

    values["updated_at"] = _now()
    result = await session.execute(
        _objectives.update().where(_objectives.c.id == objective_id).values(**values)
    )
    if _rowcount(result) == 0:
        return None
    return await get_objective(objective_id, session)


async def delete_objective(objective_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _objectives.delete().where(_objectives.c.id == objective_id)
    )
    return _rowcount(result) > 0


# ── Links ─────────────────────────────────────────────────────────────────────


async def link_objective_capability(
    objective_id: str, capability_id: str, session: AsyncSession
) -> None:
    """Insert the link row. Caller (router) has already validated both ids
    exist -- objective_id in this same session, capability_id via a separate
    adp.business-scoped session (research.md Decision 2)."""
    try:
        await session.execute(
            _objective_capabilities.insert().values(
                objective_id=objective_id, capability_id=capability_id, created_at=_now()
            )
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateLinkError(
                f"Link ({objective_id!r}, {capability_id!r}) already exists"
            ) from exc
        raise


async def unlink_objective_capability(
    objective_id: str, capability_id: str, session: AsyncSession
) -> None:
    result = await session.execute(
        _objective_capabilities.delete().where(
            _objective_capabilities.c.objective_id == objective_id,
            _objective_capabilities.c.capability_id == capability_id,
        )
    )
    if _rowcount(result) == 0:
        raise LinkNotFoundError(f"Link ({objective_id!r}, {capability_id!r}) not found")


async def link_objective_value_stream(
    objective_id: str, value_stream_id: str, session: AsyncSession
) -> None:
    try:
        await session.execute(
            _objective_value_streams.insert().values(
                objective_id=objective_id,
                value_stream_id=value_stream_id,
                created_at=_now(),
            )
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateLinkError(
                f"Link ({objective_id!r}, {value_stream_id!r}) already exists"
            ) from exc
        raise


async def unlink_objective_value_stream(
    objective_id: str, value_stream_id: str, session: AsyncSession
) -> None:
    result = await session.execute(
        _objective_value_streams.delete().where(
            _objective_value_streams.c.objective_id == objective_id,
            _objective_value_streams.c.value_stream_id == value_stream_id,
        )
    )
    if _rowcount(result) == 0:
        raise LinkNotFoundError(f"Link ({objective_id!r}, {value_stream_id!r}) not found")
