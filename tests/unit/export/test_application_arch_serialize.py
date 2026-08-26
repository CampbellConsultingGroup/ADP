"""Unit tests: pure serialization functions for the Application registry
export (ADP-SPEC-045 / ADP-81p.2, data-model.md §2).

Mirrors tests/unit/export/test_business_arch_serialize.py's conventions:
nullable fields present as explicit `null` (never omitted), deterministic
sorted-key output, no `exported_at` (stamped separately at write time).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal

from adp.application.models import (
    Application,
    ApplicationCost,
    ApplicationGovernance,
    ApplicationIntegration,
    ApplicationQualityMetric,
    ApplicationRisk,
    CostBucket,
    TechnicalCapability,
    TransformationInitiativeDetail,
)
from adp.export.application_arch import (
    _serialize_application,
    _serialize_initiative,
    _serialize_integration,
    _serialize_technical_capability,
)


def _minimal_app(**overrides) -> Application:
    defaults = dict(
        id="app-1",
        name="Claims Processing",
        description=None,
        vendor=None,
        primary_owner=None,
        time_classification=None,
        r_strategy=None,
        pace_layer=None,
        health_score=None,
        business_value=None,
        business_criticality=None,
        owning_business_unit=None,
        business_owner=None,
        technical_owner=None,
        lifecycle_status="active",
        hosting_model=None,
        architecture_pattern=None,
        tech_debt_flags=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Application(**defaults)


def test_serialize_application_with_no_extension_records_is_all_null() -> None:
    app = _minimal_app()
    out = _serialize_application(
        app,
        risk=None,
        cost=None,
        governance=None,
        quality=None,
        linked_business_capabilities=[],
        linked_technical_capabilities=[],
        linked_value_stream_stages=[],
        domain_integrations=[],
        initiative_links=[],
    )
    assert out["id"] == "app-1"
    assert out["name"] == "Claims Processing"
    assert out["lifecycle_status"] == "active"
    # ADP-3jj: present as explicit null, never omitted, matching hosting_model's own convention.
    assert out["application_type"] is None
    assert "application_type" in out
    # risk/cost/governance/quality present, all-unset (FR-018) -- never omitted.
    assert out["risk"] == {
        "security_posture": None,
        "vulnerability_status": None,
        "data_classification": None,
        "regulatory_tags": [],
        "dr_bc_status": None,
        "end_of_life_date": None,
        "end_of_support_date": None,
    }
    assert out["cost"]["currency"] == "USD"
    assert out["cost"]["horizon_years"] == 5
    assert out["cost"]["acquisition"] == {"one_time": "0", "annual": "0"}
    assert out["governance"] == {
        "contract_terms": None,
        "renewal_date": None,
        "sla": None,
        "business_sponsor": None,
        "it_owner": None,
        "decision_rights": None,
    }
    assert out["quality"] == {
        "uptime_pct": None,
        "incidents_ytd": None,
        "satisfaction_score": None,
        "perf_note": None,
        "ticket_volume_30d": None,
    }
    assert out["linked_business_capabilities"] == []
    assert out["linked_technical_capabilities"] == []
    assert out["linked_value_stream_stages"] == []
    assert out["domain_integrations"] == []
    assert out["initiative_links"] == []
    assert "exported_at" not in out


def test_serialize_application_embeds_populated_extension_records_and_relationships() -> None:
    app = _minimal_app(
        id="app-2", name="Policy Admin", time_classification="Invest", application_type="cots",
    )
    risk = ApplicationRisk(
        security_posture="adequate",
        vulnerability_status="open_low",
        data_classification="confidential",
        regulatory_tags=["PCI"],
        dr_bc_status="tested",
        end_of_life_date=date(2030, 1, 1),
        end_of_support_date=date(2029, 1, 1),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    cost = ApplicationCost(
        currency="USD",
        horizon_years=5,
        acquisition=CostBucket(one_time=Decimal("2000.50"), annual=Decimal("0")),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    governance = ApplicationGovernance(
        contract_terms="Net 30",
        business_sponsor="Alice",
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    quality = ApplicationQualityMetric(
        uptime_pct=Decimal("99.90"),
        incidents_ytd=2,
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    out = _serialize_application(
        app,
        risk=risk,
        cost=cost,
        governance=governance,
        quality=quality,
        linked_business_capabilities=[
            {"capability_id": "cap-1", "capability_name": "Claims Intake", "fit_score": 4}
        ],
        linked_technical_capabilities=[
            {"tech_cap_id": "tc-1", "tech_cap_name": "Rules Engine", "usage_type": "provides"}
        ],
        linked_value_stream_stages=[{"stage_id": "st-1", "stage_name": "Quote"}],
        domain_integrations=[
            {
                "id": "di-1",
                "domain_id": "dom-1",
                "domain_name": "Claims",
                "integration_type": "batch",
                "direction": "inbound",
            }
        ],
        initiative_links=[
            {"initiative_id": "ti-1", "initiative_name": "Legacy Retirement",
             "planned_disposition": "retire"}
        ],
    )

    assert out["application_type"] == "cots"
    assert out["risk"]["security_posture"] == "adequate"
    assert out["risk"]["regulatory_tags"] == ["PCI"]
    # Decimal cost amounts serialize as JSON strings, never binary floats.
    assert out["cost"]["acquisition"]["one_time"] == "2000.50"
    assert isinstance(out["cost"]["acquisition"]["one_time"], str)
    assert out["governance"]["contract_terms"] == "Net 30"
    assert out["quality"]["uptime_pct"] == "99.90"
    assert out["linked_business_capabilities"] == [
        {"capability_id": "cap-1", "capability_name": "Claims Intake", "fit_score": 4}
    ]
    assert out["initiative_links"][0]["planned_disposition"] == "retire"

    # Must be genuinely JSON-serializable (Decimal would otherwise raise).
    json.dumps(out)


def test_serialize_technical_capability() -> None:
    tc = TechnicalCapability(
        id="tc-1", name="Rules Engine", description=None, parent_id=None,
        level=1, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        strategic_relevance=None,
    )
    out = _serialize_technical_capability(tc)
    assert out == {
        "id": "tc-1", "name": "Rules Engine", "description": None,
        "parent_id": None, "level": 1, "strategic_relevance": None,
    }


def test_serialize_initiative_includes_members() -> None:
    initiative = TransformationInitiativeDetail(
        id="ti-1", name="Legacy Retirement", description=None, target_date=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        members=[],
    )
    out = _serialize_initiative(
        initiative,
        members=[
            {"app_id": "app-1", "app_name": "Claims Processing", "planned_disposition": "retire"}
        ],
    )
    assert out["id"] == "ti-1"
    assert out["members"] == [
        {"app_id": "app-1", "app_name": "Claims Processing", "planned_disposition": "retire"}
    ]


def test_serialize_initiative_empty_members_is_empty_list_not_omitted() -> None:
    initiative = TransformationInitiativeDetail(
        id="ti-2", name="No members yet", description=None, target_date=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        members=[],
    )
    out = _serialize_initiative(initiative, members=[])
    assert out["members"] == []


def test_serialize_integration() -> None:
    intg = ApplicationIntegration(
        id="intg-1", source_app_id="app-1", source_app_name="Claims Processing",
        target_app_id="app-2", target_app_name="Policy Admin",
        integration_type="API", description=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    out = _serialize_integration(intg)
    assert out == {
        "id": "intg-1",
        "source_app_id": "app-1", "source_app_name": "Claims Processing",
        "target_app_id": "app-2", "target_app_name": "Policy Admin",
        "integration_type": "API", "description": None,
    }


def test_serialize_application_is_deterministic() -> None:
    app = _minimal_app()
    kwargs = dict(
        risk=None, cost=None, governance=None, quality=None,
        linked_business_capabilities=[], linked_technical_capabilities=[],
        linked_value_stream_stages=[], domain_integrations=[], initiative_links=[],
    )
    first = _serialize_application(app, **kwargs)
    second = _serialize_application(app, **kwargs)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
