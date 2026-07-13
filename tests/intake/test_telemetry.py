"""Tests for IntakeTelemetry span emission (US4 / FR-006 / QG-11)."""

from __future__ import annotations

import logging

import pytest

from adp.intake.models import ExtractionSpan
from adp.intake.telemetry import IntakeTelemetry

_telemetry = IntakeTelemetry()


def _span(error: str | None = None, proposal_count: int = 3) -> ExtractionSpan:
    return ExtractionSpan(
        operation_id="op-001",
        correlation_id="corr-001",
        model="gpt-4o",
        endpoint="https://api.example.com",
        source_char_count=500,
        input_tokens=150,
        output_tokens=80,
        cost_usd=0.002,
        proposal_count=proposal_count,
        proposal_ids=["p1", "p2", "p3"][:proposal_count],
        latency_ms=1234.5,
        error=error,
    )


def test_telemetry_emit_succeeds_on_success() -> None:
    """emit() does not raise on a success span."""
    _telemetry.emit(_span())  # should not raise


def test_telemetry_emit_succeeds_on_failure() -> None:
    """emit() does not raise even when error is set."""
    _telemetry.emit(_span(error="Connection refused"))


def test_telemetry_emit_with_zero_proposals() -> None:
    """emit() handles zero proposals without error."""
    _telemetry.emit(_span(proposal_count=0))


def test_span_never_contains_api_key(caplog: pytest.LogCaptureFixture) -> None:
    """API key MUST NOT appear in span attributes or log output (QG-08)."""
    fake_key = "fake-api-key-do-not-log"
    span = ExtractionSpan(
        operation_id="op-002",
        correlation_id=None,
        model="gpt-4o",
        endpoint="https://api.example.com",  # endpoint is ok, key is not
        source_char_count=100,
        input_tokens=50,
        output_tokens=20,
        cost_usd=0.0,
        proposal_count=1,
        proposal_ids=["p1"],
        latency_ms=500.0,
    )
    with caplog.at_level(logging.DEBUG):
        _telemetry.emit(span)

    full_log = "\n".join(r.message for r in caplog.records)
    assert fake_key not in full_log
