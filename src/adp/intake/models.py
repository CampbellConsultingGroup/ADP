"""Intake pipeline data models (ADP-SPEC-006)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class SubmissionMode(StrEnum):
    BULK_TEXT = "bulk_text"
    STRUCTURED_FORM = "structured_form"


class RequirementKind(StrEnum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    CONSTRAINT = "constraint"
    DRIVER = "driver"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EDITED_CONFIRMED = "edited_confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class IntakeSubmission:
    """Input package provided by the architect. Text is NEVER persisted."""

    submission_id: str
    mode: SubmissionMode
    text: str
    submitted_by: str
    submitted_at: datetime
    operation_id: str


@dataclass
class ExtractedProposal:
    """AI-proposed requirement before human confirmation (transient, TTL 24h)."""

    proposal_id: str
    operation_id: str
    submission_id: str
    draft_statement: str
    kind: RequirementKind
    source_excerpt: str
    verification_status: VerificationStatus
    confidence: float
    proposed_links: list[str] = field(default_factory=list)
    status: ProposalStatus = ProposalStatus.PENDING
    confirmed_statement: str | None = None
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    requirement_id: str | None = None


@dataclass
class ExtractionSpan:
    """Telemetry payload emitted per extraction job (QG-11 / FR-006)."""

    operation_id: str
    correlation_id: str | None
    model: str
    endpoint: str
    source_char_count: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    proposal_count: int
    proposal_ids: list[str]
    latency_ms: float
    error: str | None = None
