"""Knowledge Base CRUD HTTP API — ADP-SPEC-020.

Exposes five endpoints for browsing, creating, updating, and soft-deleting
knowledge items. Embeddings are regenerated server-side on every write using
the same EmbeddingProvider used during seeding.

ART-V: full_text capped at 10,000 chars; source_ref validated non-empty.
ART-VII: embeddings always regenerated on write to keep grounding quality current.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from adp.api.deps import get_kb_session
from adp.compliance.models import ControlMappingListResponse
from adp.knowledge.index import KnowledgeIndex, knowledge_items
from adp.knowledge.schema import KnowledgeItem, KnowledgeType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


async def _get_compliance_session():
    """A compliance-scoped session (COMPLY-02 research.md D7), used only by the
    reverse-lookup GET /knowledge/{id}/compliance-mappings endpoint below."""
    from adp.compliance import store as cstore

    factory = cstore._get_session_factory()
    async with factory() as session:
        yield session

# ── Embedding ────────────────────────────────────────────────────────────────


def _embed(title: str, full_text: str) -> list[float]:
    """Generate a 384-dim embedding; fall back to zero vector on failure.

    Delegates to the shared knowledge write-path helper (935 research D6); kept as a module
    function so tests can patch it.
    """
    from adp.knowledge.embedder import embed_or_zero

    return embed_or_zero(title, full_text)


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


# ── Registry-owned items (935-pattern-registry FR-015, research.md D8) ─────────

_PATTERN_PREFIX = "adp-pattern:"
_PATTERN_MANAGER = "pattern-registry"


def _metadata_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        import json

        try:
            parsed = json.loads(raw)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _is_registry_managed(item_id: str, metadata: Any) -> bool:
    return item_id.startswith(_PATTERN_PREFIX) or (
        _metadata_dict(metadata).get("managed_by") == _PATTERN_MANAGER
    )


def _reject_if_registry_managed(row: Any) -> None:
    """A pattern projection is derived from the governed current version; change the pattern."""
    if _is_registry_managed(row.id, row.metadata):
        key = _metadata_dict(row.metadata).get("pattern_key") or row.id[len(_PATTERN_PREFIX):]
        raise HTTPException(
            status_code=409,
            detail=(
                f"Knowledge item {row.id!r} is managed by the Patterns registry; change the "
                f"pattern '{key}' (and promote a new version) instead"
            ),
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
    # ADP-blp.23: only the summary columns. Selecting whole rows also pulled every item's
    # full_text and its 384-number embedding, none of which the list returns.
    c = knowledge_items.c
    rows = (await session.execute(
        sa.select(c.id, c.version, c.kind, c.title, c.source_ref, c.metadata, c.indexed_at)
        .where(c.active.is_(True))
        .order_by(c.kind, c.title)
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


@router.get("/{item_id}/compliance-mappings", response_model=ControlMappingListResponse)
async def get_knowledge_item_compliance_mappings(
    item_id: str,
    session: AsyncSession = Depends(get_kb_session),
    compliance_session: AsyncSession = Depends(_get_compliance_session),
) -> ControlMappingListResponse:
    """Reverse lookup (COMPLY-02 FR-012): every Control mapped to this knowledge item
    (scoped to target_type == "pattern" mappings, since only kind == "pattern" items can be
    mapped -- research.md D5). Ungated -- matches every other knowledge item read
    (research.md D2 only gates Application-targeted reads)."""
    await _fetch_active_row(item_id, session)

    from adp.compliance import store as cstore

    items = await cstore.list_mappings_for_pattern(item_id, compliance_session)
    return ControlMappingListResponse(items=items, total=len(items))


@router.post("", response_model=KnowledgeItemSummary, status_code=201)
async def create_knowledge_item(
    request: KnowledgeItemCreateRequest,
    session: AsyncSession = Depends(get_kb_session),
) -> KnowledgeItemSummary:
    """FR-003: Create a new knowledge item with a freshly generated embedding."""
    item_id = request.id or str(uuid.uuid4())
    if _is_registry_managed(item_id, request.metadata):
        raise HTTPException(
            status_code=422,
            detail="Pattern projections are created only by the Patterns registry",
        )
    # In a worker thread: encoding is CPU-bound (ADP-blp.16).
    embedding = await asyncio.to_thread(_embed, request.title, request.full_text)

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
    _reject_if_registry_managed(row)
    if request.metadata is not None and _is_registry_managed("", request.metadata):
        raise HTTPException(
            status_code=422, detail="managed_by is reserved for the Patterns registry"
        )

    new_title = request.title if request.title is not None else row.title
    new_full_text = request.full_text if request.full_text is not None else row.full_text
    need_reembed = (request.title is not None or request.full_text is not None)

    if need_reembed:
        embedding = await asyncio.to_thread(_embed, new_title, new_full_text)
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
    row = await _fetch_active_row(item_id, session)  # raises 404 if not found
    _reject_if_registry_managed(row)
    idx = KnowledgeIndex(session_factory=None)
    await idx.mark_inactive([item_id], session)
    await session.commit()
