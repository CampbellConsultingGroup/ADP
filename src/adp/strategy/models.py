"""Pydantic v2 models for the strategic-objective-capture domain (ADP-d8u.1).

ART-XIII: extra="forbid" on all models; all boundary payloads are typed.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# data-model.md: direction is semantic (increase/decrease/reach a value), not
# an ordered scale like strategic_relevance/maturity_level -- a Literal string
# set, not a SmallInteger.
ObjectiveDirection = Literal["increase", "decrease", "reach"]
ObjectivePeriod = Literal["Q1", "Q2", "Q3", "Q4", "FY"]

# ADP-d8u.5, research.md Decision 1/2: proposed/active/at_risk/achieved are
# NEVER persisted -- always computed on read from progress history + target
# (ART-II). abandoned is the one value a human can actually set (the
# strategic_objectives.status column itself only ever holds NULL or
# 'abandoned' -- see migration 026).
ObjectiveStatus = Literal["proposed", "active", "at_risk", "achieved", "abandoned"]


# ── StrategicTheme ──────────────────────────────────────────────────────────


class StrategicTheme(BaseModel):
    """Read model. ADP-d8u.5 extends the original v1 minimal shape (FR-011's
    Assumption: create + list only) with description/owner/priority (FR-012)
    -- name stays the only required field, matching data-model.md."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str | None = None
    owner: str | None = None
    priority: int | None = None
    created_at: datetime
    framework_ids: list[str] = []  # 927-theme-framework-mapping -- mirrors control_ids exactly


class StrategicThemeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    owner: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v


class StrategicThemeUpdate(BaseModel):
    """name is NOT editable in this version (FR-013 asks only for
    description/owner/priority) -- avoids re-litigating the existing
    DuplicateThemeNameError uniqueness path for a field nobody asked to
    change (data-model.md)."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    owner: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)


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
    design_ids: list[str] = []
    application_ids: list[str] = []
    control_ids: list[str] = []
    status: ObjectiveStatus
    status_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class StrategicObjectiveSummary(BaseModel):
    """List-response item (FR-008: 'enough summary information,' not full detail).

    status included per spec.md SC-001: "visible at a glance wherever the
    objective appears" -- a list view is exactly such a place."""

    model_config = ConfigDict(extra="forbid")

    id: str
    theme_id: str
    owner: str
    statement: str
    fiscal_year: int
    period: ObjectivePeriod
    status: ObjectiveStatus
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


# ── Objective Progress (ADP-d8u.5) ───────────────────────────────────────────


class ObjectiveProgressEntry(BaseModel):
    """Read model. One dated, editable actual value against an objective's
    target (data-model.md) -- the date is immutable once recorded (FR-002a);
    only actual_value/note can be corrected in place."""

    model_config = ConfigDict(extra="forbid")

    objective_id: str
    as_of_date: date
    actual_value: Decimal
    note: str | None = None
    recorded_by: str
    created_at: datetime


class ObjectiveProgressCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: date
    actual_value: Decimal
    note: str | None = Field(default=None, max_length=500)


class ObjectiveProgressUpdate(BaseModel):
    """No as_of_date field at all -- FR-002a: the date is fixed once recorded,
    only the value/note can be corrected."""

    model_config = ConfigDict(extra="forbid")

    actual_value: Decimal
    note: str | None = Field(default=None, max_length=500)


class ObjectiveProgressListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ObjectiveProgressEntry]
    total: int


class AbandonRequest(BaseModel):
    """No `status` field at all -- the action IS "abandon"; nothing else is
    acceptable via this endpoint (FR-011)."""

    model_config = ConfigDict(extra="forbid")

    status_reason: str = Field(min_length=1, max_length=500)


# ── Links ─────────────────────────────────────────────────────────────────────


class ObjectiveCapabilityLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability_id: str


class ObjectiveValueStreamLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value_stream_id: str


class ObjectiveDesignLinkCreate(BaseModel):
    """ADP-d8u.2: objective -> design traceability link."""

    model_config = ConfigDict(extra="forbid")
    design_id: str


class ObjectiveApplicationLinkCreate(BaseModel):
    """ADP-d8u.2: objective -> application traceability link."""

    model_config = ConfigDict(extra="forbid")
    application_id: str


class ObjectiveControlLinkCreate(BaseModel):
    """925-strategy-compliance-linkage (COMPLY-05): objective -> Control traceability link -- "why
    does this objective exist." A bare link, no compliance_status of its own (that lives on
    ControlMapping, COMPLY-02)."""

    model_config = ConfigDict(extra="forbid")
    control_id: str


class ThemeFrameworkLinkCreate(BaseModel):
    """927-theme-framework-mapping (COMPLY-05, link #3): theme -> RegulatoryFramework coarse
    grouping tag. A bare link, no fields of its own beyond the reference -- unlike ControlMapping,
    this carries no status/evidence payload at all."""

    model_config = ConfigDict(extra="forbid")
    framework_id: str


# ── Overview dashboard summary (051-strategy-landing-card) ────────────────────


class StrategicSummaryResponse(BaseModel):
    """Aggregate counts for the Overview dashboard's Strategy domain card.

    All seven fields come from one atomic query (adp.strategy.store.
    get_summary_stats, research.md Decision 3) -- linked_count +
    unlinked_count == total_objectives and current_period_count +
    upcoming_count + past_due_count == total_objectives always hold
    (data-model.md's invariants).
    """

    model_config = ConfigDict(extra="forbid")
    total_objectives: int
    total_themes: int
    linked_count: int
    unlinked_count: int
    current_period_count: int
    upcoming_count: int
    past_due_count: int
    # 918-strategy-rollups: proposed_count + active_count + at_risk_count +
    # achieved_count + abandoned_count == total_objectives always holds,
    # joining the two existing invariants above.
    proposed_count: int
    active_count: int
    at_risk_count: int
    achieved_count: int
    abandoned_count: int
    initiative_count: int


class ThemeStatusCounts(BaseModel):
    """One row of the strategy heat map (918-strategy-rollups) -- a theme and
    its objective count broken down by each of the 5 ObjectiveStatus values.
    Explicit fields, not a dict[str, int], per ART-XIII (research.md Decision
    3)."""

    model_config = ConfigDict(extra="forbid")
    theme_id: str
    theme_name: str
    proposed_count: int
    active_count: int
    at_risk_count: int
    achieved_count: int
    abandoned_count: int


class StrategyHeatMapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    themes: list[ThemeStatusCounts]
    total_objectives: int
