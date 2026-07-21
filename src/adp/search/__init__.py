"""Unified hybrid search over registry text (ADP-b6o).

Keyword (PostgreSQL full-text) + vector (pgvector) retrieval fused with
Reciprocal Rank Fusion, over a single polymorphic ``searchable_items`` table.
"""

from adp.search.index import (
    ENTITY_APPLICATION,
    ENTITY_BUSINESS_CAPABILITY,
    ENTITY_BUSINESS_DOMAIN,
    ENTITY_TECHNICAL_CAPABILITY,
    ENTITY_VALUE_STREAM,
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
    "ENTITY_APPLICATION",
    "ENTITY_BUSINESS_CAPABILITY",
    "ENTITY_BUSINESS_DOMAIN",
    "ENTITY_TECHNICAL_CAPABILITY",
    "ENTITY_VALUE_STREAM",
    "build_text",
    "default_index",
    "index_entity",
    "rrf_fuse",
    "unindex_entity",
]
