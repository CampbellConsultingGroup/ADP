"""Unit tests: full reconciliation cycle produces the expected file tree
(ADP-SPEC-045 US1 T013, US2 T018-T020). Mirrors
tests/unit/export/test_business_arch_reconciliation.py's conventions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import store as astore
from adp.export import application_arch

_NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
async def seeded_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/apps.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        await session.execute(astore._biz_caps.insert().values(id="cap-1", name="Claims Intake"))
        await session.execute(astore._applications.insert().values(
            id="app-1", name="Claims Processing", description=None, vendor=None,
            primary_owner=None, time_classification="Invest", r_strategy=None,
            pace_layer=None, health_score=None, business_value=None,
            business_criticality=None, owning_business_unit=None, business_owner=None,
            technical_owner=None, lifecycle_status="active", hosting_model=None,
            architecture_pattern=None, tech_debt_flags=[], created_at=_NOW, updated_at=_NOW,
        ))
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
        await session.execute(astore._application_risk.insert().values(
            app_id="app-1", security_posture="adequate", vulnerability_status=None,
            data_classification=None, regulatory_tags=[], dr_bc_status=None,
            end_of_life_date=None, end_of_support_date=None, updated_at=_NOW,
        ))
        await session.execute(astore._app_cap_links.insert().values(
            app_id="app-1", capability_id="cap-1", fit_score=4,
        ))
        await session.commit()

    yield engine
    await engine.dispose()


async def _reconcile_once(export_root, engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await application_arch.run_reconciliation_cycle(export_root, session)


async def test_reconciliation_produces_expected_file_tree(tmp_path, seeded_engine) -> None:
    await _reconcile_once(tmp_path, seeded_engine)

    root = tmp_path / "applications"
    app1 = json.loads((root / "applications" / "app-1.json").read_text())
    assert app1["name"] == "Claims Processing"
    assert app1["risk"]["security_posture"] == "adequate"
    assert app1["linked_business_capabilities"] == [
        {"capability_id": "cap-1", "capability_name": "Claims Intake", "fit_score": 4}
    ]

    app2 = json.loads((root / "applications" / "app-2.json").read_text())
    assert app2["risk"] == {
        "security_posture": None, "vulnerability_status": None, "data_classification": None,
        "regulatory_tags": [], "dr_bc_status": None,
        "end_of_life_date": None, "end_of_support_date": None,
    }

    tc1 = json.loads((root / "technical-capabilities" / "tc-1.json").read_text())
    assert tc1["name"] == "Rules Engine"

    ti1 = json.loads((root / "transformation-initiatives" / "ti-1.json").read_text())
    assert ti1["members"] == []

    intg1 = json.loads((root / "integrations" / "intg-1.json").read_text())
    assert intg1["source_app_name"] == "Claims Processing"
    assert intg1["target_app_name"] == "Policy Admin"


# ── US2: clean diffs ──────────────────────────────────────────────────────────

async def test_unchanged_reconciliation_does_not_rewrite_files(tmp_path, seeded_engine) -> None:
    await _reconcile_once(tmp_path, seeded_engine)
    path = tmp_path / "applications" / "applications" / "app-1.json"
    mtime_before = path.stat().st_mtime_ns
    content_before = path.read_text()

    await _reconcile_once(tmp_path, seeded_engine)

    assert path.stat().st_mtime_ns == mtime_before
    assert path.read_text() == content_before


async def test_changing_one_application_rewrites_only_its_file(tmp_path, seeded_engine) -> None:
    await _reconcile_once(tmp_path, seeded_engine)
    root = tmp_path / "applications"
    app2_path = root / "applications" / "app-2.json"
    tc_path = root / "technical-capabilities" / "tc-1.json"
    app2_mtime_before = app2_path.stat().st_mtime_ns
    tc_mtime_before = tc_path.stat().st_mtime_ns

    factory = async_sessionmaker(seeded_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(
            astore._applications.update()
            .where(astore._applications.c.id == "app-1")
            .values(time_classification="Eliminate")
        )
        await session.commit()

    await _reconcile_once(tmp_path, seeded_engine)

    app1 = json.loads((root / "applications" / "app-1.json").read_text())
    assert app1["time_classification"] == "Eliminate"
    assert app2_path.stat().st_mtime_ns == app2_mtime_before
    assert tc_path.stat().st_mtime_ns == tc_mtime_before


async def test_deleting_an_application_removes_its_file(tmp_path, seeded_engine) -> None:
    await _reconcile_once(tmp_path, seeded_engine)
    root = tmp_path / "applications"
    assert (root / "applications" / "app-2.json").exists()

    factory = async_sessionmaker(seeded_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(
            astore._applications.delete().where(astore._applications.c.id == "app-2")
        )
        await session.commit()

    await _reconcile_once(tmp_path, seeded_engine)

    assert not (root / "applications" / "app-2.json").exists()
    assert (root / "applications" / "app-1.json").exists()  # untouched


async def test_deleting_technical_capability_initiative_integration_removes_each_file(
    tmp_path, seeded_engine
) -> None:
    await _reconcile_once(tmp_path, seeded_engine)
    root = tmp_path / "applications"

    factory = async_sessionmaker(seeded_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(
            astore._app_integrations.delete().where(astore._app_integrations.c.id == "intg-1")
        )
        await session.execute(
            astore._transformation_initiatives.delete()
            .where(astore._transformation_initiatives.c.id == "ti-1")
        )
        await session.execute(
            astore._tech_caps.delete().where(astore._tech_caps.c.id == "tc-1")
        )
        await session.commit()

    await _reconcile_once(tmp_path, seeded_engine)

    assert not (root / "integrations" / "intg-1.json").exists()
    assert not (root / "transformation-initiatives" / "ti-1.json").exists()
    assert not (root / "technical-capabilities" / "tc-1.json").exists()
    # Applications remain, unaffected.
    assert (root / "applications" / "app-1.json").exists()
    assert (root / "applications" / "app-2.json").exists()
