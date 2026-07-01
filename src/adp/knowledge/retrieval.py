"""KnowledgeRetrieval — hybrid query interface for the ADP knowledge base (ADP-SPEC-005).

Combines vector similarity, keyword search, and relationship traversal using
Reciprocal Rank Fusion (RRF). Every result carries a CitationRef for QG-12.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.knowledge.embedder import EmbeddingProvider
from adp.knowledge.index import knowledge_items, knowledge_relationships
from adp.knowledge.schema import (
    CitationRef,
    KnowledgeItem,
    KnowledgeType,
    RetrievalError,
    RetrievalQuery,
    RetrievalResult,
    RetrievalResultEntry,
)

_logger = logging.getLogger("adp.knowledge")

_RRF_K = 60  # Reciprocal Rank Fusion constant


class KnowledgeRetrieval:
    """Typed hybrid retrieval interface for the knowledge index."""

    def __init__(
        self,
        database_url: str,
        embedding_model: str,
        embedding_dim: int = 384,
    ) -> None:
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._embedder = EmbeddingProvider(embedding_model)
        self._embedding_dim = embedding_dim

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_result_entry(self, row: Any, match_reason: str) -> RetrievalResultEntry:
        """Build a result entry; enforces citation completeness (FR-005 / QG-12)."""
        item_id = getattr(row, "id", None) or ""
        item_version = getattr(row, "version", None) or ""

        if not item_id or not item_version:
            raise RetrievalError(
                f"Knowledge index returned a row without id or version "
                f"(id={item_id!r}, version={item_version!r}). "
                "This violates FR-005 / QG-12."
            )

        citation = CitationRef(item_id=item_id, item_version=item_version)
        item = KnowledgeItem(
            id=item_id,
            version=item_version,
            kind=row.kind,
            title=row.title,
            full_text=row.full_text,
            metadata=row.metadata or {},
            source_ref=row.source_ref,
            schema_version=row.schema_version,
            active=row.active,
            embedding=[],  # embeddings stripped from response
            indexed_at=row.indexed_at,
        )
        return RetrievalResultEntry(
            item=item,
            citation=citation,
            relevance_score=0.0,
            match_reason=match_reason,
        )

    def _apply_kind_filter(
        self, q: "sa.Select[Any]", kinds: list[KnowledgeType] | None
    ) -> "sa.Select[Any]":
        if kinds:
            q = q.where(knowledge_items.c.kind.in_([k.value for k in kinds]))
        return q

    # ── Vector search ─────────────────────────────────────────────────────────

    async def vector_search(self, query: RetrievalQuery) -> RetrievalResult:
        """Retrieve by vector cosine similarity using pgvector."""
        start = time.perf_counter()
        query_id = str(uuid.uuid4())
        try:
            embedding = self._embedder.embed(query.query_text)
            embedding_literal = f"[{','.join(str(x) for x in embedding)}]"

            base_q = (
                sa.select(knowledge_items)
                .where(knowledge_items.c.active.is_(True))
                .order_by(
                    sa.text(f"embedding <=> '{embedding_literal}'::vector")
                )
                .limit(query.limit)
            )
            base_q = self._apply_kind_filter(base_q, query.kinds)

            async with self._session_factory() as session:
                rows = (await session.execute(base_q)).fetchall()

            entries = []
            for rank, row in enumerate(rows, 1):
                entry = self._build_result_entry(row, "vector")
                entry = entry.model_copy(
                    update={"relevance_score": 1.0 / (_RRF_K + rank)}
                )
                entries.append(entry)

        except Exception as exc:
            raise RetrievalError(f"vector_search failed: {exc}") from exc

        latency = (time.perf_counter() - start) * 1000
        _logger.info(json.dumps({
            "operation": "vector_search", "query_id": query_id,
            "result_count": len(entries), "latency_ms": round(latency, 2),
            "correlation_id": query.correlation_id,
        }))
        return RetrievalResult(items=entries, query_id=query_id, latency_ms=latency)

    # ── Keyword search ─────────────────────────────────────────────────────────

    async def keyword_search(self, query: RetrievalQuery) -> RetrievalResult:
        """Retrieve by PostgreSQL full-text search (ts_rank on tsvector)."""
        start = time.perf_counter()
        query_id = str(uuid.uuid4())
        try:
            base_q = (
                sa.select(knowledge_items)
                .where(knowledge_items.c.active.is_(True))
                .where(
                    sa.text("full_text_search @@ plainto_tsquery('english', :q)")
                )
                .order_by(
                    sa.text("ts_rank(full_text_search, plainto_tsquery('english', :q)) DESC")
                )
                .limit(query.limit)
                .params(q=query.query_text)
            )
            base_q = self._apply_kind_filter(base_q, query.kinds)

            async with self._session_factory() as session:
                rows = (await session.execute(base_q)).fetchall()

            entries = []
            for rank, row in enumerate(rows, 1):
                entry = self._build_result_entry(row, "keyword")
                entry = entry.model_copy(
                    update={"relevance_score": 1.0 / (_RRF_K + rank)}
                )
                entries.append(entry)

        except Exception as exc:
            raise RetrievalError(f"keyword_search failed: {exc}") from exc

        latency = (time.perf_counter() - start) * 1000
        _logger.info(json.dumps({
            "operation": "keyword_search", "query_id": query_id,
            "result_count": len(entries), "latency_ms": round(latency, 2),
            "correlation_id": query.correlation_id,
        }))
        return RetrievalResult(items=entries, query_id=query_id, latency_ms=latency)

    # ── Hybrid search (RRF) ───────────────────────────────────────────────────

    async def hybrid_search(self, query: RetrievalQuery) -> RetrievalResult:
        """Combine vector and keyword results using Reciprocal Rank Fusion."""
        start = time.perf_counter()
        query_id = str(uuid.uuid4())

        vec_result = await self.vector_search(query)
        kw_result = await self.keyword_search(query)

        # Build combined score map: item_id → (score, entry)
        scores: dict[str, tuple[float, RetrievalResultEntry]] = {}
        for rank, entry in enumerate(vec_result.items, 1):
            s = 1.0 / (_RRF_K + rank) * query.vector_weight
            scores[entry.citation.item_id] = (s, entry)

        for rank, entry in enumerate(kw_result.items, 1):
            s = 1.0 / (_RRF_K + rank) * query.keyword_weight
            eid = entry.citation.item_id
            if eid in scores:
                prev_s, prev_entry = scores[eid]
                merged_reason = "vector+keyword"
                scores[eid] = (
                    prev_s + s,
                    prev_entry.model_copy(update={
                        "relevance_score": prev_s + s,
                        "match_reason": merged_reason,
                    }),
                )
            else:
                scores[eid] = (s, entry.model_copy(update={"relevance_score": s}))

        combined = sorted(scores.values(), key=lambda x: x[0], reverse=True)
        entries = [e for _, e in combined[: query.limit]]

        latency = (time.perf_counter() - start) * 1000
        _logger.info(json.dumps({
            "operation": "hybrid_search", "query_id": query_id,
            "result_count": len(entries), "latency_ms": round(latency, 2),
            "correlation_id": query.correlation_id,
        }))
        return RetrievalResult(items=entries, query_id=query_id, latency_ms=latency)

    # ── Relationship traversal ─────────────────────────────────────────────────

    async def relationship_query(self, query: RetrievalQuery) -> RetrievalResult:
        """Return items related to traverse_from_id by relationship_type."""
        start = time.perf_counter()
        query_id = str(uuid.uuid4())

        if not query.traverse_from_id or not query.relationship_type:
            return RetrievalResult(query_id=query_id, latency_ms=0.0)

        try:
            q = (
                sa.select(knowledge_items)
                .join(
                    knowledge_relationships,
                    (knowledge_relationships.c.source_id == query.traverse_from_id)
                    & (knowledge_relationships.c.relationship_type == query.relationship_type)
                    & (knowledge_relationships.c.target_id == knowledge_items.c.id),
                )
                .where(knowledge_items.c.active.is_(True))
                .limit(query.limit)
            )
            q = self._apply_kind_filter(q, query.kinds)

            async with self._session_factory() as session:
                rows = (await session.execute(q)).fetchall()

            entries = []
            for rank, row in enumerate(rows, 1):
                reason = f"relationship:{query.relationship_type}"
                entry = self._build_result_entry(row, reason)
                entry = entry.model_copy(
                    update={"relevance_score": 1.0 / (_RRF_K + rank) * query.relationship_weight}
                )
                entries.append(entry)

        except Exception as exc:
            raise RetrievalError(f"relationship_query failed: {exc}") from exc

        latency = (time.perf_counter() - start) * 1000
        _logger.info(json.dumps({
            "operation": "relationship_query", "query_id": query_id,
            "result_count": len(entries), "latency_ms": round(latency, 2),
            "correlation_id": query.correlation_id,
        }))
        return RetrievalResult(items=entries, query_id=query_id, latency_ms=latency)

    # ── Citation resolution ────────────────────────────────────────────────────

    async def resolve_citation(self, citation: CitationRef) -> KnowledgeItem | None:
        """Resolve a citation to the exact item it describes.

        Passes include_inactive=True so old versions (deactivated during re-index)
        remain resolvable — required by FR-004 and US2 acceptance scenario 2.
        """

        async with self._session_factory() as session:
            q = (
                sa.select(knowledge_items)
                .where(knowledge_items.c.id == citation.item_id)
                .where(knowledge_items.c.version == citation.item_version)
                .limit(1)
            )
            row = (await session.execute(q)).fetchone()

        if row is None:
            return None

        return KnowledgeItem(
            id=row.id,
            version=row.version,
            kind=row.kind,
            title=row.title,
            full_text=row.full_text,
            metadata=row.metadata or {},
            source_ref=row.source_ref,
            schema_version=row.schema_version,
            active=row.active,
            embedding=[],
            indexed_at=row.indexed_at,
        )

    async def dispose(self) -> None:
        await self._engine.dispose()
