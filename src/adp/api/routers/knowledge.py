"""Knowledge Base CRUD HTTP API — ADP-SPEC-020.

Exposes five endpoints for browsing, creating, updating, and soft-deleting
knowledge items. Embeddings are regenerated server-side on every write using
the same EmbeddingProvider used during seeding.

ART-V: full_text capped at 10,000 chars; source_ref validated non-empty.
ART-VII: embeddings always regenerated on write to keep grounding quality current.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from adp.api.deps import get_kb_session
from adp.knowledge.index import KnowledgeIndex, knowledge_items
from adp.knowledge.schema import KnowledgeItem, KnowledgeType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

# ── Lazy embedder singleton ───────────────────────────────────────────────────

_embedder: Any = None


def _get_embedder() -> Any:
    global _embedder
    if _embedder is None:
        from adp.knowledge.embedder import EmbeddingProvider
        _embedder = EmbeddingProvider("all-MiniLM-L6-v2")
    return _embedder


def _embed(title: str, full_text: str) -> list[float]:
    """Generate a 384-dim embedding; fall back to zero vector on failure."""
    try:
        text = f"{title}\n{full_text}"
        return _get_embedder().embed(text)
    except Exception as exc:
        logger.warning("Embedding generation failed, using zero vector: %s", exc)
        return [0.0] * 384


# ── Pydantic models ───────────────────────────────────────────────────────────

class KnowledgeItemSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    version: str
    kind: str
    title: str
    source_ref: str
    metadata: dict = Field(default_factory=dict)
    indexed_at: datetime | None = None


class KnowledgeItemDetail(KnowledgeItemSummary):
    full_text: str


class KnowledgeItemListResponse(BaseModel):
    items: list[KnowledgeItemSummary]
    total: int


class KnowledgeItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    version: str = "1.0.0"
    kind: KnowledgeType
    title: str = Field(min_length=1, max_length=200)
    full_text: str = Field(min_length=1, max_length=10_000)
    source_ref: str = Field(min_length=1)
    metadata: dict = Field(default_factory=dict)

    @field_validator("title", "source_ref")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field must not be blank")
        return v

    @field_validator("full_text")
    @classmethod
    def _full_text_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("full_text must not be blank")
        return v


class KnowledgeItemUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str | None = None
    kind: KnowledgeType | None = None
    title: str | None = Field(default=None, max_length=200)
    full_text: str | None = Field(default=None, max_length=10_000)
    source_ref: str | None = None
    metadata: dict | None = None

    @field_validator("title", "source_ref", mode="before")
    @classmethod
    def _non_empty_if_set(cls, v: str | None) -> str | None:
        if v is not None and not str(v).strip():
            raise ValueError("field must not be blank when provided")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_summary(row: Any) -> KnowledgeItemSummary:
    return KnowledgeItemSummary(
        id=row.id,
        version=row.version,
        kind=row.kind,
        title=row.title,
        source_ref=row.source_ref,
        metadata=row.metadata or {},
        indexed_at=row.indexed_at,
    )


def _row_to_detail(row: Any) -> KnowledgeItemDetail:
    return KnowledgeItemDetail(
        id=row.id,
        version=row.version,
        kind=row.kind,
        title=row.title,
        full_text=row.full_text,
        source_ref=row.source_ref,
        metadata=row.metadata or {},
        indexed_at=row.indexed_at,
    )


async def _fetch_active_row(item_id: str, session: AsyncSession) -> Any:
    row = (await session.execute(
        sa.select(knowledge_items).where(
            knowledge_items.c.id == item_id,
            knowledge_items.c.active.is_(True),
        )
    )).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Knowledge item {item_id!r} not found")
    return row


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=KnowledgeItemListResponse, status_code=200)
async def list_knowledge_items(
    session: AsyncSession = Depends(get_kb_session),
) -> KnowledgeItemListResponse:
    """FR-001: List all active knowledge items (summary, no full_text)."""
    rows = (await session.execute(
        sa.select(knowledge_items)
        .where(knowledge_items.c.active.is_(True))
        .order_by(knowledge_items.c.kind, knowledge_items.c.title)
    )).fetchall()
    items = [_row_to_summary(r) for r in rows]
    return KnowledgeItemListResponse(items=items, total=len(items))


@router.get("/{item_id}", response_model=KnowledgeItemDetail, status_code=200)
async def get_knowledge_item(
    item_id: str,
    session: AsyncSession = Depends(get_kb_session),
) -> KnowledgeItemDetail:
    """FR-002: Return a single item's full details including full_text."""
    row = await _fetch_active_row(item_id, session)
    return _row_to_detail(row)


@router.post("", response_model=KnowledgeItemSummary, status_code=201)
async def create_knowledge_item(
    request: KnowledgeItemCreateRequest,
    session: AsyncSession = Depends(get_kb_session),
) -> KnowledgeItemSummary:
    """FR-003: Create a new knowledge item with a freshly generated embedding."""
    item_id = request.id or str(uuid.uuid4())
    embedding = _embed(request.title, request.full_text)

    item = KnowledgeItem(
        id=item_id,
        version=request.version,
        kind=request.kind,
        title=request.title,
        full_text=request.full_text,
        source_ref=request.source_ref,
        metadata=request.metadata,
    )
    idx = KnowledgeIndex(session_factory=None)
    await idx.upsert_item(item, embedding, session)
    await session.commit()

    row = await _fetch_active_row(item_id, session)
    return _row_to_summary(row)


@router.put("/{item_id}", response_model=KnowledgeItemSummary, status_code=200)
async def update_knowledge_item(
    item_id: str,
    request: KnowledgeItemUpdateRequest,
    session: AsyncSession = Depends(get_kb_session),
) -> KnowledgeItemSummary:
    """FR-004: Update a knowledge item; re-embed if title or full_text changed."""
    row = await _fetch_active_row(item_id, session)

    new_title = request.title if request.title is not None else row.title
    new_full_text = request.full_text if request.full_text is not None else row.full_text
    need_reembed = (request.title is not None or request.full_text is not None)

    if need_reembed:
        embedding = _embed(new_title, new_full_text)
    else:
        embedding = list(row.embedding or [0.0] * 384)

    item = KnowledgeItem(
        id=item_id,
        version=request.version or row.version,
        kind=KnowledgeType(request.kind.value if request.kind else row.kind),
        title=new_title,
        full_text=new_full_text,
        source_ref=request.source_ref if request.source_ref is not None else row.source_ref,
        metadata=request.metadata if request.metadata is not None else (row.metadata or {}),
    )
    idx = KnowledgeIndex(session_factory=None)
    await idx.upsert_item(item, embedding, session)
    await session.commit()

    updated_row = await _fetch_active_row(item_id, session)
    return _row_to_summary(updated_row)


@router.delete("/{item_id}", status_code=204)
async def delete_knowledge_item(
    item_id: str,
    session: AsyncSession = Depends(get_kb_session),
) -> None:
    """FR-005: Soft-delete a knowledge item (sets active=false)."""
    await _fetch_active_row(item_id, session)  # raises 404 if not found
    idx = KnowledgeIndex(session_factory=None)
    await idx.mark_inactive([item_id], session)
    await session.commit()
