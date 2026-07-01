"""Deterministic gating function for validation verdicts (ART-X / QG-15).

gate() is a PURE FUNCTION — no side effects, no external calls, no randomness.
Given identical inputs it ALWAYS returns an identical result.
"""

from __future__ import annotations

from adp.validation.models import Finding, FindingSeverity, GatingThreshold


def gate(
    findings: list[Finding],
    thresholds: GatingThreshold,
    *,
    llm_critics_ran: bool = True,
) -> str:
    """Return 'pass', 'fail', or 'indeterminate' given findings and thresholds.

    This is the ART-X / QG-15 implementation. It is deterministic: same
    findings + same thresholds + same llm_critics_ran → same return value, always.

    Advisory findings are NEVER counted toward any blocking threshold.
    """
    if not llm_critics_ran:
        return "indeterminate"

    critical = sum(1 for f in findings if f.severity == FindingSeverity.CRITICAL)
    major = sum(1 for f in findings if f.severity == FindingSeverity.MAJOR)
    minor = sum(1 for f in findings if f.severity == FindingSeverity.MINOR)

    if (
        critical > thresholds.max_critical
        or major > thresholds.max_major
        or minor > thresholds.max_minor
    ):
        return "fail"

    return "pass"
