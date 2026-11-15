"""Adoption, conformance and discovery models (936-pattern-conformance, data-model.md).

Nothing here is persisted except adoptions, members and pins: conformance status, plateau and
findings are derived on every read and never stored (ART-II, SC-007).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from adp.patterns.models import ElementType, PatternKind, Severity

_FROZEN = ConfigDict(extra="forbid", frozen=True)

MAX_ELEMENT_REFS = 100


class ScopeType(StrEnum):
    BUSINESS_DOMAIN = "business_domain"
    APPLICATION_SET = "application_set"
    PORTFOLIO = "portfolio"


class ConformanceStatus(StrEnum):
    CONFORMANT = "conformant"
    CONFORMANT_WITH_WARNINGS = "conformant_with_warnings"
    NON_CONFORMANT = "non_conformant"
    INDETERMINATE = "indeterminate"
    NOT_APPLICABLE = "not_applicable"


class FindingKind(StrEnum):
    VIOLATION = "violation"
    MATCH = "match"
    BINDING = "binding"
    EVALUATION_ERROR = "evaluation_error"
    FIELD_UNAVAILABLE = "field_unavailable"
    UNVERIFIABLE = "unverifiable"
    LIMIT = "limit"


# ── Report models ──────────────────────────────────────────────────────────────────────
class ElementRef(BaseModel):
    model_config = _FROZEN

    type: ElementType
    id: str
    name: str


class Finding(BaseModel):
    model_config = _FROZEN

    code: str
    kind: FindingKind
    severity: Severity
    rule: str
    element_refs: list[ElementRef] = Field(default_factory=list)
    element_count: int = 0  # elements involved before truncation to element_refs
    truncated: bool = False


class RoleBinding(BaseModel):
    model_config = _FROZEN

    role_key: str
    element_type: ElementType
    label: str
    elements: list[ElementRef] = Field(default_factory=list)
    count: int = 0


class BindingResult(BaseModel):
    model_config = _FROZEN

    roles: list[RoleBinding] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)

    def ids(self, role_key: str) -> list[str]:
        for role in self.roles:
            if role.role_key == role_key:
                return [e.id for e in role.elements]
        return []


class PlateauState(BaseModel):
    model_config = _FROZEN

    reached: str | None = None
    next: str | None = None
    blocking: list[str] = Field(default_factory=list)


class AdoptionScope(BaseModel):
    model_config = _FROZEN

    scope_type: ScopeType
    scope_ref: str | None = None
    member_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ref_matches_type(self) -> AdoptionScope:
        if (self.scope_type == ScopeType.BUSINESS_DOMAIN) != (self.scope_ref is not None):
            raise ValueError("scope_ref is required for, and only for, business_domain scopes")
        if self.member_ids and self.scope_type != ScopeType.APPLICATION_SET:
            raise ValueError("member_ids are only valid for application_set scopes")
        return self


class ConformanceReport(BaseModel):
    model_config = _FROZEN

    adoption_id: str | None = None
    pattern_key: str
    version: str | None = None
    digest: str | None = None
    evaluated_at: datetime
    scope: AdoptionScope
    bindings: list[RoleBinding] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    status: ConformanceStatus
    plateau: PlateauState | None = None


class DiscoveryReport(BaseModel):
    model_config = _FROZEN

    pattern_key: str
    version: str
    digest: str
    evaluated_at: datetime
    matches: list[Finding] = Field(default_factory=list)
    match_count: int = 0


class EvalLimits(BaseModel):
    model_config = _FROZEN

    max_element_evaluations: int = Field(default=50_000, ge=1)
    max_element_refs: int = Field(default=MAX_ELEMENT_REFS, ge=1)


# ── Adoption API models ───────────────────────────────────────────────────────────────
AdoptionName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
SemVerStr = Annotated[str, StringConstraints(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")]


class PinIn(BaseModel):
    model_config = _FROZEN

    role_key: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    element_type: ElementType
    element_id: Annotated[str, StringConstraints(min_length=1, max_length=64)]


class AdoptionCreate(BaseModel):
    model_config = _FROZEN

    pattern_key: str
    name: AdoptionName
    scope_type: ScopeType
    scope_ref: str | None = None
    member_ids: list[str] = Field(default_factory=list)
    pinned_version: SemVerStr | None = None
    pins: list[PinIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _scope(self) -> AdoptionCreate:
        AdoptionScope(
            scope_type=self.scope_type, scope_ref=self.scope_ref, member_ids=self.member_ids
        )
        return self


class AdoptionUpdate(BaseModel):
    """PATCH body. An explicit ``pinned_version: null`` switches to following current."""

    model_config = _FROZEN

    name: AdoptionName | None = None
    pinned_version: SemVerStr | None = None


class MembersIn(BaseModel):
    model_config = _FROZEN

    member_ids: list[str]


class PinsIn(BaseModel):
    model_config = _FROZEN

    pins: list[PinIn]


class Adoption(BaseModel):
    model_config = _FROZEN

    id: str
    pattern_key: str
    pattern_name: str | None = None
    kind: PatternKind
    name: str
    scope_type: ScopeType
    scope_ref: str | None = None
    scope_name: str | None = None
    member_ids: list[str] = Field(default_factory=list)
    pinned_version: str | None = None
    resolved_version: str | None = None
    pins: list[PinIn] = Field(default_factory=list)
    created_at: datetime
    created_by: str
    updated_at: datetime
    status: ConformanceStatus | None = None


class AdoptionListResponse(BaseModel):
    model_config = _FROZEN

    items: list[Adoption]
    total: int


class EvaluateRequest(BaseModel):
    """Dry run: either unsaved YAML or a stored version, against a scope (FR-018)."""

    model_config = _FROZEN

    yaml: Annotated[str, StringConstraints(max_length=256 * 1024)] | None = None
    pattern_key: str | None = None
    version: SemVerStr | None = None
    scope: AdoptionScope
    pins: list[PinIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _one_source(self) -> EvaluateRequest:
        stored = self.pattern_key is not None and self.version is not None
        if (self.yaml is not None) == stored:
            raise ValueError("give either yaml, or pattern_key and version")
        return self


# ── Store exceptions ────────────────────────────────────────────────────────────────────
class AdoptionError(Exception):
    """Base class; the router maps each subclass to one HTTP status."""


class AdoptionNotFoundError(AdoptionError):
    def __init__(self, adoption_id: str) -> None:
        super().__init__(f"adoption '{adoption_id}' not found")


class ScopeTargetNotFoundError(AdoptionError):
    def __init__(self, what: str, target_id: str) -> None:
        super().__init__(f"{what} '{target_id}' not found")


class DuplicateAdoptionError(AdoptionError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidScopeError(AdoptionError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class DraftPinError(AdoptionError):
    def __init__(self, key: str, version: str) -> None:
        super().__init__(f"{key}@{version} is a draft; adoptions can pin only non-draft versions")


class InvalidPinError(AdoptionError):
    def __init__(self, reasons: list[str]) -> None:
        super().__init__(f"{len(reasons)} invalid pin(s)")
        self.reasons = reasons


class NotAntiPatternError(AdoptionError):
    def __init__(self, key: str) -> None:
        super().__init__(f"'{key}' is not an anti-pattern; discovery applies only to anti-patterns")
