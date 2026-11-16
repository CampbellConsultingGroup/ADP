"""938-capability-model-analysis: the snapshot builder (research R2/R3), on SQLite.

Checks the maps it builds, that dangling link rows never appear, and that risk / cost are not
even queried when the caller may not read them.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import store as astore
from adp.application.cap_analysis_store import build_snapshot
from adp.application.models import (
    ApplicationCostUpdate,
    ApplicationCreate,
    ApplicationRiskUpdate,
    CostBucket,
    TechnicalCapabilityCreate,
)

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)


@pytest.fixture()
async def env(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(astore, "index_entity", _noop)
    monkeypatch.setattr(astore, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/snap.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    statements: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _record(conn, cursor, statement, *args):
        statements.append(statement)

    async with factory() as s:
        yield s, statements
    await engine.dispose()


async def _seed(s) -> dict[str, str]:
    for cid, level, parent in [("b1", 1, None), ("b2", 2, "b1"), ("b3", 3, "b2")]:
        await s.execute(
            astore._biz_caps.insert().values(
                id=cid, name=cid.upper(), level=level, parent_id=parent
            )
        )
    for cid, level, parent in [("a1", 1, None), ("a2", 2, "a1"), ("a3", 3, "a2")]:
        await s.execute(
            astore._app_caps.insert().values(
                id=cid,
                name=cid.upper(),
                level=level,
                parent_id=parent,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    tc = await astore.create_technical_capability(
        TechnicalCapabilityCreate(
            name="Offline Sync", lifecycle_status="retiring", end_of_life_date=date(2027, 6, 30)
        ),
        s,
    )
    app = await astore.create_application(ApplicationCreate(name="Store POS"), s)
    await s.execute(
        astore._biz_app_cap_links.insert().values(
            business_capability_id="b3", app_capability_id="a3", created_at=NOW
        )
    )
    await s.execute(
        astore._app_cap_tech_links.insert().values(
            app_capability_id="a3", tech_cap_id=tc.id, created_at=NOW
        )
    )
    await s.execute(
        astore._app_cap_realizations.insert().values(
            app_capability_id="a3", app_id=app.id, created_at=NOW
        )
    )
    # Dangling rows: the far end does not exist (SQLite does not enforce the FK).
    await s.execute(
        astore._biz_app_cap_links.insert().values(
            business_capability_id="b3", app_capability_id="ghost", created_at=NOW
        )
    )
    await s.execute(
        astore._app_cap_realizations.insert().values(
            app_capability_id="a3", app_id="ghost-app", created_at=NOW
        )
    )
    await astore.upsert_application_risk(app.id, ApplicationRiskUpdate(security_posture="weak"), s)
    await astore.upsert_application_cost(
        app.id, ApplicationCostUpdate(acquisition=CostBucket(one_time=Decimal("1000"))), s
    )
    return {"tc": tc.id, "app": app.id}


async def test_snapshot_maps(env):
    s, _ = env
    ids = await _seed(s)
    snap = await build_snapshot(s, risk_visible=True, cost_visible=True)
    assert set(snap.business) == {"b1", "b2", "b3"} and snap.business["b3"].parent_id == "b2"
    assert set(snap.app_caps) == {"a1", "a2", "a3"}
    assert snap.technical[ids["tc"]].lifecycle_status == "retiring"
    assert snap.technical[ids["tc"]].end_of_life_date == date(2027, 6, 30)
    assert snap.biz_to_ac == {"b3": frozenset({"a3"})}
    assert snap.ac_to_tc == {"a3": frozenset({ids["tc"]})}
    assert snap.ac_to_apps == {"a3": frozenset({ids["app"]})}
    assert snap.apps[ids["app"]].lifecycle_status == "active"
    assert snap.risk[ids["app"]].security_posture == "weak"
    assert snap.cost[ids["app"]] > 0


@pytest.mark.parametrize(
    ("risk_visible", "cost_visible"), [(False, True), (True, False), (False, False)]
)
async def test_gated_data_is_not_queried(env, risk_visible, cost_visible):
    s, statements = env
    await _seed(s)
    statements.clear()
    snap = await build_snapshot(s, risk_visible=risk_visible, cost_visible=cost_visible)
    joined = "\n".join(statements).lower()
    assert ("application_risk" in joined) is risk_visible
    assert ("application_cost" in joined) is cost_visible
    assert (snap.risk == {}) is not risk_visible
    assert (snap.cost == {}) is not cost_visible
    assert snap.risk_visible is risk_visible and snap.cost_visible is cost_visible


async def test_empty_database(env):
    s, _ = env
    snap = await build_snapshot(s, risk_visible=True, cost_visible=True)
    assert snap.business == {} and snap.biz_to_ac == {} and snap.apps == {}


# ── 943-mapping-rationale (research R4) ──────────────────────────────────────


async def test_rationale_and_time_in_snapshot_without_geography_query(env):
    s, statements = env
    ids = await _seed(s)
    await s.execute(
        astore._app_cap_realizations.update()
        .where(astore._app_cap_realizations.c.app_id == ids["app"])
        .values(rationale="target")
    )
    await s.execute(
        astore._applications.update()
        .where(astore._applications.c.id == ids["app"])
        .values(time_classification="Invest", r_strategy="Retain")
    )
    statements.clear()
    snap = await build_snapshot(s, risk_visible=False, cost_visible=False)
    assert snap.realizations[("a3", ids["app"])].rationale == "target"
    assert ("a3", "ghost-app") not in snap.realizations  # inner-joined
    info = snap.apps[ids["app"]]
    assert (info.time_classification, info.r_strategy) == ("Invest", "Retain")
    # No realization names a geography: the geography tree is not queried (this fixture
    # doesn't even have the organization tables).
    assert snap.geographies == {}
    assert "geographies" not in "\n".join(statements).lower()


async def test_geography_index_loaded_when_a_realization_names_one(env, monkeypatch):
    from adp.organization import store as ostore
    from adp.organization.store import GeographyInfo

    s, _ = env
    ids = await _seed(s)
    await s.execute(
        astore._app_cap_realizations.update()
        .where(astore._app_cap_realizations.c.app_id == ids["app"])
        .values(rationale="tactical", geography_id="geo-DE")
    )

    async def _index(session):
        return {
            "geo-m49-150": GeographyInfo("geo-001", "Europe", None),
            "geo-DE": GeographyInfo("geo-m49-150", "Germany", "DE"),
        }

    monkeypatch.setattr(ostore, "geography_index", _index)
    snap = await build_snapshot(s, risk_visible=False, cost_visible=False)
    assert snap.realizations[("a3", ids["app"])].geography_id == "geo-DE"
    assert snap.geographies["geo-DE"].parent_id == "geo-m49-150"
    assert snap.geographies["geo-DE"].code == "DE"
