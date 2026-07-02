"""Step telemetry span emission for the recommendation pipeline (FR-006 / QG-11).

Attribute names imported from adp.telemetry.contract (ADP-SPEC-012 normalization).
API keys MUST NOT appear in spans.
"""

from __future__ import annotations

import logging

from adp.recommendation.models import RecommendationStep
from adp.telemetry.contract import (
    SPAN_ATTR_ERROR_MSG,
    SPAN_ATTR_ESTIMATED_COST_USD,
    SPAN_ATTR_INPUT_TOKENS,
    SPAN_ATTR_KNOWLEDGE_ITEM_IDS,
    SPAN_ATTR_LATENCY_MS,
    SPAN_ATTR_OPERATION_ID,
    SPAN_ATTR_OUTPUT_TOKENS,
    SPAN_ATTR_STEP_NAME,
)

_logger = logging.getLogger("adp.recommendation")


class RecommendationTelemetry:
    """Emit one OTel span per orchestration step. API keys MUST NOT appear in spans."""

    def emit_step_span(self, step: RecommendationStep) -> None:
        """Create and end an OTel child span for one pipeline step."""
        try:
            from opentelemetry import trace

            tracer = trace.get_tracer("adp.recommendation")
            with tracer.start_as_current_span(
                f"adp.recommendation.{step.step_name}"
            ) as span:
                span.set_attribute(SPAN_ATTR_OPERATION_ID, step.operation_id)
                span.set_attribute(SPAN_ATTR_STEP_NAME, step.step_name)
                span.set_attribute("adp.correlation_id", step.correlation_id or "")
                span.set_attribute(
                    SPAN_ATTR_KNOWLEDGE_ITEM_IDS,
                    ",".join(step.retrieved_knowledge_refs),
                )
                span.set_attribute(SPAN_ATTR_INPUT_TOKENS, step.input_tokens)
                span.set_attribute(SPAN_ATTR_OUTPUT_TOKENS, step.output_tokens)
                span.set_attribute(SPAN_ATTR_ESTIMATED_COST_USD, step.cost_usd)
                span.set_attribute(SPAN_ATTR_LATENCY_MS, step.latency_ms)
                if step.option_count:
                    span.set_attribute("adp.option_count", step.option_count)
                if step.advisory_count:
                    span.set_attribute("adp.advisory_count", step.advisory_count)
                if step.error:
                    span.set_status(trace.StatusCode.ERROR, step.error)
                    span.set_attribute(SPAN_ATTR_ERROR_MSG, step.error)

        except Exception as exc:
            _logger.warning("Failed to emit recommendation step span: %s", exc)
