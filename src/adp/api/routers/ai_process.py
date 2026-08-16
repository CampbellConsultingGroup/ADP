"""AI Process Reporting API — ADP-3ei.

Read-only endpoints over the durable AI-process capture tables (intake
submissions/proposals, recommendation runs/options, validation
verdicts/findings, llm_reasoning_log), all keyed by design_id. No new UI yet
(per the confirmed scope) — this is the backend surface a future
visualization/dashboard would call.

  GET /api/v1/designs/{design_id}/ai-process           — per-design summary
  GET /api/v1/designs/{design_id}/ai-process/timeline   — paginated event feed
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from adp.api.deps import get_kb_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/designs", tags=["ai-process"])


# ── Response models ────────────────────────────────────────────────────────────

class IntakeSubmissionSummary(BaseModel):
    submission_id: str
    operation_id: str
    mode: str
    model_id: str | None
    source_char_count: int
    source_excerpt: str
    business_problem: str | None
    desired_outcome: str | None
    submitted_by: str
    submitted_at: str


class IntakeSection(BaseModel):
    submission_count: int
    proposal_count: int
    confirmed_count: int
    edited_confirmed_count: int
    rejected_count: int
    pending_count: int
    submissions: list[IntakeSubmissionSummary]


class RecommendationOptionSummary(BaseModel):
    option_id: str
    title: str
    status: str
    rank: int
    advisory: bool
    decided_by: str | None
    decision_reason: str | None


class RecommendationRunSummary(BaseModel):
    run_id: str
    model_id: str | None
    status: str
    option_count: int
    started_at: str
    options: list[RecommendationOptionSummary]


class RecommendationSection(BaseModel):
    run_count: int
    option_count: int
    accepted_count: int
    rejected_count: int
    pending_count: int
    runs: list[RecommendationRunSummary]


class VerdictSummary(BaseModel):
    verdict_id: str
    status: str
    composite_score: float | None
    finding_count: int
    blocking_finding_count: int
    model_id: str | None
    created_at: str


class ValidationSection(BaseModel):
    verdict_count: int
    latest_status: str | None
    finding_count: int
    blocking_finding_count: int
    verdicts: list[VerdictSummary]


class ReasoningSection(BaseModel):
    record_count: int
    models_used: list[str]


class AiProcessSummaryResponse(BaseModel):
    design_id: str
    intake: IntakeSection
    recommendation: RecommendationSection
    validation: ValidationSection
    reasoning: ReasoningSection


class TimelineEntry(BaseModel):
    event_type: str
    entity_id: str
    occurred_at: str
    actor: str | None
    status: str
    summary: str


class TimelineResponse(BaseModel):
    entries: list[TimelineEntry]
    total: int
    page: int
    page_size: int


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _require_design(session: AsyncSession, design_id: str) -> None:
    exists = (await session.execute(
        sa.text("SELECT 1 FROM designs WHERE id = :design_id"), {"design_id": design_id},
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{design_id}/ai-process", response_model=AiProcessSummaryResponse)
async def get_ai_process_summary(
    design_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_kb_session),
) -> AiProcessSummaryResponse:
    """Aggregate counts + bounded recent-item lists across all three AI pipelines."""
    await _require_design(session, design_id)

    # ── Intake ──────────────────────────────────────────────────────────────
    submission_agg = (await session.execute(
        sa.text("SELECT COUNT(*) AS total FROM intake_submissions WHERE design_id = :id"),
        {"id": design_id},
    )).mappings().one()

    proposal_agg = (await session.execute(
        sa.text("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status = 'confirmed') AS confirmed,
                   COUNT(*) FILTER (WHERE status = 'edited_confirmed') AS edited_confirmed,
                   COUNT(*) FILTER (WHERE status = 'rejected') AS rejected,
                   COUNT(*) FILTER (WHERE status = 'pending') AS pending
            FROM intake_proposals WHERE design_id = :id
        """),
        {"id": design_id},
    )).mappings().one()

    submission_rows = (await session.execute(
        sa.text("""
            SELECT id, operation_id, mode, model_id, source_char_count,
                   LEFT(source_text, 500) AS source_excerpt,
                   business_problem, desired_outcome, submitted_by, submitted_at
            FROM intake_submissions WHERE design_id = :id
            ORDER BY submitted_at DESC LIMIT :limit
        """),
        {"id": design_id, "limit": limit},
    )).mappings().all()

    intake = IntakeSection(
        submission_count=submission_agg["total"],
        proposal_count=proposal_agg["total"],
        confirmed_count=proposal_agg["confirmed"],
        edited_confirmed_count=proposal_agg["edited_confirmed"],
        rejected_count=proposal_agg["rejected"],
        pending_count=proposal_agg["pending"],
        submissions=[
            IntakeSubmissionSummary(
                submission_id=r["id"], operation_id=r["operation_id"], mode=r["mode"],
                model_id=r["model_id"], source_char_count=r["source_char_count"],
                source_excerpt=r["source_excerpt"], business_problem=r["business_problem"],
                desired_outcome=r["desired_outcome"], submitted_by=r["submitted_by"],
                submitted_at=r["submitted_at"].isoformat(),
            )
            for r in submission_rows
        ],
    )

    # ── Recommendation ──────────────────────────────────────────────────────
    run_agg = (await session.execute(
        sa.text("SELECT COUNT(*) AS total FROM recommendation_runs WHERE design_id = :id"),
        {"id": design_id},
    )).mappings().one()

    option_agg = (await session.execute(
        sa.text("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status = 'accepted') AS accepted,
                   COUNT(*) FILTER (WHERE status = 'rejected') AS rejected,
                   COUNT(*) FILTER (WHERE status = 'pending') AS pending
            FROM recommendation_options WHERE design_id = :id
        """),
        {"id": design_id},
    )).mappings().one()

    run_rows = (await session.execute(
        sa.text("""
            SELECT id, model_id, status, option_count, started_at
            FROM recommendation_runs WHERE design_id = :id
            ORDER BY started_at DESC LIMIT :limit
        """),
        {"id": design_id, "limit": limit},
    )).mappings().all()

    run_ids = [r["id"] for r in run_rows]
    options_by_run: dict[str, list[RecommendationOptionSummary]] = {rid: [] for rid in run_ids}
    if run_ids:
        option_rows = (await session.execute(
            sa.text("""
                SELECT run_id, id, title, status, rank, advisory, decided_by, decision_reason
                FROM recommendation_options WHERE run_id = ANY(:run_ids)
                ORDER BY run_id, rank
            """),
            {"run_ids": run_ids},
        )).mappings().all()
        for r in option_rows:
            options_by_run.setdefault(r["run_id"], []).append(RecommendationOptionSummary(
                option_id=r["id"], title=r["title"], status=r["status"], rank=r["rank"],
                advisory=r["advisory"], decided_by=r["decided_by"],
                decision_reason=r["decision_reason"],
            ))

    recommendation = RecommendationSection(
        run_count=run_agg["total"],
        option_count=option_agg["total"],
        accepted_count=option_agg["accepted"],
        rejected_count=option_agg["rejected"],
        pending_count=option_agg["pending"],
        runs=[
            RecommendationRunSummary(
                run_id=r["id"], model_id=r["model_id"], status=r["status"],
                option_count=r["option_count"], started_at=r["started_at"].isoformat(),
                options=options_by_run.get(r["id"], []),
            )
            for r in run_rows
        ],
    )

    # ── Validation ──────────────────────────────────────────────────────────
    verdict_agg = (await session.execute(
        sa.text("""
            SELECT COUNT(*) AS total, COALESCE(SUM(finding_count), 0) AS findings,
                   COALESCE(SUM(blocking_finding_count), 0) AS blocking
            FROM validation_verdicts WHERE design_id = :id
        """),
        {"id": design_id},
    )).mappings().one()

    verdict_rows = (await session.execute(
        sa.text("""
            SELECT id, status, composite_score, finding_count, blocking_finding_count,
                   model_id, created_at
            FROM validation_verdicts WHERE design_id = :id
            ORDER BY created_at DESC LIMIT :limit
        """),
        {"id": design_id, "limit": limit},
    )).mappings().all()

    validation = ValidationSection(
        verdict_count=verdict_agg["total"],
        latest_status=verdict_rows[0]["status"] if verdict_rows else None,
        finding_count=verdict_agg["findings"],
        blocking_finding_count=verdict_agg["blocking"],
        verdicts=[
            VerdictSummary(
                verdict_id=r["id"], status=r["status"], composite_score=r["composite_score"],
                finding_count=r["finding_count"],
                blocking_finding_count=r["blocking_finding_count"],
                model_id=r["model_id"], created_at=r["created_at"].isoformat(),
            )
            for r in verdict_rows
        ],
    )

    # ── Reasoning log ───────────────────────────────────────────────────────
    reasoning_agg = (await session.execute(
        sa.text("""
            SELECT COUNT(*) AS total,
                   COALESCE(array_agg(DISTINCT model_id) FILTER (WHERE model_id IS NOT NULL), '{}')
                       AS models
            FROM llm_reasoning_log WHERE design_id = :id
        """),
        {"id": design_id},
    )).mappings().one()

    reasoning = ReasoningSection(
        record_count=reasoning_agg["total"],
        models_used=list(reasoning_agg["models"] or []),
    )

    return AiProcessSummaryResponse(
        design_id=design_id,
        intake=intake,
        recommendation=recommendation,
        validation=validation,
        reasoning=reasoning,
    )


@router.get("/{design_id}/ai-process/timeline", response_model=TimelineResponse)
async def get_ai_process_timeline(
    design_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    event_type: str | None = Query(default=None),
    session: AsyncSession = Depends(get_kb_session),
) -> TimelineResponse:
    """Flat, chronological (occurred_at DESC) feed across every captured AI event."""
    await _require_design(session, design_id)

    offset = (page - 1) * page_size
    type_filter = "WHERE event_type = :event_type" if event_type else ""
    params: dict = {"id": design_id, "limit": page_size, "offset": offset}
    if event_type:
        params["event_type"] = event_type

    union_sql = """
        SELECT 'submission' AS event_type, id AS entity_id, submitted_at AS occurred_at,
               submitted_by AS actor, 'completed' AS status,
               ('Intake submission (' || mode || ')') AS summary
        FROM intake_submissions WHERE design_id = :id
        UNION ALL
        SELECT 'proposal', id, created_at, NULL, status, draft_statement
        FROM intake_proposals WHERE design_id = :id
        UNION ALL
        SELECT 'proposal_decision', id, COALESCE(decided_at, created_at), decided_by, status,
               COALESCE(confirmed_statement, draft_statement)
        FROM intake_proposals WHERE design_id = :id AND status != 'pending'
        UNION ALL
        SELECT 'recommendation_run', id, started_at, actor, status, COALESCE(result_summary, '')
        FROM recommendation_runs WHERE design_id = :id
        UNION ALL
        SELECT 'recommendation_option', id, created_at, NULL, status, title
        FROM recommendation_options WHERE design_id = :id
        UNION ALL
        SELECT 'option_decision', id, COALESCE(decided_at, created_at), decided_by, status,
               COALESCE(decision_reason, title)
        FROM recommendation_options WHERE design_id = :id AND status != 'pending'
        UNION ALL
        SELECT 'verdict', id, created_at, actor, status, ('Verdict: ' || status)
        FROM validation_verdicts WHERE design_id = :id
        UNION ALL
        SELECT 'verdict_override', id, override_at, overridden_by, 'overridden',
               COALESCE(override_justification, '')
        FROM validation_verdicts WHERE design_id = :id AND override_at IS NOT NULL
    """

    count_result = await session.execute(
        sa.text(f"SELECT COUNT(*) FROM ({union_sql}) events {type_filter}"),  # nosec B608 - type_filter is a hardcoded literal, not user input
        params,
    )
    total = count_result.scalar_one()

    result = await session.execute(
        sa.text(
            f"SELECT * FROM ({union_sql}) events {type_filter} "  # nosec B608 - type_filter is a hardcoded literal, not user input
            f"ORDER BY occurred_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    rows = result.mappings().all()

    entries = [
        TimelineEntry(
            event_type=r["event_type"],
            entity_id=r["entity_id"],
            occurred_at=r["occurred_at"].isoformat() if r["occurred_at"] else "",
            actor=r["actor"],
            status=r["status"],
            summary=r["summary"] or "",
        )
        for r in rows
    ]

    return TimelineResponse(entries=entries, total=total, page=page, page_size=page_size)
