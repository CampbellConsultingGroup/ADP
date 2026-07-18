"""Contract tests for APM US7 — ownership & governance (ADP-SPEC-038).

Full-stack against the real store on in-memory SQLite. Auth is disabled in
tests, so the caller is ENTERPRISE_ARCHITECT and passes the sensitive-read
gate; the gate's denial path is covered in tests/authz/test_enforcement.py.
"""

from __future__ import annotations

from datetime import date, timedelta

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


async def test_get_governance_defaults_empty(client):
    app_id = await _mk_app(client, "CRM")
    resp = await client.get(f"/api/v1/applications/{app_id}/governance")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["contract_terms"] is None
    assert body["renewal_date"] is None
    assert body["sla"] is None


async def test_upsert_and_get_governance(client):
    app_id = await _mk_app(client, "ERP")
    resp = await client.put(
        f"/api/v1/applications/{app_id}/governance",
        json={
            "contract_terms": "Net 30, auto-renew",
            "renewal_date": "2027-03-15",
            "sla": "99.9% uptime",
            "business_sponsor": "jane",
            "it_owner": "raj",
            "decision_rights": "Sponsor approves scope changes",
        },
    )
    assert resp.status_code == 200, resp.text
    got = (await client.get(f"/api/v1/applications/{app_id}/governance")).json()
    assert got["contract_terms"] == "Net 30, auto-renew"
    assert got["renewal_date"] == "2027-03-15"
    assert got["sla"] == "99.9% uptime"
    assert got["business_sponsor"] == "jane"
    assert got["it_owner"] == "raj"
    assert got["decision_rights"] == "Sponsor approves scope changes"
    assert got["updated_at"] is not None


async def test_upsert_is_idempotent_update(client):
    app_id = await _mk_app(client, "WMS")
    await client.put(
        f"/api/v1/applications/{app_id}/governance", json={"sla": "99%"}
    )
    await client.put(
        f"/api/v1/applications/{app_id}/governance", json={"sla": "99.99%"}
    )
    body = (await client.get(f"/api/v1/applications/{app_id}/governance")).json()
    assert body["sla"] == "99.99%"


async def test_governance_404_for_unknown_app(client):
    resp = await client.get("/api/v1/applications/nope/governance")
    assert resp.status_code == 404
    resp2 = await client.put("/api/v1/applications/nope/governance", json={})
    assert resp2.status_code == 404


async def test_renewals_soon_within_default_window(client):
    soon = await _mk_app(client, "SoonRenewal")
    far = await _mk_app(client, "FarRenewal")
    past = await _mk_app(client, "PastRenewal")

    today = date.today()
    await client.put(
        f"/api/v1/applications/{soon}/governance",
        json={"renewal_date": (today + timedelta(days=30)).isoformat()},
    )
    await client.put(
        f"/api/v1/applications/{far}/governance",
        json={"renewal_date": (today + timedelta(days=365)).isoformat()},
    )
    await client.put(
        f"/api/v1/applications/{past}/governance",
        json={"renewal_date": (today - timedelta(days=10)).isoformat()},
    )

    resp = await client.get("/api/v1/applications/governance/renewals-soon")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "SoonRenewal"


async def test_renewals_soon_custom_window(client):
    app_id = await _mk_app(client, "MidRange")
    today = date.today()
    await client.put(
        f"/api/v1/applications/{app_id}/governance",
        json={"renewal_date": (today + timedelta(days=120)).isoformat()},
    )

    default_resp = await client.get("/api/v1/applications/governance/renewals-soon")
    assert default_resp.json()["total"] == 0

    wide_resp = await client.get(
        "/api/v1/applications/governance/renewals-soon", params={"within_days": 180}
    )
    assert wide_resp.status_code == 200
    assert wide_resp.json()["total"] == 1
