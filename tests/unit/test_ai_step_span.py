"""Tests for ai_step_span, truncation, and error handling (T005, T006, T011, T022)."""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import StatusCode

# Module-level in-memory exporter — OTel provider can only be set once per process
_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider()
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))


@pytest.fixture(autouse=True)
def _reset_exporter():
    """Clear the in-memory exporter before each test."""
    _EXPORTER.clear()
    trace.set_tracer_provider(_PROVIDER)
    yield
    _EXPORTER.clear()


def test_ai_step_span_emits_required_attributes():
    """QG-11: AI step spans MUST carry all required attributes per FR-003."""
    from adp.telemetry.contract import (
        SPAN_ATTR_DESIGN_ID,
        SPAN_ATTR_ESTIMATED_COST_USD,
        SPAN_ATTR_INPUT_TOKENS,
        SPAN_ATTR_KNOWLEDGE_ITEM_IDS,
        SPAN_ATTR_LATENCY_MS,
        SPAN_ATTR_OUTPUT_TOKENS,
        SPAN_ATTR_STEP_NAME,
    )
    from adp.telemetry.spans import ai_step_span

    with ai_step_span("retrieve", design_id="D-001") as span:
        span.set_attribute(SPAN_ATTR_INPUT_TOKENS, 10)
        span.set_attribute(SPAN_ATTR_OUTPUT_TOKENS, 5)
        span.set_attribute(SPAN_ATTR_ESTIMATED_COST_USD, 0.001)
        span.set_attribute(SPAN_ATTR_KNOWLEDGE_ITEM_IDS, '["K-001"]')

    spans = _EXPORTER.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes or {}

    assert attrs.get(SPAN_ATTR_STEP_NAME) == "retrieve"
    assert attrs.get(SPAN_ATTR_INPUT_TOKENS) == 10
    assert attrs.get(SPAN_ATTR_OUTPUT_TOKENS) == 5
    assert attrs.get(SPAN_ATTR_ESTIMATED_COST_USD) == 0.001
    assert attrs.get(SPAN_ATTR_KNOWLEDGE_ITEM_IDS) == '["K-001"]'
    assert attrs.get(SPAN_ATTR_DESIGN_ID) == "D-001"
    assert isinstance(attrs.get(SPAN_ATTR_LATENCY_MS), int)
    assert attrs.get(SPAN_ATTR_LATENCY_MS) >= 0


def test_ai_step_span_sets_error_status_on_exception():
    """US4 / FR-005: failed spans must have ERROR status and error attributes."""
    from adp.telemetry.contract import SPAN_ATTR_ERROR_MSG, SPAN_ATTR_ERROR_TYPE
    from adp.telemetry.spans import ai_step_span

    with pytest.raises(ValueError, match="test error"):
        with ai_step_span("generate"):
            raise ValueError("test error")

    spans = _EXPORTER.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert span.status.status_code == StatusCode.ERROR
    attrs = span.attributes or {}
    assert attrs.get(SPAN_ATTR_ERROR_TYPE) == "ValueError"
    assert "test error" in (attrs.get(SPAN_ATTR_ERROR_MSG) or "")


def test_span_attr_truncation():
    """SC-002 / FR-006: attribute values over MAX_SPAN_ATTR_LEN must be truncated."""
    from adp.telemetry.contract import MAX_SPAN_ATTR_LEN
    from adp.telemetry.spans import _truncate

    long_value = "x" * 2000
    result = _truncate(long_value)
    assert len(result) == 1024
    assert result.endswith("...")

    short_value = "short"
    assert _truncate(short_value) == "short"

    exact = "y" * MAX_SPAN_ATTR_LEN
    assert _truncate(exact) == exact


def test_ai_step_span_name_is_correct():
    from adp.telemetry.spans import ai_step_span

    with ai_step_span("rank"):
        pass

    spans = _EXPORTER.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "adp.rank"
