"""Pydantic models and error hierarchy for the ADP knowledge base (ADP-SPEC-005)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# ── Knowledge type taxonomy ──────────────────────────────────────────────────

class KnowledgeType(StrEnum):
    PATTERN = "pattern"
    REFERENCE_ARCHITECTURE = "reference_architecture"
    STANDARD = "standard"
    PRINCIPLE = "principle"
    PRIOR_SOLUTION = "prior_solution"


# ── Error hierarchy ───────────────────────────────────────────────────────────

class KnowledgeError(Exception):
    pass


class RetrievalError(KnowledgeError):
    pass


class IndexingError(KnowledgeError):
    pass


class SchemaValidationError(KnowledgeError):
    pass


class CitationResolutionError(KnowledgeError):
    pass


# ── Core data classes ─────────────────────────────────────────────────────────

_CFG = ConfigDict(extra="forbid")


class KnowledgeItem(BaseModel):
    model_config = _CFG

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    kind: KnowledgeType
    title: str = Field(min_length=1)
    full_text: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)
    source_ref: str = Field(min_length=1)
    schema_version: str = "1.0.0"
    active: bool = True
    embedding: list[float] = Field(default_factory=list)
    indexed_at: datetime | None = None


class KnowledgeRelationship(BaseModel):
    model_config = _CFG

    id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    weight: float = 1.0


class CitationRef(BaseModel):
    model_config = _CFG

    item_id: str = Field(min_length=1)
    item_version: str = Field(min_length=1)


class RetrievalQuery(BaseModel):
    model_config = _CFG

    query_text: str = ""
    kinds: list[KnowledgeType] | None = None
    relationship_type: str | None = None
    traverse_from_id: str | None = None
    limit: int = Field(default=10, ge=1, le=50)
    vector_weight: float = 1.0
    keyword_weight: float = 1.0
    relationship_weight: float = 1.0
    correlation_id: str | None = None


class RetrievalResultEntry(BaseModel):
    model_config = _CFG

    item: KnowledgeItem
    citation: CitationRef
    relevance_score: float
    match_reason: str


class RetrievalResult(BaseModel):
    model_config = _CFG

    items: list[RetrievalResultEntry] = Field(default_factory=list)
    query_id: str = ""
    latency_ms: float = 0.0
