"""Effective scoring-rubric-weight lookup for ADP's composite scores (ADP-68z).

Mirrors adp.admin.prompt_registry's shape exactly (see that module's own docstring for the full
rationale): check for a saved admin override first; fall back to the rubric's own built-in
constant otherwise. This is the READ path only, self-contained (its own tiny session factory, no
caller-supplied session) so every existing computation call site can adopt it with a small change.
The admin WRITE path (edit/confirm/restore) lives in `adp.admin.rubric_service`, which owns its
own request-scoped session and Core Table objects for the same two tables -- this module only
ever reads `rubric_weight_overrides`.

Unlike a prompt (a bare string with no validity rule beyond non-empty), a rubric's weight set has
a genuine per-rubric validity rule (data-model.md §2) -- exactly the right dimension keys, each in
[0, 1], summing to 1.0 within a small tolerance for `business_value` -- so each registration also
carries its own `validate()` callback, checked by `adp.admin.rubric_service` before ever writing a
proposed weight set (never by this read-only module).

get_effective_weights() falls back to the registration's fallback_provider() on ANY error
resolving the override (unreachable DB, timeout, missing table), not just "no row found" --
identical resilience property to prompt_registry.get_effective_prompt(), for the identical reason:
compute_business_value_score()'s two call sites have no try/except of their own, so a transient DB
blip must not break every business-value assessment platform-wide just because one admin-editable
lookup failed.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_logger = logging.getLogger("adp.admin.rubric_registry")

_metadata = sa.MetaData()

# Minimal projection of rubric_weight_overrides (migration 040) -- only the columns this read
# path needs. adp.admin.rubric_service defines the full table (including updated_by/updated_at)
# for the write path. sa.JSON() (not postgresql.JSONB()) for SQLite-backed test portability --
# mirrors adp.application.store's own tech_debt_flags precedent for this exact class of split
# (migration uses JSONB for real Postgres, the Python Core Table def uses portable JSON).
_overrides = sa.Table(
    "rubric_weight_overrides",
    _metadata,
    sa.Column("rubric_id", sa.Text(), primary_key=True),
    sa.Column("weights", sa.JSON(), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
)


@dataclass(frozen=True)
class EffectiveWeights:
    """What a rubric should actually use right now."""

    weights: dict[str, float]
    is_override: bool
    version: int


@dataclass(frozen=True)
class RubricRegistration:
    """One rubric's weight-tuning slot (data-model.md §2)."""

    rubric_id: str
    display_name: str
    dimension_labels: dict[str, str]
    fallback_provider: Callable[[], dict[str, float]]
    validate: Callable[[dict[str, float]], None]


_WEIGHT_SUM_TOLERANCE = 1e-6


def _validate_business_value_weights(weights: dict[str, float]) -> None:
    from adp.application.models import BUSINESS_VALUE_DIMENSIONS

    expected_keys = set(BUSINESS_VALUE_DIMENSIONS)
    actual_keys = set(weights.keys())
    if actual_keys != expected_keys:
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        raise ValueError(
            f"weights must have exactly these dimensions: {sorted(expected_keys)} "
            f"(missing={sorted(missing)}, extra={sorted(extra)})"
        )
    for dim, weight in weights.items():
        if not isinstance(weight, (int, float)) or isinstance(weight, bool):
            raise ValueError(f"weight for {dim!r} must be a number, got {weight!r}")
        if not (0.0 <= weight <= 1.0):
            raise ValueError(f"weight for {dim!r} must be between 0 and 1, got {weight!r}")
    total = sum(weights.values())
    if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError(f"weights must sum to 1.0 (100%), got {total!r}")


def _business_value_fallback() -> dict[str, float]:
    from adp.application.models import BUSINESS_VALUE_WEIGHTS

    # BUSINESS_VALUE_WEIGHTS is keyed by the narrower BusinessValueDimension
    # Literal; this registry's own types are rubric-agnostic (dict[str, float])
    # since a future rubric's dimension keys are unknown today.
    return {str(dim): weight for dim, weight in BUSINESS_VALUE_WEIGHTS.items()}


_BUSINESS_VALUE_DIMENSION_LABELS: dict[str, str] = {
    "strategic_alignment": "Strategic Alignment",
    "revenue_cost_impact": "Revenue/Cost Impact",
    "customer_stakeholder_impact": "Customer/Stakeholder Impact",
    "competitive_differentiation": "Competitive Differentiation",
    "risk_compliance_contribution": "Risk/Compliance Contribution",
    "evidence_measurability": "Evidence & Measurability",
}

# Only one rubric registered today -- extensible without a schema change (spec.md SC-004).
RUBRIC_REGISTRATIONS: tuple[RubricRegistration, ...] = (
    RubricRegistration(
        rubric_id="business_value",
        display_name="Business Value Assessment",
        dimension_labels=_BUSINESS_VALUE_DIMENSION_LABELS,
        fallback_provider=_business_value_fallback,
        validate=_validate_business_value_weights,
    ),
)

_REGISTRATIONS_BY_ID: dict[str, RubricRegistration] = {
    r.rubric_id: r for r in RUBRIC_REGISTRATIONS
}


def get_registration(rubric_id: str) -> RubricRegistration | None:
    return _REGISTRATIONS_BY_ID.get(rubric_id)


# ── Self-contained session factory (mirrors adp.admin.prompt_registry's own) ─────────────────

_engine: Any = None
_session_factory: Any = None
_engine_loop: Any = None


def _get_session_factory() -> async_sessionmaker:
    import asyncio

    global _engine, _session_factory, _engine_loop
    current_loop = asyncio.get_running_loop()
    if _session_factory is None or _engine_loop is not current_loop:
        db_url = os.environ.get(
            "ADP_DATABASE_URL", "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
        )
        _engine = create_async_engine(db_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
        _engine_loop = current_loop
    return _session_factory


async def _fetch_override(rubric_id: str, session: AsyncSession) -> sa.Row[Any] | None:
    result = await session.execute(
        sa.select(_overrides.c.weights, _overrides.c.version).where(
            _overrides.c.rubric_id == rubric_id
        )
    )
    return result.first()


async def get_effective_weights(rubric_id: str) -> EffectiveWeights:
    """Return what `rubric_id` should actually use right now.

    Raises KeyError for an unregistered rubric_id -- callers are the fixed registered set plus
    the admin list/history endpoints, never arbitrary user input. Any OTHER failure resolving the
    override (DB unreachable, timeout, etc.) is caught and treated as "no override" -- see the
    module docstring for why this fallback is load-bearing, not just defensive.
    """
    registration = _REGISTRATIONS_BY_ID[rubric_id]
    try:
        factory = _get_session_factory()
        async with factory() as session:
            row = await _fetch_override(rubric_id, session)
    except Exception:
        _logger.warning(
            "rubric_registry: could not resolve override for %r, using fallback", rubric_id,
            exc_info=True,
        )
        row = None
    if row is not None:
        return EffectiveWeights(weights=dict(row.weights), is_override=True, version=row.version)
    return EffectiveWeights(
        weights=registration.fallback_provider(), is_override=False, version=0
    )
