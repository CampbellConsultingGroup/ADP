"""Integration test: one full reconciliation cycle against a real Postgres
container (ADP-SPEC-045 T014), including the pgvector-image container and
real migrations the shared tests/integration/conftest.py fixtures provide.

Seeds data BEFORE ever running a reconciliation cycle, confirming the very
first cycle performs a complete bootstrap export with no separate manual
step (FR-008), including a sensitive risk record (Clarification Q1) and a
capability-link relationship.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from adp.application import store as astore
from adp.business import store as bstore
from adp.export import application_arch

_NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)


async def test_first_cycle_bootstraps_full_export(tmp_path, db_session) -> None:
    # Seed a business capability first (application_capability_links FKs to
    # it) -- this is the one relationship crossing into ADP-SPEC-044's domain.
    await db_session.execute(bstore._capabilities.insert().values(
        id="cap-1", name="Claims Intake", description=None, level=1,
        parent_id=None, position=0, created_at=_NOW, updated_at=_NOW,
        domain_id=None, strategic_relevance=None, maturity_level=None,
    ))

    await db_session.execute(astore._applications.insert().values(
        id="app-1", name="Claims Processing", description=None, vendor=None,
        primary_owner=None, time_classification="Invest", r_strategy=None,
        pace_layer=None, health_score=None, business_value=None,
        business_criticality=None, owning_business_unit=None, business_owner=None,
        technical_owner=None, lifecycle_status="active", hosting_model=None,
        architecture_pattern=None, tech_debt_flags=[], created_at=_NOW, updated_at=_NOW,
    ))
    await db_session.execute(astore._application_risk.insert().values(
        app_id="app-1", security_posture="adequate", vulnerability_status=None,
        data_classification="confidential", regulatory_tags=["PCI"], dr_bc_status=None,
        end_of_life_date=None, end_of_support_date=None, updated_at=_NOW,
    ))
    await db_session.execute(astore._app_cap_links.insert().values(
        app_id="app-1", capability_id="cap-1", fit_score=4,
    ))
    await db_session.flush()

    export_root = tmp_path / "export"
    await application_arch.run_reconciliation_cycle(export_root, db_session)

    base = export_root / "applications"
    app = json.loads((base / "applications" / "app-1.json").read_text(encoding="utf-8"))
    assert app["name"] == "Claims Processing"
    assert app["risk"]["security_posture"] == "adequate"
    assert app["risk"]["regulatory_tags"] == ["PCI"]
    assert app["linked_business_capabilities"] == [
        {"capability_id": "cap-1", "capability_name": "Claims Intake", "fit_score": 4}
    ]
