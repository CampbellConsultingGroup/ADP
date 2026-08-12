"""Unit tests: adp.strategy.models validation (ADP-d8u.1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adp.strategy.models import StrategicObjectiveCreate, StrategicThemeCreate


def _base_kwargs(**overrides):
    kwargs = {
        "theme_id": "theme-1",
        "owner": "Claims Platform Team",
        "statement": "Reduce claims cycle time to improve retention",
        "fiscal_year": 2026,
        "period": "Q3",
    }
    kwargs.update(overrides)
    return kwargs


def test_objective_rejects_blank_owner():
    with pytest.raises(ValidationError):
        StrategicObjectiveCreate(**_base_kwargs(owner="   "))


def test_objective_rejects_blank_statement():
    with pytest.raises(ValidationError):
        StrategicObjectiveCreate(**_base_kwargs(statement=""))


def test_objective_rejects_partially_filled_metric_group():
    # metric_name set but target_unit missing -- data-model.md's all-or-nothing rule
    with pytest.raises(ValidationError):
        StrategicObjectiveCreate(**_base_kwargs(metric_name="Claims cycle time", target_value=40))


def test_objective_accepts_fully_populated_metric_group():
    obj = StrategicObjectiveCreate(
        **_base_kwargs(
            metric_name="Claims cycle time",
            target_value=40,
            target_unit="%",
            direction="decrease",
        )
    )
    assert obj.metric_name == "Claims cycle time"
    assert obj.direction == "decrease"


def test_objective_accepts_no_metric_group_at_all():
    obj = StrategicObjectiveCreate(**_base_kwargs())
    assert obj.metric_name is None
    assert obj.target_value is None
    assert obj.target_unit is None
    assert obj.direction is None


def test_objective_rejects_invalid_direction():
    with pytest.raises(ValidationError):
        StrategicObjectiveCreate(
            **_base_kwargs(
                metric_name="x", target_value=1, target_unit="%", direction="sideways"
            )
        )


def test_objective_rejects_invalid_period():
    with pytest.raises(ValidationError):
        StrategicObjectiveCreate(**_base_kwargs(period="Q5"))


def test_theme_rejects_blank_name():
    with pytest.raises(ValidationError):
        StrategicThemeCreate(name="  ")


def test_theme_accepts_valid_name():
    theme = StrategicThemeCreate(name="Usage-based pricing")
    assert theme.name == "Usage-based pricing"
