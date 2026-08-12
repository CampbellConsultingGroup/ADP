"""Pydantic v2 models for the strategic-objective-capture domain (ADP-d8u.1).

ART-XIII: extra="forbid" on all models; all boundary payloads are typed.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# data-model.md: direction is semantic (increase/decrease/reach a value), not
# an ordered scale like strategic_relevance/maturity_level -- a Literal string
# set, not a SmallInteger.
ObjectiveDirection = Literal["increase", "decrease", "reach"]
ObjectivePeriod = Literal["Q1", "Q2", "Q3", "Q4", "FY"]


# ── StrategicTheme ──────────────────────────────────────────────────────────


class StrategicTheme(BaseModel):
    """Read model. Minimal by design (FR-011's Assumption) -- create + list
    only in v1, no description/classification field unlike BusinessDomain."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    created_at: datetime


class StrategicThemeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v


class StrategicThemeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[StrategicTheme]
    total: int


# ── StrategicObjective ───────────────────────────────────────────────────────


def _metric_group_all_or_nothing(
    metric_name: str | None,
    target_value: Decimal | None,
    target_unit: str | None,
    direction: str | None,
) -> None:
    """data-model.md: metric_name/target_value/target_unit/direction are
    all-or-nothing as a group -- a data-quality rule not expressible as a
    single column constraint (FR-003: 'never collapsed into a single
    free-text string when provided', and never partially provided either)."""
    fields = (metric_name, target_value, target_unit, direction)
    present = [f is not None for f in fields]
    if any(present) and not all(present):
        raise ValueError(
            "metric_name, target_value, target_unit, and direction must be "
            "provided together or not at all"
        )


class StrategicObjective(BaseModel):
    """Read model (full detail, including linked ids)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    theme_id: str
    owner: str
    statement: str
    metric_name: str | None = None
    target_value: Decimal | None = None
    target_unit: str | None = None
    direction: ObjectiveDirection | None = None
    fiscal_year: int
    period: ObjectivePeriod
    capability_ids: list[str] = []
    value_stream_ids: list[str] = []
    created_at: datetime
    updated_at: datetime


class StrategicObjectiveSummary(BaseModel):
    """List-response item (FR-008: 'enough summary information,' not full detail)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    theme_id: str
    owner: str
    statement: str
    fiscal_year: int
    period: ObjectivePeriod
    updated_at: datetime


class StrategicObjectiveCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme_id: str
    owner: str
    statement: str
    metric_name: str | None = None
    target_value: Decimal | None = None
    target_unit: str | None = None
    direction: ObjectiveDirection | None = None
    fiscal_year: int
    period: ObjectivePeriod

    @field_validator("owner", "statement")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    @model_validator(mode="after")
    def metric_group_all_or_nothing(self) -> "StrategicObjectiveCreate":
        _metric_group_all_or_nothing(
            self.metric_name, self.target_value, self.target_unit, self.direction
        )
        return self


class StrategicObjectiveUpdate(BaseModel):
    """All fields optional (FR-009: edit any field of a saved objective)."""

    model_config = ConfigDict(extra="forbid")

    theme_id: str | None = None
    owner: str | None = None
    statement: str | None = None
    metric_name: str | None = None
    target_value: Decimal | None = None
    target_unit: str | None = None
    direction: ObjectiveDirection | None = None
    fiscal_year: int | None = None
    period: ObjectivePeriod | None = None

    @field_validator("owner", "statement")
    @classmethod
    def must_not_be_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("must not be blank")
        return v

    @model_validator(mode="after")
    def metric_group_all_or_nothing(self) -> "StrategicObjectiveUpdate":
        # An Update only validates the group when at least one of the four
        # fields is being touched in this request -- a partial edit that
        # doesn't mention any of them (e.g. just changing `owner`) must not
        # be rejected because the *other, unchanged* fields aren't provided
        # here (they're not being replaced, just left alone).
        fields = (self.metric_name, self.target_value, self.target_unit, self.direction)
        if any(f is not None for f in fields):
            _metric_group_all_or_nothing(*fields)
        return self


class StrategicObjectiveListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[StrategicObjectiveSummary]
    total: int


# ── Links ─────────────────────────────────────────────────────────────────────


class ObjectiveCapabilityLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability_id: str


class ObjectiveValueStreamLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value_stream_id: str
