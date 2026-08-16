"""Durable, design-linked capture of AI pipeline activity (Intake, Recommendation,
Validation/LLM-as-Judge) — for later reporting/visualization, not for pipeline
control flow (that remains OperationStore's job, ADP-SPEC-024).

Style mirrors adp.store.operations (raw sa.text() + json.dumps for JSON columns)
rather than adp.store.reasoning's sa.Table mirror — because the unit-test harness
for this style of store runs against in-memory SQLite via aiosqlite, and a typed
JSONB column bound through a plain string parameter only works because asyncpg
infers the target column type; SQLite has no JSONB type at all, so JSON columns
here are always written as TEXT via json.dumps()/json.loads(), matching
OperationStore.payload's existing approach exactly.

Error policy:
  - Generation-path writes (a submission/proposal/run/option/verdict was just
    produced) are best-effort: caught, logged, never raised. A capture-store
    hiccup must never fail an AI pipeline. Mirrors ReasoningStore.write.
  - Decision-path writes (confirm/reject/accept/override) are awaited inline
    and raise on failure, logged loudly. Deliberately NOT fire-and-forget —
    fire-and-forget is exactly why recommendation rejections were invisible
    before this module existed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

if TYPE_CHECKING:
    from adp.validation.models import Verdict

logger = logging.getLogger("adp.store.ai_capture")


def _dump_json(value: Any) -> str:
    return json.dumps(value if value is not None else [])


def _load_json(raw: Any) -> Any:
    if isinstance(raw, (list, dict)):
        return raw
    return json.loads(raw or "[]")


# ── Intake ──────────────────────────────────────────────────────────────────

@dataclass
class SubmissionRecord:
    submission_id: str
    design_id: str
    operation_id: str
    mode: str
    source_text: str
    business_problem: str | None
    desired_outcome: str | None
    model_id: str | None
    submitted_by: str
    submitted_at: datetime


@dataclass
class ProposalRecord:
    proposal_id: str
    submission_id: str
    design_id: str
    operation_id: str
    draft_statement: str
    kind: str
    source_excerpt: str
    verification_status: str
    confidence: float
    proposed_links: list[Any] = field(default_factory=list)


_SOURCE_TEXT_MAX_CHARS = 200_000


class IntakeCaptureStore:
    """Durable capture for Requirements Intake submissions, proposals, and decisions."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def record_submission(self, rec: SubmissionRecord) -> None:
        """Best-effort: a capture failure must never fail an intake submission."""
        text = rec.source_text or ""
        truncated = len(text) > _SOURCE_TEXT_MAX_CHARS
        if truncated:
            text = text[:_SOURCE_TEXT_MAX_CHARS]
        try:
            async with self._session_factory() as session:
                await session.execute(sa.text("""
                    INSERT INTO intake_submissions
                        (id, design_id, operation_id, mode, source_text, source_char_count,
                         source_truncated, business_problem, desired_outcome, model_id,
                         submitted_by, submitted_at)
                    VALUES
                        (:id, :design_id, :operation_id, :mode, :source_text, :char_count,
                         :truncated, :business_problem, :desired_outcome, :model_id,
                         :submitted_by, :submitted_at)
                """), {
                    "id": rec.submission_id,
                    "design_id": rec.design_id,
                    "operation_id": rec.operation_id,
                    "mode": rec.mode,
                    "source_text": text,
                    "char_count": len(rec.source_text or ""),
                    "truncated": truncated,
                    "business_problem": rec.business_problem,
                    "desired_outcome": rec.desired_outcome,
                    "model_id": rec.model_id,
                    "submitted_by": rec.submitted_by,
                    "submitted_at": rec.submitted_at,
                })
                await session.commit()
        except Exception as exc:
            logger.warning("IntakeCaptureStore.record_submission failed (non-fatal): %s", exc)

    async def record_proposals(self, records: list[ProposalRecord]) -> None:
        """Best-effort: a capture failure must never fail an extraction run."""
        if not records:
            return
        try:
            async with self._session_factory() as session:
                for rec in records:
                    await session.execute(sa.text("""
                        INSERT INTO intake_proposals
                            (id, submission_id, design_id, operation_id, draft_statement,
                             kind, source_excerpt, verification_status, confidence,
                             proposed_links)
                        VALUES
                            (:id, :submission_id, :design_id, :operation_id, :draft_statement,
                             :kind, :source_excerpt, :verification_status, :confidence,
                             :proposed_links)
                    """), {
                        "id": rec.proposal_id,
                        "submission_id": rec.submission_id,
                        "design_id": rec.design_id,
                        "operation_id": rec.operation_id,
                        "draft_statement": rec.draft_statement,
                        "kind": rec.kind,
                        "source_excerpt": rec.source_excerpt,
                        "verification_status": rec.verification_status,
                        "confidence": rec.confidence,
                        "proposed_links": _dump_json(rec.proposed_links),
                    })
                await session.commit()
        except Exception as exc:
            logger.warning("IntakeCaptureStore.record_proposals failed (non-fatal): %s", exc)

    async def record_decision(
        self,
        proposal_id: str,
        *,
        status: str,
        decided_by: str,
        decided_at: datetime,
        confirmed_statement: str | None = None,
        requirement_id: str | None = None,
        audit_entry_id: str | None = None,
    ) -> bool:
        """Record a confirm/reject decision. Awaited inline; raises on failure.

        Returns True if a pending proposal row was updated, False if the proposal
        row doesn't exist in this durable store (e.g. capture wasn't wired up for
        the run that produced it) — callers should not fail the request on False,
        only log it, since the decision itself already succeeded against the
        transient OperationStore/DesignStore.
        """
        async with self._session_factory() as session:
            result = await session.execute(sa.text("""
                UPDATE intake_proposals
                SET status = :status, decided_by = :decided_by, decided_at = :decided_at,
                    confirmed_statement = :confirmed_statement,
                    requirement_id = :requirement_id, audit_entry_id = :audit_entry_id
                WHERE id = :id AND status = 'pending'
            """), {
                "id": proposal_id,
                "status": status,
                "decided_by": decided_by,
                "decided_at": decided_at,
                "confirmed_statement": confirmed_statement,
                "requirement_id": requirement_id,
                "audit_entry_id": audit_entry_id,
            })
            await session.commit()
            return result.rowcount > 0  # type: ignore[return-value]


# ── Recommendation ──────────────────────────────────────────────────────────

@dataclass
class RunRecord:
    run_id: str
    design_id: str
    requirement_ids: list[str]
    model_id: str | None
    actor: str
    correlation_id: str | None
    started_at: datetime


@dataclass
class OptionRecord:
    option_id: str
    run_id: str
    design_id: str
    rank: int
    title: str
    rationale: str
    advisory: bool
    grounded_on: list[Any]
    satisfies: list[Any]
    trade_offs: list[Any]
    proposed_elements: list[Any]
    reuse_candidates: list[Any]
    ranking_score: float
    coverage_score: float
    principle_score: float
    tradeoff_score: float
    history_score: float
    knowledge_source: str


class RecommendationCaptureStore:
    """Durable capture for Recommendation Engine runs, options, and decisions."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def record_run(self, rec: RunRecord) -> None:
        """Best-effort. Written at submission time so failed runs are captured too."""
        try:
            async with self._session_factory() as session:
                await session.execute(sa.text("""
                    INSERT INTO recommendation_runs
                        (id, design_id, requirement_ids, model_id, actor, correlation_id,
                         status, started_at)
                    VALUES
                        (:id, :design_id, :requirement_ids, :model_id, :actor, :correlation_id,
                         'running', :started_at)
                """), {
                    "id": rec.run_id,
                    "design_id": rec.design_id,
                    "requirement_ids": _dump_json(rec.requirement_ids),
                    "model_id": rec.model_id,
                    "actor": rec.actor,
                    "correlation_id": rec.correlation_id,
                    "started_at": rec.started_at,
                })
                await session.commit()
        except Exception as exc:
            logger.warning("RecommendationCaptureStore.record_run failed (non-fatal): %s", exc)

    async def complete_run(
        self,
        run_id: str,
        *,
        status: str,
        option_count: int = 0,
        result_summary: str | None = None,
        error_description: str | None = None,
        citations_present: bool = False,
        completed_at: datetime | None = None,
    ) -> None:
        """Best-effort."""
        from datetime import timezone as _tz
        try:
            async with self._session_factory() as session:
                await session.execute(sa.text("""
                    UPDATE recommendation_runs
                    SET status = :status, option_count = :option_count,
                        result_summary = :result_summary,
                        error_description = :error_description,
                        citations_present = :citations_present,
                        completed_at = :completed_at
                    WHERE id = :id
                """), {
                    "id": run_id,
                    "status": status,
                    "option_count": option_count,
                    "result_summary": result_summary,
                    "error_description": error_description,
                    "citations_present": citations_present,
                    "completed_at": completed_at or datetime.now(_tz.utc),
                })
                await session.commit()
        except Exception as exc:
            logger.warning("RecommendationCaptureStore.complete_run failed (non-fatal): %s", exc)

    async def record_options(self, records: list[OptionRecord]) -> None:
        """Best-effort."""
        if not records:
            return
        try:
            async with self._session_factory() as session:
                for rec in records:
                    await session.execute(sa.text("""
                        INSERT INTO recommendation_options
                            (id, run_id, design_id, rank, title, rationale, advisory,
                             grounded_on, satisfies, trade_offs, proposed_elements,
                             reuse_candidates, ranking_score, coverage_score,
                             principle_score, tradeoff_score, history_score,
                             knowledge_source)
                        VALUES
                            (:id, :run_id, :design_id, :rank, :title, :rationale, :advisory,
                             :grounded_on, :satisfies, :trade_offs, :proposed_elements,
                             :reuse_candidates, :ranking_score, :coverage_score,
                             :principle_score, :tradeoff_score, :history_score,
                             :knowledge_source)
                    """), {
                        "id": rec.option_id,
                        "run_id": rec.run_id,
                        "design_id": rec.design_id,
                        "rank": rec.rank,
                        "title": rec.title,
                        "rationale": rec.rationale,
                        "advisory": rec.advisory,
                        "grounded_on": _dump_json(rec.grounded_on),
                        "satisfies": _dump_json(rec.satisfies),
                        "trade_offs": _dump_json(rec.trade_offs),
                        "proposed_elements": _dump_json(rec.proposed_elements),
                        "reuse_candidates": _dump_json(rec.reuse_candidates),
                        "ranking_score": rec.ranking_score,
                        "coverage_score": rec.coverage_score,
                        "principle_score": rec.principle_score,
                        "tradeoff_score": rec.tradeoff_score,
                        "history_score": rec.history_score,
                        "knowledge_source": rec.knowledge_source,
                    })
                await session.commit()
        except Exception as exc:
            logger.warning("RecommendationCaptureStore.record_options failed (non-fatal): %s", exc)

    async def record_option_decision(
        self,
        option_id: str,
        *,
        status: str,
        decided_by: str,
        decided_at: datetime,
        decision_reason: str | None = None,
        confirmation_id: str | None = None,
        advisory_acknowledged: bool = False,
        audit_entry_id: str | None = None,
        created_element_ids: list[str] | None = None,
    ) -> bool:
        """Record an accept/reject decision. Awaited inline; raises on failure."""
        async with self._session_factory() as session:
            result = await session.execute(sa.text("""
                UPDATE recommendation_options
                SET status = :status, decided_by = :decided_by, decided_at = :decided_at,
                    decision_reason = :decision_reason, confirmation_id = :confirmation_id,
                    advisory_acknowledged = :advisory_acknowledged,
                    audit_entry_id = :audit_entry_id, created_element_ids = :created_element_ids
                WHERE id = :id AND status = 'pending'
            """), {
                "id": option_id,
                "status": status,
                "decided_by": decided_by,
                "decided_at": decided_at,
                "decision_reason": decision_reason,
                "confirmation_id": confirmation_id,
                "advisory_acknowledged": advisory_acknowledged,
                "audit_entry_id": audit_entry_id,
                "created_element_ids": _dump_json(created_element_ids or []),
            })
            await session.commit()
            return result.rowcount > 0  # type: ignore[return-value]


# ── Validation / LLM-as-Judge ────────────────────────────────────────────────

class ValidationCaptureStore:
    """Durable capture for LLM-as-Judge verdicts and findings."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def record_verdict(
        self,
        verdict: "Verdict",
        *,
        design_id: str,
        actor: str,
        model_id: str | None,
    ) -> None:
        """Best-effort: write the verdict and all its findings in one transaction."""
        try:
            blocking = sum(
                1 for f in verdict.findings
                if getattr(f.severity, "value", f.severity) != "advisory"
            )
            critic_outputs = [
                {
                    "critic_name": c.critic_name,
                    "score": c.score,
                    "retrieved_knowledge_refs": c.retrieved_knowledge_refs,
                    "input_tokens": c.input_tokens,
                    "output_tokens": c.output_tokens,
                    "cost_usd": c.cost_usd,
                    "latency_ms": c.latency_ms,
                    "error": c.error,
                }
                for c in verdict.critic_outputs
            ]
            thresholds = {
                "max_critical": verdict.thresholds_snapshot.max_critical,
                "max_major": verdict.thresholds_snapshot.max_major,
                "max_minor": verdict.thresholds_snapshot.max_minor,
                "version": verdict.thresholds_snapshot.version,
            }
            status_value = getattr(verdict.status, "value", verdict.status)

            async with self._session_factory() as session:
                await session.execute(sa.text("""
                    INSERT INTO validation_verdicts
                        (id, operation_id, design_id, design_version, status, composite_score,
                         citations_present, thresholds_snapshot, critic_outputs, model_id,
                         finding_count, blocking_finding_count, actor)
                    VALUES
                        (:id, :operation_id, :design_id, :design_version, :status,
                         :composite_score, :citations_present, :thresholds_snapshot,
                         :critic_outputs, :model_id, :finding_count, :blocking_finding_count,
                         :actor)
                """), {
                    "id": verdict.verdict_id,
                    "operation_id": verdict.operation_id,
                    "design_id": design_id,
                    "design_version": verdict.design_version,
                    "status": status_value,
                    "composite_score": verdict.composite_score,
                    "citations_present": verdict.citations_present,
                    "thresholds_snapshot": _dump_json(thresholds),
                    "critic_outputs": _dump_json(critic_outputs),
                    "model_id": model_id,
                    "finding_count": len(verdict.findings),
                    "blocking_finding_count": blocking,
                    "actor": actor,
                })
                for f in verdict.findings:
                    await session.execute(sa.text("""
                        INSERT INTO validation_findings
                            (id, verdict_id, design_id, operation_id, critic_name, severity,
                             description, element_id, citation_item_id, citation_item_version,
                             score)
                        VALUES
                            (:id, :verdict_id, :design_id, :operation_id, :critic_name,
                             :severity, :description, :element_id, :citation_item_id,
                             :citation_item_version, :score)
                    """), {
                        "id": f.finding_id,
                        "verdict_id": verdict.verdict_id,
                        "design_id": design_id,
                        "operation_id": f.operation_id,
                        "critic_name": f.critic_name,
                        "severity": getattr(f.severity, "value", f.severity),
                        "description": f.description,
                        "element_id": f.element_id,
                        "citation_item_id": f.citation.item_id if f.citation else None,
                        "citation_item_version": f.citation.item_version if f.citation else None,
                        "score": f.score,
                    })
                await session.commit()
        except Exception as exc:
            logger.warning("ValidationCaptureStore.record_verdict failed (non-fatal): %s", exc)

    async def record_override(
        self,
        verdict_id: str,
        *,
        overridden_by: str,
        override_at: datetime,
        justification: str,
        audit_entry_id: str | None,
    ) -> bool:
        """Record a human override of a FAIL verdict. Awaited inline; raises on failure."""
        async with self._session_factory() as session:
            result = await session.execute(sa.text("""
                UPDATE validation_verdicts
                SET status = 'overridden', overridden_by = :overridden_by,
                    override_at = :override_at, override_justification = :justification,
                    audit_entry_id = :audit_entry_id
                WHERE id = :id AND status = 'fail'
            """), {
                "id": verdict_id,
                "overridden_by": overridden_by,
                "override_at": override_at,
                "justification": justification,
                "audit_entry_id": audit_entry_id,
            })
            await session.commit()
            return result.rowcount > 0  # type: ignore[return-value]
