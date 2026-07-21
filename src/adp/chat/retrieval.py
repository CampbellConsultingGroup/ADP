"""Semantic/keyword retrieval leg for the AI Chat Assistant (ADP-SPEC-041).

Thin wrapper over the existing adp.search hybrid index (ADP-b6o) -- see
research D4/D5 for why this, not adp.knowledge (curated organizational
knowledge, not live portfolio data) or a bespoke index.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from adp.search.index import (
    ENTITY_APPLICATION,
    ENTITY_BUSINESS_CAPABILITY,
    ENTITY_BUSINESS_DOMAIN,
    ENTITY_TECHNICAL_CAPABILITY,
    ENTITY_VALUE_STREAM,
    SearchHit,
    default_index,
)

# US2 (research D4): now covers every entity type adp.search indexes --
# applications/value-streams/business-domains were wired up in
# adp.application.store/adp.business.store alongside this change.
DEFAULT_ENTITY_TYPES: list[str] = [
    ENTITY_BUSINESS_CAPABILITY,
    ENTITY_TECHNICAL_CAPABILITY,
    ENTITY_APPLICATION,
    ENTITY_VALUE_STREAM,
    ENTITY_BUSINESS_DOMAIN,
]


async def retrieve_context(
    query_text: str,
    session: AsyncSession,
    *,
    entity_types: list[str] | None = None,
    limit: int = 5,
) -> list[SearchHit]:
    return await default_index().hybrid_search(
        query_text, session, entity_types=entity_types or DEFAULT_ENTITY_TYPES, limit=limit,
    )
