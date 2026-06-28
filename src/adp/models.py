"""Canonical data model for ADP architecture descriptions.

This module is the single source of truth per ART-II. The JSON Schema and all
downstream artifacts are generated from these definitions — never hand-authored.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ── Schema version ──────────────────────────────────────────────────────────

SCHEMA_VERSION = "1.0.0"

# ── Identifier type aliases ──────────────────────────────────────────────────

RequirementId = Annotated[str, Field(pattern=r"^REQ-\d{3}$")]
ElementId = Annotated[str, Field(pattern=r"^ELM-\d{3}$")]
RelationshipId = Annotated[str, Field(pattern=r"^REL-\d{3}$")]
OptionId = Annotated[str, Field(pattern=r"^OPT-\d{3}$")]
FindingId = Annotated[str, Field(pattern=r"^FND-\d{3}$")]
VerdictId = Annotated[str, Field(pattern=r"^VRD-\d{3}$")]
AuditEntryId = Annotated[str, Field(pattern=r"^AUD-\d{3}$")]

# ── Enumerations ─────────────────────────────────────────────────────────────


class ElementKind(StrEnum):
    """C4 structural element types. Stops at component level (v1 scope)."""

    PERSON = "person"
    SYSTEM = "system"
    CONTAINER = "container"
    COMPONENT = "component"


class VerdictStatus(StrEnum):
    """Decision state of a SolutionOption."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"


# ── Base model config ─────────────────────────────────────────────────────────

_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=False)


class _BaseModel(BaseModel):
    model_config = _MODEL_CONFIG


# ── Entity models ─────────────────────────────────────────────────────────────


class Requirement(_BaseModel):
    """A single design requirement. Starting point of every traceability chain."""

    id: RequirementId
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1)
    priority: Literal["must", "should", "may"] | None = None
    tags: list[str] = Field(default_factory=list)


class Element(_BaseModel):
    """A C4 structural element with traceability fields."""

    id: ElementId
    name: str = Field(min_length=1, max_length=120)
    kind: ElementKind
    description: str | None = None
    satisfies: list[RequirementId] = Field(default_factory=list)
    provenance: str | None = None
    tags: list[str] = Field(default_factory=list)


class Relationship(_BaseModel):
    """A directed link between two elements."""

    id: RelationshipId
    source: ElementId
    target: ElementId
    label: str | None = Field(default=None, max_length=80)
    technology: str | None = Field(default=None, max_length=80)


class SolutionOption(_BaseModel):
    """A recommendation option under consideration for a design decision."""

    id: OptionId
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1)
    status: VerdictStatus
    satisfies: list[RequirementId] = Field(default_factory=list)
    provenance: str | None = None


class Finding(_BaseModel):
    """An audit or review observation attached to an element or option."""

    id: FindingId
    subject: str  # ElementId | OptionId — validated by ArchitectureDescription
    summary: str = Field(min_length=1, max_length=240)
    detail: str | None = None
    severity: Literal["info", "warning", "critical"] = "info"
    source: str | None = None


class Verdict(_BaseModel):
    """A recorded decision on a SolutionOption. Closes the traceability chain."""

    id: VerdictId
    option_id: OptionId
    status: VerdictStatus
    rationale: str = Field(min_length=1)
    decided_by: str = Field(min_length=1)
    decided_at: datetime
    provenance: str | None = None


class AuditEntry(_BaseModel):
    """Immutable record of a mutation. Append-only per ART-IX."""

    id: AuditEntryId
    actor: str = Field(min_length=1)
    action: str = Field(min_length=1)
    affected_entity: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=240)
    timestamp: datetime
    origin: Literal["human", "ai"]


# ── Aggregate root ────────────────────────────────────────────────────────────

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


class ArchitectureDescription(_BaseModel):
    """Aggregate root. Unit of serialization, validation, and schema conformance."""

    schema_version: str
    id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    requirements: list[Requirement] = Field(default_factory=list)
    elements: list[Element] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    options: list[SolutionOption] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    verdicts: list[Verdict] = Field(default_factory=list)
    audit_log: list[AuditEntry] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, v: str) -> str:
        if not _SEMVER_RE.match(v):
            raise ValueError(f"schema_version must be semver (X.Y.Z), got {v!r}")
        return v

    @model_validator(mode="after")
    def _validate_integrity(self) -> "ArchitectureDescription":
        from adp.validate import build_id_index, validate_references

        index = build_id_index(self)
        validate_references(self, index)
        return self
