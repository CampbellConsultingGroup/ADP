"""A business domain's owner is a division: a level-2 org unit (migration 056).

The domain links to the division by id (owner_org_unit_id). Create and update refuse an unknown
org unit and any org unit that is not at level 2; null clears the owner; an omitted field
leaves it unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.business import router as brouter
from adp.business import store as bstore
from adp.organization import store as ostore

BASE = "/api/v1/business/domains"


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/owner.db")
    async with engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
        await conn.run_sync(
            ostore._metadata.create_all, tables=[ostore._geographies, ostore._org_units]
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    async with factory() as session:
        for ou_id, name, level, parent in (
            ("ent", "Retail Co", 1, None),
            ("div", "Retail Operations", 2, "ent"),
            ("div2", "Digital Commerce", 2, "ent"),
            ("fn", "Store Support", 3, "div"),
        ):
            await session.execute(
                ostore._org_units.insert().values(
                    id=ou_id, name=name, level=level, parent_id=parent,
                    created_at=now, updated_at=now,
                )
            )
        await session.commit()

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[brouter._get_session] = _override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    await engine.dispose()


async def _create(client, **extra) -> httpx.Response:
    return await client.post(BASE, json={"name": "Stores", "classification": "strategic", **extra})


async def test_create_with_a_division_owner(client):
    resp = await _create(client, owner_org_unit_id="div")
    assert resp.status_code == 201, resp.text
    domain = resp.json()
    assert domain["owner_org_unit_id"] == "div"
    listed = (await client.get(BASE)).json()["items"]
    assert listed[0]["owner_org_unit_id"] == "div"
    detail = (await client.get(f"{BASE}/{domain['id']}")).json()
    assert detail["owner_org_unit_id"] == "div"


async def test_owner_is_optional(client):
    resp = await _create(client)
    assert resp.status_code == 201
    assert resp.json()["owner_org_unit_id"] is None


@pytest.mark.parametrize(
    ("ou_id", "message"),
    [("ent", "level-2"), ("fn", "level-2"), ("nope", "not found")],
)
async def test_owner_must_be_an_existing_division(client, ou_id, message):
    resp = await _create(client, owner_org_unit_id=ou_id)
    assert resp.status_code == 422
    assert message in resp.json()["detail"]


async def test_update_changes_clears_and_keeps_the_owner(client):
    domain = (await _create(client, owner_org_unit_id="div", org_unit="Old text")).json()
    url = f"{BASE}/{domain['id']}"

    resp = await client.put(url, json={"owner_org_unit_id": "div2", "org_unit": None})
    assert resp.status_code == 200
    assert resp.json()["owner_org_unit_id"] == "div2"
    assert resp.json()["org_unit"] is None

    # Omitted: unchanged.
    resp = await client.put(url, json={"classification": "commodity"})
    assert resp.json()["owner_org_unit_id"] == "div2"

    resp = await client.put(url, json={"owner_org_unit_id": "fn"})
    assert resp.status_code == 422
    assert (await client.get(url)).json()["owner_org_unit_id"] == "div2"

    resp = await client.put(url, json={"owner_org_unit_id": None})
    assert resp.json()["owner_org_unit_id"] is None
