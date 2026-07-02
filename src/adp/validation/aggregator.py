"""Aggregate critic outputs into Verdict components (ADP-SPEC-008)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from adp.validation.models import CriticOutput, Finding

if TYPE_CHECKING:
    from adp.validation.telemetry import ValidationTelemetry


def aggregate(
    critic_outputs: list[CriticOutput],
    operation_id: str,
    telemetry: "ValidationTelemetry",
    correlation_id: str | None = None,
) -> tuple[list[Finding], float | None, bool]:
    """Merge all findings, compute composite score, and determine citations_present.

    Returns: (all_findings, composite_score, citations_present)
    """
    start = time.perf_counter()

    all_findings: list[Finding] = []
    scores: list[float] = []

    for output in critic_outputs:
        all_findings.extend(output.findings)
        if output.score is not None:
            scores.append(output.score)

    composite_score = sum(scores) / len(scores) if scores else None
    citations_present = any(f.citation is not None for f in all_findings)

    latency = (time.perf_counter() - start) * 1000

    # Emit aggregation telemetry span (research Decision 9: adp.validation.aggregate)
    from adp.validation.models import CriticOutput as _CO

    agg_output = _CO(
        critic_name="aggregate",
        score=composite_score,
        latency_ms=latency,
    )
    agg_output.retrieved_knowledge_refs = []  # no retrieval in aggregation
    telemetry.emit_span(agg_output, correlation_id)

    return all_findings, composite_score, citations_present
