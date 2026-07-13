"""Recommendation engine data models (ADP-SPEC-007)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, TypedDict

from adp.knowledge.schema import CitationRef
from adp.models import ElementKind

if TYPE_CHECKING:
    pass


class TradeOffStance(StrEnum):
    MEETS = "meets"
    PARTIALLY_MEETS = "partially_meets"
    DOES_NOT_MEET = "does_not_meet"


@dataclass
class TradeOffEntry:
    """One row in a SolutionOption's trade-off assessment."""

    criterion: str
    stance: TradeOffStance
    rationale: str


@dataclass
class ProposedElement:
    """A partial element description embedded in a SolutionOption."""

    name: str
    kind: ElementKind
    description: str | None = None
    satisfies: list[str] = field(default_factory=list)


@dataclass
class SolutionOption:
    """Primary output of the recommendation pipeline. Stored transiently (TTL 24h)."""

    option_id: str
    operation_id: str
    rank: int = 0
    title: str = ""
    rationale: str = ""
    advisory: bool = False
    grounded_on: list[CitationRef] = field(default_factory=list)
    satisfies: list[str] = field(default_factory=list)
    trade_offs: list[TradeOffEntry] = field(default_factory=list)
    proposed_elements: list[ProposedElement] = field(default_factory=list)
    ranking_score: float = 0.0
    coverage_score: float = 0.0
    principle_score: float = 0.0
    tradeoff_score: float = 0.0
    status: str = "pending"
    accepted_by: str | None = None
    accepted_at: datetime | None = None
    # ADP-SPEC-019: "knowledge_base" when KB had entries; "requirements_only" when KB was empty
    knowledge_source: str = "knowledge_base"


@dataclass
class RecommendationStep:
    """One orchestration step's telemetry record (FR-006 / QG-11)."""

    operation_id: str
    step_name: str
    correlation_id: str | None = None
    retrieved_knowledge_refs: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    option_count: int = 0
    advisory_count: int = 0
    error: str | None = None


class RecommendationState(TypedDict, total=False):
    """Shared state threaded through all LangGraph pipeline steps."""

    operation_id: str
    design_id: str
    requirement_ids: list[str]
    requirements: list[Any]  # list[Requirement] — typed loosely to avoid circular
    retrieved_knowledge: list[Any]  # list[RetrievalResultEntry]
    candidate_options: list[SolutionOption]
    ranked_options: list[SolutionOption]
    validated_options: list[SolutionOption]
    correlation_id: str | None
    error: str | None
    option_count: int
    ranking_weights: tuple[float, float, float]
