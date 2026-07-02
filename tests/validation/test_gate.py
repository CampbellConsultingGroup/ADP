"""Tests for gate() pure function — determinism and threshold enforcement (US2 / ART-X / QG-15)."""

from __future__ import annotations

import uuid

from adp.validation.gate import gate
from adp.validation.models import Finding, FindingSeverity, GatingThreshold


def _finding(severity: FindingSeverity, op_id: str = "op-001") -> Finding:
    return Finding(
        finding_id=str(uuid.uuid4()),
        operation_id=op_id,
        critic_name="test",
        severity=severity,
        description="Test finding",
    )


_DEFAULT = GatingThreshold()  # max_critical=0, max_major=3, max_minor=10


# ── Determinism (ART-X / QG-15) ──────────────────────────────────────────────

def test_gate_is_deterministic() -> None:
    """Calling gate() twice with identical inputs returns the same result."""
    findings = [_finding(FindingSeverity.MAJOR), _finding(FindingSeverity.MINOR)]
    result1 = gate(findings, _DEFAULT)
    result2 = gate(findings, _DEFAULT)
    assert result1 == result2


def test_gate_empty_findings_returns_pass() -> None:
    assert gate([], _DEFAULT) == "pass"


def test_gate_determinism_on_fail() -> None:
    """gate() with identical fail-triggering inputs always returns fail."""
    findings = [_finding(FindingSeverity.CRITICAL)]
    assert gate(findings, _DEFAULT) == "fail"
    assert gate(findings, _DEFAULT) == "fail"


# ── Critical threshold ────────────────────────────────────────────────────────

def test_gate_critical_threshold_zero() -> None:
    """Any critical finding fails with default max_critical=0."""
    findings = [_finding(FindingSeverity.CRITICAL)]
    assert gate(findings, _DEFAULT) == "fail"


def test_gate_no_critical_passes_default() -> None:
    """Zero critical findings with default threshold → not blocked by critical."""
    findings = [_finding(FindingSeverity.MAJOR)]
    # 1 major ≤ max_major=3, 0 critical ≤ max_critical=0 → pass
    assert gate(findings, _DEFAULT) == "pass"


# ── Major threshold ───────────────────────────────────────────────────────────

def test_gate_major_at_threshold_passes() -> None:
    """Exactly max_major major findings → pass (equal to threshold is allowed)."""
    findings = [_finding(FindingSeverity.MAJOR)] * 3  # == max_major
    assert gate(findings, _DEFAULT) == "pass"


def test_gate_major_over_threshold_fails() -> None:
    """max_major + 1 major findings → fail."""
    findings = [_finding(FindingSeverity.MAJOR)] * 4  # > max_major=3
    assert gate(findings, _DEFAULT) == "fail"


# ── Minor threshold ───────────────────────────────────────────────────────────

def test_gate_minor_at_threshold_passes() -> None:
    findings = [_finding(FindingSeverity.MINOR)] * 10  # == max_minor
    assert gate(findings, _DEFAULT) == "pass"


def test_gate_minor_over_threshold_fails() -> None:
    findings = [_finding(FindingSeverity.MINOR)] * 11  # > max_minor=10
    assert gate(findings, _DEFAULT) == "fail"


# ── Advisory never blocks ─────────────────────────────────────────────────────

def test_advisory_findings_never_block() -> None:
    """Any number of advisory findings → pass (advisory NEVER counts)."""
    findings = [_finding(FindingSeverity.ADVISORY)] * 1000
    assert gate(findings, _DEFAULT) == "pass"


def test_advisory_mixed_with_pass_findings_passes() -> None:
    """Advisory + 1 minor + 2 major → still pass (below thresholds)."""
    findings = (
        [_finding(FindingSeverity.ADVISORY)] * 50
        + [_finding(FindingSeverity.MINOR)]
        + [_finding(FindingSeverity.MAJOR)] * 2
    )
    assert gate(findings, _DEFAULT) == "pass"


# ── Indeterminate ─────────────────────────────────────────────────────────────

def test_gate_indeterminate_when_no_llm_critics_ran() -> None:
    """llm_critics_ran=False → indeterminate regardless of findings."""
    assert gate([], _DEFAULT, llm_critics_ran=False) == "indeterminate"
    assert gate(
        [_finding(FindingSeverity.CRITICAL)], _DEFAULT, llm_critics_ran=False
    ) == "indeterminate"


def test_gate_indeterminate_is_deterministic() -> None:
    """indeterminate is also deterministic."""
    assert gate([], _DEFAULT, llm_critics_ran=False) == gate([], _DEFAULT, llm_critics_ran=False)


# ── Custom thresholds ─────────────────────────────────────────────────────────

def test_gate_custom_thresholds() -> None:
    """Custom thresholds respected."""
    strict = GatingThreshold(max_critical=0, max_major=0, max_minor=0)
    # Any finding fails with strict=True
    assert gate([_finding(FindingSeverity.MINOR)], strict) == "fail"

    loose = GatingThreshold(max_critical=10, max_major=50, max_minor=100)
    assert gate([_finding(FindingSeverity.CRITICAL)] * 10, loose) == "pass"
