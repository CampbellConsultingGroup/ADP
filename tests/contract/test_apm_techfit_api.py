"""Contract tests for APM US5 — technical fit depth (ADP-SPEC-038).

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


async def test_create_with_technical_fit(client):
    app = await _mk_app(
        client,
        "CRM",
        hosting_model="cloud",
        architecture_pattern="microservices",
        tech_debt_flags=["unsupported_version", "deprecated_tech"],
    )
    assert app["hosting_model"] == "cloud"
    assert app["architecture_pattern"] == "microservices"
    assert app["tech_debt_flags"] == ["unsupported_version", "deprecated_tech"]


async def test_technical_fit_defaults(client):
    app = await _mk_app(client, "ERP")
    assert app["hosting_model"] is None
    assert app["architecture_pattern"] is None
    assert app["tech_debt_flags"] == []


async def test_invalid_hosting_model_rejected(client):
    resp = await client.post(
        "/api/v1/applications", json={"name": "WMS", "hosting_model": "mainframe"}
    )
    assert resp.status_code == 422


async def test_patch_technical_fit(client):
    app = await _mk_app(client, "HRIS")
    resp = await client.patch(
        f"/api/v1/applications/{app['id']}",
        json={"hosting_model": "saas", "tech_debt_flags": ["deprecated_tech"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["hosting_model"] == "saas"
    assert body["tech_debt_flags"] == ["deprecated_tech"]


async def test_filter_by_hosting_model(client):
    await _mk_app(client, "Alpha", hosting_model="cloud")
    await _mk_app(client, "Beta", hosting_model="cloud")
    await _mk_app(client, "Gamma", hosting_model="on_prem")

    resp = await client.get("/api/v1/applications", params={"hosting_model": "cloud"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {a["name"] for a in body["items"]} == {"Alpha", "Beta"}


async def test_filter_by_tech_debt_flag(client):
    await _mk_app(client, "Flagged", tech_debt_flags=["unsupported_version"])
    await _mk_app(client, "AlsoFlagged", tech_debt_flags=["unsupported_version", "deprecated_tech"])
    await _mk_app(client, "Clean", tech_debt_flags=[])

    resp = await client.get(
        "/api/v1/applications", params={"tech_debt_flag": "unsupported_version"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {a["name"] for a in body["items"]} == {"Flagged", "AlsoFlagged"}
