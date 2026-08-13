"""Design management API — list and create designs (ADP-SPEC-025).

GET  /api/v1/designs            → paginated list of design summaries
POST /api/v1/designs            → create a new blank design
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from adp.audit.writer import next_audit_id
from adp.models import SCHEMA_VERSION, ArchitectureDescription, AuditEntry
from adp.strategy.models import StrategicObjectiveListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/designs", tags=["designs"])

_MAX_DESIGNS_DEFAULT = 1000


async def _get_design_store():  # type: ignore[return]
    from adp.api.deps import get_design_store
    return await get_design_store()


async def _get_strategy_session():
    """A strategy-scoped session (ADP-d8u.2), used only by the reverse-lookup
    GET /designs/{id}/objectives endpoint below."""
    from adp.strategy import store as sstore

    factory = sstore._get_session_factory()
    async with factory() as session:
        yield session


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
    # ADP-SPEC-030: lifecycle fields
    lifecycle_status: str = "draft"
    proposed_date: datetime | None = None
    current_since: datetime | None = None
    review_due: datetime | None = None
    retirement_date: datetime | None = None
    overdue_review: bool = False  # computed: current + review_due in the past


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
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None, description="Filter by lifecycle status"),
    store=Depends(_get_design_store),
) -> DesignListResponse:
    """FR-001/002: List all designs with summary metadata. Optionally filter by lifecycle status."""
    now = datetime.now(timezone.utc)
    all_designs = await store.list_all(page=page, page_size=page_size, status=status)
    total = await store.count_all(status=status)

    summaries = [
        DesignSummary(
            id=d.id,
            title=d.title,
            description=d.description,
            element_count=len(d.elements),
            requirement_count=len(d.requirements),
            created_at=d.created_at,
            updated_at=d.updated_at,
            lifecycle_status=d.lifecycle_status.value,
            proposed_date=d.proposed_date,
            current_since=d.current_since,
            review_due=d.review_due,
            retirement_date=d.retirement_date,
            overdue_review=(
                d.lifecycle_status.value == "current"
                and d.review_due is not None
                and d.review_due < now
            ),
        )
        for d in all_designs
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


@router.get("/{design_id}/objectives", response_model=StrategicObjectiveListResponse)
async def get_design_objectives(
    design_id: str,
    store=Depends(_get_design_store),
    strategy_session: AsyncSession = Depends(_get_strategy_session),
):
    """ADP-d8u.2: reverse lookup -- every strategic objective this design
    realizes. Mirrors src/adp/api/routers/elements.py's own
    `_get_design_or_404` pattern for the design-existence check (store.get()
    + catch DesignNotFoundError), rather than adp.strategy.store's lighter-
    weight mirror -- that pattern is specifically for adp.strategy's own
    forward-link existence check (research.md Decision 2), not this
    endpoint's, which already has a real DesignStore on hand."""
    from adp.store.store import DesignNotFoundError

    try:
        await store.get(design_id)
    except DesignNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")

    from adp.strategy import store as sstore

    return await sstore.list_objectives_for_design(design_id, strategy_session)
