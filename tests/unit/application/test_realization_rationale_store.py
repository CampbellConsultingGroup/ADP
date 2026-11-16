"""943-mapping-rationale US1: the rationale and geography on an application capability
realization, on SQLite. The organization metadata is created after the application metadata so
the geography tree exists (its narrow mirrors of application tables are skipped as existing)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import app_capabilities as ac
from adp.application import store as astore
from adp.application.app_capability_models import (
    AppCapNotFoundError,
    ApplicationCapabilityCreate,
    CapabilityLevelError,
)
from adp.application.models import ApplicationCreate
from adp.organization import store as ostore
from adp.organization.geodata import geography_seed_rows

NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)
EU, DE, GLOBAL = "geo-m49-150", "geo-DE", "geo-001"


@pytest.fixture()
async def session(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    for mod in (ac, astore):
        monkeypatch.setattr(mod, "index_entity", _noop)
        monkeypatch.setattr(mod, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/rationale.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
        await conn.run_sync(ostore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(ostore._geographies.insert(), geography_seed_rows(NOW))
        yield s
    await engine.dispose()


async def _l3(session) -> str:
    l1 = (await ac.create_app_capability(ApplicationCapabilityCreate(name="Commerce"), session)).id
    l2 = (
        await ac.create_app_capability(
            ApplicationCapabilityCreate(name="Promotions", parent_id=l1), session
        )
    ).id
    return (
        await ac.create_app_capability(
            ApplicationCapabilityCreate(name="Promotion Evaluation", parent_id=l2), session
        )
    ).id


async def _app(session, name: str) -> str:
    return (await astore.create_application(ApplicationCreate(name=name), session)).id


async def _realized(session, l3: str) -> dict:
    detail = await ac.get_app_capability_detail(l3, session)
    assert detail is not None
    return {r.name: r for r in detail.realized_by}


async def test_existing_realization_is_unclassified_everywhere(session) -> None:
    l3, pos = await _l3(session), await _app(session, "Store POS")
    await ac.add_realization(l3, pos, session)
    r = (await _realized(session, l3))["Store POS"]
    assert (r.rationale, r.geography, r.hint) == (None, None, None)


async def test_add_with_rationale_and_geography(session) -> None:
    l3, ecom = await _l3(session), await _app(session, "Commerce Cloud")
    await ac.add_realization(l3, ecom, session, rationale="tactical", geography_id=DE)
    r = (await _realized(session, l3))["Commerce Cloud"]
    assert r.rationale == "tactical"
    assert r.geography is not None and (r.geography.id, r.geography.name, r.geography.code) == (
        DE,
        "Germany",
        "DE",
    )


async def test_update_sets_changes_and_clears_each_field_independently(session) -> None:
    l3, pos = await _l3(session), await _app(session, "Store POS")
    await ac.add_realization(l3, pos, session)

    old, new = await ac.update_realization(l3, pos, {"rationale": "target"}, session)
    assert old == (None, None) and new == ("target", None)
    await ac.update_realization(l3, pos, {"geography_id": EU}, session)
    r = (await _realized(session, l3))["Store POS"]
    assert r.rationale == "target" and r.geography is not None and r.geography.id == EU

    # Omitted rationale is unchanged; explicit None clears the geography.
    await ac.update_realization(l3, pos, {"geography_id": None}, session)
    r = (await _realized(session, l3))["Store POS"]
    assert (r.rationale, r.geography) == ("target", None)
    await ac.update_realization(l3, pos, {"rationale": None}, session)
    assert (await _realized(session, l3))["Store POS"].rationale is None


async def test_update_unknown_link_is_not_found(session) -> None:
    l3, pos = await _l3(session), await _app(session, "Store POS")
    with pytest.raises(AppCapNotFoundError):
        await ac.update_realization(l3, pos, {"rationale": "target"}, session)


@pytest.mark.parametrize(
    "geo, message", [("nope", "not found"), (GLOBAL, "No geography already means everywhere")]
)
async def test_geography_is_validated(session, geo: str, message: str) -> None:
    l3, pos = await _l3(session), await _app(session, "Store POS")
    with pytest.raises(CapabilityLevelError, match=message):
        await ac.add_realization(l3, pos, session, geography_id=geo)
    await ac.add_realization(l3, pos, session)
    with pytest.raises(CapabilityLevelError, match=message):
        await ac.update_realization(l3, pos, {"geography_id": geo}, session)


async def test_dangling_geography_reads_as_everywhere(session) -> None:
    l3, pos = await _l3(session), await _app(session, "Store POS")
    await ac.add_realization(l3, pos, session, rationale="target", geography_id=DE)
    # SQLite doesn't enforce the FK; simulate the row Postgres would SET NULL.
    await session.execute(astore._app_cap_realizations.update().values(geography_id="geo-gone"))
    r = (await _realized(session, l3))["Store POS"]
    assert (r.rationale, r.geography) == ("target", None)


async def test_hint_reflects_time_classification(session) -> None:
    l3 = await _l3(session)
    app = (
        await astore.create_application(
            ApplicationCreate(name="Legacy POS", time_classification="Eliminate"), session
        )
    ).id
    await ac.add_realization(l3, app, session, rationale="target")
    assert (await _realized(session, l3))["Legacy POS"].hint == "TIME says Eliminate"


async def test_remove_drops_the_attributes(session) -> None:
    l3, pos = await _l3(session), await _app(session, "Store POS")
    await ac.add_realization(l3, pos, session, rationale="redundant", geography_id=EU)
    assert await ac.remove_realization(l3, pos, session)
    count = (
        await session.execute(sa.select(sa.func.count()).select_from(astore._app_cap_realizations))
    ).scalar_one()
    assert count == 0
