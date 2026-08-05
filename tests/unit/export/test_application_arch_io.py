"""Unit tests: bulk reads and failure isolation for Application registry
export (ADP-SPEC-045 T009/T011). Mirrors
tests/unit/export/test_business_arch_io.py's conventions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import store as astore
from adp.export import application_arch

_NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
async def seeded_session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/apps.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        # Reference rows for joins (business capability, value stream stage, domain).
        await session.execute(astore._biz_caps.insert().values(id="cap-1", name="Claims Intake"))
        await session.execute(astore._stages.insert().values(id="stage-1", name="Quote"))
        await session.execute(astore._domains.insert().values(id="dom-1", name="Claims"))

        # app-1: fully populated (extension records + every relationship type).
        await session.execute(astore._applications.insert().values(
            id="app-1", name="Claims Processing", description=None, vendor=None,
            primary_owner=None, time_classification="Invest", r_strategy=None,
            pace_layer=None, health_score=None, business_value=None,
            business_criticality=None, owning_business_unit=None, business_owner=None,
            technical_owner=None, lifecycle_status="active", hosting_model=None,
            architecture_pattern=None, tech_debt_flags=[], created_at=_NOW, updated_at=_NOW,
        ))
        # app-2: no extension records, no relationships.
        await session.execute(astore._applications.insert().values(
            id="app-2", name="Policy Admin", description=None, vendor=None,
            primary_owner=None, time_classification=None, r_strategy=None,
            pace_layer=None, health_score=None, business_value=None,
            business_criticality=None, owning_business_unit=None, business_owner=None,
            technical_owner=None, lifecycle_status="active", hosting_model=None,
            architecture_pattern=None, tech_debt_flags=[], created_at=_NOW, updated_at=_NOW,
        ))

        await session.execute(astore._tech_caps.insert().values(
            id="tc-1", name="Rules Engine", description=None, parent_id=None,
            level=1, created_at=_NOW, strategic_relevance=None,
        ))

        await session.execute(astore._transformation_initiatives.insert().values(
            id="ti-1", name="Legacy Retirement", description=None, target_date=None,
            created_at=_NOW, updated_at=_NOW,
        ))

        await session.execute(astore._app_integrations.insert().values(
            id="intg-1", source_app_id="app-1", target_app_id="app-2",
            integration_type="API", description=None, created_at=_NOW, updated_at=_NOW,
        ))

        # Sensitive extension records for app-1 only.
        await session.execute(astore._application_risk.insert().values(
            app_id="app-1", security_posture="adequate", vulnerability_status=None,
            data_classification=None, regulatory_tags=[], dr_bc_status=None,
            end_of_life_date=None, end_of_support_date=None, updated_at=_NOW,
        ))
        cost_values = {"app_id": "app-1", "currency": "USD", "horizon_years": 5, "updated_at": _NOW}
        for bucket in (
            "acquisition", "implementation", "training", "operational",
            "maintenance", "upgrades", "risk_downtime", "end_of_life",
        ):
            cost_values[f"{bucket}_one_time"] = 0
            cost_values[f"{bucket}_annual"] = 0
        await session.execute(astore._application_cost.insert().values(**cost_values))
        await session.execute(astore._application_contracts.insert().values(
            app_id="app-1", contract_terms="Net 30", renewal_date=None, sla=None,
            business_sponsor=None, it_owner=None, decision_rights=None, updated_at=_NOW,
        ))
        await session.execute(astore._application_quality_metrics.insert().values(
            app_id="app-1", uptime_pct=None, incidents_ytd=None,
            satisfaction_score=None, perf_note=None, ticket_volume_30d=None, updated_at=_NOW,
        ))

        # Relationships, all on app-1.
        await session.execute(astore._app_cap_links.insert().values(
            app_id="app-1", capability_id="cap-1", fit_score=4,
        ))
        await session.execute(astore._app_tech_cap_links.insert().values(
            app_id="app-1", tech_cap_id="tc-1", usage_type="provides",
        ))
        await session.execute(astore._app_stage_links.insert().values(
            app_id="app-1", stage_id="stage-1",
        ))
        await session.execute(astore._app_domain_integrations.insert().values(
            id="di-1", app_id="app-1", domain_id="dom-1",
            integration_type="batch", direction="inbound", created_at=_NOW,
        ))
        await session.execute(astore._app_initiative_links.insert().values(
            app_id="app-1", initiative_id="ti-1", planned_disposition="retire",
        ))
        await session.commit()

    async with factory() as session:
        yield session
    await engine.dispose()


async def test_fetch_all_returns_complete_snapshot(seeded_session) -> None:
    snapshot = await application_arch._fetch_all(seeded_session)

    app_ids = {a.id for a in snapshot.applications}
    assert app_ids == {"app-1", "app-2"}
    assert {tc.id for tc in snapshot.technical_capabilities} == {"tc-1"}
    assert {ti.id for ti in snapshot.initiatives} == {"ti-1"}
    assert {i.id for i in snapshot.integrations} == {"intg-1"}

    assert snapshot.risk_by_app["app-1"].security_posture == "adequate"
    assert snapshot.cost_by_app["app-1"].currency == "USD"
    assert snapshot.governance_by_app["app-1"].contract_terms == "Net 30"
    assert "app-1" in snapshot.quality_by_app

    assert snapshot.capability_links_by_app["app-1"] == [
        {"capability_id": "cap-1", "capability_name": "Claims Intake", "fit_score": 4}
    ]
    assert snapshot.tech_cap_links_by_app["app-1"] == [
        {"tech_cap_id": "tc-1", "tech_cap_name": "Rules Engine", "usage_type": "provides"}
    ]
    assert snapshot.stage_links_by_app["app-1"] == [
        {"stage_id": "stage-1", "stage_name": "Quote"}
    ]
    assert snapshot.domain_integrations_by_app["app-1"] == [
        {"id": "di-1", "domain_id": "dom-1", "domain_name": "Claims",
         "integration_type": "batch", "direction": "inbound"}
    ]
    assert snapshot.initiative_links_by_app["app-1"] == [
        {"initiative_id": "ti-1", "initiative_name": "Legacy Retirement",
         "planned_disposition": "retire"}
    ]
    # Reverse view: the initiative sees app-1 as a member.
    assert snapshot.members_by_initiative["ti-1"] == [
        {"app_id": "app-1", "app_name": "Claims Processing", "planned_disposition": "retire"}
    ]


async def test_fetch_all_gives_empty_relationships_for_unlinked_app(seeded_session) -> None:
    snapshot = await application_arch._fetch_all(seeded_session)
    assert snapshot.capability_links_by_app.get("app-2", []) == []
    assert snapshot.risk_by_app.get("app-2") is None
    assert snapshot.cost_by_app.get("app-2") is None
    assert snapshot.governance_by_app.get("app-2") is None
    assert snapshot.quality_by_app.get("app-2") is None


async def test_run_reconciliation_cycle_catches_and_logs_failure(tmp_path, caplog) -> None:
    class _BoomSession:
        pass

    with patch.object(
        application_arch, "_fetch_all", side_effect=RuntimeError("boom")
    ):
        with caplog.at_level("WARNING"):
            await application_arch.run_reconciliation_cycle(tmp_path, _BoomSession())

    assert any(
        "application_arch_export.cycle_failed" in r.message for r in caplog.records
    )
