"""Unit tests for Application Registry Pydantic models (ADP-SPEC-036 T004)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adp.application.models import (
    ApplicationCapabilityLinkCreate,
    ApplicationCapabilityLinkUpdate,
    ApplicationCreate,
    ApplicationDomainIntegrationCreate,
    ApplicationIntegrationCreate,
    ApplicationTechCapLinkCreate,
    ApplicationUpdate,
    BusinessValueAssessmentSubmit,
    HealthAssessmentSubmit,
    TechnicalCapabilityCreate,
    TechnicalCapabilityUpdate,
)

# ── ApplicationCreate ─────────────────────────────────────────────────────────

def test_application_create_valid_minimal():
    app = ApplicationCreate(name="My App")
    assert app.name == "My App"
    assert app.time_classification is None


def test_application_create_valid_full():
    app = ApplicationCreate(
        name="Customer Portal",
        vendor="Acme",
        primary_owner="Platform Team",
        time_classification="Invest",
        r_strategy="Refactor",
        pace_layer="Differentiation",
    )
    assert app.time_classification == "Invest"


def test_application_create_rejects_health_score():
    # docs/application-health-assessment-spec.md §6 Q5: health_score is only
    # ever set via PUT /applications/{id}/health-assessment.
    with pytest.raises(ValidationError):
        ApplicationCreate(name="App", health_score=4)  # type: ignore[call-arg]


def test_application_create_blank_name():
    with pytest.raises(ValidationError):
        ApplicationCreate(name="   ")


def test_application_create_invalid_time():
    with pytest.raises(ValidationError):
        ApplicationCreate(name="App", time_classification="Spend")  # type: ignore[arg-type]


def test_application_create_invalid_r_strategy():
    with pytest.raises(ValidationError):
        ApplicationCreate(name="App", r_strategy="Discard")  # type: ignore[arg-type]


def test_application_create_invalid_pace_layer():
    with pytest.raises(ValidationError):
        ApplicationCreate(name="App", pace_layer="Fast")  # type: ignore[arg-type]


def test_application_create_extra_fields_rejected():
    with pytest.raises(ValidationError):
        ApplicationCreate(name="App", unknown_field="x")  # type: ignore[call-arg]


# ── ApplicationUpdate ─────────────────────────────────────────────────────────

def test_application_update_blank_name():
    with pytest.raises(ValidationError):
        ApplicationUpdate(name="")


def test_application_update_none_name_ok():
    update = ApplicationUpdate(name=None)
    assert update.name is None


def test_application_update_rejects_health_score():
    with pytest.raises(ValidationError):
        ApplicationUpdate(health_score=6)  # type: ignore[call-arg]


def test_application_create_rejects_business_value():
    # docs/application-business-value-assessment-spec.md §7: business_value
    # is only ever set via PUT /applications/{id}/business-value-assessment.
    with pytest.raises(ValidationError):
        ApplicationCreate(name="App", business_value=4)  # type: ignore[call-arg]


def test_application_update_rejects_business_value():
    with pytest.raises(ValidationError):
        ApplicationUpdate(business_value=4)  # type: ignore[call-arg]


# ── HealthAssessmentSubmit ────────────────────────────────────────────────────


def _all_scores(**overrides: int) -> dict[str, int]:
    base = dict(
        stability_incidents=3,
        technical_currency_debt=3,
        security_posture=3,
        support_team_capacity=3,
        documentation_knowledge=3,
        business_value_criticality=3,
    )
    base.update(overrides)
    return base


def test_health_assessment_submit_valid_all_six():
    submit = HealthAssessmentSubmit(**_all_scores(security_posture=1))
    assert submit.security_posture == 1
    assert submit.as_dimension_scores()["security_posture"] == 1
    assert len(submit.as_dimension_scores()) == 6


def test_health_assessment_submit_missing_dimension_rejected():
    scores = _all_scores()
    del scores["documentation_knowledge"]
    with pytest.raises(ValidationError):
        HealthAssessmentSubmit(**scores)  # type: ignore[arg-type]


def test_health_assessment_submit_score_zero_rejected():
    with pytest.raises(ValidationError):
        HealthAssessmentSubmit(**_all_scores(stability_incidents=0))


def test_health_assessment_submit_score_six_rejected():
    with pytest.raises(ValidationError):
        HealthAssessmentSubmit(**_all_scores(stability_incidents=6))


def test_health_assessment_submit_extra_fields_rejected():
    with pytest.raises(ValidationError):
        HealthAssessmentSubmit(**_all_scores(), unknown_field=1)  # type: ignore[call-arg]


# ── BusinessValueAssessmentSubmit ──────────────────────────────────────────────


def _all_value_scores(**overrides: int) -> dict[str, int]:
    base = dict(
        strategic_alignment=3,
        revenue_cost_impact=3,
        customer_stakeholder_impact=3,
        competitive_differentiation=3,
        risk_compliance_contribution=3,
        evidence_measurability=3,
    )
    base.update(overrides)
    return base


def test_business_value_assessment_submit_valid_all_six():
    submit = BusinessValueAssessmentSubmit(**_all_value_scores(evidence_measurability=1))
    assert submit.evidence_measurability == 1
    assert submit.as_dimension_scores()["evidence_measurability"] == 1
    assert len(submit.as_dimension_scores()) == 6


def test_business_value_assessment_submit_missing_dimension_rejected():
    scores = _all_value_scores()
    del scores["risk_compliance_contribution"]
    with pytest.raises(ValidationError):
        BusinessValueAssessmentSubmit(**scores)  # type: ignore[arg-type]


def test_business_value_assessment_submit_score_zero_rejected():
    with pytest.raises(ValidationError):
        BusinessValueAssessmentSubmit(**_all_value_scores(strategic_alignment=0))


def test_business_value_assessment_submit_score_six_rejected():
    with pytest.raises(ValidationError):
        BusinessValueAssessmentSubmit(**_all_value_scores(strategic_alignment=6))


def test_business_value_assessment_submit_extra_fields_rejected():
    with pytest.raises(ValidationError):
        BusinessValueAssessmentSubmit(**_all_value_scores(), unknown_field=1)  # type: ignore[call-arg]


# ── TechnicalCapabilityCreate ─────────────────────────────────────────────────

def test_tech_cap_create_valid():
    tc = TechnicalCapabilityCreate(name="Data Management")
    assert tc.name == "Data Management"
    assert tc.parent_id is None


def test_tech_cap_create_blank_name():
    with pytest.raises(ValidationError):
        TechnicalCapabilityCreate(name="")


def test_tech_cap_create_with_parent():
    tc = TechnicalCapabilityCreate(name="Relational DB", parent_id="some-uuid")
    assert tc.parent_id == "some-uuid"


def test_tech_cap_update_blank_name():
    with pytest.raises(ValidationError):
        TechnicalCapabilityUpdate(name="  ")


def test_tech_cap_update_none_name_ok():
    update = TechnicalCapabilityUpdate(name=None)
    assert update.name is None


# ── ApplicationCapabilityLink ─────────────────────────────────────────────────

def test_cap_link_create_valid():
    link = ApplicationCapabilityLinkCreate(capability_id="cap-1", fit_score=3)
    assert link.fit_score == 3


def test_cap_link_create_fit_score_zero():
    with pytest.raises(ValidationError):
        ApplicationCapabilityLinkCreate(capability_id="cap-1", fit_score=0)


def test_cap_link_create_fit_score_six():
    with pytest.raises(ValidationError):
        ApplicationCapabilityLinkCreate(capability_id="cap-1", fit_score=6)


def test_cap_link_create_fit_score_bounds():
    ApplicationCapabilityLinkCreate(capability_id="cap-1", fit_score=1)
    ApplicationCapabilityLinkCreate(capability_id="cap-1", fit_score=5)


def test_cap_link_update_valid():
    update = ApplicationCapabilityLinkUpdate(fit_score=5)
    assert update.fit_score == 5


def test_cap_link_update_out_of_range():
    with pytest.raises(ValidationError):
        ApplicationCapabilityLinkUpdate(fit_score=0)


# ── ApplicationTechCapLink ────────────────────────────────────────────────────

def test_tech_cap_link_create_valid():
    link = ApplicationTechCapLinkCreate(tech_cap_id="tc-1", usage_type="provides")
    assert link.usage_type == "provides"


def test_tech_cap_link_create_consumes():
    link = ApplicationTechCapLinkCreate(tech_cap_id="tc-1", usage_type="consumes")
    assert link.usage_type == "consumes"


def test_tech_cap_link_create_invalid_type():
    with pytest.raises(ValidationError):
        ApplicationTechCapLinkCreate(tech_cap_id="tc-1", usage_type="reads")  # type: ignore[arg-type]


# ── ApplicationDomainIntegrationCreate ───────────────────────────────────────

def test_domain_integration_create_valid():
    adi = ApplicationDomainIntegrationCreate(
        domain_id="dom-1", integration_type="primary-support", direction="inbound"
    )
    assert adi.direction == "inbound"


def test_domain_integration_create_blank_type():
    with pytest.raises(ValidationError):
        ApplicationDomainIntegrationCreate(integration_type="   ", direction="inbound")


def test_domain_integration_create_invalid_direction():
    with pytest.raises(ValidationError):
        ApplicationDomainIntegrationCreate(
            integration_type="support", direction="lateral"  # type: ignore[arg-type]
        )


def test_domain_integration_create_all_directions():
    for d in ("inbound", "outbound", "bidirectional"):
        adi = ApplicationDomainIntegrationCreate(integration_type="x", direction=d)  # type: ignore[arg-type]
        assert adi.direction == d


# ── ApplicationIntegrationCreate ─────────────────────────────────────────────

def test_integration_create_valid():
    intg = ApplicationIntegrationCreate(
        source_app_id="app-a",
        target_app_id="app-b",
        integration_type="API",
    )
    assert intg.integration_type == "API"


def test_integration_create_self_loop():
    with pytest.raises(ValidationError):
        ApplicationIntegrationCreate(
            source_app_id="app-a",
            target_app_id="app-a",
            integration_type="API",
        )


def test_integration_create_invalid_type():
    with pytest.raises(ValidationError):
        ApplicationIntegrationCreate(
            source_app_id="app-a",
            target_app_id="app-b",
            integration_type="REST",  # type: ignore[arg-type]
        )


def test_integration_create_all_types():
    for t in ("API", "event", "file", "database", "messaging", "other"):
        intg = ApplicationIntegrationCreate(
            source_app_id="a", target_app_id="b", integration_type=t  # type: ignore[arg-type]
        )
        assert intg.integration_type == t
