"""Governance Reporting API — ADP-SPEC-032.

Read-only endpoints. No new DB tables — all data from existing tables.

Endpoints:
  GET /api/v1/governance/status           — per-design audit/reasoning aggregation
  GET /api/v1/governance/exceptions       — FAIL/ADVISORY findings from design JSONB
  GET /api/v1/governance/activity         — paginated audit log with date-range filter
  GET /api/v1/governance/activity/export  — CSV export of filtered activity
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timezone
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from adp.api.deps import get_kb_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/governance", tags=["governance"])


async def _get_design_store():  # type: ignore[return]
    from adp.api.deps import get_design_store
    return await get_design_store()


# ── Response models ────────────────────────────────────────────────────────────

class DesignGovernanceRecord(BaseModel):
    design_id: str
    title: str
    lifecycle_status: str
    last_activity: datetime | None
    audit_count: int
    accepted_recommendations: int
    reasoning_record_count: int


class GovernanceStatusResponse(BaseModel):
    designs: list[DesignGovernanceRecord]
    total: int


class ComplianceExceptionRecord(BaseModel):
    design_id: str
    title: str
    finding_id: str
    finding_summary: str
    severity: Literal["FAIL", "ADVISORY"]
    source: str | None
    recorded_at: datetime


class ComplianceExceptionsResponse(BaseModel):
    exceptions: list[ComplianceExceptionRecord]
    total: int


class AuditActivityEntry(BaseModel):
    id: str
    design_id: str
    design_title: str
    actor: str
    action: str
    affected_entity: str
    summary: str
    timestamp: datetime
    origin: str


class ActivityFeedResponse(BaseModel):
    entries: list[AuditActivityEntry]
    total: int
    page: int
    page_size: int
    from_date: str
    to_date: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _validate_date_range(from_date: date, to_date: date) -> None:
    """Raise 422 if date range exceeds 90 days."""
    if (to_date - from_date).days > 90:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 90 days.")


def _activity_where(action: str | None, actor: str | None) -> tuple[str, dict]:
    """Build WHERE filter clauses for optional action/actor params.

    asyncpg cannot infer the type of a NULL named param used in a comparison
    expression, and the '::text' cast suffix confuses SQLAlchemy's text()
    parameter parser. We avoid both issues by only appending filter clauses
    when the caller actually provides values.
    """
    clauses: list[str] = []
    extra: dict = {}
    if action is not None:
        clauses.append("ae.action = :action")
        extra["action"] = action
    if actor is not None:
        clauses.append("ae.actor = :actor")
        extra["actor"] = actor
    suffix = (" AND " + " AND ".join(clauses)) if clauses else ""
    return suffix, extra


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=GovernanceStatusResponse)
async def get_governance_status(
    session: AsyncSession = Depends(get_kb_session),
) -> GovernanceStatusResponse:
    """Per-design governance summary: last activity, audit count, accepted recs, reasoning."""
    result = await session.execute(
        sa.text(
            """
            SELECT
                d.id,
                d.title,
                d.lifecycle_status,
                MAX(ae.timestamp) AS last_activity,
                COUNT(ae.id) AS audit_count,
                COUNT(CASE WHEN ae.action = 'accept-recommendation' THEN 1 END) AS accepted_recs,
                COUNT(DISTINCT lrl.id) AS reasoning_count
            FROM designs d
            LEFT JOIN audit_entries ae ON ae.design_id = d.id
            LEFT JOIN operations op ON op.design_id = d.id
            LEFT JOIN llm_reasoning_log lrl ON lrl.operation_id = op.id
            GROUP BY d.id, d.title, d.lifecycle_status
            ORDER BY MAX(ae.timestamp) DESC NULLS LAST
            """
        )
    )
    rows = result.fetchall()
    records = [
        DesignGovernanceRecord(
            design_id=r.id,
            title=r.title,
            lifecycle_status=r.lifecycle_status,
            last_activity=r.last_activity,
            audit_count=r.audit_count,
            accepted_recommendations=r.accepted_recs,
            reasoning_record_count=r.reasoning_count,
        )
        for r in rows
    ]
    return GovernanceStatusResponse(designs=records, total=len(records))


@router.get("/exceptions", response_model=ComplianceExceptionsResponse)
async def get_compliance_exceptions(
    store=Depends(_get_design_store),
) -> ComplianceExceptionsResponse:
    """FAIL and ADVISORY findings extracted from canonical design JSONB."""
    designs = await store.list_all()
    exceptions: list[ComplianceExceptionRecord] = []

    for design in designs:
        for finding in getattr(design, "findings", []):
            if finding.severity not in ("warning", "critical"):
                continue
            severity: Literal["FAIL", "ADVISORY"] = (
                "FAIL" if finding.severity == "critical" else "ADVISORY"
            )
            exceptions.append(
                ComplianceExceptionRecord(
                    design_id=design.id,
                    title=design.title,
                    finding_id=finding.id,
                    finding_summary=finding.summary,
                    severity=severity,
                    source=finding.source,
                    recorded_at=design.updated_at,
                )
            )

    # Sort: FAIL first, then by recorded_at descending
    exceptions.sort(key=lambda e: (0 if e.severity == "FAIL" else 1, -e.recorded_at.timestamp()))
    return ComplianceExceptionsResponse(exceptions=exceptions, total=len(exceptions))


@router.get("/activity/export")
async def export_activity_csv(
    from_date: date = Query(...),
    to_date: date = Query(...),
    action: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_kb_session),
) -> StreamingResponse:
    """CSV export of audit entries within the date range (max 90 days)."""
    _validate_date_range(from_date, to_date)

    filter_sql, filter_params = _activity_where(action, actor)
    params: dict = {
        "from_dt": datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc),
        "to_dt": datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc),
        **filter_params,
    }
    result = await session.execute(
        sa.text(
            f"""
            SELECT ae.id, ae.design_id, d.title AS design_title,
                   ae.actor, ae.action, ae.affected_entity,
                   ae.summary, ae.timestamp, ae.origin
            FROM audit_entries ae
            JOIN designs d ON d.id = ae.design_id
            WHERE ae.timestamp BETWEEN :from_dt AND :to_dt{filter_sql}
            ORDER BY ae.timestamp DESC
            """  # nosec B608 - action/actor clauses are hardcoded; values bound as params
        ),
        params,
    )
    rows = result.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["id", "design_id", "design_title", "actor", "action",
         "affected_entity", "summary", "timestamp", "origin"]
    )
    for r in rows:
        writer.writerow([
            r.id, r.design_id, r.design_title, r.actor, r.action,
            r.affected_entity, r.summary,
            r.timestamp.isoformat() if r.timestamp else "",
            r.origin,
        ])

    filename = f"adp-audit-{from_date}-{to_date}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/activity", response_model=ActivityFeedResponse)
async def get_activity_feed(
    from_date: date = Query(...),
    to_date: date = Query(...),
    action: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_kb_session),
) -> ActivityFeedResponse:
    """Paginated audit log filtered by date range, action, and actor."""
    _validate_date_range(from_date, to_date)

    from_dt = datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    to_dt = datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc)
    offset = (page - 1) * page_size

    filter_sql, filter_params = _activity_where(action, actor)
    base_params: dict = {"from_dt": from_dt, "to_dt": to_dt, **filter_params}

    count_result = await session.execute(
        sa.text(
            f"""
            SELECT COUNT(*) AS total
            FROM audit_entries ae
            WHERE ae.timestamp BETWEEN :from_dt AND :to_dt{filter_sql}
            """  # nosec B608 - action/actor clauses are hardcoded; values bound as params
        ),
        base_params,
    )
    total = count_result.scalar_one()

    result = await session.execute(
        sa.text(
            f"""
            SELECT ae.id, ae.design_id, d.title AS design_title,
                   ae.actor, ae.action, ae.affected_entity,
                   ae.summary, ae.timestamp, ae.origin
            FROM audit_entries ae
            JOIN designs d ON d.id = ae.design_id
            WHERE ae.timestamp BETWEEN :from_dt AND :to_dt{filter_sql}
            ORDER BY ae.timestamp DESC
            LIMIT :limit OFFSET :offset
            """  # nosec B608 - action/actor clauses are hardcoded; values bound as params
        ),
        {**base_params, "limit": page_size, "offset": offset},
    )
    rows = result.fetchall()

    entries = [
        AuditActivityEntry(
            id=r.id,
            design_id=r.design_id,
            design_title=r.design_title,
            actor=r.actor,
            action=r.action,
            affected_entity=r.affected_entity,
            summary=r.summary,
            timestamp=r.timestamp,
            origin=r.origin,
        )
        for r in rows
    ]

    return ActivityFeedResponse(
        entries=entries,
        total=total,
        page=page,
        page_size=page_size,
        from_date=str(from_date),
        to_date=str(to_date),
    )
