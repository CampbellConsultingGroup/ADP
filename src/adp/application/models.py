"""Pydantic v2 models for the Application Registry (ADP-SPEC-036)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ── Enum literals ─────────────────────────────────────────────────────────────

TimeClassification = Literal["Tolerate", "Invest", "Migrate", "Eliminate"]
RStrategy = Literal[
    "Rehost", "Replatform", "Repurchase", "Refactor", "Retire", "Retain", "Relocate"
]
PaceLayer = Literal["Record", "Differentiation", "Innovation"]
UsageType = Literal["provides", "consumes"]
IntegrationDir = Literal["inbound", "outbound", "bidirectional"]
AppIntegrationType = Literal["API", "event", "file", "database", "messaging", "other"]

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
    health_score: Annotated[int, Field(ge=1, le=5)] | None = None

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
    health_score: Annotated[int, Field(ge=1, le=5)] | None = None

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


# ── Technical Capability models ───────────────────────────────────────────────


class TechnicalCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str | None
    parent_id: str | None
    level: int
    created_at: datetime


class TechnicalCapabilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    parent_id: str | None = None

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
