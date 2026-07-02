"""Tests for trace ID context, filter, and US4 failure surfacing (T004, T022, T023)."""

from __future__ import annotations

import logging

import pytest


def test_set_get_trace_id():
    from adp.telemetry.context import get_trace_id, set_trace_id

    set_trace_id("abc123")
    assert get_trace_id() == "abc123"


def test_generate_trace_id_is_non_empty():
    from adp.telemetry.context import generate_trace_id

    tid = generate_trace_id()
    assert len(tid) > 0
    assert isinstance(tid, str)


def test_trace_id_filter_injects_trace_id(caplog):
    """QG-10: TraceIdFilter must inject trace_id into every log record."""
    from adp.telemetry.context import TraceIdFilter, set_trace_id

    set_trace_id("test-trace-001")
    logger = logging.getLogger("test_trace_filter")
    logger.addFilter(TraceIdFilter())

    with caplog.at_level(logging.INFO, logger="test_trace_filter"):
        logger.info("test event")

    assert len(caplog.records) == 1
    assert caplog.records[0].trace_id == "test-trace-001"  # type: ignore[attr-defined]


def test_trace_id_filter_falls_back_to_no_trace(caplog):
    from adp.telemetry.context import TraceIdFilter, set_trace_id

    set_trace_id("")  # empty → no-trace fallback
    logger = logging.getLogger("test_trace_filter_fallback")
    logger.addFilter(TraceIdFilter())

    with caplog.at_level(logging.INFO, logger="test_trace_filter_fallback"):
        logger.info("fallback event")

    assert caplog.records[0].trace_id == "no-trace"  # type: ignore[attr-defined]


def test_exception_propagates_from_ai_step_span(caplog):
    """US4 / FR-005: exceptions must not be silently swallowed; ERROR log emitted."""
    from adp.telemetry.context import set_trace_id
    from adp.telemetry.spans import ai_step_span

    set_trace_id("trace-error-test")

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="network timeout"):
            with ai_step_span("test_step"):
                raise RuntimeError("network timeout")

    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(error_records) >= 1
    messages = " ".join(r.getMessage() for r in error_records)
    assert "RuntimeError" in messages or "network timeout" in messages
