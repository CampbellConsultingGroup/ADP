"""Element Technology Tags API — ADP-SPEC-029.

PUT /api/v1/designs/{design_id}/elements/{element_id}/tags

Stores structured technology metadata (technology, vendor, platform, version,
owner_team) and free-form string tags on a design element. Data is written to:
  1. The canonical ArchitectureDescription model (JSONB, source of truth)
  2. The element_technology_tags table (indexed, for portfolio queries)

Every write produces an ART-IX audit entry.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from adp.audit.writer import next_audit_id
from adp.models import AuditEntry, TechnologyMetadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/designs", tags=["tags"])


async def _get_design_store():  # type: ignore[return]
    from adp.api.deps import get_design_store
    return await get_design_store()


def _get_actor(request: Request) -> str:
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


# ── Request / response models ─────────────────────────────────────────────────

class TagsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technology: str | None = Field(default=None, max_length=200)
    vendor: str | None = Field(default=None, max_length=200)
    platform: str | None = Field(default=None, max_length=200)
    version: str | None = Field(default=None, max_length=50)
    owner_team: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, v: list[str]) -> list[str]:
        for tag in v:
            if not tag or not tag.strip():
                raise ValueError("tags must not contain blank strings")
            if len(tag) > 50:
                raise ValueError(f"tag {tag!r} exceeds 50 character limit")
        return v


class TagsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    element_id: str
    design_id: str
    technology: str | None = None
    vendor: str | None = None
    platform: str | None = None
    version: str | None = None
    owner_team: str | None = None
    tags: list[str] = Field(default_factory=list)
    updated_at: datetime


# ── Helpers ───────────────────────────────────────────────────────────────────

def _diff_summary(
    old: TechnologyMetadata | None,
    new: TechnologyMetadata | None,
    tags_changed: bool,
) -> str:
    """Build a human-readable summary of what changed for the audit entry."""
    parts: list[str] = []
    fields = ("technology", "vendor", "platform", "version", "owner_team")
    old_d = {f: getattr(old, f) for f in fields} if old else {f: None for f in fields}
    new_d = {f: getattr(new, f) for f in fields} if new else {f: None for f in fields}
    for field in fields:
        if old_d[field] != new_d[field]:
            parts.append(f"{field}: {old_d[field]!r} → {new_d[field]!r}")
    if tags_changed:
        parts.append("tags updated")
    return "Technology metadata updated" + (f": {'; '.join(parts)}" if parts else "")


async def _upsert_tags_table(
    design_id: str,
    element_id: str,
    metadata: TechnologyMetadata | None,
    tags: list[str],
    session_factory: Any,
) -> None:
    """Fire-and-forget upsert to the element_technology_tags indexed table."""
    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        table = sa.table(
            "element_technology_tags",
            sa.column("design_id"),
            sa.column("element_id"),
            sa.column("technology"),
            sa.column("vendor"),
            sa.column("platform"),
            sa.column("version"),
            sa.column("owner_team"),
            sa.column("free_tags"),
            sa.column("updated_at"),
        )
        values = {
            "design_id": design_id,
            "element_id": element_id,
            "technology": metadata.technology if metadata else None,
            "vendor": metadata.vendor if metadata else None,
            "platform": metadata.platform if metadata else None,
            "version": metadata.version if metadata else None,
            "owner_team": metadata.owner_team if metadata else None,
            "free_tags": json.dumps(tags),
            "updated_at": datetime.now(timezone.utc),
        }
        stmt = pg_insert(table).values(**values).on_conflict_do_update(
            index_elements=["design_id", "element_id"],
            set_={k: v for k, v in values.items() if k not in ("design_id", "element_id")},
        )
        async with session_factory() as session:
            await session.execute(stmt)
            await session.commit()
    except Exception as exc:
        logger.warning("element_technology_tags upsert failed (non-fatal): %s", exc)


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.put("/{design_id}/elements/{element_id}/tags", response_model=TagsResponse)
async def update_element_tags(
    design_id: str,
    element_id: str,
    request_body: TagsRequest,
    raw_request: Request,
    store=Depends(_get_design_store),
) -> TagsResponse:
    """FR-004 to FR-008: Set structured technology metadata + free-form tags on an element.

    Writes to the canonical model (JSONB) and the indexed element_technology_tags table.
    Every write produces an ART-IX audit entry.
    """
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]

    try:
        design = await store.get(design_id)
    except DesignNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")

    element = next((e for e in design.elements if e.id == element_id), None)
    if element is None:
        raise HTTPException(
            status_code=404,
            detail=f"Element {element_id!r} not found in design {design_id!r}",
        )

    # Build new TechnologyMetadata (all None = metadata cleared)
    old_metadata = element.technology_metadata
    old_tags = list(element.tags)

    new_metadata = TechnologyMetadata(
        technology=request_body.technology,
        vendor=request_body.vendor,
        platform=request_body.platform,
        version=request_body.version,
        owner_team=request_body.owner_team,
    )
    # If all fields are None, store as None (cleaner JSON)
    if not any(v is not None for v in (
        new_metadata.technology, new_metadata.vendor, new_metadata.platform,
        new_metadata.version, new_metadata.owner_team
    )):
        new_metadata = None  # type: ignore[assignment]

    tags_changed = request_body.tags != old_tags

    # Update canonical model
    element.technology_metadata = new_metadata
    element.tags = request_body.tags

    # ART-IX: audit entry
    actor = _get_actor(raw_request)
    audit_id = next_audit_id(design)
    summary = _diff_summary(old_metadata, new_metadata, tags_changed)
    design.audit_log.append(AuditEntry(
        id=audit_id,
        actor=actor,
        action="update-element-technology-tags",
        affected_entity=element_id,
        summary=summary[:240],
        timestamp=datetime.now(timezone.utc),
        origin="human",
    ))

    await store.save(design, actor=actor)

    # Upsert indexed table (fire-and-forget; non-fatal on failure)
    try:
        from adp.api.deps import _get_kb_session_factory
        await _upsert_tags_table(
            design_id, element_id, new_metadata,
            request_body.tags, _get_kb_session_factory()
        )
    except Exception as exc:
        logger.warning("element_technology_tags index upsert skipped: %s", exc)

    logger.info(
        "tags.update design=%s element=%s actor=%s",
        design_id, element_id, actor,
    )

    return TagsResponse(
        element_id=element_id,
        design_id=design_id,
        technology=new_metadata.technology if new_metadata else None,
        vendor=new_metadata.vendor if new_metadata else None,
        platform=new_metadata.platform if new_metadata else None,
        version=new_metadata.version if new_metadata else None,
        owner_team=new_metadata.owner_team if new_metadata else None,
        tags=request_body.tags,
        updated_at=datetime.now(timezone.utc),
    )
