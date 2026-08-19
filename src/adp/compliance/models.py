"""Pydantic v2 models for the Compliance domain (COMPLY-01, COMPLY-02).

ART-XIII: extra="forbid" on all models; all boundary payloads are typed.

Two registry entities (COMPLY-01): RegulatoryFramework (reference data for a tracked regulation/
standard) and Control (a self-referencing hierarchy of individual clauses/requirements within a
framework). Plus the traceability link (COMPLY-02): ControlMapping, linking a Control to the
Capability/Application/Design/Pattern it governs, or to a standing estate-wide obligation with no
single owning entity (Clarification Session 2026-08-18; research.md D1).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── RegulatoryFramework ────────────────────────────────────────────────────

# 926-framework-versioning-correction (COMPLY-01a): directly set by an architect, not derived --
# neither new child concept below (application phases, amendments) records a repeal event, so a
# full derivation from that data would always be wrong for one of the four values (research.md D3).
FrameworkStatus = Literal["in_force", "amended", "repealed", "not_yet_applicable"]


def _validate_source_url(v: str | None) -> str | None:
    """Reject any scheme other than http/https (security review finding, 923-derived-compliance-
    status): source_url is rendered directly as an <a href> in FrameworkDetail.tsx with no
    frontend sanitization, so a `javascript:` (or other dangerous-scheme) value would execute in
    the browser of any authenticated user who views the framework and clicks "Source" -- reads
    are open to everyone, while only WRITE_COMPLIANCE is needed to set the field. Blank/None is
    left as-is (the field is optional); a non-blank value must parse to http or https."""
    if v is None or not v.strip():
        return v
    scheme = urlparse(v.strip()).scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError("source_url must be an http:// or https:// URL")
    return v

class RegulatoryFramework(BaseModel):
    """Read model returned by the API.

    926-framework-versioning-correction (COMPLY-01a): regulation_number..status are additive --
    name/jurisdiction/authority/version/effective_date/source_url above are the original COMPLY-01
    fields, completely untouched (spec.md FR-004). All seven new fields are optional; a framework
    that has never set any of them (every framework tracked before this feature shipped) reads
    them back as None/the "in_force" default, not an error (spec.md FR-001/002)."""
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    jurisdiction: str
    authority: str
    version: str
    effective_date: date | None
    source_url: str | None
    regulation_number: str | None
    celex_number: str | None
    adoption_date: date | None
    oj_publication_date: date | None
    entry_into_force_date: date | None
    consolidated_as_of: date | None
    status: FrameworkStatus
    created_at: datetime
    updated_at: datetime


class RegulatoryFrameworkDetail(RegulatoryFramework):
    """Framework with its full control hierarchy, nested by parent_id, ordered by position, plus
    (COMPLY-01a) its application phases and amendments -- same "everything about this framework in
    one call" nesting precedent controls already established (research.md D4)."""
    controls: list["ControlNode"] = []
    application_phases: list["FrameworkApplicationPhase"] = []
    amendments: list["FrameworkAmendment"] = []


class RegulatoryFrameworkCreate(BaseModel):
    """Write model for creating a framework.

    name/jurisdiction/authority/version are max_length-capped to match the DB columns exactly
    (regulatory_frameworks: VARCHAR(255)/(255)/(255)/(100) -- migration 032). Without this, an
    over-length value reaches the INSERT and fails with a raw 500
    (asyncpg.StringDataRightTruncationError) instead of a clean 422 -- caught live: a
    paragraph-length jurisdiction/version description crashed create_framework() before this
    validation existed."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=255)
    jurisdiction: str = Field(max_length=255)
    authority: str = Field(max_length=255)
    version: str = Field(max_length=100)
    effective_date: date | None = None
    source_url: str | None = None
    # 926-framework-versioning-correction (COMPLY-01a): every field below is optional -- a
    # framework's regulation identity and legal-event dates are filled in over time, at an
    # architect's own pace, not required at creation (spec.md FR-001/002, Clarifications).
    regulation_number: str | None = Field(default=None, max_length=100)
    celex_number: str | None = Field(default=None, max_length=50)
    adoption_date: date | None = None
    oj_publication_date: date | None = None
    entry_into_force_date: date | None = None
    consolidated_as_of: date | None = None
    status: FrameworkStatus = "in_force"

    @field_validator("name", "jurisdiction", "authority", "version")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    @field_validator("source_url")
    @classmethod
    def source_url_must_be_http(cls, v: str | None) -> str | None:
        return _validate_source_url(v)


class RegulatoryFrameworkUpdate(BaseModel):
    """Write model for updating a framework. All fields optional. Same DB-column-matching
    max_length caps as RegulatoryFrameworkCreate -- see its docstring."""
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=255)
    jurisdiction: str | None = Field(default=None, max_length=255)
    authority: str | None = Field(default=None, max_length=255)
    version: str | None = Field(default=None, max_length=100)
    effective_date: date | None = None
    source_url: str | None = None
    regulation_number: str | None = Field(default=None, max_length=100)
    celex_number: str | None = Field(default=None, max_length=50)
    adoption_date: date | None = None
    oj_publication_date: date | None = None
    entry_into_force_date: date | None = None
    consolidated_as_of: date | None = None
    status: FrameworkStatus | None = None

    @field_validator("name", "jurisdiction", "authority", "version")
    @classmethod
    def must_not_be_blank_if_set(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("must not be blank")
        return v

    @field_validator("source_url")
    @classmethod
    def source_url_must_be_http(cls, v: str | None) -> str | None:
        return _validate_source_url(v)


class RegulatoryFrameworkListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RegulatoryFramework]
    total: int


# ── Control ───────────────────────────────────────────────────────────────

class Control(BaseModel):
    """Read model returned by the API."""
    model_config = ConfigDict(extra="forbid")

    id: str
    framework_id: str
    parent_id: str | None
    code: str
    title: str
    description: str | None
    position: int
    created_at: datetime
    updated_at: datetime


class ControlNode(Control):
    """Control with nested children for tree responses."""
    children: list["ControlNode"] = []


class ControlCreate(BaseModel):
    """Write model for creating a control under a framework. `framework_id` comes from the
    route path, not the body (mirrors ValueStreamStageCreate's shape in adp.business.models).

    code/title are max_length-capped to match the DB columns exactly (controls: VARCHAR(100)/
    (255) -- migration 032), same reasoning as RegulatoryFrameworkCreate's identical fix.
    description has no cap -- it's an unbounded Text() column."""
    model_config = ConfigDict(extra="forbid")

    parent_id: str | None = None
    code: str = Field(max_length=100)
    title: str = Field(max_length=255)
    description: str
    position: int = 0

    @field_validator("code", "title", "description")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class ControlUpdate(BaseModel):
    """Write model for updating a control. All fields optional. Changing `parent_id` or `code`
    re-runs the same cycle/cross-framework/uniqueness validation as create (research.md D5, D6).
    Same DB-column-matching max_length caps on code/title as ControlCreate -- see its docstring."""
    model_config = ConfigDict(extra="forbid")

    parent_id: str | None = None
    code: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    position: int | None = None

    @field_validator("code", "title", "description")
    @classmethod
    def must_not_be_blank_if_set(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("must not be blank")
        return v


# ── Typed exceptions (adp.compliance.store raises these; router translates to HTTP) ────────────

class DuplicateControlCodeError(Exception):
    """Raised when (framework_id, code) already exists. Router maps to HTTP 409."""

    def __init__(self, framework_id: str, code: str) -> None:
        self.framework_id = framework_id
        self.code = code
        super().__init__(f"Control code {code!r} already exists for framework {framework_id!r}")


class DuplicateRegulationNumberError(Exception):
    """926-framework-versioning-correction (COMPLY-01a): raised when regulation_number is already
    used by another framework. Router maps to HTTP 409. Never raised for two frameworks that both
    leave regulation_number unset -- NULLs don't collide under the UNIQUE constraint (research.md
    D2)."""

    def __init__(self, regulation_number: str) -> None:
        self.regulation_number = regulation_number
        super().__init__(f"Regulation number {regulation_number!r} already in use")


class CyclicParentError(Exception):
    """Raised when a proposed parent_id is the control itself or one of its own descendants.
    Router maps to HTTP 422."""

    def __init__(self, control_id: str, proposed_parent_id: str) -> None:
        self.control_id = control_id
        self.proposed_parent_id = proposed_parent_id
        super().__init__(
            f"Control {control_id!r} cannot be parented under {proposed_parent_id!r}: "
            "would create a cycle"
        )


class CrossFrameworkParentError(Exception):
    """Raised when a proposed parent_id belongs to a different framework_id. Router maps to
    HTTP 422."""

    def __init__(
        self, parent_id: str, expected_framework_id: str, actual_framework_id: str
    ) -> None:
        self.parent_id = parent_id
        self.expected_framework_id = expected_framework_id
        self.actual_framework_id = actual_framework_id
        super().__init__(
            f"Parent control {parent_id!r} belongs to framework {actual_framework_id!r}, "
            f"not {expected_framework_id!r}"
        )


class ParentNotFoundError(Exception):
    """Raised when a proposed parent_id does not reference an existing control. Router maps to
    HTTP 404."""

    def __init__(self, parent_id: str) -> None:
        self.parent_id = parent_id
        super().__init__(f"Parent control {parent_id!r} not found")


# ── Framework Application Phases & Amendments (COMPLY-01a) ─────────────────────
# Two independent one-to-many concepts hanging off RegulatoryFramework -- staged application
# dates (spec.md US2, e.g. the EU AI Act's phased rollout) and amending legal instruments
# (spec.md US3, e.g. DORA's growing RTS stack). Neither carries a URL field in this pass, so
# neither reopens the source_url scheme-validation surface above (plan.md Threat Model).

class FrameworkApplicationPhase(BaseModel):
    """Read model."""
    model_config = ConfigDict(extra="forbid")

    id: str
    framework_id: str
    phase_label: str
    applies_from_date: date
    description: str | None
    created_at: datetime


class FrameworkApplicationPhaseCreate(BaseModel):
    """framework_id comes from the route path, not the body (mirrors ControlCreate's shape)."""
    model_config = ConfigDict(extra="forbid")

    phase_label: str = Field(max_length=255)
    applies_from_date: date
    description: str | None = None

    @field_validator("phase_label")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class FrameworkApplicationPhaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FrameworkApplicationPhase]
    total: int


class FrameworkAmendment(BaseModel):
    """Read model."""
    model_config = ConfigDict(extra="forbid")

    id: str
    framework_id: str
    amending_celex: str | None
    amending_title: str
    effective_date: date | None
    created_at: datetime


class FrameworkAmendmentCreate(BaseModel):
    """framework_id comes from the route path, not the body."""
    model_config = ConfigDict(extra="forbid")

    amending_celex: str | None = Field(default=None, max_length=50)
    amending_title: str = Field(max_length=255)
    effective_date: date | None = None

    @field_validator("amending_title")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class FrameworkAmendmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FrameworkAmendment]
    total: int


class ApplicationPhaseNotFoundError(Exception):
    """Raised when (framework_id, phase_id) has no matching row. Router maps to HTTP 404."""

    def __init__(self, phase_id: str) -> None:
        self.phase_id = phase_id
        super().__init__(f"Application phase {phase_id!r} not found")


class AmendmentNotFoundError(Exception):
    """Raised when (framework_id, amendment_id) has no matching row. Router maps to HTTP 404."""

    def __init__(self, amendment_id: str) -> None:
        self.amendment_id = amendment_id
        super().__init__(f"Amendment {amendment_id!r} not found")


# ── ControlMapping (COMPLY-02) ──────────────────────────────────────────────

class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_ASSESSED = "not_assessed"
    NOT_APPLICABLE = "not_applicable"


class MappingTargetType(StrEnum):
    CAPABILITY = "capability"
    APPLICATION = "application"
    DESIGN = "design"
    PATTERN = "pattern"
    ORGANIZATION = "organization"


class ControlMapping(BaseModel):
    """Read model. target_id is None only when target_type == ORGANIZATION (research.md D1)."""
    model_config = ConfigDict(extra="forbid")

    control_id: str
    target_type: MappingTargetType
    target_id: str | None
    compliance_status: ComplianceStatus
    evidence_ref: str | None
    assessed_at: date | None
    assessed_by: str | None
    created_at: datetime


class ControlMappingWrite(BaseModel):
    """Write model for PUT (create-or-update -- research.md D3, an upsert that never 409s on
    re-mapping the same (control, target) pair, per spec.md FR-007/FR-008)."""
    model_config = ConfigDict(extra="forbid")

    compliance_status: ComplianceStatus = ComplianceStatus.NOT_ASSESSED
    evidence_ref: str | None = None
    assessed_at: date | None = None
    assessed_by: str | None = None


class ControlMappingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ControlMapping]
    total: int


# ── Typed exceptions (COMPLY-02) ────────────────────────────────────────────

class ControlNotFoundError(Exception):
    """control_id does not reference an existing Control. Router maps to HTTP 404."""

    def __init__(self, control_id: str) -> None:
        self.control_id = control_id
        super().__init__(f"Control {control_id!r} not found")


class MappingTargetNotFoundError(Exception):
    """target_id does not reference an existing Capability/Application/Design/knowledge item.
    Router maps to HTTP 404."""

    def __init__(self, target_type: str, target_id: str) -> None:
        self.target_type = target_type
        self.target_id = target_id
        super().__init__(f"{target_type} {target_id!r} not found")


class InvalidPatternTargetError(Exception):
    """target_id resolves to a knowledge_items row whose kind != 'pattern' (research.md D5).
    Router maps to HTTP 422."""

    def __init__(self, target_id: str, actual_kind: str) -> None:
        self.target_id = target_id
        self.actual_kind = actual_kind
        super().__init__(f"knowledge item {target_id!r} has kind {actual_kind!r}, not 'pattern'")


class MappingNotFoundError(Exception):
    """Raised by delete when the (control_id, target) pair has no existing mapping.
    Router maps to HTTP 404."""

    def __init__(self, control_id: str, target_type: str, target_id: str | None) -> None:
        self.control_id = control_id
        self.target_type = target_type
        self.target_id = target_id
        super().__init__(
            f"No mapping from control {control_id!r} to {target_type} {target_id!r}"
        )


# ── Compliance Rollup Reporting (COMPLY-04) ─────────────────────────────────
# Read-only, computed views over existing data (COMPLY-01/02/03) -- no new table. Explicit
# fields, not dict[ComplianceStatus, int], mirroring adp.strategy.models.ThemeStatusCounts's own
# documented ART-XIII reasoning (research.md D4).

class EntityStatusCounts(BaseModel):
    """A tally of how many distinct entities landed in each of the five ComplianceStatus
    buckets, for some scope (one framework, or the whole estate)."""
    model_config = ConfigDict(extra="forbid")

    compliant_count: int
    partial_count: int
    non_compliant_count: int
    not_assessed_count: int
    not_applicable_count: int


class FrameworkCoverageRollup(BaseModel):
    """One RegulatoryFramework's coverage picture (US1). organization_status is None when no
    control in this framework has an estate-wide obligation mapped to it at all -- distinct from
    a mapped-but-unassessed obligation, which would be NOT_ASSESSED, not None (data-model.md)."""
    model_config = ConfigDict(extra="forbid")

    framework_id: str
    entity_counts: EntityStatusCounts
    organization_status: ComplianceStatus | None


class ComplianceSummaryResponse(BaseModel):
    """Platform-wide compliance summary (US2), backing the Overview dashboard's Compliance
    domain card. coverage_percent is None when zero entities anywhere have any mapped control at
    all -- distinct from a genuine 0% (spec.md FR-009)."""
    model_config = ConfigDict(extra="forbid")

    framework_count: int
    coverage_percent: float | None
    at_risk_count: int


RegulatoryFrameworkDetail.model_rebuild()
ControlNode.model_rebuild()
