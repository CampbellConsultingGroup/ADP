"""940-org-units-geography (research R7): org units + geography in the business export."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.export.organization import reconcile_organization
from adp.organization import store as ostore
from adp.organization.geodata import geography_seed_rows
from adp.organization.models import OrgUnitCreate

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)


@pytest.fixture()
async def session(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(ostore, "index_entity", _noop)
    monkeypatch.setattr(ostore, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/exp.db")
    async with engine.begin() as conn:
        await conn.run_sync(ostore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(ostore._geographies.insert(), geography_seed_rows(NOW))
        yield s
    await engine.dispose()


async def test_writes_org_units_and_geographies_and_cleans_orphans(session, tmp_path):
    rc = await ostore.create_org_unit(OrgUnitCreate(name="Retail Co"), session)
    st = await ostore.create_org_unit(
        OrgUnitCreate(name="Stores", parent_id=rc.id, primary_geography_id="geo-m49-019"), session
    )
    await ostore.link_geography(st.id, "geo-US", session)
    await session.execute(
        ostore._applications.insert().values(
            id="pos", name="POS", owning_business_unit="x", owning_org_unit_id=st.id
        )
    )
    root = tmp_path / "out"
    await reconcile_organization(root, session, NOW)

    stores = json.loads((root / "organization" / "org-units" / f"{st.id}.json").read_text())
    assert stores["kind"] == "division" and stores["path"] == ["Retail Co"]
    assert stores["geography_ids"] == ["geo-US"]
    assert stores["primary_geography_id"] == "geo-m49-019"
    assert stores["application_ids"] == ["pos"]
    geos = json.loads((root / "organization" / "geographies.json").read_text())["geographies"]
    assert geos[0]["id"] == "geo-001"
    assert next(g for g in geos if g["id"] == "geo-DE")["code"] == "DE"

    await ostore.delete_org_unit(st.id, session)
    await reconcile_organization(root, session, NOW)
    assert not (root / "organization" / "org-units" / f"{st.id}.json").exists()
    assert (root / "organization" / "org-units" / f"{rc.id}.json").exists()
