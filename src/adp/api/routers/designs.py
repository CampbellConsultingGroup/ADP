"""Design management API — list and create designs (ADP-SPEC-025).

GET  /api/v1/designs            → paginated list of design summaries
POST /api/v1/designs            → create a new blank design
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from adp.audit.writer import next_audit_id
from adp.models import SCHEMA_VERSION, ArchitectureDescription, AuditEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/designs", tags=["designs"])

_MAX_DESIGNS_DEFAULT = 1000


async def _get_design_store():  # type: ignore[return]
    from adp.api.deps import get_design_store
    return await get_design_store()


def _get_actor(request: Request) -> str:
    """Return actor identity: authenticated user if available, else X-Actor header."""
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


# ── Pydantic models ───────────────────────────────────────────────────────────

class DesignSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    description: str | None = None
    element_count: int
    requirement_count: int
    created_at: datetime
    updated_at: datetime


class DesignListResponse(BaseModel):
    designs: list[DesignSummary]
    total: int
    page: int
    page_size: int


class CreateDesignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None

    @field_validator("title")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v.strip()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=DesignListResponse, status_code=200)
async def list_designs(
    page: int = 1,
    page_size: int = 50,
    store=Depends(_get_design_store),
) -> DesignListResponse:
    """FR-001/002: List all designs with summary metadata."""
    designs = await store.list_all(page=page, page_size=page_size)
    total = await store.count_all()

    summaries = [
        DesignSummary(
            id=d.id,
            title=d.title,
            description=d.description,
            element_count=len(d.elements),
            requirement_count=len(d.requirements),
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in designs
    ]
    return DesignListResponse(
        designs=summaries,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ArchitectureDescription, status_code=201)
async def create_design(
    request_body: CreateDesignRequest,
    raw_request: Request,
    store=Depends(_get_design_store),
) -> ArchitectureDescription:
    """FR-003: Create a blank design with an auto-generated DSN-NNN id.

    ART-IX: writes a design-created audit entry.
    Returns 429 if ADP_MAX_DESIGNS limit is reached.
    """
    max_designs = int(os.environ.get("ADP_MAX_DESIGNS", str(_MAX_DESIGNS_DEFAULT)))
    total = await store.count_all()
    if total >= max_designs:
        raise HTTPException(
            status_code=429,
            detail=f"Design limit reached ({max_designs}). Delete unused designs to create new ones.",  # noqa: E501
        )

    design_id = await store.next_design_id()
    actor = _get_actor(raw_request)
    now = datetime.now(timezone.utc)

    design = ArchitectureDescription(
        schema_version=SCHEMA_VERSION,
        id=design_id,
        title=request_body.title,
        description=request_body.description,
        created_at=now,
        updated_at=now,
    )

    # ART-IX: audit entry for design creation
    audit_id = next_audit_id(design)
    design.audit_log.append(AuditEntry(
        id=audit_id,
        actor=actor,
        action="design-created",
        affected_entity=design_id,
        summary=f"Design {design_id!r} created: {request_body.title[:60]}",
        timestamp=now,
        origin="human",
    ))

    await store.save(design, actor=actor)

    logger.info("designs.create id=%s title=%r actor=%s", design_id, request_body.title, actor)
    return design
