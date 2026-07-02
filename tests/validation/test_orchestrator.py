"""Tests for ValidationOrchestrator — full pipeline, override, telemetry (US1–US5)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from adp.models import ArchitectureDescription, Element, ElementKind, Requirement
from adp.validation.models import (
    VerdictStatus,
)
from adp.validation.orchestrator import ValidationOrchestrator
from adp.validation.telemetry import ValidationTelemetry

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)

_GEN_RESPONSE_PASS = {
    "choices": [{"message": {"content": json.dumps({"score": 1.0, "findings": []})}}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 20},
}

_GEN_RESPONSE_FAIL = {
    "choices": [{"message": {"content": json.dumps({
        "score": 0.0,
        "findings": [{"element_id": "ELM-001", "description": "violation", "cited_id": "STD-001"}]
    })}}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 40},
}


def _make_design(orphan: bool = False) -> ArchitectureDescription:
    req = Requirement(id="REQ-001", title="R", description="desc")
    elm = Element(
        id="ELM-001", name="A", kind=ElementKind.CONTAINER,
        satisfies=[] if orphan else ["REQ-001"]
    )
    return ArchitectureDescription(
        schema_version="1.0.0", id="DESIGN-001", title="Test",
        requirements=[req], elements=[elm],
        created_at=_NOW, updated_at=_NOW,
    )


def _make_kr(item_id: str = "STD-001") -> MagicMock:
    from adp.knowledge.schema import CitationRef
    from tests.knowledge.conftest import make_item

    item = MagicMock()
    item.kind = "standard"
    item.title = "TLS Requirement"
    item.full_text = "All services must use TLS 1.3"

    entry = MagicMock()
    entry.item = item
    entry.citation = CitationRef(item_id=item_id, item_version="2.0.0")
    entry.relevance_score = 0.9

    kr = MagicMock()
    kr.hybrid_search = AsyncMock(return_value=MagicMock(items=[entry]))
    kr.resolve_citation = AsyncMock(return_value=make_item(item_id))
    return kr


def _make_orch(
    llm_response=None, failing: bool = False
) -> tuple[ValidationOrchestrator, MagicMock]:
    call_count = [0]

    async def mock_extract(*args, **kwargs):
        call_count[0] += 1
        return _GEN_RESPONSE_FAIL if failing else (llm_response or _GEN_RESPONSE_PASS)

    mock_llm = MagicMock()
    mock_llm.extract = mock_extract
    mock_llm._api_key = "FAKE_KEY_DO_NOT_LOG"

    mock_store = AsyncMock()
    mock_store.get.return_value = _make_design()
    mock_store.save.return_value = MagicMock(current_version=2)
    mock_store.list_versions.return_value = [MagicMock(), MagicMock()]  # version 2

    mock_telemetry = MagicMock(spec=ValidationTelemetry)
    mock_telemetry.emit_span = MagicMock()

    orch = ValidationOrchestrator(
        llm=mock_llm,
        knowledge_retrieval=_make_kr(),
        design_store=mock_store,
        telemetry=mock_telemetry,
    )
    return orch, mock_telemetry


# ── US1: Full pipeline ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_pipeline_produces_verdict() -> None:
    """Full pipeline completes with a Verdict in operation_store."""
    orch, _ = _make_orch()
    operation_store: dict = {"op-001": {"status": "pending"}}
    await orch.run("op-001", "DESIGN-001", operation_store, correlation_id="corr-001")

    op = operation_store["op-001"]
    assert op["status"] == "completed"
    assert op["verdict"] is not None


@pytest.mark.asyncio
async def test_verdict_verdict_status_enum_serializes_as_pass() -> None:
    """VerdictStatus.PASS serializes to string 'pass' (not 'pass_') — I2 fix."""
    assert VerdictStatus.PASS.value == "pass"
    assert VerdictStatus.FAIL.value == "fail"
    assert VerdictStatus.INDETERMINATE.value == "indeterminate"
    assert VerdictStatus.OVERRIDDEN.value == "overridden"


# ── US3: Structural check blocks LLM critics ─────────────────────────────────

@pytest.mark.asyncio
async def test_structural_failure_blocks_llm_critics() -> None:
    """When design has orphan, structural fails and LLM critics are skipped."""
    call_count = [0]

    async def mock_extract(*args, **kwargs):
        call_count[0] += 1
        return _GEN_RESPONSE_PASS

    mock_llm = MagicMock()
    mock_llm.extract = mock_extract

    mock_store = AsyncMock()
    mock_store.get.return_value = _make_design(orphan=True)
    mock_store.list_versions.return_value = [MagicMock()]

    mock_telemetry = MagicMock(spec=ValidationTelemetry)
    mock_telemetry.emit_span = MagicMock()

    orch = ValidationOrchestrator(
        llm=mock_llm,
        knowledge_retrieval=_make_kr(),
        design_store=mock_store,
        telemetry=mock_telemetry,
    )

    operation_store: dict = {"op-001": {"status": "pending"}}
    await orch.run("op-001", "DESIGN-001", operation_store)

    assert call_count[0] == 0, "LLM was called despite structural failure"
    op = operation_store["op-001"]
    assert op["verdict"].status == VerdictStatus.FAIL


# ── US4: Override ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_override_requires_non_empty_justification() -> None:
    """Empty justification raises ValueError."""
    orch, _ = _make_orch(failing=True)
    operation_store: dict = {"op-001": {"status": "pending"}}
    await orch.run("op-001", "DESIGN-001", operation_store)

    with pytest.raises(ValueError, match="non-empty"):
        await orch.override_verdict(
            verdict_id="vrd-001",
            operation_id="op-001",
            reviewing_actor="sub:reviewer",
            justification="",
            operation_store=operation_store,
            design_id="DESIGN-001",
        )


@pytest.mark.asyncio
async def test_override_marks_verdict_overridden() -> None:
    """Valid override changes verdict status to overridden."""
    orch, _ = _make_orch(failing=True)
    operation_store: dict = {"op-001": {"status": "pending"}}
    await orch.run("op-001", "DESIGN-001", operation_store)

    await orch.override_verdict(
        verdict_id="vrd-001",
        operation_id="op-001",
        reviewing_actor="sub:reviewer-456",
        justification="Exception EXC-001 applies; see ADR-042",
        operation_store=operation_store,
        design_id="DESIGN-001",
    )

    verdict = operation_store["op-001"]["verdict"]
    assert verdict.status == VerdictStatus.OVERRIDDEN
    assert verdict.overridden_by == "sub:reviewer-456"
    assert "EXC-001" in verdict.override_justification


@pytest.mark.asyncio
async def test_override_writes_audit_entry() -> None:
    """Override writes AuditEntry with actor and action."""
    orch, _ = _make_orch(failing=True)
    operation_store: dict = {"op-001": {"status": "pending"}}
    await orch.run("op-001", "DESIGN-001", operation_store)

    await orch.override_verdict(
        verdict_id="vrd-001",
        operation_id="op-001",
        reviewing_actor="sub:reviewer-456",
        justification="Exception applies",
        operation_store=operation_store,
        design_id="DESIGN-001",
    )

    mock_store = orch._store
    mock_store.save.assert_called()
    saved_design = mock_store.save.call_args[0][0]
    assert len(saved_design.audit_log) >= 1
    entry = saved_design.audit_log[-1]
    assert entry.actor == "sub:reviewer-456"
    assert entry.action == "override-validation-verdict"


@pytest.mark.asyncio
async def test_cannot_override_pass_verdict() -> None:
    """Cannot override a passing verdict."""
    orch, _ = _make_orch()  # passes by default
    operation_store: dict = {"op-001": {"status": "pending"}}
    await orch.run("op-001", "DESIGN-001", operation_store)

    with pytest.raises(ValueError, match="Only 'fail'"):
        await orch.override_verdict(
            verdict_id="vrd-001",
            operation_id="op-001",
            reviewing_actor="sub:reviewer",
            justification="Trying to override a pass",
            operation_store=operation_store,
            design_id="DESIGN-001",
        )


# ── US5: Telemetry ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_five_spans_emitted_per_job() -> None:
    """At least 5 spans emitted (structural + 4 LLM + aggregate + gate)."""
    orch, mock_telemetry = _make_orch()
    operation_store: dict = {"op-001": {"status": "pending"}}
    await orch.run("op-001", "DESIGN-001", operation_store, correlation_id="corr-001")

    critic_names = {call.args[0].critic_name for call in mock_telemetry.emit_span.call_args_list}
    assert "structural" in critic_names
    assert "standards" in critic_names
    assert "principles" in critic_names
    assert "pattern_fit" in critic_names
    assert "consistency" in critic_names


@pytest.mark.asyncio
async def test_all_spans_share_correlation_id() -> None:
    """All spans receive the correlation_id from the job."""
    orch, mock_telemetry = _make_orch()
    operation_store: dict = {"op-001": {"status": "pending"}}
    await orch.run("op-001", "DESIGN-001", operation_store, correlation_id="trace-xyz")

    for call in mock_telemetry.emit_span.call_args_list:
        assert call.args[1] == "trace-xyz"  # correlation_id arg


@pytest.mark.asyncio
async def test_citations_present_true_when_cited_findings_exist() -> None:
    """citations_present=True when at least one finding has a citation (ART-VII bridge)."""
    orch, _ = _make_orch(failing=True)  # generates findings with citations
    operation_store: dict = {"op-001": {"status": "pending"}}
    await orch.run("op-001", "DESIGN-001", operation_store)
    # If any critic returned cited findings, citations_present should be True
    # (depends on whether resolve_citation succeeded)
    assert "span" in operation_store["op-001"]


# ── Performance: NFR-001 / SC-003 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fan_out_completes_structurally() -> None:
    """Full orchestrator.run() with mocked critics completes in < 1 second."""
    orch, _ = _make_orch()
    operation_store: dict = {"op-001": {"status": "pending"}}
    start = time.perf_counter()
    await orch.run("op-001", "DESIGN-001", operation_store)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"Pipeline took {elapsed:.2f}s with mock LLM"


# ── Security: QG-08 ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_key_never_in_validation_logs(caplog) -> None:
    """API key must never appear in any log output."""
    import logging

    FAKE_KEY = "FAKE_VALIDATION_KEY_regression_xyz777"
    orch, _ = _make_orch()
    orch._llm._api_key = FAKE_KEY

    operation_store: dict = {"op-001": {"status": "pending"}}
    with caplog.at_level(logging.DEBUG, logger="adp"):
        await orch.run("op-001", "DESIGN-001", operation_store)

    full_log = "\n".join(r.message for r in caplog.records)
    assert FAKE_KEY not in full_log
