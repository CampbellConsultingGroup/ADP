"""Pydantic v2 models for the Business Architecture domain (ADP-SPEC-033/034/035).

ART-XIII: extra="forbid" on all models; all boundary payloads are typed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from adp.agents.models import (
    AgentReviewOperationStatus,
    AgentSuggestionStatus,
    GroundingCitation,
)

# ── Strategic relevance (ADP-33v) ─────────────────────────────────────────────
# Applies to BOTH business_capabilities and technical_capabilities. Distinct
# from the hierarchy 'level' (1-3 = L1/L2/L3 depth) and from maturity_level
# (1-5, business capabilities only, ADP-4ga) -- three separate numeric axes.

StrategicRelevance = Literal[1, 2, 3]

STRATEGIC_RELEVANCE_LABELS: dict[int, str] = {1: "Strategic", 2: "Core", 3: "Supporting"}


# ── Maturity level (ADP-4ga) ──────────────────────────────────────────────────
# Business capabilities only (the CMMI-style ladder is business-process
# oriented). Distinct from 'level' (hierarchy depth) and from
# strategic_relevance -- three separate numeric axes.

MaturityLevel = Literal[1, 2, 3, 4, 5]

MATURITY_LEVEL_LABELS: dict[int, str] = {
    1: "Ad hoc",
    2: "Emerging",
    3: "Established",
    4: "Advanced",
    5: "World Class",
}

MATURITY_LEVEL_DESCRIPTIONS: dict[int, str] = {
    1: (
        "Capability exists informally, person-dependent, undocumented, "
        "inconsistent; outcomes unpredictable."
    ),
    2: (
        "Basic processes exist, somewhat consistent within a team/unit, "
        "still largely reactive, not standardized org-wide."
    ),
    3: (
        "Documented, standardized, consistently applied across the org; "
        "roles/processes/tools formally defined, not tribal knowledge."
    ),
    4: (
        "Quantitatively managed; performance tracked with metrics/KPIs, "
        "decisions data-driven, variability understood and controlled."
    ),
    5: (
        "Continuous improvement via feedback loops, innovation, proactive "
        "adaptation, often ahead of business need."
    ),
}


# ── BusinessCapability ────────────────────────────────────────────────────────

class BusinessCapability(BaseModel):
    """Read model returned by the API."""
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str | None
    level: Literal[1, 2, 3]
    parent_id: str | None
    position: int
    created_at: datetime
    updated_at: datetime
    # ADP-SPEC-035: domain assignment (null when unassigned or level > 1)
    domain_id: str | None = None
    domain_name: str | None = None
    # ADP-33v: strategic classification (null = unclassified)
    strategic_relevance: StrategicRelevance | None = None
    # ADP-4ga: CMMI-style maturity assessment (null = not yet assessed)
    maturity_level: MaturityLevel | None = None


class BusinessCapabilityCreate(BaseModel):
    """Write model for creating a capability. Validates level/parent_id consistency."""
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    level: Literal[1, 2, 3]
    parent_id: str | None = None
    position: int = 0
    strategic_relevance: StrategicRelevance | None = None
    maturity_level: MaturityLevel | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v

    @model_validator(mode="after")
    def parent_id_consistency(self) -> "BusinessCapabilityCreate":
        # model_validator (not field_validator): must run even when parent_id
        # is omitted, since field validators skip unset defaults.
        if self.level == 1 and self.parent_id is not None:
            raise ValueError("parent_id must be null for level-1 capabilities")
        if self.level in (2, 3) and self.parent_id is None:
            raise ValueError("parent_id is required for level-2 and level-3 capabilities")
        return self


class BusinessCapabilityUpdate(BaseModel):
    """Write model for updating a capability. All fields optional."""
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    position: int | None = None
    strategic_relevance: StrategicRelevance | None = None
    maturity_level: MaturityLevel | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v


class BusinessCapabilityListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[BusinessCapability]
    total: int


# ── ValueStream ───────────────────────────────────────────────────────────────

class ValueStreamStage(BaseModel):
    """Read model for a single value stream stage."""
    model_config = ConfigDict(extra="forbid")

    id: str
    value_stream_id: str
    name: str
    description: str | None
    position: int


class ValueStream(BaseModel):
    """Read model for a value stream summary (no stages)."""
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str | None
    stakeholder: str | None
    position: int
    created_at: datetime
    updated_at: datetime


class ValueStreamDetail(ValueStream):
    """Value stream with its ordered stages."""
    stages: list[ValueStreamStage] = []


class ValueStreamListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ValueStream]
    total: int


class ValueStreamCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    stakeholder: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v


class ValueStreamUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    stakeholder: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v


class ValueStreamStageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    position: int = 0

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v


class ValueStreamStageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    position: int | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v


class StageReorderItem(BaseModel):
    """Single stage item in a bulk-reorder request."""
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str | None = None


class ValueStreamStagesReorder(BaseModel):
    """Bulk-replace stages list (reorder). Positions assigned 0..n-1 from array order."""
    model_config = ConfigDict(extra="forbid")

    stages: list[StageReorderItem]


# ── Traceability link models (ADP-SPEC-034) ───────────────────────────────────

class DesignRef(BaseModel):
    """Lightweight design reference returned by link list endpoints."""
    model_config = ConfigDict(extra="forbid")

    design_id: str
    title: str
    lifecycle_status: str


class CapabilityRef(BaseModel):
    """Lightweight capability reference for reverse-lookup responses."""
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    name: str
    level: int


class ValueStreamRef(BaseModel):
    """Lightweight value stream reference for reverse-lookup responses."""
    model_config = ConfigDict(extra="forbid")

    value_stream_id: str
    name: str
    stakeholder: str | None


class DesignLinkCreate(BaseModel):
    """Request body for linking a design to a capability or value stream."""
    model_config = ConfigDict(extra="forbid")

    design_id: str

    @field_validator("design_id")
    @classmethod
    def design_id_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("design_id must not be blank")
        return v.strip()


class LinkedDesignsResponse(BaseModel):
    """Response for listing designs linked to a capability or value stream."""
    model_config = ConfigDict(extra="forbid")

    items: list[DesignRef]


class BusinessContextResponse(BaseModel):
    """Reverse lookup: capabilities and value streams linked to a design."""
    model_config = ConfigDict(extra="forbid")

    design_id: str
    capabilities: list[CapabilityRef]
    value_streams: list[ValueStreamRef]


# ── Traceability error classes ─────────────────────────────────────────────────

class DuplicateLinkError(Exception):
    """Raised when a (capability_id, design_id) or (value_stream_id, design_id)
    link already exists."""


class LinkNotFoundError(Exception):
    """Raised when a link to delete does not exist."""


# ── Business Domain models (ADP-SPEC-035) ─────────────────────────────────────

DomainClassification = Literal["strategic", "differentiating", "commodity"]


class BusinessDomain(BaseModel):
    """Read model for a business domain."""
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    scope_statement: str | None
    classification: DomainClassification
    org_unit: str | None
    risk_flags: list[str]
    created_at: datetime
    updated_at: datetime


class DomainSummary(BaseModel):
    """List-response item: domain fields without scope_statement, plus capability count."""
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    classification: DomainClassification
    org_unit: str | None
    risk_flags: list[str]
    capability_count: int
    created_at: datetime
    updated_at: datetime


class DomainDetail(BusinessDomain):
    """Domain with its assigned L1 capabilities."""
    capabilities: list[CapabilityRef] = []


class DomainListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[DomainSummary]
    total: int


class BusinessDomainCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    scope_statement: str | None = None
    classification: DomainClassification
    org_unit: str | None = None
    risk_flags: list[str] = []

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v

    @field_validator("risk_flags")
    @classmethod
    def flags_not_blank(cls, v: list[str]) -> list[str]:
        for flag in v:
            if not flag.strip():
                raise ValueError("risk_flags entries must not be blank")
        return list(dict.fromkeys(v))


class BusinessDomainUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    scope_statement: str | None = None
    classification: DomainClassification | None = None
    org_unit: str | None = None
    risk_flags: list[str] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v

    @field_validator("risk_flags")
    @classmethod
    def flags_not_blank(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for flag in v:
                if not flag.strip():
                    raise ValueError("risk_flags entries must not be blank")
            return list(dict.fromkeys(v))
        return v


class CapabilityDomainAssign(BaseModel):
    """PATCH body to assign or clear a capability's domain."""
    model_config = ConfigDict(extra="forbid")

    domain_id: str | None


# ── Stage-capability models (ADP-SPEC-035) ────────────────────────────────────

class StageCapabilityRef(BaseModel):
    """A capability linked to a value stream stage, with domain context."""
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    name: str
    level: int
    domain_id: str | None
    domain_name: str | None


class StageCapabilityLinkCreate(BaseModel):
    """Request body for linking a capability to a stage."""
    model_config = ConfigDict(extra="forbid")

    capability_id: str

    @field_validator("capability_id")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("capability_id must not be blank")
        return v.strip()


class StageCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[StageCapabilityRef]


# ── Stage-capability error classes ────────────────────────────────────────────

class DuplicateStageCapError(Exception):
    """Raised when (stage_id, capability_id) link already exists."""


class StageCapNotFoundError(Exception):
    """Raised when a stage-capability link to delete does not exist."""


# ── Agent Review: Business Capabilities adapter (ADP-SPEC-039) ───────────────
# Five suggestion types, fixed for this adapter's v1 scope (spec Clarifications).
# Each suggestion carries the shared toolkit fields (rationale, citations,
# advisory, status) plus its own type-specific payload; unused fields for a
# given type stay None. previous_* fields are generation-time snapshots used
# by FR-015's field-scoped accept-time staleness check (research.md D8) --
# assign_domain has none, since FR-012 scopes it to domain_id IS NULL
# capabilities, so its implicit snapshot is always None.

AgentSuggestionType = Literal[
    "reclassify_strategic_relevance",
    "set_maturity_level",
    "assign_domain",
    "flag_duplicate",
    "propose_new_capability",
]


class CapabilitySuggestion(BaseModel):
    """One suggestion from a capability review (FR-010)."""

    model_config = ConfigDict(extra="forbid")

    suggestion_id: str
    type: AgentSuggestionType
    capability_id: str | None = None  # null only for propose_new_capability
    rationale: str
    citations: list[GroundingCitation] = []
    advisory: bool = False
    status: AgentSuggestionStatus = AgentSuggestionStatus.PENDING

    # reclassify_strategic_relevance
    strategic_relevance: StrategicRelevance | None = None
    previous_strategic_relevance: StrategicRelevance | None = None

    # set_maturity_level
    maturity_level: MaturityLevel | None = None
    previous_maturity_level: MaturityLevel | None = None

    # assign_domain
    domain_id: str | None = None

    # flag_duplicate
    duplicate_of_capability_id: str | None = None

    # propose_new_capability
    proposed_name: str | None = None
    proposed_description: str | None = None
    proposed_level: Literal[1, 2, 3] | None = None
    proposed_parent_id: str | None = None


class CapabilityAgentReviewResponse(BaseModel):
    """Poll response, mirrors IntakeStatusResponse's shape (FR-007)."""

    model_config = ConfigDict(extra="forbid")

    operation_id: str
    capability_id: str
    status: AgentReviewOperationStatus
    suggestions: list[CapabilitySuggestion] = []
    # Set only when status=FAILED (FR-021); short, sanitized -- never raw
    # prompt/response content.
    error_description: str | None = None


class SuggestionAcceptRequest(BaseModel):
    """Accept body. Mirrors AcceptOptionRequest (recommend.py): confirmation_id
    is required and non-empty (ART-VIII -- CONFIRM_AGENT_SUGGESTION is in
    REQUIRES_CONFIRMATION). advisory_acknowledged must be True to accept a
    suggestion where advisory=True."""

    model_config = ConfigDict(extra="forbid")

    confirmation_id: str
    advisory_acknowledged: bool = False

    @field_validator("confirmation_id")
    @classmethod
    def _require_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "confirmation_id must be non-empty — accepting a suggestion is a "
                "consequential action per ART-VIII"
            )
        return v


# Reject takes no request body (FR-017: no write occurs, nothing to confirm --
# unlike a hypothetical rejection_reason field, there is no ADP-SPEC-019-style
# feedback loop here, per this spec's Clarifications).
    """Raised when a stage-capability link to delete does not exist."""
