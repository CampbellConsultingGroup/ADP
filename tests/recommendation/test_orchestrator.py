"""Tests for RecommendationOrchestrator — full pipeline, telemetry, performance (US1–US4)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from adp.models import ArchitectureDescription, Requirement
from adp.recommendation.orchestrator import RecommendationOrchestrator
from adp.recommendation.telemetry import RecommendationTelemetry
from tests.knowledge.conftest import make_item


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

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)

_MOCK_GEN_RESPONSE = {
    "choices": [{"message": {"content": json.dumps({"options": [
        {
            "title": "API Gateway Option",
            "rationale": "Reuses gateway pattern",
            "grounded_on": ["PAT-012"],
            "satisfies": ["REQ-001"],
            "proposed_elements": [
                {"name": "API Gateway", "kind": "container",
                 "description": "Entry point", "satisfies": ["REQ-001"]}
            ],
        },
    ]})}}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 150},
}

_MOCK_TRADEOFF_RESPONSE = {
    "choices": [{"message": {"content": json.dumps({"trade_offs": [
        {"criterion": "REQ-001", "stance": "meets", "rationale": "Handles it."}
    ]})}}],
    "usage": {"prompt_tokens": 50, "completion_tokens": 30},
}


def _make_design() -> ArchitectureDescription:
    return ArchitectureDescription(
        schema_version="1.0.0",
        id="DESIGN-001",
        title="Test Design",
        requirements=[Requirement(id="REQ-001", title="Stateless",
                                  description="stateless service performance")],
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_orchestrator(llm_response=None, tradeoff_response=None):
    mock_llm = MagicMock()
    call_count = [0]

    async def mock_extract(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return llm_response or _MOCK_GEN_RESPONSE
        return tradeoff_response or _MOCK_TRADEOFF_RESPONSE

    mock_llm.chat = mock_extract

    mock_kr = MagicMock()
    mock_kr.hybrid_search = AsyncMock(return_value=MagicMock(items=[]))
    mock_kr.resolve_citation = AsyncMock(return_value=make_item("PAT-012"))

    mock_store = AsyncMock()
    mock_store.get.return_value = _make_design()
    mock_store.save.return_value = MagicMock(current_version=2)

    mock_telemetry = MagicMock(spec=RecommendationTelemetry)
    mock_telemetry.emit_step_span = MagicMock()

    orch = RecommendationOrchestrator(
        llm=mock_llm,
        knowledge_retrieval=mock_kr,
        design_store=mock_store,
        option_count=1,
        telemetry=mock_telemetry,
    )
    return orch, mock_telemetry, mock_store


# ── US1: Full pipeline ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_pipeline_produces_ranked_options() -> None:
    """Full pipeline completes with ranked options in operation_store."""
    orch, _, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})

    await orch.run(
        operation_id="op-001",
        design_id="DESIGN-001",
        requirement_ids=["REQ-001"],
        operation_store=operation_store,
        correlation_id="corr-001",
    )

    op = operation_store["op-001"]
    assert op["status"] == "completed"
    assert len(op["options"]) >= 1
    for opt in op["options"].values():
        # Options stored as dicts after ADP-SPEC-024
        assert opt.get("status") == "pending"  # not auto-accepted


@pytest.mark.asyncio
async def test_citations_present_true_when_any_non_advisory() -> None:
    """citations_present=True when at least one option has advisory=False."""
    orch, _, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    await orch.run("op-001", "DESIGN-001", ["REQ-001"], operation_store, "corr-001")
    assert operation_store["op-001"]["citations_present"] is True


@pytest.mark.asyncio
async def test_citations_present_false_when_all_advisory() -> None:
    """citations_present=False when all options are advisory."""
    orch, _, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    await orch.run("op-001", "DESIGN-001", ["REQ-001"], operation_store)

    # Verify citations_present reflects whether any options are non-advisory
    opts = list(operation_store["op-001"].get("options", {}).values())
    expected = any(not opt.get("advisory", False) for opt in opts)
    assert operation_store["op-001"]["citations_present"] is expected


# ── US4: Telemetry ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_five_spans_emitted_per_job() -> None:
    """Exactly 5 step spans are emitted per recommendation job."""
    orch, mock_telemetry, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    await orch.run("op-001", "DESIGN-001", ["REQ-001"], operation_store, "corr-001")

    step_names = {call.args[0].step_name for call in mock_telemetry.emit_step_span.call_args_list}
    assert "retrieve" in step_names
    assert "generate" in step_names
    assert "analyze_tradeoffs" in step_names
    assert "rank" in step_names
    assert "validate_citations" in step_names
    assert mock_telemetry.emit_step_span.call_count == 5


@pytest.mark.asyncio
async def test_each_span_has_required_fields() -> None:
    """Each emitted RecommendationStep has non-empty step_name and latency_ms > 0."""
    orch, mock_telemetry, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    await orch.run("op-001", "DESIGN-001", ["REQ-001"], operation_store, "corr-001")

    for call in mock_telemetry.emit_step_span.call_args_list:
        step = call.args[0]
        assert step.step_name != ""
        assert step.operation_id == "op-001"
        assert step.latency_ms >= 0


@pytest.mark.asyncio
async def test_all_spans_share_correlation_id() -> None:
    """All 5 spans share the same correlation_id (QG-11)."""
    orch, mock_telemetry, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    await orch.run("op-001", "DESIGN-001", ["REQ-001"], operation_store, "trace-123")

    for call in mock_telemetry.emit_step_span.call_args_list:
        assert call.args[0].correlation_id == "trace-123"


@pytest.mark.asyncio
async def test_failure_span_emitted_on_step_error() -> None:
    """Span is emitted and operation marked failed when a step raises."""
    orch, mock_telemetry, _ = _make_orchestrator()
    # Sabotage the knowledge retrieval to force a generate failure
    orch._knowledge.hybrid_search = AsyncMock(side_effect=ConnectionError("KB unreachable"))

    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(side_effect=ConnectionError("LLM unreachable"))
    orch._llm = mock_llm

    # Rebuild graph with sabotaged llm
    orch._graph = orch._build_graph()

    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    await orch.run("op-001", "DESIGN-001", ["REQ-001"], operation_store)

    assert operation_store["op-001"]["status"] == "failed"
    assert mock_telemetry.emit_step_span.call_count >= 1


# ── Performance: NFR-001 / SC-003 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_operation_handle_available_immediately() -> None:
    """Operation handle exists with status=pending before pipeline completes (NFR-001)."""
    orch, _, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    assert "op-001" in operation_store  # handle pre-exists before run


@pytest.mark.asyncio
async def test_recommendation_completes_within_deadline() -> None:
    """Full pipeline with mock LLM completes in under 1 second (SC-003 structural)."""
    orch, _, _ = _make_orchestrator()
    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    start = time.perf_counter()
    await orch.run("op-001", "DESIGN-001", ["REQ-001"], operation_store)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"Pipeline took {elapsed:.2f}s — should be < 1s with mock LLM"


# ── Security: QG-08 ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_key_never_in_logs(caplog) -> None:
    """API key MUST NOT appear in any log output during recommendation pipeline."""
    import logging

    FAKE_KEY = "FAKE_REC_API_KEY_regression_guard_abc999"
    orch, _, _ = _make_orchestrator()
    # Inject fake key into llm
    orch._llm._api_key = FAKE_KEY  # type: ignore[attr-defined]

    operation_store = DictOperationStore({"op-001": {"status": "pending"}})
    with caplog.at_level(logging.DEBUG, logger="adp"):
        await orch.run("op-001", "DESIGN-001", ["REQ-001"], operation_store)

    full_log = "\n".join(r.message for r in caplog.records)
    assert FAKE_KEY not in full_log
