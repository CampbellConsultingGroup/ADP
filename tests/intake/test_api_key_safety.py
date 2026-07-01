"""Permanent regression guard: API key must never appear in logs (QG-08 / ART-V)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from adp.intake.llm import LLMClient
from adp.intake.models import IntakeSubmission, SubmissionMode
from adp.intake.orchestrator import ExtractionOrchestrator
from adp.intake.telemetry import IntakeTelemetry

_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
_FAKE_KEY = "FAKE_API_KEY_regression_guard_xyz789"


@pytest.mark.asyncio
async def test_api_key_never_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    """The API key must never appear anywhere in log output during extraction."""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm._model = "gpt-4o"
    mock_llm._base_url = "https://api.example.com"
    mock_llm.extract = AsyncMock(return_value={
        "choices": [{"message": {"content": '{"requirements": []}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    })
    # Inject the fake key into the llm client's private attribute
    mock_llm._api_key = _FAKE_KEY

    mock_telemetry = MagicMock(spec=IntakeTelemetry)
    mock_telemetry.emit = MagicMock()

    orchestrator = ExtractionOrchestrator(llm_client=mock_llm, telemetry=mock_telemetry)
    submission = IntakeSubmission(
        submission_id="sub-key-test",
        mode=SubmissionMode.BULK_TEXT,
        text="The system must be secure.",
        submitted_by="sub:test",
        submitted_at=_NOW,
        operation_id="op-key-test",
    )
    operation_store: dict = {"op-key-test": {"status": "pending"}}

    with caplog.at_level(logging.DEBUG, logger="adp"):
        await orchestrator.run(submission, operation_store)

    full_log = "\n".join(r.message for r in caplog.records)
    assert _FAKE_KEY not in full_log, (
        f"API key {_FAKE_KEY!r} leaked into log output! Log:\n{full_log}"
    )
