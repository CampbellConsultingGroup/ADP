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
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── RegulatoryFramework ────────────────────────────────────────────────────


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
    """Read model returned by the API."""
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    jurisdiction: str
    authority: str
    version: str
    effective_date: date | None
    source_url: str | None
    created_at: datetime
    updated_at: datetime


class RegulatoryFrameworkDetail(RegulatoryFramework):
    """Framework with its full control hierarchy, nested by parent_id, ordered by position."""
    controls: list["ControlNode"] = []


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
