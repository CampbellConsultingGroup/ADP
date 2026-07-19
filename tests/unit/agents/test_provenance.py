"""Unit tests for the Agent Review toolkit's provenance helpers (ADP-SPEC-039)."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

from adp.agents.provenance import write_suggestion_audit, write_suggestion_reasoning


def test_write_suggestion_audit_logs_origin_ai(caplog):
    logger = logging.getLogger("test.agents.provenance")
    with caplog.at_level(logging.INFO, logger="test.agents.provenance"):
        write_suggestion_audit(
            logger,
            actor="jane",
            action="business.capability.agent_review_accept",
            affected_entity="CAP-001",
            summary="set maturity_level=3",
            operation_id="OP-001",
            suggestion_id="SUG-001",
        )
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "origin=ai" in message
    assert "CAP-001" in message
    assert "jane" in message
    assert "OP-001" in message
    assert "SUG-001" in message


async def test_write_suggestion_reasoning_writes_via_reasoning_store():
    mock_store = AsyncMock()
    with patch("adp.api.deps.get_reasoning_store", AsyncMock(return_value=mock_store)):
        await write_suggestion_reasoning(
            operation_id="OP-001",
            suggestion_id="SUG-001",
            step_name="agent_review",
            model_id="claude-sonnet-4-6",
            reasoning_text="This capability overlaps with CAP-002.",
            prompt="system+user prompt text",
            input_tokens=10,
            output_tokens=20,
        )
    mock_store.write.assert_awaited_once()
    record = mock_store.write.await_args.args[0]
    assert record.operation_id == "OP-001"
    assert record.option_id == "SUG-001"
    assert record.step_name == "agent_review"
    assert record.input_tokens == 10
    assert record.output_tokens == 20


async def test_write_suggestion_reasoning_swallows_errors():
    with patch("adp.api.deps.get_reasoning_store", AsyncMock(side_effect=RuntimeError("boom"))):
        # Must not raise -- fire-and-forget, never blocks acceptance.
        await write_suggestion_reasoning(
            operation_id="OP-001",
            suggestion_id="SUG-001",
            step_name="agent_review",
            model_id="claude-sonnet-4-6",
            reasoning_text="text",
            prompt="prompt",
        )
