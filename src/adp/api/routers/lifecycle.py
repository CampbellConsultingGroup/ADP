"""Design Lifecycle Management API — ADP-SPEC-030.

PATCH /api/v1/designs/{design_id}/lifecycle

Transitions a design through its lifecycle. Enforces the permitted transition
graph (FR-004), auto-sets dates on relevant transitions (FR-005), and writes an
ART-IX audit entry for every transition (FR-006).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from adp.audit.writer import next_audit_id
from adp.models import AuditEntry, LifecycleStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/designs", tags=["lifecycle"])

# ── Transition graph (FR-004) ─────────────────────────────────────────────────

VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft":          {"proposed"},
    "proposed":       {"current", "draft"},
    "current":        {"deprecated"},
    "deprecated":     {"decommissioned", "current"},
    "decommissioned": set(),
}
# "Reset to Draft" is always permitted from any non-draft status (ART-VIII escape hatch)


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

class LifecycleTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LifecycleStatus
    note: str | None = Field(default=None, max_length=500)
    # Optional date overrides (FR-005 — override auto-set or set review_due)
    proposed_date: datetime | None = None
    current_since: datetime | None = None
    review_due: datetime | None = None
    retirement_date: datetime | None = None


class LifecycleResponse(BaseModel):
    design_id: str
    lifecycle_status: str
    proposed_date: datetime | None = None
    current_since: datetime | None = None
    review_due: datetime | None = None
    retirement_date: datetime | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _apply_auto_dates(
    design_any: Any,
    new_status: LifecycleStatus,
    req: LifecycleTransitionRequest,
) -> None:
    """Auto-set relevant date fields on transition (FR-005).

    Only sets a field if it is currently None AND no override was provided.
    review_due is never auto-set — it requires explicit input.
    """
    now = datetime.now(timezone.utc)

    if new_status == LifecycleStatus.PROPOSED:
        design_any.proposed_date = req.proposed_date or design_any.proposed_date or now
    elif new_status == LifecycleStatus.CURRENT:
        design_any.current_since = req.current_since or design_any.current_since or now
    elif new_status == LifecycleStatus.DECOMMISSIONED:
        design_any.retirement_date = req.retirement_date or design_any.retirement_date or now

    # review_due override can always be applied regardless of transition
    if req.review_due is not None:
        design_any.review_due = req.review_due


# ── Endpoint ──────────────────────────────────────────────────────────────────

from typing import Any  # noqa: E402 — placed after helpers to satisfy ruff import order


@router.patch("/{design_id}/lifecycle", response_model=LifecycleResponse)
async def transition_lifecycle(
    design_id: str,
    request_body: LifecycleTransitionRequest,
    raw_request: Request,
    store=Depends(_get_design_store),
) -> LifecycleResponse:
    """PATCH lifecycle state with transition-graph enforcement and audit trail (ADP-SPEC-030).

    ART-VIII: explicit human action required for every transition.
    ART-IX: audit entry written for every transition.
    """
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]

    try:
        design = await store.get(design_id)
    except DesignNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")

    old_status = design.lifecycle_status
    new_status = request_body.status

    # Validate transition (FR-004)
    # "Reset to Draft" is always permitted as an escape hatch
    is_reset_to_draft = (
        new_status == LifecycleStatus.DRAFT and old_status != LifecycleStatus.DRAFT
    )
    allowed = VALID_TRANSITIONS.get(old_status.value, set())
    if not is_reset_to_draft and new_status.value not in allowed:
        valid = sorted(allowed | {"draft"})
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot transition from '{old_status.value}' to '{new_status.value}'. "
                f"Valid next states from '{old_status.value}': {valid}"
            ),
        )

    # Apply auto-dates (FR-005)
    _apply_auto_dates(design, new_status, request_body)

    # Update status
    design.lifecycle_status = new_status
    design.updated_at = datetime.now(timezone.utc)

    # ART-IX: audit entry (FR-006)
    actor = _get_actor(raw_request)
    audit_id = next_audit_id(design)
    summary_parts = [f"Lifecycle: {old_status.value} → {new_status.value}"]
    if is_reset_to_draft:
        summary_parts.append("[reset]")
    if request_body.note:
        summary_parts.append(f"Note: {request_body.note}")
    design.audit_log.append(AuditEntry(
        id=audit_id,
        actor=actor,
        action="lifecycle-transition",
        affected_entity=design_id,
        summary=" | ".join(summary_parts)[:240],
        timestamp=datetime.now(timezone.utc),
        origin="human",
    ))

    await store.save(design, actor=actor)

    logger.info(
        "lifecycle.transition design=%s %s → %s actor=%s",
        design_id, old_status.value, new_status.value, actor,
    )

    return LifecycleResponse(
        design_id=design_id,
        lifecycle_status=design.lifecycle_status.value,
        proposed_date=design.proposed_date,
        current_since=design.current_since,
        review_due=design.review_due,
        retirement_date=design.retirement_date,
    )
