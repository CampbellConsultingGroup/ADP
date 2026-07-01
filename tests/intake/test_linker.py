"""Tests for KnowledgeLinker (US3 / FR-005)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from adp.intake.linker import KnowledgeLinker


def _mock_retrieval(item_id: str, score: float):  # type: ignore[type-arg]
    from adp.knowledge.schema import CitationRef, RetrievalResult, RetrievalResultEntry
    from tests.knowledge.conftest import make_item

    entry = RetrievalResultEntry(
        item=make_item(item_id, "1.0.0"),
        citation=CitationRef(item_id=item_id, item_version="1.0.0"),
        relevance_score=score,
        match_reason="keyword",
    )
    result = RetrievalResult(items=[entry], query_id="q-001", latency_ms=5.0)

    retrieval = MagicMock()
    retrieval.keyword_search = AsyncMock(return_value=result)
    return retrieval


@pytest.mark.asyncio
async def test_linker_resolves_known_principle() -> None:
    """Linker returns item_id when keyword search exceeds threshold."""
    retrieval = _mock_retrieval("PR-007", 0.85)
    linker = KnowledgeLinker(knowledge_retrieval=retrieval, confidence_threshold=0.7)
    result = await linker.link(["Zero Trust Architecture"])
    assert result == ["PR-007"]


@pytest.mark.asyncio
async def test_linker_returns_empty_below_threshold() -> None:
    """Score below threshold → empty list."""
    retrieval = _mock_retrieval("PR-007", 0.5)
    linker = KnowledgeLinker(knowledge_retrieval=retrieval, confidence_threshold=0.7)
    result = await linker.link(["Low Match"])
    assert result == []


@pytest.mark.asyncio
async def test_linker_skips_when_no_knowledge_base() -> None:
    """No knowledge_retrieval → empty list, no exception."""
    linker = KnowledgeLinker(knowledge_retrieval=None)
    result = await linker.link(["any name"])
    assert result == []


@pytest.mark.asyncio
async def test_linker_deduplicates_results() -> None:
    """Same id returned twice → appears once in output."""
    retrieval = _mock_retrieval("PR-001", 0.9)
    linker = KnowledgeLinker(knowledge_retrieval=retrieval)
    result = await linker.link(["Principle A", "Principle A"])
    assert result.count("PR-001") == 1
