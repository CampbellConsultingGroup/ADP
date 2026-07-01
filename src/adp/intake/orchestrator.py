"""ExtractionOrchestrator — coordinates the full requirements intake pipeline (ADP-SPEC-006).

Consumed by ADP-SPEC-003's operations router when kind=intake.
Source text is NEVER stored, logged, or included in telemetry.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from adp.intake.linker import KnowledgeLinker
from adp.intake.llm import LLMClient
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

if TYPE_CHECKING:
    from adp.store import DesignStore

_logger = logging.getLogger("adp.intake")


class ExtractionOrchestrator:
    """Coordinates the full requirements extraction pipeline."""

    def __init__(
        self,
        llm_client: LLMClient,
        linker: KnowledgeLinker | None = None,
        telemetry: IntakeTelemetry | None = None,
    ) -> None:
        self._llm = llm_client
        self._linker = linker or KnowledgeLinker()
        self._telemetry = telemetry or IntakeTelemetry()
        self._parser = LLMResponseParser()
        self._verifier = SourceExcerptVerifier()

    async def run(
        self,
        submission: IntakeSubmission,
        operation_store: dict[str, Any],
    ) -> None:
        """Execute extraction pipeline. Called as background task by ADP-SPEC-003."""
        op = operation_store.get(submission.operation_id, {})
        op["status"] = "running"
        operation_store[submission.operation_id] = op

        start = time.perf_counter()
        proposals: list[ExtractedProposal] = []
        error_msg: str | None = None
        input_tokens = 0
        output_tokens = 0

        try:
            if submission.mode == SubmissionMode.STRUCTURED_FORM:
                # Skip LLM — single pre-written requirement
                proposals = [
                    ExtractedProposal(
                        proposal_id=str(uuid.uuid4()),
                        operation_id=submission.operation_id,
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
                correlation_id = op.get("correlation_id")
                raw_response = await self._llm.extract(submission.text, correlation_id)

                # Count tokens for telemetry
                usage = raw_response.get("usage", {})
                input_tokens = usage.get("prompt_tokens", _count_chars(submission.text))
                output_tokens = usage.get("completion_tokens", 0)

                proposals = self._parser.parse(
                    raw_response,
                    submission.submission_id,
                    submission.operation_id,
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

            # Set citations_present on operation span (bridges to ADP-SPEC-003 ART-VII gate)
            citations_present = any(
                p.verification_status == VerificationStatus.VERIFIED for p in proposals
            )
            op.setdefault("span", {})["citations_present"] = citations_present

            op["proposals"] = {p.proposal_id: p for p in proposals}
            op["status"] = "completed"
            suffix = "s" if len(proposals) != 1 else ""
            op["result_summary"] = f"{len(proposals)} requirement{suffix} extracted"

        except Exception as exc:
            error_msg = str(exc)
            op["status"] = "failed"
            op["error_description"] = error_msg
            _logger.error(
                json.dumps({
                    "operation": "intake.extraction_failed",
                    "operation_id": submission.operation_id,
                    "error": error_msg,
                })
            )
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            # Emit telemetry span regardless of success/failure (QG-11 / FR-006)
            span_data = ExtractionSpan(
                operation_id=submission.operation_id,
                correlation_id=op.get("correlation_id"),
                model=self._llm._model,
                endpoint=self._llm._base_url,
                source_char_count=len(submission.text),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=0.0,  # populated if cost rates are configured
                proposal_count=len(proposals),
                proposal_ids=[p.proposal_id for p in proposals],
                latency_ms=latency_ms,
                error=error_msg,
            )
            self._telemetry.emit(span_data)

            _logger.info(
                json.dumps({
                    "operation": "intake.extraction",
                    "operation_id": submission.operation_id,
                    "proposal_count": len(proposals),
                    "latency_ms": round(latency_ms, 2),
                    "status": op.get("status"),
                })
            )
            # Discard source text — never retained after extraction
            del submission

    async def confirm_proposal(
        self,
        proposal_id: str,
        operation_id: str,
        confirming_actor: str,
        edited_statement: str | None,
        operation_store: dict[str, Any],
        design_store: "DesignStore",
        design_id: str,
    ) -> Any:
        """Confirm one proposal → write Requirement + AuditEntry to the design store."""
        from adp.models import Requirement

        op = operation_store.get(operation_id, {})
        proposals: dict[str, ExtractedProposal] = op.get("proposals", {})
        proposal = proposals.get(proposal_id)

        if proposal is None:
            raise ValueError(f"Proposal {proposal_id!r} not found in operation {operation_id!r}")
        if proposal.status != ProposalStatus.PENDING:
            raise ValueError(
                f"Proposal {proposal_id!r} is not pending (status={proposal.status})"
            )

        statement = edited_statement or proposal.draft_statement
        if not statement or not statement.strip():
            raise ValueError("Requirement statement must be non-empty (NFR-002)")

        # Read design, generate Requirement id, write back
        design = await design_store.get(design_id)
        req_id = f"REQ-{len(design.requirements) + 1:03d}"

        requirement = Requirement(
            id=req_id,
            title=statement[:120],
            description=statement,
            priority="must",
            tags=[],
        )

        from adp.models import AuditEntry as _AuditEntry
        audit_entry_id = f"AUD-{len(design.audit_log) + 1:03d}"
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

        proposal.status = (
            ProposalStatus.EDITED_CONFIRMED if edited_statement else ProposalStatus.CONFIRMED
        )
        proposal.confirmed_statement = statement
        proposal.confirmed_by = confirming_actor
        proposal.confirmed_at = datetime.now(timezone.utc)
        proposal.requirement_id = req_id

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
        operation_store: dict[str, Any],
        design_store: "DesignStore | None" = None,
        design_id: str | None = None,
    ) -> None:
        """Reject one proposal — writes rejection audit entry, DOES NOT add Requirement."""
        op = operation_store.get(operation_id, {})
        proposals: dict[str, ExtractedProposal] = op.get("proposals", {})
        proposal = proposals.get(proposal_id)

        if proposal is None:
            raise ValueError(f"Proposal {proposal_id!r} not found in operation {operation_id!r}")
        if proposal.status != ProposalStatus.PENDING:
            raise ValueError(f"Proposal {proposal_id!r} is not pending")

        proposal.status = ProposalStatus.REJECTED

        # Write rejection audit entry to design if store is available
        if design_store is not None and design_id is not None:
            design = await design_store.get(design_id)
            from adp.models import AuditEntry as _AuditEntry

            audit_entry = _AuditEntry(
                id=f"AUD-{len(design.audit_log) + 1:03d}",
                actor=rejecting_actor,
                action="reject-requirement-proposal",
                affected_entity=proposal_id,
                summary=f"Rejected requirement proposal {proposal_id}",
                timestamp=datetime.now(timezone.utc),
                origin="human",
            )
            design.audit_log.append(audit_entry)
            await design_store.save(design, actor=rejecting_actor)

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
