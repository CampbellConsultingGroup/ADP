"""Contract tests for APM US2 — application identity & ownership (ADP-SPEC-038).

Runs the applications router full-stack against the real store on in-memory
SQLite (store metadata picks up the new columns via create_all).
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import router as arouter
from adp.application import store as astore


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/apm.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[arouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def _mk_app(client, name, **extra) -> dict:
    resp = await client.post("/api/v1/applications", json={"name": name, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_with_identity(client):
    app = await _mk_app(
        client,
        "CRM",
        owning_business_unit="Sales",
        business_owner="jane",
        technical_owner="raj",
        lifecycle_status="sunset",
    )
    assert app["owning_business_unit"] == "Sales"
    assert app["business_owner"] == "jane"
    assert app["technical_owner"] == "raj"
    assert app["lifecycle_status"] == "sunset"


async def test_lifecycle_defaults_active(client):
    app = await _mk_app(client, "ERP")
    assert app["lifecycle_status"] == "active"
    assert app["owning_business_unit"] is None


async def test_invalid_lifecycle_rejected(client):
    resp = await client.post(
        "/api/v1/applications", json={"name": "WMS", "lifecycle_status": "zombie"}
    )
    assert resp.status_code == 422


async def test_patch_identity_and_lifecycle(client):
    app = await _mk_app(client, "HRIS")
    resp = await client.patch(
        f"/api/v1/applications/{app['id']}",
        json={"owning_business_unit": "People", "lifecycle_status": "retired"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["owning_business_unit"] == "People"
    assert body["lifecycle_status"] == "retired"


async def test_filter_by_business_unit(client):
    await _mk_app(client, "Alpha", owning_business_unit="Finance")
    await _mk_app(client, "Beta", owning_business_unit="Finance")
    await _mk_app(client, "Gamma", owning_business_unit="Ops")

    resp = await client.get("/api/v1/applications", params={"business_unit": "Finance"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {a["name"] for a in body["items"]} == {"Alpha", "Beta"}


async def test_filter_by_lifecycle_status(client):
    await _mk_app(client, "Live", lifecycle_status="active")
    await _mk_app(client, "Old", lifecycle_status="retired")

    resp = await client.get("/api/v1/applications", params={"lifecycle_status": "retired"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Old"
