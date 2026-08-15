"""Pydantic v2 models for the Application Registry (ADP-SPEC-036)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

# ── Enum literals ─────────────────────────────────────────────────────────────

TimeClassification = Literal["Tolerate", "Invest", "Migrate", "Eliminate"]
RStrategy = Literal[
    "Rehost", "Replatform", "Repurchase", "Refactor", "Retire", "Retain", "Relocate"
]
PaceLayer = Literal["Record", "Differentiation", "Innovation"]
UsageType = Literal["provides", "consumes"]
IntegrationDir = Literal["inbound", "outbound", "bidirectional"]
AppIntegrationType = Literal["API", "event", "file", "database", "messaging", "other"]

# ADP-SPEC-038 (APM US1): 1–5 assessment scores and the TIME rationalization quadrant.
Score15 = Annotated[int, Field(ge=1, le=5)]
Quadrant = Literal["tolerate", "invest", "migrate", "eliminate"]

# ADP-SPEC-038 (APM US2): explicit application lifecycle state.
LifecycleStatus = Literal["planned", "active", "sunset", "retired"]

# ADP-SPEC-038 (APM US5): technical fit depth.
HostingModel = Literal["on_prem", "cloud", "saas", "hybrid"]

# docs/application-health-assessment-spec.md: the six health-rubric
# dimensions (docs/health-table.md's six rows), in the same order the rubric
# table lists them.
HealthDimension = Literal[
    "stability_incidents",
    "technical_currency_debt",
    "security_posture",
    "support_team_capacity",
    "documentation_knowledge",
    "business_value_criticality",
]
HEALTH_DIMENSIONS: tuple[HealthDimension, ...] = (
    "stability_incidents",
    "technical_currency_debt",
    "security_posture",
    "support_team_capacity",
    "documentation_knowledge",
    "business_value_criticality",
)

# ── Error classes ─────────────────────────────────────────────────────────────


class TechCapHasChildrenError(Exception):
    """Raised when deleting a technical capability that still has children."""


class TechCapDepthError(Exception):
    """Raised when creating a child of an L3 technical capability."""


class DuplicateAppCapLinkError(Exception):
    """Raised when the (app_id, capability_id) link already exists."""


class DuplicateAppTechCapLinkError(Exception):
    """Raised when the (app_id, tech_cap_id, usage_type) link already exists."""


class DuplicateAppStageLinkError(Exception):
    """Raised when the (app_id, stage_id) link already exists."""


class DuplicateAppDesignLinkError(Exception):
    """Raised when the (app_id, design_id) link already exists."""


# ── Application models ────────────────────────────────────────────────────────


class Application(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str | None
    vendor: str | None
    primary_owner: str | None
    time_classification: TimeClassification | None
    r_strategy: RStrategy | None
    pace_layer: PaceLayer | None
    health_score: Annotated[int, Field(ge=1, le=5)] | None
    business_value: Score15 | None = None
    business_criticality: Score15 | None = None
    owning_business_unit: str | None = None
    business_owner: str | None = None
    technical_owner: str | None = None
    lifecycle_status: LifecycleStatus = "active"
    hosting_model: HostingModel | None = None
    architecture_pattern: str | None = None
    tech_debt_flags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    vendor: str | None = None
    primary_owner: str | None = None
    time_classification: TimeClassification | None = None
    r_strategy: RStrategy | None = None
    pace_layer: PaceLayer | None = None
    # health_score is intentionally absent: it is only ever set via
    # PUT /applications/{id}/health-assessment (docs/application-health-
    # assessment-spec.md §6 Q5) -- it doesn't exist yet at creation anyway
    # (the assessment popup needs a real application_id, §4).
    business_value: Score15 | None = None
    business_criticality: Score15 | None = None
    owning_business_unit: str | None = None
    business_owner: str | None = None
    technical_owner: str | None = None
    lifecycle_status: LifecycleStatus = "active"
    hosting_model: HostingModel | None = None
    architecture_pattern: str | None = None
    tech_debt_flags: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v


class ApplicationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    vendor: str | None = None
    primary_owner: str | None = None
    time_classification: TimeClassification | None = None
    r_strategy: RStrategy | None = None
    pace_layer: PaceLayer | None = None
    # health_score is intentionally absent -- see ApplicationCreate's own
    # comment above. extra="forbid" rejects (422) any request that still
    # tries to PATCH it directly, which is the enforcement mechanism for
    # spec §6 Q5 ("reject direct writes").
    business_value: Score15 | None = None
    business_criticality: Score15 | None = None
    owning_business_unit: str | None = None
    business_owner: str | None = None
    technical_owner: str | None = None
    lifecycle_status: LifecycleStatus | None = None
    hosting_model: HostingModel | None = None
    architecture_pattern: str | None = None
    tech_debt_flags: list[str] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v


class ApplicationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[Application]
    total: int


# ── Health Assessment (docs/application-health-assessment-spec.md) ───────────


class HealthAssessmentEntry(BaseModel):
    """One dimension's current answer. Read-only; written only via
    HealthAssessmentSubmit below."""

    model_config = ConfigDict(extra="forbid")
    dimension: HealthDimension
    score: Annotated[int, Field(ge=1, le=5)]
    assessed_at: datetime
    assessed_by: str | None = None


class HealthAssessmentSubmit(BaseModel):
    """PUT body -- all six dimensions required (spec §2/§6 Q2: no partial
    assessment). One field per dimension rather than a dict, per ART-XIII
    (explicit typed fields over a loosely-typed mapping)."""

    model_config = ConfigDict(extra="forbid")
    stability_incidents: Annotated[int, Field(ge=1, le=5)]
    technical_currency_debt: Annotated[int, Field(ge=1, le=5)]
    security_posture: Annotated[int, Field(ge=1, le=5)]
    support_team_capacity: Annotated[int, Field(ge=1, le=5)]
    documentation_knowledge: Annotated[int, Field(ge=1, le=5)]
    business_value_criticality: Annotated[int, Field(ge=1, le=5)]

    def as_dimension_scores(self) -> dict[HealthDimension, int]:
        return {dim: getattr(self, dim) for dim in HEALTH_DIMENSIONS}


class HealthAssessmentResponse(BaseModel):
    """GET/PUT response. `entries` is empty when the application has never
    been assessed; `health_score` mirrors Application.health_score (None
    until the first assessment)."""

    model_config = ConfigDict(extra="forbid")
    application_id: str
    entries: list[HealthAssessmentEntry] = Field(default_factory=list)
    health_score: Annotated[int, Field(ge=1, le=5)] | None = None


# ── Rationalization (APM US1) ─────────────────────────────────────────────────


class RationalizationEntry(BaseModel):
    """One application placed (or not) on the business-value × technical-health plot."""
    model_config = ConfigDict(extra="forbid")
    app_id: str
    name: str
    business_value: int | None
    health_score: int | None
    # None when the app is unassessed (missing business_value and/or health_score).
    quadrant: Quadrant | None


class RationalizationResponse(BaseModel):
    """TIME rationalization projection: assessed apps placed, unassessed listed apart."""
    model_config = ConfigDict(extra="forbid")
    assessed: list[RationalizationEntry]
    unassessed: list[RationalizationEntry]
    total: int


# ── Risk & compliance (APM US3) ───────────────────────────────────────────────

DataClassification = Literal["public", "internal", "confidential", "restricted"]
SecurityPosture = Literal["strong", "adequate", "weak", "unknown"]
VulnerabilityStatus = Literal["none_known", "open_low", "open_high", "critical"]
DrBcStatus = Literal["tested", "documented", "none"]


class ApplicationRiskUpdate(BaseModel):
    """Upsert body for an application's risk & compliance record."""
    model_config = ConfigDict(extra="forbid")
    security_posture: SecurityPosture | None = None
    vulnerability_status: VulnerabilityStatus | None = None
    data_classification: DataClassification | None = None
    regulatory_tags: list[str] = Field(default_factory=list)
    dr_bc_status: DrBcStatus | None = None
    end_of_life_date: date | None = None
    end_of_support_date: date | None = None


class ApplicationRisk(ApplicationRiskUpdate):
    """Read model — the stored risk record (updated_at set once persisted)."""
    updated_at: datetime | None = None


class OutOfSupportEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    name: str
    end_of_support_date: date


class OutOfSupportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[OutOfSupportEntry]
    total: int


# ── Total Cost of Ownership (APM US4, ADP-9x6) ────────────────────────────────
# NUMERIC/Decimal only — money must never use binary floating point.

TCO_BUCKET_NAMES: tuple[str, ...] = (
    "acquisition", "implementation", "training", "operational",
    "maintenance", "upgrades", "risk_downtime", "end_of_life",
)
# run = ongoing cost of operating what exists; change = cost of acquiring/altering it.
_RUN_BUCKETS = ("operational", "maintenance", "risk_downtime")
_CHANGE_BUCKETS = ("acquisition", "implementation", "upgrades")


class CostBucket(BaseModel):
    """One TCO bucket: a one-time amount plus an ongoing annual amount."""
    model_config = ConfigDict(extra="forbid")
    one_time: Decimal = Decimal("0")
    annual: Decimal = Decimal("0")

    @field_validator("one_time", "annual")
    @classmethod
    def not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("cost amounts must not be negative")
        return v


class ApplicationCostUpdate(BaseModel):
    """Upsert body for an application's TCO record. Full replace, like risk."""
    model_config = ConfigDict(extra="forbid")
    currency: str = "USD"
    horizon_years: Annotated[int, Field(gt=0)] = 5
    acquisition: CostBucket = Field(default_factory=CostBucket)
    implementation: CostBucket = Field(default_factory=CostBucket)
    training: CostBucket = Field(default_factory=CostBucket)
    operational: CostBucket = Field(default_factory=CostBucket)
    maintenance: CostBucket = Field(default_factory=CostBucket)
    upgrades: CostBucket = Field(default_factory=CostBucket)
    risk_downtime: CostBucket = Field(default_factory=CostBucket)
    end_of_life: CostBucket = Field(default_factory=CostBucket)

    @field_validator("currency")
    @classmethod
    def currency_is_iso4217_shape(cls, v: str) -> str:
        if len(v) != 3 or not v.isalpha():
            raise ValueError("currency must be a 3-letter ISO-4217 code")
        return v.upper()

    def _bucket_totals(self) -> tuple[Decimal, Decimal]:
        one_time = sum((getattr(self, n).one_time for n in TCO_BUCKET_NAMES), Decimal("0"))
        annual = sum((getattr(self, n).annual for n in TCO_BUCKET_NAMES), Decimal("0"))
        return one_time, annual


class ApplicationCost(ApplicationCostUpdate):
    """Read model — TCO and run-vs-change are derived on read, never stored."""
    updated_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tco(self) -> Decimal:
        """TCO = Σ(one_time) + Σ(annual) × horizon_years."""
        one_time, annual = self._bucket_totals()
        return one_time + annual * self.horizon_years

    @computed_field  # type: ignore[prop-decorator]
    @property
    def run_total(self) -> Decimal:
        """Ongoing operate-what-exists cost over the horizon (one-time + annual×years)."""
        return self._group_total(_RUN_BUCKETS)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def change_total(self) -> Decimal:
        """Acquire/alter cost over the horizon (one-time + annual×years)."""
        return self._group_total(_CHANGE_BUCKETS)

    def _group_total(self, names: tuple[str, ...]) -> Decimal:
        one_time = sum((getattr(self, n).one_time for n in names), Decimal("0"))
        annual = sum((getattr(self, n).annual for n in names), Decimal("0"))
        return one_time + annual * self.horizon_years


class BusinessUnitCostRollup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_unit: str | None
    app_count: int
    tco: Decimal


class CostRollupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[BusinessUnitCostRollup]
    total_tco: Decimal


# ── Technical Capability models ───────────────────────────────────────────────

# ADP-33v: strategic relevance (1=Strategic, 2=Core, 3=Supporting) applies to
# both business_capabilities and technical_capabilities. Distinct from the
# hierarchy 'level' (1-3 depth) on this same table.
TechCapStrategicRelevance = Literal[1, 2, 3]

TECH_CAP_STRATEGIC_RELEVANCE_LABELS: dict[int, str] = {1: "Strategic", 2: "Core", 3: "Supporting"}


class TechnicalCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str | None
    parent_id: str | None
    level: int
    created_at: datetime
    strategic_relevance: TechCapStrategicRelevance | None = None


class TechnicalCapabilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    parent_id: str | None = None
    strategic_relevance: TechCapStrategicRelevance | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v


class TechnicalCapabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    strategic_relevance: TechCapStrategicRelevance | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v


class TechCapListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[TechnicalCapability]
    total: int


# ── Application–Business Capability Link models ───────────────────────────────


class ApplicationCapabilityLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    capability_id: str
    capability_name: str
    fit_score: Annotated[int, Field(ge=1, le=5)]


class ApplicationCapabilityLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability_id: str
    fit_score: Annotated[int, Field(ge=1, le=5)]


class ApplicationCapabilityLinkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fit_score: Annotated[int, Field(ge=1, le=5)]


class ApplicationCapabilityLinksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationCapabilityLink]


# ── Application–Technical Capability Link models ──────────────────────────────


class ApplicationTechCapLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    tech_cap_id: str
    tech_cap_name: str
    usage_type: UsageType


class ApplicationTechCapLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tech_cap_id: str
    usage_type: UsageType


class ApplicationTechCapLinksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationTechCapLink]


# ── Application–Value Stream Stage Link models ────────────────────────────────


class ApplicationStageLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    stage_id: str
    stage_name: str


class ApplicationStageLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage_id: str


class ApplicationStageLinksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationStageLink]


# ── Application–Domain Integration models ─────────────────────────────────────


class ApplicationDomainIntegration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    app_id: str
    domain_id: str | None
    domain_name: str | None
    integration_type: str
    direction: IntegrationDir
    created_at: datetime


class ApplicationDomainIntegrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain_id: str | None = None
    integration_type: str
    direction: IntegrationDir

    @field_validator("integration_type")
    @classmethod
    def type_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("integration_type must not be blank")
        return v


class ApplicationDomainIntegrationsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationDomainIntegration]


# ── Application Integration models ────────────────────────────────────────────


class ApplicationIntegration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source_app_id: str
    source_app_name: str
    target_app_id: str
    target_app_name: str
    integration_type: AppIntegrationType
    description: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationIntegrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_app_id: str
    target_app_id: str
    integration_type: AppIntegrationType
    description: str | None = None

    @model_validator(mode="after")
    def source_ne_target(self) -> "ApplicationIntegrationCreate":
        if self.source_app_id == self.target_app_id:
            raise ValueError("source_app_id and target_app_id must differ")
        return self


class ApplicationIntegrationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None = None


class ApplicationIntegrationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationIntegration]
    total: int


# ── Application–Design Link models ────────────────────────────────────────────


class ApplicationDesignLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    design_id: str


class ApplicationDesignLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    design_id: str


class ApplicationDesignLinksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationDesignLink]


# ── Lifecycle & Roadmap: Transformation Initiatives (APM US6) ─────────────────

Disposition = Literal["retire", "replace", "modernize", "invest"]


class DuplicateAppInitiativeLinkError(Exception):
    """Raised when the (app_id, initiative_id) link already exists."""


class TransformationInitiative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str | None
    target_date: date | None
    created_at: datetime
    updated_at: datetime


class TransformationInitiativeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    target_date: date | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v


class TransformationInitiativeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    target_date: date | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v


class TransformationInitiativeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[TransformationInitiative]
    total: int


class InitiativeMember(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    app_name: str
    planned_disposition: Disposition


class TransformationInitiativeDetail(TransformationInitiative):
    """An initiative with its member applications and their planned dispositions."""
    members: list[InitiativeMember] = Field(default_factory=list)


class ApplicationInitiativeLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    initiative_id: str
    initiative_name: str
    planned_disposition: Disposition


class ApplicationInitiativeLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    initiative_id: str
    planned_disposition: Disposition


class ApplicationInitiativeLinkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    planned_disposition: Disposition


class ApplicationInitiativeLinksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationInitiativeLink]
    total: int


class RoadmapEntry(BaseModel):
    """An application on the decommission/roadmap track: Eliminate-classified or
    sunset/retired, with its EOL date (if recorded, ADP-SPEC-038 US3) and any
    initiative links."""
    model_config = ConfigDict(extra="forbid")
    app_id: str
    name: str
    time_classification: TimeClassification | None
    lifecycle_status: LifecycleStatus
    end_of_life_date: date | None
    initiative_links: list[ApplicationInitiativeLink]


class RoadmapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[RoadmapEntry]
    total: int


# ── Ownership & Governance (APM US7) ──────────────────────────────────────────


class ApplicationGovernanceUpdate(BaseModel):
    """Upsert body for an application's ownership & governance record."""
    model_config = ConfigDict(extra="forbid")
    contract_terms: str | None = None
    renewal_date: date | None = None
    sla: str | None = None
    business_sponsor: str | None = None
    it_owner: str | None = None
    decision_rights: str | None = None


class ApplicationGovernance(ApplicationGovernanceUpdate):
    """Read model — the stored governance record (updated_at set once persisted)."""
    updated_at: datetime | None = None


class RenewalSoonEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    name: str
    renewal_date: date


class RenewalsSoonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[RenewalSoonEntry]
    total: int


# ── Quality & Performance Signals (APM US8) ───────────────────────────────────
# Manual/advisory in v1 — these never override health_score.


class ApplicationQualityMetricUpdate(BaseModel):
    """Upsert body for an application's quality & performance signals."""
    model_config = ConfigDict(extra="forbid")
    uptime_pct: Annotated[Decimal, Field(ge=0, le=100)] | None = None
    incidents_ytd: Annotated[int, Field(ge=0)] | None = None
    satisfaction_score: Score15 | None = None
    perf_note: str | None = None
    ticket_volume_30d: Annotated[int, Field(ge=0)] | None = None


class ApplicationQualityMetric(ApplicationQualityMetricUpdate):
    """Read model — the stored quality record (updated_at set once persisted)."""
    updated_at: datetime | None = None
