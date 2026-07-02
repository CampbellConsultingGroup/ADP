"""AI step span context manager and truncation helper (ADP-SPEC-012 FR-003, QG-11)."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from adp.telemetry.context import get_trace_id
from adp.telemetry.contract import (
    MAX_ERROR_MSG_LEN,
    MAX_SPAN_ATTR_LEN,
    SPAN_ATTR_DESIGN_ID,
    SPAN_ATTR_ERROR_MSG,
    SPAN_ATTR_ERROR_TYPE,
    SPAN_ATTR_LATENCY_MS,
    SPAN_ATTR_OPERATION_ID,
    SPAN_ATTR_STEP_NAME,
)

logger = logging.getLogger(__name__)


def _truncate(v: str, max_len: int = MAX_SPAN_ATTR_LEN) -> str:
    """Truncate a string to max_len characters, appending '...' if truncated.

    Enforces FR-006: span attribute values must never overflow telemetry backends.
    """
    if len(v) <= max_len:
        return v
    return v[: max_len - 3] + "..."


@contextmanager
def ai_step_span(
    step_name: str,
    *,
    design_id: str | None = None,
    operation_id: str | None = None,
) -> Generator[Span, None, None]:
    """Context manager for AI orchestration step spans (QG-11 / FR-003).

    Usage::

        with ai_step_span("retrieve", design_id="D-001") as span:
            span.set_attribute(SPAN_ATTR_INPUT_TOKENS, 42)
            span.set_attribute(SPAN_ATTR_KNOWLEDGE_ITEM_IDS, '["K-001"]')

    Guarantees:
    - Sets adp.step_name at entry.
    - Records adp.latency_ms at exit (always, even on error).
    - On exception: sets span status to ERROR, logs an ERROR-level event,
      sets error.type and error.message attributes, then re-raises.

    POLICY (FR-006 / QG-08): Never pass design content (names, descriptions,
    AI prompt text, AI response text) as attribute values. Pass only IDs,
    counts, lengths, and latencies.
    """
    tracer = trace.get_tracer("adp")
    with tracer.start_as_current_span(f"adp.{step_name}") as span:
        span.set_attribute(SPAN_ATTR_STEP_NAME, step_name)
        if design_id:
            span.set_attribute(SPAN_ATTR_DESIGN_ID, design_id)
        if operation_id:
            span.set_attribute(SPAN_ATTR_OPERATION_ID, operation_id)

        t0 = time.monotonic()
        try:
            yield span
        except Exception as exc:
            error_type = type(exc).__name__
            error_msg = _truncate(str(exc), MAX_ERROR_MSG_LEN)

            span.set_attribute(SPAN_ATTR_ERROR_TYPE, error_type)
            span.set_attribute(SPAN_ATTR_ERROR_MSG, error_msg)
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, error_msg))

            # FR-005: failures MUST be surfaced explicitly (ART-VI)
            logger.error(
                "ai_step.error: %s %s",
                error_type,
                error_msg,
                extra={
                    "event": "ai_step.error",
                    "step_name": step_name,
                    "error_type": error_type,
                    "trace_id": get_trace_id(),
                },
            )
            raise
        finally:
            latency_ms = int((time.monotonic() - t0) * 1000)
            span.set_attribute(SPAN_ATTR_LATENCY_MS, latency_ms)
