"""Step telemetry span emission for the recommendation pipeline (FR-006 / QG-11)."""

from __future__ import annotations

import logging

from adp.recommendation.models import RecommendationStep

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
                span.set_attribute("adp.operation_id", step.operation_id)
                span.set_attribute("adp.step", step.step_name)
                span.set_attribute("adp.correlation_id", step.correlation_id or "")
                span.set_attribute(
                    "adp.retrieved_knowledge_refs",
                    ",".join(step.retrieved_knowledge_refs),
                )
                span.set_attribute("adp.input_tokens", step.input_tokens)
                span.set_attribute("adp.output_tokens", step.output_tokens)
                span.set_attribute("adp.cost_usd", step.cost_usd)
                span.set_attribute("adp.latency_ms", step.latency_ms)
                if step.option_count:
                    span.set_attribute("adp.option_count", step.option_count)
                if step.advisory_count:
                    span.set_attribute("adp.advisory_count", step.advisory_count)
                if step.error:
                    span.set_status(trace.StatusCode.ERROR, step.error)
                    span.set_attribute("adp.error", step.error)

        except Exception as exc:
            _logger.warning("Failed to emit recommendation step span: %s", exc)
