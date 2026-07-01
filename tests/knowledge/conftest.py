"""Shared fixtures for knowledge base tests (ADP-SPEC-005)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from adp.knowledge.schema import (
    CitationRef,
    KnowledgeItem,
    KnowledgeType,
    RetrievalResultEntry,
)

_NOW = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def embedding_provider():
    """Mock EmbeddingProvider with dimension 4 and fixed embeddings."""
    mock = MagicMock()
    mock.dimension = 4
    mock.embed.return_value = [0.1, 0.2, 0.3, 0.4]
    mock.embed_batch.return_value = lambda texts: [[0.1, 0.2, 0.3, 0.4]] * len(texts)
    mock.embed_batch.side_effect = lambda texts: [[0.1, 0.2, 0.3, 0.4]] * len(texts)
    return mock


@pytest.fixture()
def mock_index():
    """Mock KnowledgeIndex with AsyncMock session."""
    idx = MagicMock()
    idx.upsert_item = AsyncMock()
    idx.get_item = AsyncMock(return_value=None)
    idx.get_all_active_ids = AsyncMock(return_value=set())
    idx.mark_inactive = AsyncMock(return_value=0)
    idx.upsert_relationship = AsyncMock()
    return idx


def make_item(
    item_id: str = "PAT-001",
    version: str = "1.0.0",
    kind: KnowledgeType = KnowledgeType.PATTERN,
    active: bool = True,
) -> KnowledgeItem:
    return KnowledgeItem(
        id=item_id,
        version=version,
        kind=kind,
        title=f"Item {item_id}",
        full_text=f"Full text for {item_id}",
        metadata={"tags": ["test"]},
        source_ref=f"git:test:{item_id}.md",
        active=active,
        indexed_at=_NOW,
    )


def make_entry(
    item_id: str = "PAT-001",
    version: str = "1.0.0",
    match_reason: str = "vector",
    score: float = 0.9,
) -> RetrievalResultEntry:
    return RetrievalResultEntry(
        item=make_item(item_id, version),
        citation=CitationRef(item_id=item_id, item_version=version),
        relevance_score=score,
        match_reason=match_reason,
    )
