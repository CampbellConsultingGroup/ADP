"""Contract tests for APM US3 — risk & compliance register (ADP-SPEC-038).

Full-stack against the real store on in-memory SQLite. Auth is disabled in
tests, so the caller is ENTERPRISE_ARCHITECT and passes the sensitive-read gate;
the gate's denial path is covered in tests/authz/test_enforcement.py.
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


async def test_get_risk_defaults_empty(client):
    app_id = await _mk_app(client, "CRM")
    resp = await client.get(f"/api/v1/applications/{app_id}/risk")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data_classification"] is None
    assert body["regulatory_tags"] == []
    assert body["end_of_support_date"] is None


async def test_upsert_and_get_risk(client):
    app_id = await _mk_app(client, "ERP")
    resp = await client.put(
        f"/api/v1/applications/{app_id}/risk",
        json={
            "security_posture": "adequate",
            "data_classification": "confidential",
            "regulatory_tags": ["SOX", "GDPR"],
            "dr_bc_status": "tested",
            "end_of_support_date": "2030-01-01",
        },
    )
    assert resp.status_code == 200, resp.text
    got = await client.get(f"/api/v1/applications/{app_id}/risk")
    body = got.json()
    assert body["security_posture"] == "adequate"
    assert body["data_classification"] == "confidential"
    assert body["regulatory_tags"] == ["SOX", "GDPR"]
    assert body["dr_bc_status"] == "tested"
    assert body["end_of_support_date"] == "2030-01-01"
    assert body["updated_at"] is not None


async def test_upsert_is_idempotent_update(client):
    app_id = await _mk_app(client, "WMS")
    await client.put(
        f"/api/v1/applications/{app_id}/risk", json={"data_classification": "internal"}
    )
    await client.put(
        f"/api/v1/applications/{app_id}/risk", json={"data_classification": "restricted"}
    )
    body = (await client.get(f"/api/v1/applications/{app_id}/risk")).json()
    assert body["data_classification"] == "restricted"


@pytest.mark.parametrize(
    "payload",
    [
        {"data_classification": "top-secret"},
        {"security_posture": "bulletproof"},
        {"dr_bc_status": "maybe"},
    ],
)
async def test_invalid_enum_rejected(client, payload):
    app_id = await _mk_app(client, "HRIS")
    resp = await client.put(f"/api/v1/applications/{app_id}/risk", json=payload)
    assert resp.status_code == 422


async def test_risk_404_for_unknown_app(client):
    resp = await client.get("/api/v1/applications/nope/risk")
    assert resp.status_code == 404
    resp2 = await client.put("/api/v1/applications/nope/risk", json={})
    assert resp2.status_code == 404


async def test_out_of_support_query(client):
    past = await _mk_app(client, "Legacy")
    future = await _mk_app(client, "Modern")
    await client.put(
        f"/api/v1/applications/{past}/risk", json={"end_of_support_date": "2000-01-01"}
    )
    await client.put(
        f"/api/v1/applications/{future}/risk", json={"end_of_support_date": "2999-01-01"}
    )

    resp = await client.get("/api/v1/applications/risk/out-of-support")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Legacy"
    assert body["items"][0]["end_of_support_date"] == "2000-01-01"
