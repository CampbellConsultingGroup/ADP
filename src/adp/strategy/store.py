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

import logging
import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.strategy.models import (
    AbandonRequest,
    ObjectiveProgressCreate,
    ObjectiveProgressEntry,
    ObjectiveProgressListResponse,
    ObjectiveProgressUpdate,
    ObjectiveStatus,
    StrategicObjective,
    StrategicObjectiveCreate,
    StrategicObjectiveListResponse,
    StrategicObjectiveSummary,
    StrategicObjectiveUpdate,
    StrategicSummaryResponse,
    StrategicTheme,
    StrategicThemeCreate,
    StrategicThemeListResponse,
    StrategicThemeUpdate,
)

logger = logging.getLogger(__name__)

_metadata = sa.MetaData()

_themes = sa.Table(
    "strategic_themes",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("owner", sa.Text(), nullable=True),
    sa.Column("priority", sa.SmallInteger(), nullable=True),
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
    sa.Column("status", sa.Text(), nullable=True),
    sa.Column("status_reason", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

# ADP-d8u.5, migration 026: composite PK (objective_id, as_of_date) --
# PK/FK constraints deliberately omitted here, matching the join-table
# convention already established above (_objective_capabilities/
# _objective_value_streams): those constraints live only in the migration.
_progress = sa.Table(
    "strategic_objective_progress",
    _metadata,
    sa.Column("objective_id", sa.String(36), nullable=False),
    sa.Column("as_of_date", sa.Date(), nullable=False),
    sa.Column("actual_value", sa.Numeric(14, 2), nullable=False),
    sa.Column("note", sa.Text(), nullable=True),
    sa.Column("recorded_by", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
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

# ADP-d8u.2: objective -> design / objective -> application traceability
# links. Composite PK omitted here too (migration owns it).
_objective_design_links = sa.Table(
    "objective_design_links",
    _metadata,
    sa.Column("objective_id", sa.String(36), nullable=False),
    sa.Column("design_id", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_objective_application_links = sa.Table(
    "objective_application_links",
    _metadata,
    sa.Column("objective_id", sa.String(36), nullable=False),
    sa.Column("application_id", sa.String(36), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

# Lightweight read-only mirrors of designs/applications (research.md Decision
# 2) -- mirrors adp.business.store's own established `_designs` precedent
# ("designs table reference for JOIN queries (read-only; managed by
# DesignStore migration 001)"). Used purely for existence checks and the
# reverse-lookup JOIN; never written to from this module. Since designs and
# applications live in the same physical Postgres database as everything
# else, a single session (this module's own) can query them directly --
# no second, cross-package session is needed here (unlike capability_id/
# value_stream_id, which are validated via adp.business.store's own
# higher-level get_capability/get_value_stream through a genuinely separate
# adp.business-scoped session, research.md Decision 2 as originally written
# for those two targets).
_designs = sa.Table(
    "designs",
    _metadata,
    sa.Column("id", sa.Text(), primary_key=True),
    sa.Column("title", sa.Text(), nullable=False),
)

_applications = sa.Table(
    "applications",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
)


class DuplicateLinkError(Exception):
    """Raised when a link already exists (mirrors adp.business.models's)."""


class LinkNotFoundError(Exception):
    """Raised when an unlink target does not exist."""


class DuplicateThemeNameError(Exception):
    """Raised when a theme with that exact name already exists (contracts/
    strategy-api.md: case-sensitive uniqueness, backed by the `unique=True`
    constraint on strategic_themes.name in migration 025)."""


class DuplicateProgressEntryError(Exception):
    """Raised on a second POST for a date that already has a progress entry
    (FR-002) -- the router maps this to 409, guiding the caller to PATCH
    instead (FR-002a, the correction path)."""


class ThemeInUseError(Exception):
    """Raised when deleting a theme that any objective still references
    (FR-014) -- mirrors the platform-wide "referenced entities are blocked
    from deletion, never silently orphaned" pattern."""


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
    return StrategicTheme(
        id=row.id,
        name=row.name,
        description=row.description,
        owner=row.owner,
        priority=row.priority,
        created_at=row.created_at,
    )


async def create_theme(body: StrategicThemeCreate, session: AsyncSession) -> StrategicTheme:
    theme_id = str(uuid.uuid4())
    now = _now()
    try:
        await session.execute(
            _themes.insert().values(
                id=theme_id,
                name=body.name,
                description=body.description,
                owner=body.owner,
                priority=body.priority,
                created_at=now,
            )
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateThemeNameError(
                f"Theme named {body.name!r} already exists"
            ) from exc
        raise
    return StrategicTheme(
        id=theme_id,
        name=body.name,
        description=body.description,
        owner=body.owner,
        priority=body.priority,
        created_at=now,
    )


async def list_themes(session: AsyncSession) -> StrategicThemeListResponse:
    result = await session.execute(sa.select(_themes).order_by(_themes.c.name))
    items = [_row_to_theme(row) for row in result.mappings().all()]
    return StrategicThemeListResponse(items=items, total=len(items))


async def theme_exists(theme_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        sa.select(_themes.c.id).where(_themes.c.id == theme_id)
    )
    return result.first() is not None


async def get_theme(theme_id: str, session: AsyncSession) -> StrategicTheme | None:
    result = await session.execute(sa.select(_themes).where(_themes.c.id == theme_id))
    row = result.mappings().first()
    return _row_to_theme(row) if row is not None else None


async def update_theme(
    theme_id: str, body: StrategicThemeUpdate, session: AsyncSession
) -> StrategicTheme | None:
    """FR-013. name is not editable here (StrategicThemeUpdate has no name
    field at all -- data-model.md)."""
    values: dict[str, Any] = {}
    for field in ("description", "owner", "priority"):
        value = getattr(body, field)
        if value is not None:
            values[field] = value
    if not values:
        return await get_theme(theme_id, session)

    result = await session.execute(
        _themes.update().where(_themes.c.id == theme_id).values(**values)
    )
    if _rowcount(result) == 0:
        return None
    return await get_theme(theme_id, session)


async def delete_theme(theme_id: str, session: AsyncSession) -> bool:
    """FR-014/FR-015: blocked (ThemeInUseError) while any objective
    references the theme, never a silent orphan."""
    referencing = await session.execute(
        sa.select(_objectives.c.id).where(_objectives.c.theme_id == theme_id).limit(1)
    )
    if referencing.first() is not None:
        raise ThemeInUseError(
            f"Theme {theme_id!r} is still referenced by at least one objective"
        )
    result = await session.execute(_themes.delete().where(_themes.c.id == theme_id))
    return _rowcount(result) > 0


# ── Objectives ────────────────────────────────────────────────────────────────


def compute_status(
    status: str | None,
    target_value: Decimal | None,
    direction: str | None,
    progress: list[tuple[date, Decimal]],
    trend_window: int = 3,
) -> ObjectiveStatus:
    """Pure function, no I/O (ADP-d8u.5, research.md Decision 1, ART-II):
    on-track/at-risk/achieved/proposed are NEVER persisted -- always derived
    on read from the objective's own target/direction plus its progress
    history. `abandoned` is the one value a human sets directly (the
    `status` column only ever holds NULL or 'abandoned'; that is the only
    non-derived input this function takes).

    `progress` must be ordered ascending by date (list_progress_entries
    already returns it that way -- this function does not re-sort).
    """
    if status == "abandoned":
        return "abandoned"

    if target_value is None or direction is None:
        # FR-008: no target at all -- not measurable, not an error, not a guess.
        return "proposed"

    if not progress:
        # FR-005: no progress yet is distinct from at-risk.
        return "proposed"

    latest_date, latest_value = progress[-1]

    if direction == "increase" and latest_value >= target_value:
        return "achieved"
    if direction == "decrease" and latest_value <= target_value:
        return "achieved"
    if direction == "reach" and latest_value == target_value:
        return "achieved"

    recent = progress[-trend_window:]
    if len(recent) < 2:
        # A single entry has no prior point to compare a trend against.
        return "active"

    def _distance(value: Decimal) -> Decimal:
        return abs(value - target_value)

    consecutive_pairs = list(zip(recent, recent[1:]))
    all_trending_away = all(
        _distance(next_value) > _distance(prev_value)
        for (_, prev_value), (_, next_value) in consecutive_pairs
    )
    return "at_risk" if all_trending_away else "active"


async def _status_for_objective(
    row: Any, session: AsyncSession
) -> tuple[ObjectiveStatus, str | None]:
    result = await session.execute(
        sa.select(_progress.c.as_of_date, _progress.c.actual_value)
        .where(_progress.c.objective_id == row["id"])
        .order_by(_progress.c.as_of_date)
    )
    progress = [(r.as_of_date, r.actual_value) for r in result]
    status = compute_status(row["status"], row["target_value"], row["direction"], progress)
    return status, row["status_reason"] if status == "abandoned" else None


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


async def _row_to_summary(row: Any, session: AsyncSession) -> StrategicObjectiveSummary:
    status, _reason = await _status_for_objective(row, session)
    return StrategicObjectiveSummary(
        id=row.id,
        theme_id=row.theme_id,
        owner=row.owner,
        statement=row.statement,
        fiscal_year=row.fiscal_year,
        period=row.period,
        status=status,
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
    status, status_reason = await _status_for_objective(row, session)
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
        status=status,
        status_reason=status_reason,
        capability_ids=await _linked_capability_ids(objective_id, session),
        value_stream_ids=await _linked_value_stream_ids(objective_id, session),
        design_ids=await _linked_design_ids(objective_id, session),
        application_ids=await _linked_application_ids(objective_id, session),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def list_objectives(session: AsyncSession) -> StrategicObjectiveListResponse:
    result = await session.execute(
        sa.select(_objectives).order_by(_objectives.c.updated_at.desc())
    )
    items = [await _row_to_summary(row, session) for row in result.mappings().all()]
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


async def abandon_objective(
    objective_id: str, body: AbandonRequest, session: AsyncSession
) -> StrategicObjective | None:
    """FR-009/FR-010/FR-011: the only settable status transition -- writes
    the persisted status='abandoned' column, which compute_status() then
    short-circuits on before any trend logic runs (research.md Decision 1)."""
    result = await session.execute(
        _objectives.update()
        .where(_objectives.c.id == objective_id)
        .values(status="abandoned", status_reason=body.status_reason, updated_at=_now())
    )
    if _rowcount(result) == 0:
        return None
    return await get_objective(objective_id, session)


async def delete_objective(objective_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        _objectives.delete().where(_objectives.c.id == objective_id)
    )
    return _rowcount(result) > 0


# ── Progress (ADP-d8u.5) ─────────────────────────────────────────────────────


def _row_to_progress_entry(row: Any) -> ObjectiveProgressEntry:
    return ObjectiveProgressEntry(
        objective_id=row.objective_id,
        as_of_date=row.as_of_date,
        actual_value=row.actual_value,
        note=row.note,
        recorded_by=row.recorded_by,
        created_at=row.created_at,
    )


async def create_progress_entry(
    objective_id: str,
    body: ObjectiveProgressCreate,
    actor: str,
    session: AsyncSession,
) -> ObjectiveProgressEntry:
    """FR-001/FR-002. Caller (router) has already validated objective_id
    exists. Raises DuplicateProgressEntryError (mapped to 409) if that date
    already has an entry -- FR-002a's PATCH endpoint is the correction path."""
    existing = await session.execute(
        sa.select(_progress.c.objective_id).where(
            _progress.c.objective_id == objective_id,
            _progress.c.as_of_date == body.as_of_date,
        )
    )
    if existing.first() is not None:
        raise DuplicateProgressEntryError(
            f"A progress entry for {body.as_of_date} already exists on objective "
            f"{objective_id!r} -- edit it instead of recording a new one"
        )

    now = _now()
    await session.execute(
        _progress.insert().values(
            objective_id=objective_id,
            as_of_date=body.as_of_date,
            actual_value=body.actual_value,
            note=body.note,
            recorded_by=actor,
            created_at=now,
        )
    )
    logger.info(
        "strategy.objective.progress.create objective_id=%s as_of_date=%s actor=%s",
        objective_id, body.as_of_date, actor,
    )
    # Re-fetch rather than construct in-process (mirrors create_objective's own
    # convention) -- the DB's Numeric(14, 2) column normalizes actual_value's
    # precision, which a hand-built response object wouldn't reflect.
    fetched = await session.execute(
        sa.select(_progress).where(
            _progress.c.objective_id == objective_id, _progress.c.as_of_date == body.as_of_date
        )
    )
    row = fetched.mappings().first()
    assert row is not None  # just inserted
    return _row_to_progress_entry(row)


async def update_progress_entry(
    objective_id: str,
    as_of_date: date,
    body: ObjectiveProgressUpdate,
    session: AsyncSession,
) -> ObjectiveProgressEntry | None:
    """FR-002a: the correction path -- as_of_date is not editable (it's the
    key), only actual_value/note."""
    result = await session.execute(
        _progress.update()
        .where(_progress.c.objective_id == objective_id, _progress.c.as_of_date == as_of_date)
        .values(actual_value=body.actual_value, note=body.note)
    )
    if _rowcount(result) == 0:
        return None
    fetched = await session.execute(
        sa.select(_progress).where(
            _progress.c.objective_id == objective_id, _progress.c.as_of_date == as_of_date
        )
    )
    row = fetched.mappings().first()
    assert row is not None  # just updated
    return _row_to_progress_entry(row)


async def list_progress_entries(
    objective_id: str, session: AsyncSession
) -> ObjectiveProgressListResponse:
    """FR-003: full history, ordered oldest to newest."""
    result = await session.execute(
        sa.select(_progress)
        .where(_progress.c.objective_id == objective_id)
        .order_by(_progress.c.as_of_date)
    )
    items = [_row_to_progress_entry(row) for row in result.mappings().all()]
    return ObjectiveProgressListResponse(items=items, total=len(items))


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


# ── Design/Application links (ADP-d8u.2) ─────────────────────────────────────


async def design_exists(design_id: str, session: AsyncSession) -> bool:
    result = await session.execute(sa.select(_designs.c.id).where(_designs.c.id == design_id))
    return result.first() is not None


async def application_exists(application_id: str, session: AsyncSession) -> bool:
    result = await session.execute(
        sa.select(_applications.c.id).where(_applications.c.id == application_id)
    )
    return result.first() is not None


async def _linked_design_ids(objective_id: str, session: AsyncSession) -> list[str]:
    result = await session.execute(
        sa.select(_objective_design_links.c.design_id)
        .where(_objective_design_links.c.objective_id == objective_id)
        .order_by(_objective_design_links.c.design_id)
    )
    return [row.design_id for row in result]


async def _linked_application_ids(objective_id: str, session: AsyncSession) -> list[str]:
    result = await session.execute(
        sa.select(_objective_application_links.c.application_id)
        .where(_objective_application_links.c.objective_id == objective_id)
        .order_by(_objective_application_links.c.application_id)
    )
    return [row.application_id for row in result]


async def link_objective_design(objective_id: str, design_id: str, session: AsyncSession) -> None:
    """Caller (router) has already validated both ids exist."""
    try:
        await session.execute(
            _objective_design_links.insert().values(
                objective_id=objective_id, design_id=design_id, created_at=_now()
            )
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateLinkError(
                f"Link ({objective_id!r}, {design_id!r}) already exists"
            ) from exc
        raise


async def unlink_objective_design(
    objective_id: str, design_id: str, session: AsyncSession
) -> None:
    result = await session.execute(
        _objective_design_links.delete().where(
            _objective_design_links.c.objective_id == objective_id,
            _objective_design_links.c.design_id == design_id,
        )
    )
    if _rowcount(result) == 0:
        raise LinkNotFoundError(f"Link ({objective_id!r}, {design_id!r}) not found")


async def list_objectives_for_design(
    design_id: str, session: AsyncSession
) -> StrategicObjectiveListResponse:
    """Reverse lookup, called from src/adp/api/routers/designs.py."""
    result = await session.execute(
        sa.select(_objective_design_links.c.objective_id)
        .where(_objective_design_links.c.design_id == design_id)
        .order_by(_objective_design_links.c.objective_id)
    )
    items = []
    for row in result:
        objective_row = await session.execute(
            sa.select(_objectives).where(_objectives.c.id == row.objective_id)
        )
        obj = objective_row.mappings().first()
        if obj is not None:
            items.append(await _row_to_summary(obj, session))
    return StrategicObjectiveListResponse(items=items, total=len(items))


async def link_objective_application(
    objective_id: str, application_id: str, session: AsyncSession
) -> None:
    """Caller (router) has already validated both ids exist."""
    try:
        await session.execute(
            _objective_application_links.insert().values(
                objective_id=objective_id, application_id=application_id, created_at=_now()
            )
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateLinkError(
                f"Link ({objective_id!r}, {application_id!r}) already exists"
            ) from exc
        raise


async def unlink_objective_application(
    objective_id: str, application_id: str, session: AsyncSession
) -> None:
    result = await session.execute(
        _objective_application_links.delete().where(
            _objective_application_links.c.objective_id == objective_id,
            _objective_application_links.c.application_id == application_id,
        )
    )
    if _rowcount(result) == 0:
        raise LinkNotFoundError(f"Link ({objective_id!r}, {application_id!r}) not found")


async def list_objectives_for_application(
    application_id: str, session: AsyncSession
) -> StrategicObjectiveListResponse:
    """Reverse lookup, called from src/adp/application/router.py."""
    result = await session.execute(
        sa.select(_objective_application_links.c.objective_id)
        .where(_objective_application_links.c.application_id == application_id)
        .order_by(_objective_application_links.c.objective_id)
    )
    items = []
    for row in result:
        objective_row = await session.execute(
            sa.select(_objectives).where(_objectives.c.id == row.objective_id)
        )
        obj = objective_row.mappings().first()
        if obj is not None:
            items.append(await _row_to_summary(obj, session))
    return StrategicObjectiveListResponse(items=items, total=len(items))


# ── Overview dashboard summary (051-strategy-landing-card) ────────────────────

# Raw SQL, mirroring adp.api.routers.portfolio.get_portfolio_summary's own
# established pattern for this exact class of read (research.md Decision 3):
# Postgres-only syntax (NOW()/EXTRACT()/FILTER), so this is verified directly
# against a real Postgres instance rather than through the SQLite-backed unit
# tests (which mock session.execute() instead, matching
# tests/contract/test_portfolio_api.py's own precedent).
#
# One atomic pass: the inner subquery classifies each objective's linkage
# (EXISTS against either join table) and fiscal bucket (a CASE expression
# implementing the FY-aware past-due rule -- research.md Decision 4 / spec.md
# Edge Cases: an FY-period objective is past due only once its whole fiscal
# year has elapsed, never partway through it); the outer query aggregates
# both with COUNT(*) FILTER (WHERE ...) in one round trip.
_SUMMARY_STATS_SQL = sa.text(
    """
    SELECT
        (SELECT COUNT(*) FROM strategic_themes) AS total_themes,
        COUNT(*) AS total_objectives,
        COUNT(*) FILTER (WHERE linked) AS linked_count,
        COUNT(*) FILTER (WHERE NOT linked) AS unlinked_count,
        COUNT(*) FILTER (WHERE period_bucket = 'current') AS current_period_count,
        COUNT(*) FILTER (WHERE period_bucket = 'upcoming') AS upcoming_count,
        COUNT(*) FILTER (WHERE period_bucket = 'past_due') AS past_due_count
    FROM (
        SELECT
            o.id,
            (
                EXISTS (
                    SELECT 1 FROM strategic_objective_capabilities c
                    WHERE c.objective_id = o.id
                )
                OR EXISTS (
                    SELECT 1 FROM strategic_objective_value_streams v
                    WHERE v.objective_id = o.id
                )
            ) AS linked,
            CASE
                WHEN o.period = 'FY' THEN
                    CASE
                        WHEN o.fiscal_year < EXTRACT(YEAR FROM NOW())::int THEN 'past_due'
                        WHEN o.fiscal_year > EXTRACT(YEAR FROM NOW())::int THEN 'upcoming'
                        ELSE 'current'
                    END
                ELSE
                    CASE
                        WHEN (o.fiscal_year, CAST(SUBSTRING(o.period FROM 2) AS INT))
                             < (EXTRACT(YEAR FROM NOW())::int, EXTRACT(QUARTER FROM NOW())::int)
                            THEN 'past_due'
                        WHEN (o.fiscal_year, CAST(SUBSTRING(o.period FROM 2) AS INT))
                             > (EXTRACT(YEAR FROM NOW())::int, EXTRACT(QUARTER FROM NOW())::int)
                            THEN 'upcoming'
                        ELSE 'current'
                    END
            END AS period_bucket
        FROM strategic_objectives o
    ) sub
    """
)


async def get_summary_stats(session: AsyncSession) -> StrategicSummaryResponse:
    """Overview dashboard's Strategy card aggregate (051-strategy-landing-card).

    Computes mini-stats, the linkage-health split (FR-004/005), and the
    fiscal-period split (FR-007) in one query. "Now" is the database
    server's own clock, never Python's (FR-008).
    """
    result = await session.execute(_SUMMARY_STATS_SQL)
    row = result.mappings().first()
    assert row is not None  # a plain aggregate always returns exactly one row
    return StrategicSummaryResponse(
        total_objectives=row["total_objectives"],
        total_themes=row["total_themes"],
        linked_count=row["linked_count"],
        unlinked_count=row["unlinked_count"],
        current_period_count=row["current_period_count"],
        upcoming_count=row["upcoming_count"],
        past_due_count=row["past_due_count"],
    )
