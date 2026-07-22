"""Unified hybrid-search index over registry text (ADP-b6o).

One polymorphic ``searchable_items`` table holds text from any registry entity
(business/technical capabilities now; value streams, domains, other fields
later). Writers upsert a row per entity; search fuses a pgvector cosine leg and
a PostgreSQL full-text leg via Reciprocal Rank Fusion (same approach as the
knowledge base, ADP-SPEC-005).

Because the index is polymorphic (no FK), writers are responsible for keeping it
in sync — upsert on create/update, delete on delete. Failures are swallowed so a
search-index hiccup never blocks the primary registry write.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import insert as pg_insert

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_logger = logging.getLogger("adp.search")

_EMBEDDING_DIM = int(os.environ.get("ADP_EMBEDDING_DIM", "384"))
_EMBEDDING_MODEL = os.environ.get("ADP_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_RRF_K = 60  # Reciprocal Rank Fusion constant (matches knowledge retrieval)

# Entity-type discriminators.
ENTITY_BUSINESS_CAPABILITY = "business_capability"
ENTITY_TECHNICAL_CAPABILITY = "technical_capability"
# ADP-SPEC-041 US2: cross-domain coverage for the Chat Assistant's retrieval leg.
ENTITY_APPLICATION = "application"
ENTITY_VALUE_STREAM = "value_stream"
ENTITY_BUSINESS_DOMAIN = "business_domain"

_metadata = sa.MetaData()
searchable_items = sa.Table(
    "searchable_items",
    _metadata,
    sa.Column("entity_type", sa.Text, primary_key=True),
    sa.Column("entity_id", sa.Text, primary_key=True),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("embedding", Vector(_EMBEDDING_DIM), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    # NB: the generated `fts` TSVECTOR column exists in the DB (migration 011)
    # but is referenced via raw SQL, not declared here.
)


@dataclass
class SearchHit:
    """One fused search result."""

    entity_type: str
    entity_id: str
    text: str
    score: float


def build_text(*parts: str | None) -> str:
    """Join non-empty text parts into a single searchable string."""
    return " ".join(p.strip() for p in parts if p and p.strip())


def rrf_fuse(
    vector_results: list[tuple[str, str, str]],
    keyword_results: list[tuple[str, str, str]],
    *,
    vector_weight: float = 0.5,
    keyword_weight: float = 0.5,
    limit: int = 10,
) -> list[SearchHit]:
    """Reciprocal Rank Fusion of two ranked result lists.

    Each input is an ordered list of (entity_type, entity_id, text). An item's
    fused score sums ``weight / (RRF_K + rank)`` across the legs it appears in,
    so items surfaced by both keyword and vector rank above single-leg items.
    """
    scores: dict[tuple[str, str], float] = {}
    texts: dict[tuple[str, str], str] = {}
    for leg, weight in ((vector_results, vector_weight), (keyword_results, keyword_weight)):
        for rank, (entity_type, entity_id, text) in enumerate(leg, 1):
            key = (entity_type, entity_id)
            scores[key] = scores.get(key, 0.0) + weight / (_RRF_K + rank)
            texts[key] = text
    hits = [
        SearchHit(entity_type=et, entity_id=eid, text=texts[(et, eid)], score=score)
        for (et, eid), score in scores.items()
    ]
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


class SearchIndex:
    """Read/write access to the unified searchable-text index."""

    def __init__(self, embedder: Any = None) -> None:
        self._embedder = embedder

    def _get_embedder(self) -> Any:
        if self._embedder is None:
            from adp.knowledge.embedder import EmbeddingProvider
            self._embedder = EmbeddingProvider(_EMBEDDING_MODEL)
        return self._embedder

    # ── Write path ──────────────────────────────────────────────────────────

    async def upsert(
        self, entity_type: str, entity_id: str, text: str, session: "AsyncSession"
    ) -> None:
        """Insert or update the index row for an entity (embedding regenerated)."""
        embedding = self._get_embedder().embed(text)
        stmt = pg_insert(searchable_items).values(
            entity_type=entity_type,
            entity_id=entity_id,
            text=text,
            embedding=embedding,
            updated_at=datetime.now(timezone.utc),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["entity_type", "entity_id"],
            set_={
                "text": stmt.excluded.text,
                "embedding": stmt.excluded.embedding,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await session.execute(stmt)

    async def delete(
        self, entity_type: str, entity_id: str, session: "AsyncSession"
    ) -> None:
        """Remove an entity's index row (no-op if absent)."""
        await session.execute(
            sa.delete(searchable_items).where(
                searchable_items.c.entity_type == entity_type,
                searchable_items.c.entity_id == entity_id,
            )
        )

    # ── Read path ───────────────────────────────────────────────────────────

    async def hybrid_search(
        self,
        query_text: str,
        session: "AsyncSession",
        *,
        entity_types: list[str] | None = None,
        limit: int = 10,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
    ) -> list[SearchHit]:
        """Return entities ranked by RRF-fused keyword + vector relevance.

        entity_types filters the search (e.g. capabilities only). Each leg is
        capped at `limit` candidates before fusion.
        """
        if not query_text or not query_text.strip():
            return []

        cols = [
            searchable_items.c.entity_type,
            searchable_items.c.entity_id,
            searchable_items.c.text,
        ]

        def _with_type_filter(q: Any) -> Any:
            if entity_types:
                return q.where(searchable_items.c.entity_type.in_(entity_types))
            return q

        # Vector leg — cosine distance via pgvector. Literal is float-only (safe).
        # Best-effort: the embedding provider can be unavailable (e.g. no
        # cached model under TRANSFORMERS_OFFLINE=1, per ADP-jyu) -- that
        # must degrade to keyword-only results, never fail the whole search.
        vec_rows: Any = []
        try:
            embedding = self._get_embedder().embed(query_text)
            emb_literal = f"[{','.join(str(x) for x in embedding)}]"
            vec_q = _with_type_filter(
                sa.select(*cols)
                .order_by(sa.text(f"embedding <=> '{emb_literal}'::vector"))
                .limit(limit)
            )
            vec_rows = (await session.execute(vec_q)).fetchall()
        except Exception as exc:  # pragma: no cover - defensive, exercised via mock in tests
            _logger.warning(
                "hybrid_search: vector leg unavailable, falling back to keyword-only: %s", exc
            )

        # Keyword leg — PostgreSQL full-text on the generated `fts` column.
        kw_q = _with_type_filter(
            sa.select(*cols)
            .where(sa.text("fts @@ plainto_tsquery('english', :q)"))
            .order_by(sa.text("ts_rank(fts, plainto_tsquery('english', :q)) DESC"))
            .limit(limit)
        ).params(q=query_text)

        kw_rows = (await session.execute(kw_q)).fetchall()

        return rrf_fuse(
            [(r.entity_type, r.entity_id, r.text) for r in vec_rows],
            [(r.entity_type, r.entity_id, r.text) for r in kw_rows],
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
            limit=limit,
        )


# ── Module-level best-effort sync helpers ────────────────────────────────────
# Writers call these from within a registry write. They run inside a SAVEPOINT
# and swallow errors so a search-index problem (e.g. embedding model unavailable)
# never aborts the primary transaction.

_default_index: SearchIndex | None = None


def default_index() -> SearchIndex:
    global _default_index
    if _default_index is None:
        _default_index = SearchIndex()
    return _default_index


async def index_entity(
    entity_type: str, entity_id: str, text: str, session: "AsyncSession"
) -> None:
    """Best-effort upsert of an entity's searchable text. Never raises."""
    try:
        async with session.begin_nested():
            await default_index().upsert(entity_type, entity_id, text, session)
    except Exception as exc:  # pragma: no cover - defensive
        _logger.warning("search index upsert skipped for %s:%s — %s", entity_type, entity_id, exc)


async def unindex_entity(
    entity_type: str, entity_id: str, session: "AsyncSession"
) -> None:
    """Best-effort removal of an entity's index row. Never raises."""
    try:
        async with session.begin_nested():
            await default_index().delete(entity_type, entity_id, session)
    except Exception as exc:  # pragma: no cover - defensive
        _logger.warning("search index delete skipped for %s:%s — %s", entity_type, entity_id, exc)
