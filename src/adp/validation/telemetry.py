"""Per-critic telemetry span emission for the validation pipeline (FR-007 / QG-11).

API keys and design content are NEVER included in spans or logs.
Attribute names imported from adp.telemetry.contract (ADP-SPEC-012 normalization).
"""

from __future__ import annotations

import logging

from adp.telemetry.contract import (
    SPAN_ATTR_ERROR_MSG,
    SPAN_ATTR_ESTIMATED_COST_USD,
    SPAN_ATTR_INPUT_TOKENS,
    SPAN_ATTR_KNOWLEDGE_ITEM_IDS,
    SPAN_ATTR_LATENCY_MS,
    SPAN_ATTR_OUTPUT_TOKENS,
    SPAN_ATTR_STEP_NAME,
)
from adp.validation.models import CriticOutput

_logger = logging.getLogger("adp.validation")


class ValidationTelemetry:
    """Emit one OTel span per critic or pipeline step."""

    def emit_span(
        self,
        output: CriticOutput,
        correlation_id: str | None = None,
    ) -> None:
        """Create and end an OTel child span for one validation step."""
        try:
            from opentelemetry import trace

            tracer = trace.get_tracer("adp.validation")
            with tracer.start_as_current_span(
                f"adp.validation.{output.critic_name}"
            ) as span:
                span.set_attribute(SPAN_ATTR_STEP_NAME, output.critic_name)
                span.set_attribute("adp.critic_name", output.critic_name)
                span.set_attribute("adp.correlation_id", correlation_id or "")
                span.set_attribute(
                    SPAN_ATTR_KNOWLEDGE_ITEM_IDS,
                    ",".join(output.retrieved_knowledge_refs),
                )
                span.set_attribute(SPAN_ATTR_INPUT_TOKENS, output.input_tokens)
                span.set_attribute(SPAN_ATTR_OUTPUT_TOKENS, output.output_tokens)
                span.set_attribute(SPAN_ATTR_ESTIMATED_COST_USD, output.cost_usd)
                span.set_attribute(SPAN_ATTR_LATENCY_MS, output.latency_ms)
                if output.score is not None:
                    span.set_attribute("adp.score", output.score)
                if output.error:
                    span.set_status(trace.StatusCode.ERROR, output.error)
                    span.set_attribute(SPAN_ATTR_ERROR_MSG, output.error)

        except Exception as exc:
            _logger.warning("Failed to emit validation span for %s: %s", output.critic_name, exc)
