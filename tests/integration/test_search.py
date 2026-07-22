"""Integration tests for the unified search index SQL path (ADP-b6o).

Exercises the real pgvector + generated-TSVECTOR schema (migration 011) against a
PostgreSQL container. Uses a deterministic fake embedder so it runs offline (CI
sets TRANSFORMERS_OFFLINE=1); fusion logic itself is unit-tested in test_search.py.
"""

from __future__ import annotations

import pytest

from adp.search import (
    ENTITY_BUSINESS_CAPABILITY,
    ENTITY_TECHNICAL_CAPABILITY,
    SearchIndex,
)

pytestmark = pytest.mark.asyncio


class _FakeEmbedder:
    """Deterministic 384-d embeddings keyed on marker words (no model download)."""

    def embed(self, text: str) -> list[float]:
        v = [0.0] * 384
        t = text.lower()
        if "alpha" in t:
            v[0] = 1.0
        elif "beta" in t:
            v[1] = 1.0
        else:
            v[2] = 1.0
        return v

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class _FailingEmbedder:
    """Simulates an unavailable embedding provider (e.g. no cached model
    under TRANSFORMERS_OFFLINE=1 -- the exact failure mode ADP-jyu hit)."""

    def embed(self, text: str) -> list[float]:
        raise OSError("model not found (offline mode)")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise OSError("model not found (offline mode)")


async def test_upsert_and_hybrid_search_round_trip(db_session):
    idx = SearchIndex(embedder=_FakeEmbedder())
    await idx.upsert(ENTITY_BUSINESS_CAPABILITY, "A", "Alpha order management", db_session)
    await idx.upsert(ENTITY_BUSINESS_CAPABILITY, "B", "Beta warehouse control", db_session)
    await idx.upsert(ENTITY_TECHNICAL_CAPABILITY, "T", "Alpha messaging bus", db_session)

    # Keyword + vector both point at the "alpha order" item.
    hits = await idx.hybrid_search("alpha order", db_session, limit=10)
    assert hits, "expected at least one hit"
    assert hits[0].entity_id == "A"
    assert {h.entity_id for h in hits} >= {"A"}


async def test_hybrid_search_entity_type_filter(db_session):
    idx = SearchIndex(embedder=_FakeEmbedder())
    await idx.upsert(ENTITY_BUSINESS_CAPABILITY, "A", "Alpha order management", db_session)
    await idx.upsert(ENTITY_TECHNICAL_CAPABILITY, "T", "Alpha messaging bus", db_session)

    hits = await idx.hybrid_search(
        "alpha", db_session, entity_types=[ENTITY_TECHNICAL_CAPABILITY], limit=10
    )
    assert {h.entity_type for h in hits} == {ENTITY_TECHNICAL_CAPABILITY}
    assert {h.entity_id for h in hits} == {"T"}


async def test_keyword_leg_matches_by_text(db_session):
    """A query whose embedding is neutral still matches via the keyword leg."""
    idx = SearchIndex(embedder=_FakeEmbedder())
    await idx.upsert(ENTITY_BUSINESS_CAPABILITY, "A", "Distinctive fulfilment routing", db_session)

    hits = await idx.hybrid_search("fulfilment routing", db_session, limit=5)
    assert any(h.entity_id == "A" for h in hits)


async def test_hybrid_search_falls_back_to_keyword_only_when_embedder_fails(db_session):
    """ADP-jyu: the vector leg failing (embedding provider unavailable, e.g.
    under TRANSFORMERS_OFFLINE with no cached model) must not fail the whole
    search -- the keyword leg should still return results, not a 500."""
    seed_idx = SearchIndex(embedder=_FakeEmbedder())
    await seed_idx.upsert(
        ENTITY_BUSINESS_CAPABILITY, "A", "Distinctive fulfilment routing", db_session
    )

    broken_idx = SearchIndex(embedder=_FailingEmbedder())
    hits = await broken_idx.hybrid_search("fulfilment routing", db_session, limit=5)
    assert any(h.entity_id == "A" for h in hits)


async def test_delete_removes_from_index(db_session):
    idx = SearchIndex(embedder=_FakeEmbedder())
    await idx.upsert(ENTITY_BUSINESS_CAPABILITY, "A", "Alpha order management", db_session)
    await idx.delete(ENTITY_BUSINESS_CAPABILITY, "A", db_session)

    hits = await idx.hybrid_search("alpha order", db_session, limit=5)
    assert all(h.entity_id != "A" for h in hits)
