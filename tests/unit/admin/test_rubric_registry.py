"""Unit tests: adp.admin.rubric_registry effective-weights lookup + per-rubric validator (ADP-68z).

Mirrors tests/unit/admin/test_prompt_registry.py's exact fixture convention: points the module's
own (normally lazy, ADP_DATABASE_URL-backed) session factory at a throwaway SQLite DB for the
duration of each test.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.admin import rubric_registry
from adp.admin.rubric_registry import RUBRIC_REGISTRATIONS, get_effective_weights


@pytest.fixture()
async def sqlite_factory(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/rubrics.db")
    async with engine.begin() as conn:
        await conn.run_sync(rubric_registry._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(rubric_registry, "_session_factory", factory)
    # Pin _engine_loop to THIS test's running loop -- see test_prompt_registry.py's own
    # identical comment for why this is needed.
    monkeypatch.setattr(rubric_registry, "_engine_loop", asyncio.get_running_loop())
    yield factory
    await engine.dispose()


def test_one_registration_business_value() -> None:
    """Only business_value is registered today (data-model.md §2) -- the
    registry mechanism itself must not assume this is the only rubric that
    will ever exist (spec.md SC-004), but this is what's actually there now."""
    ids = [r.rubric_id for r in RUBRIC_REGISTRATIONS]
    assert ids == ["business_value"]


async def test_falls_back_when_no_override_exists(sqlite_factory) -> None:
    registration = rubric_registry.get_registration("business_value")
    assert registration is not None

    result = await get_effective_weights("business_value")

    assert result.is_override is False
    assert result.version == 0
    assert result.weights == registration.fallback_provider()


async def test_falls_back_gracefully_when_db_unreachable(monkeypatch) -> None:
    """Mirrors test_prompt_registry.py's identical test -- any DB error (not
    just 'no row found') must fall back exactly as if no override existed,
    since compute_business_value_score()'s two call sites have no try/except
    of their own."""
    engine = create_async_engine("postgresql+asyncpg://nobody:nobody@127.0.0.1:1/nope")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(rubric_registry, "_session_factory", factory)
    monkeypatch.setattr(rubric_registry, "_engine_loop", asyncio.get_running_loop())

    registration = rubric_registry.get_registration("business_value")
    assert registration is not None

    result = await get_effective_weights("business_value")

    assert result.is_override is False
    assert result.version == 0
    assert result.weights == registration.fallback_provider()
    await engine.dispose()


async def test_override_row_takes_precedence(sqlite_factory) -> None:
    custom = {
        "strategic_alignment": 0.40, "revenue_cost_impact": 0.20,
        "customer_stakeholder_impact": 0.10, "competitive_differentiation": 0.10,
        "risk_compliance_contribution": 0.10, "evidence_measurability": 0.10,
    }
    async with sqlite_factory() as session:
        await session.execute(
            rubric_registry._overrides.insert().values(
                rubric_id="business_value", weights=custom, version=3
            )
        )
        await session.commit()

    result = await get_effective_weights("business_value")

    assert result.is_override is True
    assert result.version == 3
    assert result.weights == custom


class TestBusinessValueValidator:
    """The business_value rubric's own registered validate() (data-model.md §2)."""

    def _valid(self) -> dict[str, float]:
        return {
            "strategic_alignment": 0.25, "revenue_cost_impact": 0.25,
            "customer_stakeholder_impact": 0.15, "competitive_differentiation": 0.10,
            "risk_compliance_contribution": 0.15, "evidence_measurability": 0.10,
        }

    def test_accepts_valid_weight_set(self) -> None:
        registration = rubric_registry.get_registration("business_value")
        assert registration is not None
        registration.validate(self._valid())  # must not raise

    def test_rejects_missing_dimension(self) -> None:
        registration = rubric_registry.get_registration("business_value")
        assert registration is not None
        weights = self._valid()
        del weights["evidence_measurability"]
        with pytest.raises(ValueError, match="dimensions"):
            registration.validate(weights)

    def test_rejects_extra_dimension(self) -> None:
        registration = rubric_registry.get_registration("business_value")
        assert registration is not None
        weights = self._valid()
        weights["not_a_real_dimension"] = 0.0
        with pytest.raises(ValueError, match="dimensions"):
            registration.validate(weights)

    def test_rejects_out_of_range_weight(self) -> None:
        registration = rubric_registry.get_registration("business_value")
        assert registration is not None
        weights = self._valid()
        weights["strategic_alignment"] = 1.5
        with pytest.raises(ValueError, match="between 0 and 1"):
            registration.validate(weights)

    def test_rejects_sum_not_equal_to_one(self) -> None:
        registration = rubric_registry.get_registration("business_value")
        assert registration is not None
        weights = self._valid()
        weights["strategic_alignment"] = 0.30  # now sums to 1.05
        with pytest.raises(ValueError, match="sum to 1.0"):
            registration.validate(weights)

    def test_tolerates_float_representation_error(self) -> None:
        """0.1 + 0.2 + ... in floating point rarely sums to EXACTLY 1.0 --
        the epsilon tolerance (research.md, spec.md Edge Cases) must accept
        this, not reject it as a spurious sum mismatch."""
        registration = rubric_registry.get_registration("business_value")
        assert registration is not None
        weights = {
            "strategic_alignment": 0.1, "revenue_cost_impact": 0.1,
            "customer_stakeholder_impact": 0.1, "competitive_differentiation": 0.1,
            "risk_compliance_contribution": 0.1, "evidence_measurability": 0.5,
        }
        assert abs(sum(weights.values()) - 1.0) < 1e-9  # sanity: genuinely ~1.0
        registration.validate(weights)  # must not raise
