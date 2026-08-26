"""Service layer for the Admin Scoring Rubric Management API (ADP-68z).

Owns the WRITE path (confirm/restore) and its own Core Table objects for
`rubric_weight_overrides`/`rubric_weight_history` (migration 040). The READ path used by
`compute_business_value_score()`'s call sites lives in `adp.admin.rubric_registry`, which defines
its own minimal projection of `rubric_weight_overrides` and is deliberately NOT imported from here
for writes -- this module always uses a request-scoped session (via the router's dependency),
never rubric_registry's self-contained one. Mirrors adp.admin.service exactly.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.admin import rubric_registry
from adp.admin.rubric_models import RubricChangeResult, RubricHistoryEntry, RubricView

_metadata = sa.MetaData()

_overrides = sa.Table(
    "rubric_weight_overrides",
    _metadata,
    sa.Column("rubric_id", sa.Text(), primary_key=True),
    sa.Column("weights", sa.JSON(), nullable=False),
    sa.Column("updated_by", sa.Text(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
)

_history = sa.Table(
    "rubric_weight_history",
    _metadata,
    # SQLite only treats a column as the auto-incrementing rowid alias when its declared type
    # affinity is exactly INTEGER, not BIGINT -- mirrors adp.admin.service's own
    # agent_prompt_history table def for the identical class of issue.
    sa.Column(
        "id",
        sa.Integer().with_variant(sa.BigInteger(), "postgresql"),
        primary_key=True,
        autoincrement=True,
    ),
    sa.Column("rubric_id", sa.Text(), nullable=False),
    sa.Column("actor", sa.Text(), nullable=False),
    sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("change_type", sa.Text(), nullable=False),
    sa.Column("prior_weights", sa.JSON(), nullable=False),
    sa.Column("new_weights", sa.JSON(), nullable=False),
    sa.Column("confirmation_id", sa.Text(), nullable=False),
)


# ── Module-level session factory (set by deps or tests) ───────────────────────

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


class RubricVersionConflict(Exception):
    """Raised when expected_version doesn't match the current row (mirrors PromptVersionConflict).

    Carries the current state so the caller (router) can surface it to the client rather than
    silently overwriting -- the admin must reload and retry, not lose the other admin's change.
    """

    def __init__(self, current_weights: dict[str, float], current_version: int) -> None:
        self.current_weights = current_weights
        self.current_version = current_version
        super().__init__(
            f"Version conflict: expected version does not match current version {current_version}"
        )


class UnknownRubricError(Exception):
    """Raised for a rubric_id not in rubric_registry.RUBRIC_REGISTRATIONS."""


class InvalidWeightsError(Exception):
    """Raised when a proposed weight set fails the rubric's own registered validator."""


class HistoryEntryNotFoundError(Exception):
    """Raised when history_id doesn't exist or doesn't belong to rubric_id."""


# ── US1: list every rubric's current effective weights (read-only) ──────────

async def _get_override_row(rubric_id: str, session: AsyncSession) -> sa.Row[Any] | None:
    result = await session.execute(
        sa.select(_overrides.c.weights, _overrides.c.version).where(
            _overrides.c.rubric_id == rubric_id
        )
    )
    return result.first()


async def _current_state(rubric_id: str, session: AsyncSession) -> tuple[dict[str, float], int]:
    """Return (current_weights, current_version) whether or not an override row exists yet
    (version=0, fallback weights, if not)."""
    row = await _get_override_row(rubric_id, session)
    if row is not None:
        return dict(row.weights), row.version
    registration = rubric_registry.get_registration(rubric_id)
    if registration is None:
        raise UnknownRubricError(rubric_id)
    return registration.fallback_provider(), 0


async def list_rubrics() -> list[RubricView]:
    """One RubricView per registration, via rubric_registry's shared effective-weights lookup --
    the same function compute_business_value_score()'s call sites use, so what this screen shows
    is guaranteed to match what's actually being computed (FR-001-style guarantee, mirroring
    admin.service.list_agents())."""
    views: list[RubricView] = []
    for registration in rubric_registry.RUBRIC_REGISTRATIONS:
        effective = await rubric_registry.get_effective_weights(registration.rubric_id)
        views.append(
            RubricView(
                rubric_id=registration.rubric_id,
                display_name=registration.display_name,
                dimension_labels=registration.dimension_labels,
                active_weights=effective.weights,
                is_override=effective.is_override,
                version=effective.version,
            )
        )
    return views


# ── User Story 1: edit + confirm (write path) ────────────────────────────────

async def save_weights(
    rubric_id: str,
    new_weights: dict[str, float],
    expected_version: int,
    actor: str,
    confirmation_id: str,
    session: AsyncSession,
) -> RubricChangeResult:
    """Confirm a manual edit (FR-005). Validates via the rubric's OWN registered validate()
    before writing anything. Caller (the router) is responsible for committing the session --
    both the override upsert and the history insert happen in the same not-yet-committed
    transaction, so they succeed or fail together (data-model.md invariant)."""
    registration = rubric_registry.get_registration(rubric_id)
    if registration is None:
        raise UnknownRubricError(rubric_id)
    try:
        registration.validate(new_weights)
    except ValueError as exc:
        raise InvalidWeightsError(str(exc)) from exc

    current_weights, current_version = await _current_state(rubric_id, session)
    if expected_version != current_version:
        raise RubricVersionConflict(current_weights, current_version)

    new_version = current_version + 1
    now = _now()
    if current_version == 0:
        await session.execute(
            _overrides.insert().values(
                rubric_id=rubric_id, weights=new_weights, updated_by=actor,
                updated_at=now, version=new_version,
            )
        )
    else:
        await session.execute(
            _overrides.update()
            .where(_overrides.c.rubric_id == rubric_id)
            .values(weights=new_weights, updated_by=actor, updated_at=now, version=new_version)
        )
    await session.execute(
        _history.insert().values(
            rubric_id=rubric_id, actor=actor, changed_at=now, change_type="edit",
            prior_weights=current_weights, new_weights=new_weights,
            confirmation_id=confirmation_id,
        )
    )
    return RubricChangeResult(rubric_id=rubric_id, active_weights=new_weights, version=new_version)


# ── User Story 2: history + restore ──────────────────────────────────────────

async def get_history(rubric_id: str, session: AsyncSession) -> list[RubricHistoryEntry]:
    result = await session.execute(
        sa.select(
            _history.c.id, _history.c.rubric_id, _history.c.actor, _history.c.changed_at,
            _history.c.change_type, _history.c.prior_weights, _history.c.new_weights,
        )
        .where(_history.c.rubric_id == rubric_id)
        .order_by(_history.c.changed_at.desc(), _history.c.id.desc())
    )
    return [
        RubricHistoryEntry(
            id=row.id, rubric_id=row.rubric_id, actor=row.actor, changed_at=row.changed_at,
            change_type=row.change_type, prior_weights=dict(row.prior_weights),
            new_weights=dict(row.new_weights),
        )
        for row in result.all()
    ]


async def restore_weights(
    rubric_id: str,
    history_id: int,
    expected_version: int,
    actor: str,
    confirmation_id: str,
    session: AsyncSession,
) -> RubricChangeResult:
    """Restore a prior version as the new active weight set (FR-006), subject to the SAME
    confirmation/version-check gate as save_weights (mirrors ADP-SPEC-042's own restore-is-not-
    lower-friction decision). The restored weights are copied from the chosen history row's
    new_weights; this transition is itself recorded as a NEW history entry
    (change_type="restore"), never a rewrite of the past."""
    registration = rubric_registry.get_registration(rubric_id)
    if registration is None:
        raise UnknownRubricError(rubric_id)

    result = await session.execute(
        sa.select(_history.c.new_weights).where(
            (_history.c.id == history_id) & (_history.c.rubric_id == rubric_id)
        )
    )
    row = result.first()
    if row is None:
        raise HistoryEntryNotFoundError(f"history_id {history_id!r} not found for {rubric_id!r}")
    restored_weights = dict(row.new_weights)

    current_weights, current_version = await _current_state(rubric_id, session)
    if expected_version != current_version:
        raise RubricVersionConflict(current_weights, current_version)

    new_version = current_version + 1
    now = _now()
    if current_version == 0:
        await session.execute(
            _overrides.insert().values(
                rubric_id=rubric_id, weights=restored_weights, updated_by=actor,
                updated_at=now, version=new_version,
            )
        )
    else:
        await session.execute(
            _overrides.update()
            .where(_overrides.c.rubric_id == rubric_id)
            .values(
                weights=restored_weights, updated_by=actor, updated_at=now, version=new_version
            )
        )
    await session.execute(
        _history.insert().values(
            rubric_id=rubric_id, actor=actor, changed_at=now, change_type="restore",
            prior_weights=current_weights, new_weights=restored_weights,
            confirmation_id=confirmation_id,
        )
    )
    return RubricChangeResult(
        rubric_id=rubric_id, active_weights=restored_weights, version=new_version
    )
