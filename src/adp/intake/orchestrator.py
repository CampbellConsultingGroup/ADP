"""ExtractionOrchestrator — coordinates the full requirements intake pipeline (ADP-SPEC-006).

Consumed by ADP-SPEC-003's operations router when kind=intake.
Source text is persisted durably to `intake_submissions` (ADP AI process capture,
ADP-3ei), linked to the design; it is still never logged or included in telemetry.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from adp.audit.writer import next_audit_id
from adp.intake.linker import KnowledgeLinker
from adp.intake.models import (
    ExtractedProposal,
    ExtractionSpan,
    IntakeSubmission,
    ProposalStatus,
    RequirementKind,
    SubmissionMode,
    VerificationStatus,
)
from adp.intake.parser import LLMResponseParser
from adp.intake.telemetry import IntakeTelemetry
from adp.intake.verifier import SourceExcerptVerifier
from adp.llm.client import LLMClient

if TYPE_CHECKING:
    from adp.store import DesignStore

# Backward-compatible alias — callers inside this module use the private name;
# external callers should import from adp.audit.writer (ADP-SPEC-023 Move B).
_next_audit_id = next_audit_id

_logger = logging.getLogger("adp.intake")


class ExtractionOrchestrator:
    """Coordinates the full requirements extraction pipeline."""

    def __init__(
        self,
        llm_client: LLMClient,
        linker: KnowledgeLinker | None = None,
        telemetry: IntakeTelemetry | None = None,
        capture_store: Any | None = None,
    ) -> None:
        self._llm = llm_client
        self._linker = linker or KnowledgeLinker()
        self._telemetry = telemetry or IntakeTelemetry()
        self._parser = LLMResponseParser()
        self._verifier = SourceExcerptVerifier()
        self._capture = capture_store

    async def run(
        self,
        submission: IntakeSubmission,
        operation_store: Any,
    ) -> None:
        """Execute extraction pipeline. Called as background task (ADP-SPEC-024).

        operation_store is an OperationStore instance (ADP-SPEC-024).
        """

        op_id = submission.operation_id
        await operation_store.update(op_id, status="running")

        start = time.perf_counter()
        proposals: list[ExtractedProposal] = []
        error_msg: str | None = None
        input_tokens = 0
        output_tokens = 0
        correlation_id: str | None = None

        try:
            # Read correlation_id / design_id from persisted payload
            current_op = await operation_store.get(op_id) or {}
            correlation_id = current_op.get("correlation_id")
            design_id = current_op.get("design_id")

            if submission.mode == SubmissionMode.STRUCTURED_FORM:
                # Skip LLM — single pre-written requirement
                proposals = [
                    ExtractedProposal(
                        proposal_id=str(uuid.uuid4()),
                        operation_id=op_id,
                        submission_id=submission.submission_id,
                        draft_statement=submission.text,
                        kind=RequirementKind.FUNCTIONAL,
                        source_excerpt=submission.text[:200],
                        verification_status=VerificationStatus.VERIFIED,
                        confidence=1.0,
                        status=ProposalStatus.PENDING,
                    )
                ]
            else:
                # Bulk text: AI extraction
                raw_response = await self._llm.extract(submission.text, correlation_id)

                # Count tokens for telemetry
                usage = raw_response.get("usage", {})
                input_tokens = usage.get("prompt_tokens", _count_chars(submission.text))
                output_tokens = usage.get("completion_tokens", 0)

                proposals = self._parser.parse(
                    raw_response,
                    submission.submission_id,
                    op_id,
                )

            # Verify source excerpts (FR-007)
            for proposal in proposals:
                proposal.verification_status = self._verifier.verify(
                    proposal.source_excerpt, submission.text
                )

            # Resolve knowledge base links (FR-005)
            for proposal in proposals:
                if proposal.proposed_links:
                    proposal.proposed_links = await self._linker.link(proposal.proposed_links)

            suffix = "s" if len(proposals) != 1 else ""
            result_summary = f"{len(proposals)} requirement{suffix} extracted"

            # Serialize proposals as dicts for persistent storage (ADP-SPEC-024)
            # ExtractedProposal is a dataclass — convert fields to JSON-safe dict
            serialized_proposals = {
                p.proposal_id: {
                    "proposal_id": p.proposal_id,
                    "operation_id": p.operation_id,
                    "submission_id": p.submission_id,
                    "draft_statement": p.draft_statement,
                    "kind": p.kind.value,
                    "source_excerpt": p.source_excerpt,
                    "verification_status": p.verification_status.value,
                    "confidence": p.confidence,
                    "status": p.status.value,
                    "confirmed_statement": p.confirmed_statement,
                }
                for p in proposals
            }
            citations_present = any(
                p.verification_status == VerificationStatus.VERIFIED for p in proposals
            )
            await operation_store.update(op_id, status="completed", payload_patch={
                "proposals": serialized_proposals,
                "result_summary": result_summary,
                "citations_present": citations_present,
            })

            # ADP-SPEC-027: write immutable extraction reasoning record (fire-and-forget)
            _write_extraction_reasoning(
                operation_id=op_id,
                model_id=self._llm._model,
                result_summary=result_summary,
                prompt_text=submission.text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                design_id=design_id,
            )

            # ADP-3ei: durable, design-linked capture of every proposal (best-effort)
            if self._capture is not None and design_id and proposals:
                from adp.store.ai_capture import ProposalRecord
                await self._capture.record_proposals([
                    ProposalRecord(
                        proposal_id=p.proposal_id,
                        submission_id=p.submission_id,
                        design_id=design_id,
                        operation_id=op_id,
                        draft_statement=p.draft_statement,
                        kind=p.kind.value,
                        source_excerpt=p.source_excerpt,
                        verification_status=p.verification_status.value,
                        confidence=p.confidence,
                        proposed_links=list(p.proposed_links or []),
                    )
                    for p in proposals
                ])

        except Exception as exc:
            error_msg = str(exc)
            await operation_store.update(op_id, status="failed", payload_patch={
                "error_description": error_msg,
            })
            _logger.error(
                json.dumps({
                    "operation": "intake.extraction_failed",
                    "operation_id": op_id,
                    "error": error_msg,
                })
            )
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            current_op_final = await operation_store.get(op_id) or {}
            span_data = ExtractionSpan(
                operation_id=op_id,
                correlation_id=correlation_id,
                model=self._llm._model,
                endpoint=self._llm._base_url,
                source_char_count=len(submission.text),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=0.0,
                proposal_count=len(proposals),
                proposal_ids=[p.proposal_id for p in proposals],
                latency_ms=latency_ms,
                error=error_msg,
            )
            self._telemetry.emit(span_data)

            _logger.info(
                json.dumps({
                    "operation": "intake.extraction",
                    "operation_id": op_id,
                    "proposal_count": len(proposals),
                    "latency_ms": round(latency_ms, 2),
                    "status": current_op_final.get("status"),
                })
            )

    async def confirm_proposal(
        self,
        proposal_id: str,
        operation_id: str,
        confirming_actor: str,
        edited_statement: str | None,
        operation_store: Any,
        design_store: "DesignStore",
        design_id: str,
    ) -> Any:
        """Confirm one proposal → write Requirement + AuditEntry to the design store."""
        from adp.models import Requirement
        from adp.models import RequirementKind as _CanonicalRequirementKind

        op = await operation_store.get(operation_id) or {}
        proposals: dict = op.get("proposals", {})
        proposal = proposals.get(proposal_id)

        if proposal is None:
            raise ValueError(f"Proposal {proposal_id!r} not found in operation {operation_id!r}")

        # Proposal is a dict (serialized); check status as string
        p_status = proposal.get("status") if isinstance(proposal, dict) else proposal.status.value
        if p_status != "pending":
            raise ValueError(
                f"Proposal {proposal_id!r} is not pending (status={p_status})"
            )

        draft = proposal.get("draft_statement") if isinstance(proposal, dict) else proposal.draft_statement  # noqa: E501
        statement = edited_statement or draft
        if not statement or not statement.strip():
            raise ValueError("Requirement statement must be non-empty (NFR-002)")
        raw_kind = proposal.get("kind") if isinstance(proposal, dict) else proposal.kind.value
        kind = (
            _CanonicalRequirementKind(raw_kind)
            if raw_kind else _CanonicalRequirementKind.FUNCTIONAL
        )

        # Read design, generate Requirement id, write back
        design = await design_store.get(design_id)
        req_id = f"REQ-{len(design.requirements) + 1:03d}"

        requirement = Requirement(
            id=req_id,
            title=statement[:120],
            description=statement,
            kind=kind,
            priority="must",
            tags=[],
        )

        from adp.models import AuditEntry as _AuditEntry
        audit_entry_id = _next_audit_id(design)
        audit_entry = _AuditEntry(
            id=audit_entry_id,
            actor=confirming_actor,
            action="confirm-requirement",
            affected_entity=req_id,
            summary=f"Confirmed requirement from proposal {proposal_id}",
            timestamp=datetime.now(timezone.utc),
            origin="human",
        )

        design.requirements.append(requirement)
        design.audit_log.append(audit_entry)
        await design_store.save(design, actor=confirming_actor)

        # Update proposal dict and write back to persistent store
        new_status = "edited_confirmed" if edited_statement else "confirmed"
        decided_at = datetime.now(timezone.utc)
        proposal_update: dict = {
            "status": new_status,
            "confirmed_statement": statement,
            "confirmed_by": confirming_actor,
            "confirmed_at": decided_at.isoformat(),
            "requirement_id": req_id,
        }
        if isinstance(proposal, dict):
            proposals[proposal_id] = {**proposal, **proposal_update}
        else:
            # Legacy path (should not occur in production after ADP-SPEC-024)
            proposal_dict = {
                "proposal_id": proposal.proposal_id, "operation_id": proposal.operation_id,
                "submission_id": proposal.submission_id, "draft_statement": proposal.draft_statement,  # noqa: E501
                "kind": proposal.kind.value, "source_excerpt": proposal.source_excerpt,
                "verification_status": proposal.verification_status.value,
                "confidence": proposal.confidence, "status": proposal.status.value,
                "confirmed_statement": proposal.confirmed_statement,
            }
            proposals[proposal_id] = {**proposal_dict, **proposal_update}

        await operation_store.update(operation_id, payload_patch={"proposals": proposals})

        if self._capture is not None:
            await self._capture.record_decision(
                proposal_id,
                status=new_status,
                decided_by=confirming_actor,
                decided_at=decided_at,
                confirmed_statement=statement,
                requirement_id=req_id,
                audit_entry_id=audit_entry_id,
            )

        _logger.info(
            json.dumps({
                "operation": "intake.confirm_proposal",
                "proposal_id": proposal_id,
                "requirement_id": req_id,
                "actor": confirming_actor,
            })
        )
        return requirement

    async def reject_proposal(
        self,
        proposal_id: str,
        operation_id: str,
        rejecting_actor: str,
        operation_store: Any,
        design_store: "DesignStore | None" = None,
        design_id: str | None = None,
    ) -> None:
        """Reject one proposal — writes rejection audit entry, DOES NOT add Requirement."""
        op = await operation_store.get(operation_id) or {}
        proposals: dict = op.get("proposals", {})
        proposal = proposals.get(proposal_id)

        if proposal is None:
            raise ValueError(f"Proposal {proposal_id!r} not found in operation {operation_id!r}")

        p_status = proposal.get("status") if isinstance(proposal, dict) else proposal.status.value
        if p_status != "pending":
            raise ValueError(f"Proposal {proposal_id!r} is not pending")

        # Update proposal status in persistent store
        if isinstance(proposal, dict):
            proposals[proposal_id] = {**proposal, "status": "rejected"}
        else:
            proposals[proposal_id] = {
                "proposal_id": proposal.proposal_id, "operation_id": proposal.operation_id,
                "submission_id": proposal.submission_id, "draft_statement": proposal.draft_statement,  # noqa: E501
                "kind": proposal.kind.value, "source_excerpt": proposal.source_excerpt,
                "verification_status": proposal.verification_status.value,
                "confidence": proposal.confidence, "status": "rejected",
                "confirmed_statement": proposal.confirmed_statement,
            }

        await operation_store.update(operation_id, payload_patch={"proposals": proposals})

        decided_at = datetime.now(timezone.utc)
        audit_entry_id: str | None = None

        # Write rejection audit entry to design if store is available
        if design_store is not None and design_id is not None:
            design = await design_store.get(design_id)
            from adp.models import AuditEntry as _AuditEntry

            audit_entry_id = _next_audit_id(design)
            audit_entry = _AuditEntry(
                id=audit_entry_id,
                actor=rejecting_actor,
                action="reject-requirement-proposal",
                affected_entity=proposal_id,
                summary=f"Rejected requirement proposal {proposal_id}",
                timestamp=decided_at,
                origin="human",
            )
            design.audit_log.append(audit_entry)
            await design_store.save(design, actor=rejecting_actor)

        if self._capture is not None:
            await self._capture.record_decision(
                proposal_id,
                status="rejected",
                decided_by=rejecting_actor,
                decided_at=decided_at,
                audit_entry_id=audit_entry_id,
            )

        _logger.info(
            json.dumps({
                "operation": "intake.reject_proposal",
                "proposal_id": proposal_id,
                "actor": rejecting_actor,
            })
        )


def _count_chars(text: str) -> int:
    """Rough token estimate from character count (fallback when usage not in response)."""
    return max(1, len(text) // 4)


def _write_extraction_reasoning(
    operation_id: str,
    model_id: str,
    result_summary: str,
    prompt_text: str,
    input_tokens: int,
    output_tokens: int,
    design_id: str | None = None,
) -> None:
    """Fire-and-forget write of intake extraction reasoning (ADP-SPEC-027)."""
    import asyncio as _asyncio

    from adp.store.reasoning import ReasoningRecord, _hash_prompt

    async def _do_write() -> None:
        try:
            from adp.api.deps import get_reasoning_store
            store = await get_reasoning_store()
            await store.write(ReasoningRecord(
                operation_id=operation_id,
                option_id=None,
                step_name="extract",
                model_id=model_id,
                reasoning_text=result_summary,
                prompt_hash=_hash_prompt(prompt_text),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                design_id=design_id,
            ))
        except Exception as exc:
            _logger.debug("intake reasoning write skipped: %s", exc)

    try:
        _asyncio.create_task(_do_write())
    except RuntimeError:
        pass  # No event loop — skip write (e.g. in sync test context)
