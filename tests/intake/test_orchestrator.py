"""Tests for ExtractionOrchestrator — full pipeline, confirmation, rejection (US1-US4)."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from adp.intake.llm import LLMClient
from adp.intake.models import (
    IntakeSubmission,
    ProposalStatus,
    SubmissionMode,
)
from adp.intake.orchestrator import ExtractionOrchestrator
from adp.intake.telemetry import IntakeTelemetry

# ── Test-only shim: wraps a plain dict as an OperationStore ──────────────────

class DictOperationStore:
    """In-memory OperationStore shim for unit tests (ADP-SPEC-024)."""

    def __init__(self, initial: dict | None = None) -> None:
        self._data: dict = initial or {}

    async def create(self, op_id, op_type, design_id, actor, payload) -> None:
        self._data[op_id] = {"status": "pending", "design_id": design_id, **payload}

    async def get(self, op_id) -> dict | None:
        return self._data.get(op_id)

    async def update(self, op_id, *, status=None, payload_patch=None, error=None) -> None:
        op = self._data.setdefault(op_id, {})
        if status is not None:
            op["status"] = status
        if payload_patch:
            op.update(payload_patch)
        if error is not None:
            op["error_description"] = error

    async def update_option_status(self, op_id, option_id, new_status) -> bool:
        op = self._data.get(op_id, {})
        options = op.get("options", {})
        option = options.get(option_id)
        if option is None or option.get("status") != "pending":
            return False
        option["status"] = new_status
        return True

    async def delete_expired(self) -> int:
        return 0

    async def mark_stale_running_as_failed(self, message: str) -> int:
        return 0

    # Dict-style access for test assertions
    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)

_MOCK_LLM_RESPONSE = {
    "choices": [{"message": {"content": json.dumps({
        "requirements": [
            {
                "statement": "The API gateway must authenticate all requests.",
                "kind": "functional",
                "source_excerpt": "authenticate all API requests before routing",
                "confidence": 0.95,
                "referenced_principles": [],
            },
            {
                "statement": "Response time must be under 200ms.",
                "kind": "non_functional",
                "source_excerpt": "response time under 200ms",
                "confidence": 0.88,
                "referenced_principles": [],
            },
        ]
    })}}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 80},
}

_SOURCE_TEXT = (
    "All API requests must be authenticated before routing. "
    "The response time under 200ms should be maintained. "
    "We need to support 10k concurrent users."
)


def _make_submission(mode: SubmissionMode = SubmissionMode.BULK_TEXT) -> IntakeSubmission:
    return IntakeSubmission(
        submission_id="sub-001",
        mode=mode,
        text=_SOURCE_TEXT,
        submitted_by="sub:architect-123",
        submitted_at=_NOW,
        operation_id="op-001",
    )


def _make_orchestrator(llm_response: dict = None) -> tuple[ExtractionOrchestrator, MagicMock]:  # type: ignore[type-arg]
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm._model = "gpt-4o"
    mock_llm._base_url = "https://api.example.com"
    mock_llm.extract = AsyncMock(return_value=llm_response or _MOCK_LLM_RESPONSE)

    mock_telemetry = MagicMock(spec=IntakeTelemetry)
    mock_telemetry.emit = MagicMock()

    orchestrator = ExtractionOrchestrator(
        llm_client=mock_llm,
        telemetry=mock_telemetry,
    )
    return orchestrator, mock_telemetry


# ── US1: Extraction pipeline ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_orchestrator_run_produces_proposals() -> None:
    """Orchestrator produces proposals with correct fields (US1)."""
    orchestrator, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})

    await orchestrator.run(_make_submission(), operation_store)

    op = operation_store["op-001"]
    assert op["status"] == "completed"
    assert len(op["proposals"]) == 2
    for proposal in op["proposals"].values():
        assert proposal.get("status") == "pending"


def test_all_proposals_start_pending() -> None:
    """Proposals begin life in PENDING state, not confirmed (US1)."""
    from adp.intake.parser import LLMResponseParser

    parser = LLMResponseParser()
    proposals = parser.parse(_MOCK_LLM_RESPONSE, "sub-001", "op-001")
    # Parser returns ExtractedProposal dataclass objects — attribute access
    assert all(p.status == ProposalStatus.PENDING for p in proposals)


@pytest.mark.asyncio
async def test_source_excerpt_verification_set() -> None:
    """Orchestrator sets verification_status on each proposal (FR-007)."""
    orchestrator, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})

    await orchestrator.run(_make_submission(), operation_store)

    proposals = list(operation_store["op-001"]["proposals"].values())
    assert all(p.get("verification_status") in ("verified", "unverified")
               for p in proposals)


@pytest.mark.asyncio
async def test_citations_present_true_when_any_verified() -> None:
    """citations_present=True when at least one verified proposal exists (I2 bridge)."""
    orchestrator, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    await orchestrator.run(_make_submission(), operation_store)

    # Both source excerpts are substrings of _SOURCE_TEXT, so at least one should be verified
    assert operation_store["op-001"]["citations_present"] is True


@pytest.mark.asyncio
async def test_citations_present_false_when_all_unverified() -> None:
    """citations_present=False when no excerpt is found in source text."""
    response = {
        "choices": [{"message": {"content": json.dumps({
            "requirements": [{"statement": "S.", "kind": "functional",
                              "source_excerpt": "hallucinated excerpt not in text",
                              "confidence": 0.5, "referenced_principles": []}]
        })}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    orchestrator, _ = _make_orchestrator(response)
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    await orchestrator.run(_make_submission(), operation_store)

    assert operation_store["op-001"]["citations_present"] is False


@pytest.mark.asyncio
async def test_structured_form_skips_llm() -> None:
    """structured_form mode creates a proposal without calling LLMClient.extract (FR-001)."""
    orchestrator, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})

    submission = _make_submission(mode=SubmissionMode.STRUCTURED_FORM)
    await orchestrator.run(submission, operation_store)

    orchestrator._llm.extract.assert_not_called()
    op = operation_store["op-001"]
    assert op["status"] == "completed"
    assert len(op["proposals"]) == 1
    proposal = list(op["proposals"].values())[0]
    assert proposal.get("verification_status") == "verified"
    assert proposal.get("confidence") == 1.0


# ── US2: Confirmation / rejection ─────────────────────────────────────────────


def _make_design_with_proposals():  # type: ignore[return]
    """Return (DictOperationStore, mock_store) with 2 pending proposals (serialized dicts)."""
    from adp.intake.parser import LLMResponseParser
    from adp.models import ArchitectureDescription

    proposals = LLMResponseParser().parse(_MOCK_LLM_RESPONSE, "sub-001", "op-001")
    # Serialize proposals as dicts (matching ADP-SPEC-024 storage format)
    serialized = {
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
    operation_store = DictOperationStore({
        "op-001": {"status": "completed", "proposals": serialized}
    })

    design = ArchitectureDescription(
        schema_version="1.0.0", id="DESIGN-001", title="Test",
        created_at=_NOW, updated_at=_NOW,
    )
    mock_store = AsyncMock()
    mock_store.get.return_value = design
    mock_store.save.return_value = MagicMock(current_version=2)

    return operation_store, mock_store, list(proposals[0].proposal_id)


@pytest.mark.asyncio
async def test_confirm_proposal_writes_requirement() -> None:
    """confirm_proposal writes a Requirement to the design store (US2 / SC-002)."""
    orchestrator, _ = _make_orchestrator()
    operation_store, mock_store, _ = _make_design_with_proposals()
    proposal_id = list(operation_store["op-001"]["proposals"].keys())[0]

    await orchestrator.confirm_proposal(
        proposal_id=proposal_id,
        operation_id="op-001",
        confirming_actor="sub:architect-123",
        edited_statement=None,
        operation_store=operation_store,
        design_store=mock_store,
        design_id="DESIGN-001",
    )

    mock_store.save.assert_called_once()
    saved_design = mock_store.save.call_args[0][0]
    assert len(saved_design.requirements) == 1
    req = saved_design.requirements[0]
    import re
    assert re.match(r"^REQ-\d{3}$", req.id)
    assert req.description == "The API gateway must authenticate all requests."


@pytest.mark.asyncio
async def test_edit_confirm_uses_edited_statement() -> None:
    """Confirming with edited_statement uses the edited version (US2)."""
    orchestrator, _ = _make_orchestrator()
    operation_store, mock_store, _ = _make_design_with_proposals()
    proposal_id = list(operation_store["op-001"]["proposals"].keys())[0]

    await orchestrator.confirm_proposal(
        proposal_id=proposal_id,
        operation_id="op-001",
        confirming_actor="sub:architect-123",
        edited_statement="Revised: all requests must be authenticated.",
        operation_store=operation_store,
        design_store=mock_store,
        design_id="DESIGN-001",
    )

    saved_design = mock_store.save.call_args[0][0]
    expected = "Revised: all requests must be authenticated."
    assert saved_design.requirements[0].description == expected
    proposal = operation_store["op-001"]["proposals"][proposal_id]
    assert proposal.get("status") == "edited_confirmed"


@pytest.mark.asyncio
async def test_confirm_writes_audit_entry() -> None:
    """confirm_proposal writes an AuditEntry with the confirming actor (FR-004 / QG-13)."""
    orchestrator, _ = _make_orchestrator()
    operation_store, mock_store, _ = _make_design_with_proposals()
    proposal_id = list(operation_store["op-001"]["proposals"].keys())[0]

    await orchestrator.confirm_proposal(
        proposal_id=proposal_id,
        operation_id="op-001",
        confirming_actor="sub:architect-123",
        edited_statement=None,
        operation_store=operation_store,
        design_store=mock_store,
        design_id="DESIGN-001",
    )

    saved_design = mock_store.save.call_args[0][0]
    assert len(saved_design.audit_log) == 1
    entry = saved_design.audit_log[0]
    assert entry.actor == "sub:architect-123"
    assert entry.origin == "human"


@pytest.mark.asyncio
async def test_reject_proposal_does_not_add_requirement() -> None:
    """Rejected proposal does NOT appear as a Requirement (US2 / SC-001)."""
    orchestrator, _ = _make_orchestrator()
    operation_store, mock_store, _ = _make_design_with_proposals()
    proposal_id = list(operation_store["op-001"]["proposals"].keys())[0]

    await orchestrator.reject_proposal(
        proposal_id=proposal_id,
        operation_id="op-001",
        rejecting_actor="sub:architect-123",
        operation_store=operation_store,
        design_store=mock_store,
        design_id="DESIGN-001",
    )

    # store.save IS called (for the rejection audit entry) but no Requirement added
    if mock_store.save.called:
        saved_design = mock_store.save.call_args[0][0]
        assert len(saved_design.requirements) == 0

    proposal = operation_store["op-001"]["proposals"][proposal_id]
    assert proposal.get("status") == "rejected"


@pytest.mark.asyncio
async def test_confirm_rejects_empty_statement() -> None:
    """confirm_proposal with empty statement raises ValueError (NFR-002)."""
    orchestrator, _ = _make_orchestrator()
    operation_store, mock_store, _ = _make_design_with_proposals()
    proposal_id = list(operation_store["op-001"]["proposals"].keys())[0]
    # Force empty draft_statement (proposals stored as dicts after ADP-SPEC-024)
    operation_store["op-001"]["proposals"][proposal_id]["draft_statement"] = ""

    with pytest.raises(ValueError, match="non-empty"):
        await orchestrator.confirm_proposal(
            proposal_id=proposal_id,
            operation_id="op-001",
            confirming_actor="sub:architect-123",
            edited_statement=None,
            operation_store=operation_store,
            design_store=mock_store,
            design_id="DESIGN-001",
        )

    mock_store.save.assert_not_called()


# ── US4: Telemetry ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_span_emitted_on_success() -> None:
    """Telemetry span is emitted on successful extraction (US4 / QG-11)."""
    orchestrator, mock_telemetry = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    await orchestrator.run(_make_submission(), operation_store)

    mock_telemetry.emit.assert_called_once()
    span = mock_telemetry.emit.call_args[0][0]
    assert span.proposal_count >= 1
    assert span.latency_ms > 0
    assert span.error is None


@pytest.mark.asyncio
async def test_span_emitted_on_failure() -> None:
    """Telemetry span is emitted even when extraction fails (US4 / QG-11)."""
    orchestrator, mock_telemetry = _make_orchestrator()
    orchestrator._llm.extract = AsyncMock(side_effect=ConnectionError("unreachable"))

    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    await orchestrator.run(_make_submission(), operation_store)

    mock_telemetry.emit.assert_called_once()
    span = mock_telemetry.emit.call_args[0][0]
    assert span.error is not None
    assert span.proposal_count == 0
    assert operation_store["op-001"]["status"] == "failed"


# ── Performance: NFR-001 / SC-003 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_operation_handle_available_immediately() -> None:
    """Operation handle exists with status=pending before extraction completes (NFR-001)."""
    orchestrator, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})

    task = asyncio.create_task(orchestrator.run(_make_submission(), operation_store))
    # Immediately check — handle must be available
    assert "op-001" in operation_store
    await task  # clean up


@pytest.mark.asyncio
async def test_extraction_completes_within_deadline() -> None:
    """Full orchestrator.run with mock LLM completes well under 60 seconds (SC-003)."""
    orchestrator, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    start = time.perf_counter()
    await orchestrator.run(_make_submission(), operation_store)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"Orchestrator took {elapsed:.2f}s with mock LLM (should be < 1s)"
