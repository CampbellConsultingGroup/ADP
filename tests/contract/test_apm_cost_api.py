"""Contract tests for APM US4 — Total Cost of Ownership (ADP-9x6, ADP-SPEC-038).

Full-stack against the real store on in-memory SQLite. Auth is disabled in
tests, so the caller is ENTERPRISE_ARCHITECT and passes the sensitive-read
gate; the gate's denial path is covered in tests/authz/test_enforcement.py.
"""

from __future__ import annotations

from decimal import Decimal

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


async def _mk_app(client, name, **extra) -> str:
    resp = await client.post("/api/v1/applications", json={"name": name, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_get_cost_defaults_zero(client):
    app_id = await _mk_app(client, "CRM")
    resp = await client.get(f"/api/v1/applications/{app_id}/cost")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["currency"] == "USD"
    assert body["horizon_years"] == 5
    assert body["tco"] == "0"
    assert body["acquisition"] == {"one_time": "0", "annual": "0"}


async def test_upsert_and_get_cost_decimal_roundtrip(client):
    app_id = await _mk_app(client, "ERP")
    resp = await client.put(
        f"/api/v1/applications/{app_id}/cost",
        json={
            "currency": "usd",
            "horizon_years": 5,
            "acquisition": {"one_time": "2000.50", "annual": "0"},
            "operational": {"one_time": "0", "annual": "5000.25"},
            "maintenance": {"one_time": "0", "annual": "1000"},
            "training": {"one_time": "3000", "annual": "0"},
        },
    )
    assert resp.status_code == 200, resp.text
    got = (await client.get(f"/api/v1/applications/{app_id}/cost")).json()
    assert got["currency"] == "USD"  # uppercased
    # NUMERIC(14,2) preserves scale exactly — no float rounding.
    assert Decimal(got["acquisition"]["one_time"]) == Decimal("2000.50")
    assert Decimal(got["operational"]["annual"]) == Decimal("5000.25")
    # one-time: 2000.50 + 3000 = 5000.50; annual: 5000.25 + 1000 = 6000.25 * 5 = 30001.25
    # total: 5000.50 + 30001.25 = 35001.75
    assert Decimal(got["tco"]) == Decimal("35001.75")
    assert got["updated_at"] is not None


async def test_horizon_change_rederives_tco_without_reentry(client):
    app_id = await _mk_app(client, "WMS")
    payload = {
        "operational": {"one_time": "0", "annual": "1000"},
        "horizon_years": 3,
    }
    await client.put(f"/api/v1/applications/{app_id}/cost", json=payload)
    first = (await client.get(f"/api/v1/applications/{app_id}/cost")).json()
    assert Decimal(first["tco"]) == Decimal("3000")

    payload["horizon_years"] = 10
    await client.put(f"/api/v1/applications/{app_id}/cost", json=payload)
    second = (await client.get(f"/api/v1/applications/{app_id}/cost")).json()
    assert Decimal(second["tco"]) == Decimal("10000")


@pytest.mark.parametrize(
    "payload",
    [
        {"currency": "US"},
        {"horizon_years": 0},
        {"acquisition": {"one_time": "-5"}},
    ],
)
async def test_invalid_cost_payload_rejected(client, payload):
    app_id = await _mk_app(client, "HRIS")
    resp = await client.put(f"/api/v1/applications/{app_id}/cost", json=payload)
    assert resp.status_code == 422


async def test_cost_404_for_unknown_app(client):
    resp = await client.get("/api/v1/applications/nope/cost")
    assert resp.status_code == 404
    resp2 = await client.put("/api/v1/applications/nope/cost", json={})
    assert resp2.status_code == 404


async def test_rollup_by_business_unit(client):
    a = await _mk_app(client, "Alpha", owning_business_unit="Finance")
    b = await _mk_app(client, "Beta", owning_business_unit="Finance")
    c = await _mk_app(client, "Gamma", owning_business_unit="Ops")
    d = await _mk_app(client, "Delta")  # unassigned business unit

    await client.put(
        f"/api/v1/applications/{a}/cost",
        json={"operational": {"annual": "1000"}, "horizon_years": 1},
    )
    await client.put(
        f"/api/v1/applications/{b}/cost",
        json={"operational": {"annual": "2000"}, "horizon_years": 1},
    )
    await client.put(
        f"/api/v1/applications/{c}/cost",
        json={"operational": {"annual": "500"}, "horizon_years": 1},
    )
    await client.put(
        f"/api/v1/applications/{d}/cost",
        json={"operational": {"annual": "100"}, "horizon_years": 1},
    )

    resp = await client.get("/api/v1/applications/cost/rollup")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    by_bu = {item["business_unit"]: item for item in body["items"]}
    assert Decimal(by_bu["Finance"]["tco"]) == Decimal("3000")
    assert by_bu["Finance"]["app_count"] == 2
    assert Decimal(by_bu["Ops"]["tco"]) == Decimal("500")
    assert Decimal(by_bu[None]["tco"]) == Decimal("100")
    assert Decimal(body["total_tco"]) == Decimal("3600")
