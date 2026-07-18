"""Contract tests for APM US6 — lifecycle & roadmap (ADP-SPEC-038).

Full-stack against the real store on in-memory SQLite. Auth is disabled in
tests, so mutations under /transformation-initiatives (WRITE_APPLICATION,
same non-sensitive prefix rule as tech-caps/integrations) are permitted.
"""

from __future__ import annotations

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import router as arouter
from adp.application import store as astore

# Composite PK from migration 017 (store metadata omits it; Alembic owns schema) —
# mirrors the _UNIQUE_DDL workaround in test_application_registry_api.py.
_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_app_initiative ON application_initiative_links(app_id, initiative_id)",
]


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/apm.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
        for ddl in _UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
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


async def _mk_app(client, name, **extra) -> str:
    resp = await client.post("/api/v1/applications", json={"name": name, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _mk_initiative(client, name, **extra) -> str:
    resp = await client.post(
        "/api/v1/transformation-initiatives", json={"name": name, **extra}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_create_and_get_initiative(client):
    initiative_id = await _mk_initiative(
        client, "Cloud Migration", description="Move legacy apps to cloud", target_date="2027-01-01"
    )
    resp = await client.get(f"/api/v1/transformation-initiatives/{initiative_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Cloud Migration"
    assert body["target_date"] == "2027-01-01"
    assert body["members"] == []


async def test_initiative_not_found(client):
    resp = await client.get("/api/v1/transformation-initiatives/nope")
    assert resp.status_code == 404


async def test_invalid_initiative_name_rejected(client):
    resp = await client.post("/api/v1/transformation-initiatives", json={"name": "  "})
    assert resp.status_code == 422


async def test_link_apps_and_retrieve_with_members(client):
    initiative_id = await _mk_initiative(client, "Legacy Retirement")
    app1 = await _mk_app(client, "Alpha")
    app2 = await _mk_app(client, "Beta")

    r1 = await client.post(
        f"/api/v1/applications/{app1}/initiative-links",
        json={"initiative_id": initiative_id, "planned_disposition": "retire"},
    )
    assert r1.status_code == 201, r1.text
    r2 = await client.post(
        f"/api/v1/applications/{app2}/initiative-links",
        json={"initiative_id": initiative_id, "planned_disposition": "replace"},
    )
    assert r2.status_code == 201, r2.text

    detail = (await client.get(f"/api/v1/transformation-initiatives/{initiative_id}")).json()
    members = {m["app_name"]: m["planned_disposition"] for m in detail["members"]}
    assert members == {"Alpha": "retire", "Beta": "replace"}

    # Each member surfaces the initiative on its own record too.
    app1_links = (await client.get(f"/api/v1/applications/{app1}/initiative-links")).json()
    assert app1_links["items"][0]["initiative_name"] == "Legacy Retirement"
    assert app1_links["items"][0]["planned_disposition"] == "retire"


async def test_duplicate_link_rejected(client):
    initiative_id = await _mk_initiative(client, "Consolidation")
    app_id = await _mk_app(client, "Gamma")
    await client.post(
        f"/api/v1/applications/{app_id}/initiative-links",
        json={"initiative_id": initiative_id, "planned_disposition": "modernize"},
    )
    resp = await client.post(
        f"/api/v1/applications/{app_id}/initiative-links",
        json={"initiative_id": initiative_id, "planned_disposition": "modernize"},
    )
    assert resp.status_code == 409


async def test_invalid_disposition_rejected(client):
    initiative_id = await _mk_initiative(client, "Modernization")
    app_id = await _mk_app(client, "Delta")
    resp = await client.post(
        f"/api/v1/applications/{app_id}/initiative-links",
        json={"initiative_id": initiative_id, "planned_disposition": "rewrite"},
    )
    assert resp.status_code == 422


async def test_update_and_delete_link(client):
    initiative_id = await _mk_initiative(client, "Rationalization")
    app_id = await _mk_app(client, "Epsilon")
    await client.post(
        f"/api/v1/applications/{app_id}/initiative-links",
        json={"initiative_id": initiative_id, "planned_disposition": "invest"},
    )

    patched = await client.patch(
        f"/api/v1/applications/{app_id}/initiative-links/{initiative_id}",
        json={"planned_disposition": "modernize"},
    )
    assert patched.status_code == 200
    assert patched.json()["planned_disposition"] == "modernize"

    deleted = await client.delete(
        f"/api/v1/applications/{app_id}/initiative-links/{initiative_id}"
    )
    assert deleted.status_code == 204
    links = (await client.get(f"/api/v1/applications/{app_id}/initiative-links")).json()
    assert links["items"] == []


async def test_roadmap_surfaces_eliminate_and_sunset_apps(client):
    eliminate_app = await _mk_app(client, "OldERP", time_classification="Eliminate")
    await _mk_app(client, "SunsetCRM", lifecycle_status="sunset")
    healthy_app = await _mk_app(client, "HealthyApp", time_classification="Invest")

    await client.put(
        f"/api/v1/applications/{eliminate_app}/risk",
        json={"end_of_life_date": "2026-12-31"},
    )

    initiative_id = await _mk_initiative(client, "Decommission Wave 1")
    await client.post(
        f"/api/v1/applications/{eliminate_app}/initiative-links",
        json={"initiative_id": initiative_id, "planned_disposition": "retire"},
    )

    resp = await client.get("/api/v1/applications/roadmap")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    names = {e["name"] for e in body["items"]}
    assert names == {"OldERP", "SunsetCRM"}
    assert healthy_app  # not on the roadmap; sanity that it exists

    old_erp = next(e for e in body["items"] if e["name"] == "OldERP")
    assert old_erp["end_of_life_date"] == "2026-12-31"
    assert old_erp["initiative_links"][0]["initiative_name"] == "Decommission Wave 1"


async def test_update_initiative(client):
    initiative_id = await _mk_initiative(client, "Draft Name")
    resp = await client.patch(
        f"/api/v1/transformation-initiatives/{initiative_id}",
        json={"name": "Final Name", "target_date": "2028-06-01"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Final Name"
    assert resp.json()["target_date"] == "2028-06-01"


async def test_delete_initiative(client):
    initiative_id = await _mk_initiative(client, "Throwaway")
    resp = await client.delete(f"/api/v1/transformation-initiatives/{initiative_id}")
    assert resp.status_code == 204
    resp2 = await client.get(f"/api/v1/transformation-initiatives/{initiative_id}")
    assert resp2.status_code == 404


async def test_list_initiatives(client):
    await _mk_initiative(client, "B Initiative")
    await _mk_initiative(client, "A Initiative")
    resp = await client.get("/api/v1/transformation-initiatives")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert [i["name"] for i in body["items"]] == ["A Initiative", "B Initiative"]
