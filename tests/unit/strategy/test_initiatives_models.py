"""Unit tests: adp.strategy.initiatives model validation (ADP-d8u.6)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adp.strategy.initiatives import StrategyInitiativeCreate


def test_initiative_rejects_blank_name():
    with pytest.raises(ValidationError):
        StrategyInitiativeCreate(name="   ")


def test_initiative_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        StrategyInitiativeCreate(name="A", unexpected_field="x")


def test_initiative_status_defaults_to_planned():
    initiative = StrategyInitiativeCreate(name="A")
    assert initiative.status == "planned"


@pytest.mark.parametrize(
    "status", ["planned", "in_progress", "blocked", "complete", "cancelled"]
)
def test_initiative_accepts_each_valid_status(status):
    initiative = StrategyInitiativeCreate(name="A", status=status)
    assert initiative.status == status


def test_initiative_rejects_invalid_status():
    with pytest.raises(ValidationError):
        StrategyInitiativeCreate(name="A", status="not_a_real_status")


def test_initiative_description_and_owner_are_optional():
    initiative = StrategyInitiativeCreate(name="A")
    assert initiative.description is None
    assert initiative.owner is None
