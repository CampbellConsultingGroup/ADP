"""Unit tests for TCO computation (APM US4, ADP-9x6, ADP-SPEC-038).

TCO = Σ(one_time) + Σ(annual) × horizon_years, computed on read — never stored.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from adp.application.models import ApplicationCost, CostBucket


def test_tco_matches_worked_example():
    """A $5,000/yr SaaS license -> ~$35,000 5-year TCO once other costs are added."""
    cost = ApplicationCost(
        currency="USD",
        horizon_years=5,
        acquisition=CostBucket(one_time=Decimal("2000")),
        operational=CostBucket(annual=Decimal("5000")),
        maintenance=CostBucket(annual=Decimal("1000")),
        training=CostBucket(one_time=Decimal("3000")),
    )
    # one-time: 2000 + 3000 = 5000; annual: 5000 + 1000 = 6000 * 5 = 30000; total 35000
    assert cost.tco == Decimal("35000")


def test_tco_all_zero_by_default():
    cost = ApplicationCost()
    assert cost.tco == Decimal("0")
    assert cost.run_total == Decimal("0")
    assert cost.change_total == Decimal("0")


def test_tco_horizon_rederives_without_reentry():
    """Changing horizon_years alone changes TCO — no bucket re-entry needed."""
    base = ApplicationCost(operational=CostBucket(annual=Decimal("1000")), horizon_years=3)
    longer = base.model_copy(update={"horizon_years": 10})
    assert base.tco == Decimal("3000")
    assert longer.tco == Decimal("10000")


def test_run_vs_change_split():
    cost = ApplicationCost(
        acquisition=CostBucket(one_time=Decimal("1000")),      # change
        implementation=CostBucket(one_time=Decimal("500")),    # change
        upgrades=CostBucket(annual=Decimal("100")),            # change
        operational=CostBucket(annual=Decimal("200")),         # run
        maintenance=CostBucket(annual=Decimal("300")),         # run
        risk_downtime=CostBucket(one_time=Decimal("50")),      # run
        horizon_years=2,
    )
    # change: 1000 + 500 (one-time) + 100*2 (annual) = 1700
    assert cost.change_total == Decimal("1700")
    # run: 50 (one-time) + (200+300)*2 (annual) = 1050
    assert cost.run_total == Decimal("1050")
    # run + change != tco in general (training/end_of_life excluded from both groups)
    assert cost.run_total + cost.change_total == cost.tco


def test_negative_amount_rejected():
    with pytest.raises(ValidationError):
        CostBucket(one_time=Decimal("-1"))
    with pytest.raises(ValidationError):
        CostBucket(annual=Decimal("-1"))


def test_horizon_must_be_positive():
    with pytest.raises(ValidationError):
        ApplicationCost(horizon_years=0)


def test_currency_must_be_iso4217_shaped():
    with pytest.raises(ValidationError):
        ApplicationCost(currency="US")
    assert ApplicationCost(currency="usd").currency == "USD"


def test_tco_serializes_computed_fields():
    """tco/run_total/change_total appear in the serialized output (computed_field)."""
    cost = ApplicationCost(operational=CostBucket(annual=Decimal("100")), horizon_years=2)
    dumped = cost.model_dump()
    assert dumped["tco"] == Decimal("200")
    assert "run_total" in dumped
    assert "change_total" in dumped
