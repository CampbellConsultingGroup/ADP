"""Contract tests for APM US3 — risk & compliance register (ADP-SPEC-038).

Full-stack against the real store on in-memory SQLite. Auth is disabled in
tests, so the caller is ENTERPRISE_ARCHITECT and passes the sensitive-read gate;
the gate's denial path is covered in tests/authz/test_enforcement.py.

932-regulatory-framework-tags (ADP-bkg): regulatory_tags is now a governed set of
RegulatoryFramework ids, not free text — the fixture seeds three frameworks directly into the
read-only _regulatory_frameworks mirror (astore._regulatory_frameworks), standing in for real
COMPLY-01 writes this package never performs itself (mirrors
tests/contract/test_theme_framework_links_api.py's own seeding convention).
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
        await conn.execute(
            astore._regulatory_frameworks.insert().values(
                id="FRM-1", name="GDPR", status="in_force"
            )
        )
        await conn.execute(
            astore._regulatory_frameworks.insert().values(
                id="FRM-2", name="DORA", status="amended"
            )
        )
        await conn.execute(
            astore._regulatory_frameworks.insert().values(
                id="FRM-3", name="Repealed Reg", status="repealed"
            )
        )
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
            "regulatory_tags": ["FRM-1", "FRM-2"],
            "dr_bc_status": "tested",
            "end_of_support_date": "2030-01-01",
        },
    )
    assert resp.status_code == 200, resp.text
    got = await client.get(f"/api/v1/applications/{app_id}/risk")
    body = got.json()
    assert body["security_posture"] == "adequate"
    assert body["data_classification"] == "confidential"
    assert sorted(body["regulatory_tags"]) == ["FRM-1", "FRM-2"]
    assert body["dr_bc_status"] == "tested"
    assert body["end_of_support_date"] == "2030-01-01"
    assert body["updated_at"] is not None


async def test_unknown_framework_id_rejected(client):
    app_id = await _mk_app(client, "Unknown Tag App")
    resp = await client.put(
        f"/api/v1/applications/{app_id}/risk", json={"regulatory_tags": ["NOPE"]}
    )
    assert resp.status_code == 422, resp.text


async def test_repealed_framework_cannot_be_newly_tagged(client):
    app_id = await _mk_app(client, "Repealed Tag App")
    resp = await client.put(
        f"/api/v1/applications/{app_id}/risk", json={"regulatory_tags": ["FRM-1", "FRM-3"]}
    )
    assert resp.status_code == 422, resp.text
    # No partial write -- FRM-1 was not saved either.
    got = await client.get(f"/api/v1/applications/{app_id}/risk")
    assert got.json()["regulatory_tags"] == []


async def test_duplicate_id_in_request_persists_once(client):
    app_id = await _mk_app(client, "Dup Tag App")
    resp = await client.put(
        f"/api/v1/applications/{app_id}/risk", json={"regulatory_tags": ["FRM-1", "FRM-1"]}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["regulatory_tags"] == ["FRM-1"]


async def test_replacing_tag_set_removes_unselected(client):
    app_id = await _mk_app(client, "Replace Tag App")
    await client.put(
        f"/api/v1/applications/{app_id}/risk", json={"regulatory_tags": ["FRM-1", "FRM-2"]}
    )
    resp = await client.put(
        f"/api/v1/applications/{app_id}/risk", json={"regulatory_tags": ["FRM-2"]}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["regulatory_tags"] == ["FRM-2"]


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
