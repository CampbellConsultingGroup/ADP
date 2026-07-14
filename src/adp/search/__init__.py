"""Unified hybrid search over registry text (ADP-b6o).

Keyword (PostgreSQL full-text) + vector (pgvector) retrieval fused with
Reciprocal Rank Fusion, over a single polymorphic ``searchable_items`` table.
"""

from adp.search.index import (
    ENTITY_BUSINESS_CAPABILITY,
    ENTITY_TECHNICAL_CAPABILITY,
    SearchHit,
    SearchIndex,
    build_text,
    default_index,
    index_entity,
    rrf_fuse,
    unindex_entity,
)

__all__ = [
    "SearchIndex",
    "SearchHit",
    "ENTITY_BUSINESS_CAPABILITY",
    "ENTITY_TECHNICAL_CAPABILITY",
    "build_text",
    "default_index",
    "index_entity",
    "rrf_fuse",
    "unindex_entity",
]
