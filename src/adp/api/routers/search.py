"""Hybrid search API over registry text (ADP-b6o).

Phase 1 exposes search over business + technical capabilities. The underlying
index is polymorphic, so additional entity types (value streams, domains) become
searchable here without an API change.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from adp.business import store as bstore
from adp.search import (
    ENTITY_BUSINESS_CAPABILITY,
    ENTITY_TECHNICAL_CAPABILITY,
    default_index,
)

router = APIRouter(prefix="/api/v1/search", tags=["search"])

# Entity types searchable in phase 1.
_CAPABILITY_TYPES = [ENTITY_BUSINESS_CAPABILITY, ENTITY_TECHNICAL_CAPABILITY]


class SearchHitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_id: str
    text: str
    score: float


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    hits: list[SearchHitResponse]
    total: int


async def _get_session():
    factory = bstore._get_session_factory()
    async with factory() as session:
        yield session


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Search query text"),
    entity_types: str | None = Query(
        None,
        description="Comma-separated entity types to search; defaults to capabilities.",
    ),
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(_get_session),
) -> SearchResponse:
    """Hybrid (keyword + vector) search over indexed registry text."""
    types = (
        [t.strip() for t in entity_types.split(",") if t.strip()]
        if entity_types
        else _CAPABILITY_TYPES
    )
    hits = await default_index().hybrid_search(
        q, session, entity_types=types, limit=limit
    )
    return SearchResponse(
        query=q,
        hits=[
            SearchHitResponse(
                entity_type=h.entity_type,
                entity_id=h.entity_id,
                text=h.text,
                score=round(h.score, 6),
            )
            for h in hits
        ],
        total=len(hits),
    )
