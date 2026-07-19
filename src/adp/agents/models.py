"""Shared model shapes for the Agent Review toolkit (ADP-SPEC-039).

Domain-agnostic: this module MUST NOT import from any single domain module
(e.g. adp.business, adp.application) -- verified by tests/unit/agents/
test_toolkit_boundary.py (SC-005). Adapters compose these pieces into their
own domain-specific suggestion models rather than inheriting a fixed shape.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class GroundingCitation(BaseModel):
    """One entity a suggestion references, to be independently verified."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_id: str


class GroundingResult(BaseModel):
    """Outcome of re-verifying a suggestion's citations against the database."""

    model_config = ConfigDict(extra="forbid")

    resolved: list[GroundingCitation]
    unresolved: list[GroundingCitation]

    @property
    def fully_grounded(self) -> bool:
        return len(self.unresolved) == 0


class AgentSuggestionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class AgentReviewOperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    # LLM call errored (FR-021): error_description is set. Distinct from a
    # legitimate empty suggestion set (no LLM configured), which COMPLETES.
    FAILED = "failed"
