"""Response models for capability-model analysis (938-capability-model-analysis, ADP-6et.2).

Everything here is derived on read and never stored (spec FR-022). Cost and risk are ``None`` when
the caller lacks READ_APPLICATION_COST / READ_APPLICATION_RISK; the response's ``*_available``
flags say which, so "not available to you" is distinguishable from "no data" (``worst: None``).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from adp.application.app_capability_models import (
    AppRef,
    CapRef,
    GeoRef,
    LinkedCapRef,
    Rationale,
)
from adp.application.models import LifecycleStatus, RStrategy, TechCapLifecycle, TimeClassification

RiskBand = Literal["high", "medium", "low", "unknown"]
LifecycleBand = Literal["past_end_of_life", "retiring", "contained", "current", "emerging"]

# Worst first.
RISK_ORDER: tuple[RiskBand, ...] = ("high", "medium", "low")
LIFECYCLE_ORDER: tuple[LifecycleBand, ...] = (
    "past_end_of_life",
    "retiring",
    "contained",
    "current",
    "emerging",
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RealizationMapping(_Model):
    """One realization behind an overlap: the application capability, and why / where (943)."""

    via: CapRef
    rationale: Rationale | None = None
    geography: GeoRef | None = None
    hint: str | None = None


class AppVia(_Model):
    """A contributing application and the application capabilities it acts through. On an
    overlap, ``mappings`` adds each realization's rationale and geography (943)."""

    id: str
    name: str
    via: list[CapRef]
    mappings: list[RealizationMapping] = []


class HealthRollup(_Model):
    worst: int | None
    spread: dict[str, int]


class RiskRollup(_Model):
    worst: RiskBand | None
    spread: dict[str, int]


class CostRollup(_Model):
    """TCO of the distinct applications involved -- not allocated across capabilities."""

    total_tco: Decimal | None
    apps_without_cost: int


class ExposureRollup(_Model):
    worst: LifecycleBand | None
    spread: dict[str, int]


class CapabilityRollup(_Model):
    capability_id: str
    name: str
    level: int
    contributing_apps: list[AppVia]
    excluded_retired_apps: list[AppRef]
    health: HealthRollup
    risk: RiskRollup | None
    cost: CostRollup | None
    exposure: ExposureRollup


class CapabilityRollupResponse(_Model):
    as_of: date
    risk_available: bool
    cost_available: bool
    items: list[CapabilityRollup]


class ImpactAppCapability(LinkedCapRef):
    via_technical: list[CapRef]


class ImpactApplication(_Model):
    id: str
    name: str
    lifecycle_status: LifecycleStatus
    via: list[CapRef]


class ImpactBusiness(LinkedCapRef):
    routes: list[CapRef]


class ImpactResult(_Model):
    technical_capability: LinkedCapRef
    covered_technical: list[CapRef]
    application_capabilities: list[ImpactAppCapability]
    applications: list[ImpactApplication]
    business_capabilities: list[ImpactBusiness]


class TechnologyDependency(_Model):
    technical: LinkedCapRef
    lifecycle_status: TechCapLifecycle
    end_of_life_date: date | None
    effective_band: LifecycleBand
    via_app_capability: CapRef
    via_business_capability: CapRef


class TechnologyDependenciesResponse(_Model):
    as_of: date
    items: list[TechnologyDependency]


OverlapReasonCode = Literal["unclassified", "redundant", "no_target", "competing_targets"]
OverlapStatus = Literal["needs_attention", "explained"]


class OverlapReason(_Model):
    """Why an overlap needs attention (943 FR-007/FR-008). ``application_ids`` are the
    applications concerned, by name (empty for ``no_target``)."""

    code: OverlapReasonCode
    application_ids: list[str]


class OverlapEntry(_Model):
    business: LinkedCapRef
    applications: list[AppVia]
    status: OverlapStatus = "needs_attention"
    reasons: list[OverlapReason] = []


class RedundantApp(_Model):
    id: str
    name: str
    time_classification: TimeClassification | None = None
    r_strategy: RStrategy | None = None


class RedundantEntry(_Model):
    """A realization marked redundant, with the application's context for rationalization."""

    application: RedundantApp
    app_capability: LinkedCapRef
    geography: GeoRef | None = None
    hint: str | None = None


class RedundantGroup(_Model):
    """Redundant mappings under one business L3; ``business`` is None for mappings that reach
    no business capability (943 FR-012)."""

    business: LinkedCapRef | None
    entries: list[RedundantEntry]


class SharedEntry(_Model):
    app_capability: LinkedCapRef
    business: list[CapRef]
    count: int


class CapabilityGaps(_Model):
    business_without_app_capability: list[LinkedCapRef]
    app_capability_without_business: list[LinkedCapRef]
    app_capability_without_application: list[LinkedCapRef]


class CapabilityFindings(_Model):
    overlaps: list[OverlapEntry]
    gaps: CapabilityGaps
    shared: list[SharedEntry]
    shared_threshold: int
    redundant: list[RedundantGroup] = []
