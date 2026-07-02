"""LLM-as-a-Judge validation data models (ADP-SPEC-008)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, TypedDict

from adp.knowledge.schema import CitationRef

if TYPE_CHECKING:
    pass


class FindingSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    ADVISORY = "advisory"


class VerdictStatus(StrEnum):
    # Note: PASS = "pass" (not pass_) — StrEnum stores the string value "pass"
    # even though Python's `pass` is a reserved keyword; the JSON output is "pass"
    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"
    OVERRIDDEN = "overridden"


@dataclass
class GatingThreshold:
    max_critical: int = 0
    max_major: int = 3
    max_minor: int = 10
    version: str = "1.0.0"


@dataclass
class Finding:
    finding_id: str
    operation_id: str
    critic_name: str
    severity: FindingSeverity
    description: str
    element_id: str | None = None
    citation: CitationRef | None = None
    score: float | None = None


@dataclass
class CriticOutput:
    critic_name: str
    score: float | None = None
    findings: list[Finding] = field(default_factory=list)
    retrieved_knowledge_refs: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class Verdict:
    verdict_id: str
    operation_id: str
    design_id: str
    design_version: int
    status: VerdictStatus
    composite_score: float | None
    findings: list[Finding]
    thresholds_snapshot: GatingThreshold
    critic_outputs: list[CriticOutput]
    citations_present: bool
    overridden_by: str | None = None
    override_at: datetime | None = None
    override_justification: str | None = None
    audit_entry_id: str | None = None


class ValidationState(TypedDict, total=False):
    """Internal pipeline state threaded through orchestration steps."""

    operation_id: str
    design_id: str
    design_version: int
    design: Any  # ArchitectureDescription
    retrieved_knowledge: list[Any]  # list[RetrievalResultEntry]
    structural_findings: list[Finding]
    structural_passed: bool
    critic_outputs: list[CriticOutput]
    verdict: Verdict | None
    correlation_id: str | None
    thresholds: GatingThreshold
    error: str | None
