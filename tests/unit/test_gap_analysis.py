"""Unit tests for capability gap analysis (ADP-zg3.4).

Pure logic, no DB/LLM required.
"""

from __future__ import annotations

from adp.intake.gap_analysis import CapabilityRef, RequirementRef, analyze_section


def test_requirement_matching_capability_is_present():
    req = RequirementRef(
        id="REQ-001",
        title="Fraud detection",
        description="The system must detect fraudulent payment transactions in real time",
    )
    cap = CapabilityRef(
        id="CAP-001",
        name="Fraud Detection",
        description="Detects fraudulent transactions across payment channels",
    )
    section = analyze_section([req], [cap])

    assert section.missing == []
    assert len(section.present) == 1
    match = section.present[0]
    assert match.requirement_id == "REQ-001"
    assert match.capability_id == "CAP-001"
    assert match.relevance > 0


def test_requirement_with_no_match_is_a_gap():
    req = RequirementRef(
        id="REQ-002",
        title="Quantum encryption",
        description="The system must use quantum-resistant encryption for all data at rest",
    )
    cap = CapabilityRef(id="CAP-001", name="Billing", description="Invoice generation")
    section = analyze_section([req], [cap])

    assert section.present == []
    assert len(section.missing) == 1
    assert section.missing[0].requirement_id == "REQ-002"


def test_empty_registry_is_all_gaps():
    req = RequirementRef(id="REQ-003", title="Onboarding", description="Customer onboarding flow")
    section = analyze_section([req], [])

    assert section.present == []
    assert len(section.missing) == 1


def test_empty_requirements_is_empty_result():
    cap = CapabilityRef(id="CAP-001", name="Billing", description=None)
    section = analyze_section([], [cap])

    assert section.present == []
    assert section.missing == []


def test_best_match_is_chosen_when_multiple_capabilities_overlap():
    req = RequirementRef(
        id="REQ-004",
        title="Fraud detection",
        description="Detect fraudulent payment transactions across channels in real time",
    )
    weak = CapabilityRef(id="CAP-WEAK", name="Payments", description="Payment processing")
    strong = CapabilityRef(
        id="CAP-STRONG",
        name="Fraud Detection",
        description="Detects fraudulent payment transactions across channels",
    )
    section = analyze_section([req], [weak, strong])

    assert len(section.present) == 1
    assert section.present[0].capability_id == "CAP-STRONG"


def test_below_threshold_match_is_still_a_gap():
    req = RequirementRef(
        id="REQ-005",
        title="Regulatory audit trail",
        description="Maintain an immutable audit trail for regulatory compliance reporting",
    )
    cap = CapabilityRef(id="CAP-001", name="Reporting", description="General reporting")
    section = analyze_section([req], [cap], threshold=0.9)

    assert section.present == []
    assert len(section.missing) == 1
