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
    TechnicalCapabilityCreate,
    TechnicalCapabilityUpdate,
)

# ── ApplicationCreate ─────────────────────────────────────────────────────────

def test_application_create_valid_minimal():
    app = ApplicationCreate(name="My App")
    assert app.name == "My App"
    assert app.health_score is None
    assert app.time_classification is None


def test_application_create_valid_full():
    app = ApplicationCreate(
        name="Customer Portal",
        vendor="Acme",
        primary_owner="Platform Team",
        time_classification="Invest",
        r_strategy="Refactor",
        pace_layer="Differentiation",
        health_score=4,
    )
    assert app.time_classification == "Invest"
    assert app.health_score == 4


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


def test_application_create_health_score_zero():
    with pytest.raises(ValidationError):
        ApplicationCreate(name="App", health_score=0)


def test_application_create_health_score_six():
    with pytest.raises(ValidationError):
        ApplicationCreate(name="App", health_score=6)


def test_application_create_health_score_one():
    app = ApplicationCreate(name="App", health_score=1)
    assert app.health_score == 1


def test_application_create_health_score_five():
    app = ApplicationCreate(name="App", health_score=5)
    assert app.health_score == 5


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


def test_application_update_health_score_out_of_range():
    with pytest.raises(ValidationError):
        ApplicationUpdate(health_score=6)


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
