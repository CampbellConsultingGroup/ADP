"""Pattern registry API models and store exceptions (935-pattern-registry, data-model.md).

The registry persists 934's :class:`~adp.patterns.models.PatternDefinition`; these models describe
families, versions, lifecycle history and the registry's request/response shapes.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from adp.patterns.models import PatternDefinition, PatternIssue, PatternKind, PatternRelationType

_FROZEN = ConfigDict(extra="forbid", frozen=True)

MAX_YAML_BYTES = 256 * 1024


class PatternLifecycle(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    CURRENT = "current"
    DEPRECATED = "deprecated"
    DECOMMISSIONED = "decommissioned"


class ImportStatus(StrEnum):
    CREATED = "created"
    UNCHANGED = "unchanged"
    REJECTED = "rejected"


class PatternViewKind(StrEnum):
    STRUCTURE = "structure"
    CATALOG = "catalog"
    TRACEABILITY = "traceability"


# ── Read models ────────────────────────────────────────────────────────────────────
class PatternVersionSummary(BaseModel):
    model_config = _FROZEN

    id: str
    pattern_key: str
    version: str
    kind: PatternKind
    lifecycle: PatternLifecycle
    name: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    digest: str
    created_at: datetime
    created_by: str
    lifecycle_changed_at: datetime


class PatternFamily(BaseModel):
    model_config = _FROZEN

    pattern_key: str
    kind: PatternKind
    owner_role: str
    created_at: datetime
    created_by: str
    current_version: str | None
    versions: list[PatternVersionSummary]


class PatternRelationRow(BaseModel):
    model_config = _FROZEN

    source_version_id: str
    source_pattern_key: str
    target_pattern_key: str
    relation_type: PatternRelationType
    note: str | None = None
    target_resolved: bool


class LifecycleEvent(BaseModel):
    model_config = _FROZEN

    id: str
    from_state: PatternLifecycle
    to_state: PatternLifecycle
    reason: str
    confirmation_id: str
    actor: str
    at: datetime
    caused_by_event_id: str | None = None


class PatternVersionDetail(PatternVersionSummary):
    definition: PatternDefinition
    relations: list[PatternRelationRow] = Field(default_factory=list)
    issues: list[PatternIssue] = Field(default_factory=list)
    allowed_transitions: list[PatternLifecycle] = Field(default_factory=list)
    history: list[LifecycleEvent] = Field(default_factory=list)
    knowledge_item_id: str | None = None


class PatternListResponse(BaseModel):
    model_config = _FROZEN

    items: list[PatternVersionSummary]
    total: int


# ── Results ───────────────────────────────────────────────────────────────────────
class PatternImportResult(BaseModel):
    model_config = _FROZEN

    status: ImportStatus
    version: PatternVersionSummary | None = None
    issues: list[PatternIssue] = Field(default_factory=list)


class PatternUpdateResult(BaseModel):
    model_config = _FROZEN

    version: PatternVersionSummary
    issues: list[PatternIssue] = Field(default_factory=list)


class PatternValidateResult(BaseModel):
    model_config = _FROZEN

    ok: bool
    digest: str | None = None
    issues: list[PatternIssue] = Field(default_factory=list)


class PatternViewResponse(BaseModel):
    model_config = _FROZEN

    view: PatternViewKind
    flowchart: str
    digest: str
    generated_at: datetime
    truncated: list[str] = Field(default_factory=list)


# ── Requests ──────────────────────────────────────────────────────────────────────
class LifecycleTransitionRequest(BaseModel):
    """ART-VIII: every transition carries a reason and a non-empty confirmation id (Q3)."""

    model_config = _FROZEN

    to: PatternLifecycle
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    confirmation_id: Annotated[str, StringConstraints(max_length=200)]

    @field_validator("confirmation_id")
    @classmethod
    def _confirmation_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "confirmation_id must be non-empty -- a lifecycle transition is a governed, "
                "consequential action (ART-VIII)"
            )
        return value.strip()


class PatternRenderRequest(BaseModel):
    model_config = _FROZEN

    yaml: Annotated[str, StringConstraints(max_length=MAX_YAML_BYTES)]
    view: Literal["structure"] = "structure"


# ── Store exceptions ────────────────────────────────────────────────────────────────
class PatternRegistryError(Exception):
    """Base class; the router maps each subclass to one HTTP status."""


class PatternNotFoundError(PatternRegistryError):
    def __init__(self, key: str) -> None:
        super().__init__(f"pattern '{key}' not found")
        self.key = key


class PatternVersionNotFoundError(PatternRegistryError):
    def __init__(self, key: str, version: str) -> None:
        super().__init__(f"pattern version '{key}@{version}' not found")
        self.key = key
        self.version = version


class NotDraftError(PatternRegistryError):
    def __init__(self, key: str, version: str, lifecycle: str) -> None:
        super().__init__(
            f"'{key}@{version}' is {lifecycle}; only draft versions can be changed or deleted"
        )


class IllegalTransitionError(PatternRegistryError):
    def __init__(self, src: str, dst: str) -> None:
        super().__init__(f"transition {src} -> {dst} is not allowed")
        self.src = src
        self.dst = dst


class ConcurrentPromotionError(PatternRegistryError):
    def __init__(self, key: str) -> None:
        super().__init__(f"another version of '{key}' became current concurrently; retry")


class PromotionBlockedError(PatternRegistryError):
    def __init__(self, issues: list[PatternIssue]) -> None:
        super().__init__(f"promotion blocked by {len(issues)} issue(s)")
        self.issues = issues


class InvalidPatternUpdateError(PatternRegistryError):
    """A draft update whose YAML is invalid or changes key/version/kind (422)."""

    def __init__(self, issues: list[PatternIssue]) -> None:
        super().__init__(f"draft update rejected with {len(issues)} issue(s)")
        self.issues = issues
