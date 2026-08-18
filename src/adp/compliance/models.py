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

from pydantic import BaseModel, ConfigDict, field_validator

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
    """Write model for creating a framework."""
    model_config = ConfigDict(extra="forbid")

    name: str
    jurisdiction: str
    authority: str
    version: str
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
    """Write model for updating a framework. All fields optional."""
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    jurisdiction: str | None = None
    authority: str | None = None
    version: str | None = None
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
    route path, not the body (mirrors ValueStreamStageCreate's shape in adp.business.models)."""
    model_config = ConfigDict(extra="forbid")

    parent_id: str | None = None
    code: str
    title: str
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
    re-runs the same cycle/cross-framework/uniqueness validation as create (research.md D5, D6)."""
    model_config = ConfigDict(extra="forbid")

    parent_id: str | None = None
    code: str | None = None
    title: str | None = None
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


RegulatoryFrameworkDetail.model_rebuild()
ControlNode.model_rebuild()
