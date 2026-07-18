"""Contract tests for APM US8 — quality & performance signals (ADP-SPEC-038).

Full-stack against the real store on in-memory SQLite. No new authz gate:
these routes ride the existing WRITE_APPLICATION prefix rule (like US5/US6).
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


async def _mk_app(client, name) -> str:
    resp = await client.post("/api/v1/applications", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_get_quality_defaults_empty(client):
    app_id = await _mk_app(client, "CRM")
    resp = await client.get(f"/api/v1/applications/{app_id}/quality")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["uptime_pct"] is None
    assert body["incidents_ytd"] is None
    assert body["satisfaction_score"] is None
    assert body["perf_note"] is None
    assert body["ticket_volume_30d"] is None


async def test_upsert_and_get_quality(client):
    app_id = await _mk_app(client, "ERP")
    resp = await client.put(
        f"/api/v1/applications/{app_id}/quality",
        json={
            "uptime_pct": "99.95",
            "incidents_ytd": 3,
            "satisfaction_score": 4,
            "perf_note": "Slow during month-end batch",
            "ticket_volume_30d": 12,
        },
    )
    assert resp.status_code == 200, resp.text
    got = (await client.get(f"/api/v1/applications/{app_id}/quality")).json()
    assert got["uptime_pct"] == "99.95"
    assert got["incidents_ytd"] == 3
    assert got["satisfaction_score"] == 4
    assert got["perf_note"] == "Slow during month-end batch"
    assert got["ticket_volume_30d"] == 12
    assert got["updated_at"] is not None


async def test_upsert_is_idempotent_update(client):
    app_id = await _mk_app(client, "WMS")
    await client.put(f"/api/v1/applications/{app_id}/quality", json={"incidents_ytd": 1})
    await client.put(f"/api/v1/applications/{app_id}/quality", json={"incidents_ytd": 5})
    body = (await client.get(f"/api/v1/applications/{app_id}/quality")).json()
    assert body["incidents_ytd"] == 5


async def test_quality_404_for_unknown_app(client):
    resp = await client.get("/api/v1/applications/nope/quality")
    assert resp.status_code == 404
    resp2 = await client.put("/api/v1/applications/nope/quality", json={})
    assert resp2.status_code == 404


@pytest.mark.parametrize(
    "field,value",
    [
        ("uptime_pct", "100.01"),
        ("uptime_pct", "-0.01"),
        ("satisfaction_score", 0),
        ("satisfaction_score", 6),
        ("incidents_ytd", -1),
        ("ticket_volume_30d", -1),
    ],
)
async def test_quality_rejects_out_of_range_values(client, field, value):
    app_id = await _mk_app(client, "OutOfRange")
    resp = await client.put(
        f"/api/v1/applications/{app_id}/quality", json={field: value}
    )
    assert resp.status_code == 422, resp.text
