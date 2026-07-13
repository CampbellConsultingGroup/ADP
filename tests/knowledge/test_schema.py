"""Tests for KnowledgeItem schema validation (FR-001, FR-002, FR-006)."""

from __future__ import annotations

import pydantic
import pytest

from adp.knowledge.schema import (
    CitationRef,
    KnowledgeItem,
    KnowledgeType,
    RetrievalQuery,
)


def test_knowledge_type_closed_enum() -> None:
    """Unrecognized knowledge types raise ValueError (taxonomy is closed, FR-002)."""
    with pytest.raises(ValueError):
        KnowledgeType("unknown_type")


def test_all_five_knowledge_types_recognized() -> None:
    for v in ["pattern", "reference_architecture", "standard", "principle", "prior_solution"]:
        assert KnowledgeType(v) is not None


def test_knowledge_item_requires_id_and_version() -> None:
    with pytest.raises(pydantic.ValidationError):
        KnowledgeItem(id="", version="1.0.0", kind="pattern",
                      title="T", full_text="F", source_ref="s")
    with pytest.raises(pydantic.ValidationError):
        KnowledgeItem(id="PAT-001", version="", kind="pattern",
                      title="T", full_text="F", source_ref="s")


def test_knowledge_item_extra_fields_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        KnowledgeItem(id="PAT-001", version="1.0.0", kind="pattern",  # type: ignore[call-arg]
                      title="T", full_text="F", source_ref="s", rogue="x")


def test_citation_ref_fields_non_empty() -> None:
    with pytest.raises(pydantic.ValidationError):
        CitationRef(item_id="", item_version="1.0.0")
    with pytest.raises(pydantic.ValidationError):
        CitationRef(item_id="PAT-001", item_version="")


def test_retrieval_query_correlation_id_optional() -> None:
    q = RetrievalQuery(query_text="stateless api")
    assert q.correlation_id is None
    q2 = RetrievalQuery(query_text="stateless api", correlation_id="trace-123")
    assert q2.correlation_id == "trace-123"


def test_retrieval_query_limit_clamped() -> None:
    with pytest.raises(pydantic.ValidationError):
        RetrievalQuery(query_text="x", limit=51)
    with pytest.raises(pydantic.ValidationError):
        RetrievalQuery(query_text="x", limit=0)
