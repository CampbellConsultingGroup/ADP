"""Telemetry span emission for extraction jobs (FR-006 / ART-VI / QG-11).

API keys and source text are NEVER included in spans or logs.
Attribute names imported from adp.telemetry.contract (ADP-SPEC-012 normalization).
"""

from __future__ import annotations

import logging

from adp.intake.models import ExtractionSpan
from adp.telemetry.contract import (
    SPAN_ATTR_ERROR_MSG,
    SPAN_ATTR_ESTIMATED_COST_USD,
    SPAN_ATTR_INPUT_TOKENS,
    SPAN_ATTR_LATENCY_MS,
    SPAN_ATTR_OPERATION_ID,
    SPAN_ATTR_OUTPUT_TOKENS,
)

_logger = logging.getLogger("adp.intake")


class IntakeTelemetry:
    """Emit one OpenTelemetry span per extraction job."""

    def emit(self, span_data: ExtractionSpan) -> None:
        """Create and end an OTel span with extraction attributes.

        If no OTel exporter is configured (dev/test), the span is a no-op.
        """
        try:
            from opentelemetry import trace

            tracer = trace.get_tracer("adp.intake")
            with tracer.start_as_current_span("adp.intake.extraction") as span:
                span.set_attribute(SPAN_ATTR_OPERATION_ID, span_data.operation_id)
                span.set_attribute("adp.correlation_id", span_data.correlation_id or "")
                span.set_attribute("adp.model", span_data.model)
                span.set_attribute("adp.endpoint", span_data.endpoint)
                span.set_attribute("adp.source_char_count", span_data.source_char_count)
                span.set_attribute(SPAN_ATTR_INPUT_TOKENS, span_data.input_tokens)
                span.set_attribute(SPAN_ATTR_OUTPUT_TOKENS, span_data.output_tokens)
                span.set_attribute(SPAN_ATTR_ESTIMATED_COST_USD, span_data.cost_usd)
                span.set_attribute("adp.proposal_count", span_data.proposal_count)
                span.set_attribute("adp.proposal_ids", ",".join(span_data.proposal_ids))
                span.set_attribute(SPAN_ATTR_LATENCY_MS, span_data.latency_ms)

                if span_data.error:
                    span.set_status(
                        trace.StatusCode.ERROR,
                        span_data.error,
                    )
                    span.set_attribute(SPAN_ATTR_ERROR_MSG, span_data.error)

        except Exception as exc:
            _logger.warning("Failed to emit telemetry span: %s", exc)
