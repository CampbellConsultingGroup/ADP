"""Tests for element materialization — provenance, satisfies, audit (US3 / FR-004/005)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from adp.knowledge.schema import CitationRef
from adp.models import ArchitectureDescription, ElementKind, Requirement
from adp.recommendation.models import ProposedElement, SolutionOption
from adp.recommendation.orchestrator import RecommendationOrchestrator
from adp.recommendation.telemetry import RecommendationTelemetry

_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_option(advisory: bool = False) -> SolutionOption:
    return SolutionOption(
        option_id="opt-001",
        operation_id="op-001",
        title="API Gateway Option",
        rationale="Reuses gateway pattern",
        grounded_on=[CitationRef(item_id="PAT-012", item_version="1.3.0")],
        satisfies=["REQ-001"],
        proposed_elements=[
            ProposedElement(name="API Gateway", kind=ElementKind.CONTAINER,
                            description="Entry point", satisfies=["REQ-001"]),
        ],
        advisory=advisory,
        status="pending",
    )


def _make_orch() -> tuple[RecommendationOrchestrator, AsyncMock]:
    mock_llm = MagicMock()
    mock_kr = MagicMock()
    design = ArchitectureDescription(
        schema_version="1.0.0",
        id="DESIGN-001",
        title="Test",
        requirements=[Requirement(id="REQ-001", title="Stateless", description="stateless")],
        created_at=_NOW,
        updated_at=_NOW,
    )
    mock_store = AsyncMock()
    mock_store.get.return_value = design
    mock_store.save.return_value = MagicMock(current_version=2)

    orch = RecommendationOrchestrator(
        llm=mock_llm,
        knowledge_retrieval=mock_kr,
        design_store=mock_store,
        telemetry=MagicMock(spec=RecommendationTelemetry),
    )
    return orch, mock_store


class DictOperationStore:
    """In-memory OperationStore shim for unit tests (ADP-SPEC-024)."""

    def __init__(self, data: dict) -> None:
        self._data = data

    async def get(self, op_id) -> dict | None:
        return self._data.get(op_id)

    async def update(self, op_id, *, status=None, payload_patch=None, error=None) -> None:
        op = self._data.setdefault(op_id, {})
        if status is not None:
            op["status"] = status
        if payload_patch:
            op.update(payload_patch)

    async def update_option_status(self, op_id, option_id, new_status) -> bool:
        op = self._data.get(op_id, {})
        options = op.get("options", {})
        option = options.get(option_id)
        if option is None or option.get("status") != "pending":
            return False
        option["status"] = new_status
        return True


def _op_store(option: SolutionOption) -> DictOperationStore:
    from adp.api.routers.recommend import _option_to_dict
    return DictOperationStore({
        "op-001": {"status": "completed", "options": {"opt-001": _option_to_dict(option)}}
    })


@pytest.mark.asyncio
async def test_materialize_creates_elements_with_provenance() -> None:
    """materialize_option writes an Element with provenance=option_id (FR-004)."""
    orch, mock_store = _make_orch()
    option = _make_option()

    await orch.materialize_option(
        option_id="opt-001",
        operation_id="op-001",
        accepting_actor="sub:architect-123",
        operation_store=_op_store(option),
        design_id="DESIGN-001",
    )

    mock_store.save.assert_called_once()
    saved_design = mock_store.save.call_args[0][0]
    assert len(saved_design.elements) == 1
    element = saved_design.elements[0]
    assert element.provenance == "opt-001"
    assert element.name == "API Gateway"


@pytest.mark.asyncio
async def test_materialized_elements_carry_satisfies_links() -> None:
    """Materialized elements have satisfies links matching the option's satisfies (QG-16)."""
    orch, mock_store = _make_orch()
    option = _make_option()

    await orch.materialize_option(
        "opt-001", "op-001", "sub:architect-123",
        _op_store(option), "DESIGN-001",
    )

    saved_design = mock_store.save.call_args[0][0]
    element = saved_design.elements[0]
    assert "REQ-001" in element.satisfies


@pytest.mark.asyncio
async def test_materialization_writes_audit_entry() -> None:
    """Acceptance writes an AuditEntry with actor and action (FR-004 / QG-13)."""
    orch, mock_store = _make_orch()
    option = _make_option()

    await orch.materialize_option(
        "opt-001", "op-001", "sub:architect-123",
        _op_store(option), "DESIGN-001",
    )

    saved_design = mock_store.save.call_args[0][0]
    assert len(saved_design.audit_log) == 1
    entry = saved_design.audit_log[0]
    assert entry.actor == "sub:architect-123"
    assert entry.origin == "human"
    assert "opt-001" in entry.affected_entity


@pytest.mark.asyncio
async def test_advisory_option_requires_acknowledgment() -> None:
    """Advisory option acceptance raises ValueError without advisory_acknowledged=True."""
    orch, mock_store = _make_orch()
    advisory_option = _make_option(advisory=True)

    with pytest.raises(ValueError, match="advisory_acknowledged"):
        await orch.materialize_option(
            "opt-001", "op-001", "sub:architect-123",
            _op_store(advisory_option), "DESIGN-001",
        )
    mock_store.save.assert_not_called()


@pytest.mark.asyncio
async def test_advisory_option_accepted_with_acknowledgment() -> None:
    """Advisory option can be accepted when advisory_acknowledged=True."""
    orch, mock_store = _make_orch()
    advisory_option = _make_option(advisory=True)

    elements = await orch.materialize_option(
        "opt-001", "op-001", "sub:architect-123",
        _op_store(advisory_option), "DESIGN-001",
        advisory_acknowledged=True,
    )

    assert len(elements) == 1
    mock_store.save.assert_called_once()
