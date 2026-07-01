"""Per-critic telemetry span emission for the validation pipeline (FR-007 / QG-11).

API keys and design content are NEVER included in spans or logs.
"""

from __future__ import annotations

import logging

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
                span.set_attribute("adp.critic_name", output.critic_name)
                span.set_attribute("adp.operation_id", output.critic_name)
                span.set_attribute("adp.correlation_id", correlation_id or "")
                span.set_attribute(
                    "adp.retrieved_knowledge_refs",
                    ",".join(output.retrieved_knowledge_refs),
                )
                span.set_attribute("adp.input_tokens", output.input_tokens)
                span.set_attribute("adp.output_tokens", output.output_tokens)
                span.set_attribute("adp.cost_usd", output.cost_usd)
                span.set_attribute("adp.latency_ms", output.latency_ms)
                if output.score is not None:
                    span.set_attribute("adp.score", output.score)
                if output.error:
                    span.set_status(trace.StatusCode.ERROR, output.error)
                    span.set_attribute("adp.error", output.error)

        except Exception as exc:
            _logger.warning("Failed to emit validation span for %s: %s", output.critic_name, exc)
