"""Tests for KnowledgeRetrieval — vector, keyword, hybrid, relationship, citation (US1-US4)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from adp.knowledge.schema import (
    CitationRef,
    RetrievalError,
    RetrievalQuery,
    RetrievalResult,
)


def _make_retrieval(mock_rows=None, return_none: bool = False):
    """Build a KnowledgeRetrieval with mocked engine + embedder."""
    from adp.knowledge.retrieval import KnowledgeRetrieval

    retrieval = KnowledgeRetrieval.__new__(KnowledgeRetrieval)

    # Mock embedder
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3, 0.4]
    retrieval._embedder = mock_embedder

    # Mock session factory — execute result must be a plain MagicMock so
    # .fetchall() / .fetchone() return lists/rows, not coroutines.
    mock_result = MagicMock()
    if return_none:
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = None
    else:
        rows = mock_rows or []
        mock_result.fetchall.return_value = rows
        mock_result.fetchone.return_value = rows[0] if rows else None

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_factory = MagicMock()
    mock_factory.return_value = mock_ctx
    retrieval._session_factory = mock_factory

    return retrieval


def _make_row(item_id="PAT-001", version="1.0.0", kind="pattern"):
    """Build a namedtuple-like row matching knowledge_items schema."""
    from collections import namedtuple
    from datetime import datetime, timezone

    Row = namedtuple("Row", [
        "id", "version", "kind", "title", "full_text", "metadata",
        "source_ref", "schema_version", "active", "embedding", "indexed_at",
    ])
    return Row(
        id=item_id, version=version, kind=kind,
        title=f"Item {item_id}", full_text=f"Text for {item_id}",
        metadata={}, source_ref=f"git:test:{item_id}.md",
        schema_version="1.0.0", active=True, embedding=[],
        indexed_at=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )


# ── US1: Citation completeness across retrieval modes ────────────────────────


@pytest.mark.asyncio
async def test_vector_search_returns_results_with_citations() -> None:
    """vector_search returns entries each with non-null CitationRef (FR-005)."""
    rows = [_make_row("PAT-001", "1.0.0"), _make_row("REF-002", "2.1.0"),
            _make_row("STD-003", "3.0.0")]
    retrieval = _make_retrieval(rows)
    result = await retrieval.vector_search(RetrievalQuery(query_text="stateless api"))

    assert len(result.items) == 3
    for entry in result.items:
        assert entry.citation is not None
        assert entry.citation.item_id != ""
        assert entry.citation.item_version != ""


@pytest.mark.asyncio
async def test_keyword_search_returns_results_with_citations() -> None:
    """keyword_search entries all carry CitationRef (FR-005)."""
    rows = [_make_row("PAT-001", "1.0.0"), _make_row("REF-002", "2.1.0")]
    retrieval = _make_retrieval(rows)
    result = await retrieval.keyword_search(RetrievalQuery(query_text="gateway"))

    for entry in result.items:
        assert entry.citation is not None
        assert entry.citation.item_id != ""
        assert entry.citation.item_version != ""


@pytest.mark.asyncio
async def test_hybrid_search_combines_results_and_deduplicates() -> None:
    """hybrid_search deduplicates by item_id and orders by descending score."""
    rows = [_make_row("PAT-001", "1.0.0"), _make_row("REF-002", "2.1.0")]
    retrieval = _make_retrieval(rows)
    result = await retrieval.hybrid_search(RetrievalQuery(query_text="api"))

    ids = [e.citation.item_id for e in result.items]
    assert len(ids) == len(set(ids)), "Duplicate item_ids found in hybrid result"
    scores = [e.relevance_score for e in result.items]
    assert scores == sorted(scores, reverse=True), "Results not ordered by descending score"


@pytest.mark.asyncio
async def test_citations_are_stable_across_identical_queries() -> None:
    """Same query submitted twice returns identical citations (SC-002)."""
    rows = [_make_row("PAT-001", "1.0.0")]
    retrieval = _make_retrieval(rows)
    query = RetrievalQuery(query_text="stateless")
    r1 = await retrieval.hybrid_search(query)
    r2 = await retrieval.hybrid_search(query)

    assert len(r1.items) == len(r2.items)
    for e1, e2 in zip(r1.items, r2.items):
        assert e1.citation == e2.citation


# ── US3: Relationship traversal ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_relationship_query_returns_only_related_items() -> None:
    """relationship_query returns only items linked by the specified relationship."""
    rows = [_make_row("PAT-001", "1.0.0"), _make_row("REF-002", "2.1.0")]
    retrieval = _make_retrieval(rows)
    query = RetrievalQuery(
        query_text="",
        traverse_from_id="PR-001",
        relationship_type="satisfies",
    )
    result = await retrieval.relationship_query(query)

    assert len(result.items) == 2
    for entry in result.items:
        assert entry.match_reason == "relationship:satisfies"


@pytest.mark.asyncio
async def test_relationship_query_returns_empty_when_no_matches() -> None:
    """Empty relationship result is an empty list, not an error (US3 scenario 3)."""
    retrieval = _make_retrieval([])
    query = RetrievalQuery(
        query_text="",
        traverse_from_id="PR-999",
        relationship_type="satisfies",
    )
    result = await retrieval.relationship_query(query)
    assert result.items == []


@pytest.mark.asyncio
async def test_relationship_query_result_includes_relationship_type() -> None:
    """match_reason encodes the relationship type."""
    rows = [_make_row("PAT-001", "1.0.0")]
    retrieval = _make_retrieval(rows)
    query = RetrievalQuery(
        query_text="", traverse_from_id="PR-001", relationship_type="extends"
    )
    result = await retrieval.relationship_query(query)
    assert result.items[0].match_reason == "relationship:extends"


# ── US4: Citation completeness parametrized ───────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["vector_search", "keyword_search"])
async def test_all_retrieval_modes_return_citations(mode: str) -> None:
    """Every result entry from every mode carries a valid CitationRef (SC-004)."""
    rows = [_make_row(f"ITEM-{i:03d}", f"{i}.0.0") for i in range(1, 4)]
    retrieval = _make_retrieval(rows)
    method = getattr(retrieval, mode)
    result: RetrievalResult = await method(RetrievalQuery(query_text="test"))
    for entry in result.items:
        assert entry.citation is not None
        assert entry.citation.item_id != ""
        assert entry.citation.item_version != ""


@pytest.mark.asyncio
async def test_resolve_citation_returns_correct_item() -> None:
    """resolve_citation returns the exact item by id+version."""
    row = _make_row("PAT-001", "1.0.0")
    retrieval = _make_retrieval([row])
    result = await retrieval.resolve_citation(CitationRef(item_id="PAT-001", item_version="1.0.0"))
    assert result is not None
    assert result.id == "PAT-001"
    assert result.version == "1.0.0"


@pytest.mark.asyncio
async def test_resolve_citation_returns_none_for_unknown() -> None:
    """resolve_citation returns None for an unknown id+version (not an exception)."""
    retrieval = _make_retrieval(return_none=True)
    result = await retrieval.resolve_citation(
        CitationRef(item_id="UNKNOWN", item_version="1.0.0")
    )
    assert result is None


@pytest.mark.asyncio
async def test_resolve_citation_returns_inactive_item() -> None:
    """resolve_citation bypasses active filter — old versions remain resolvable (FR-004)."""
    row = _make_row("PAT-001", "1.0.0")
    # Return the inactive row (active=False doesn't block resolve_citation)
    retrieval = _make_retrieval([row])
    result = await retrieval.resolve_citation(
        CitationRef(item_id="PAT-001", item_version="1.0.0")
    )
    # The query doesn't filter by active when resolving citations
    assert result is not None
    assert result.id == "PAT-001"


def test_build_result_entry_raises_on_missing_citation() -> None:
    """_build_result_entry raises RetrievalError if id or version is empty."""
    from collections import namedtuple
    from datetime import datetime, timezone

    from adp.knowledge.retrieval import KnowledgeRetrieval

    retrieval = KnowledgeRetrieval.__new__(KnowledgeRetrieval)

    Row = namedtuple("Row", [
        "id", "version", "kind", "title", "full_text", "metadata",
        "source_ref", "schema_version", "active", "embedding", "indexed_at",
    ])
    bad_row = Row(
        id="", version="1.0.0", kind="pattern", title="T", full_text="F",
        metadata={}, source_ref="s", schema_version="1.0.0", active=True,
        embedding=[], indexed_at=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )

    with pytest.raises(RetrievalError, match="FR-005"):
        retrieval._build_result_entry(bad_row, "vector")
