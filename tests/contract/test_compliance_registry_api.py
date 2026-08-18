"""Contract tests for the Compliance Framework & Control Registry API (COMPLY-01).

Runs the /api/v1/compliance router full-stack against the real adp.compliance.store on an
in-memory SQLite database, with a unique index mirroring migration 032's composite
UNIQUE(framework_id, code) constraint so the duplicate-code (409) path behaves as it does on
PostgreSQL. Mirrors tests/contract/test_business_registry_api.py's fixture shape.
"""

from __future__ import annotations

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.compliance import router as crouter
from adp.compliance import store as cstore
from adp.compliance.models import (
    Control,
    RegulatoryFramework,
    RegulatoryFrameworkDetail,
    RegulatoryFrameworkListResponse,
)

# Composite UNIQUE from migration 032 (store metadata omits it, same convention as
# test_business_registry_api.py's _UNIQUE_DDL)
_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_controls_framework_code ON controls(framework_id, code)",
]


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/compliance.db")
    async with engine.begin() as conn:
        await conn.run_sync(cstore._metadata.create_all)
        for ddl in _UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[crouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


BASE = "/api/v1/compliance"


async def _mk_framework(client, name="GDPR", **extra) -> dict:
    payload = {
        "name": name, "jurisdiction": "EU", "authority": "European Commission",
        "version": "2016/679", **extra,
    }
    resp = await client.post(f"{BASE}/frameworks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_control(client, framework_id, code="AC-2", **extra) -> dict:
    payload = {"code": code, "title": "A control", "description": "...", **extra}
    resp = await client.post(f"{BASE}/frameworks/{framework_id}/controls", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Framework CRUD (US1) ─────────────────────────────────────────────────────

async def test_framework_create_matches_contract(client):
    resp = await client.post(
        f"{BASE}/frameworks",
        json={
            "name": "NIST 800-53 Rev 5", "jurisdiction": "US-Federal", "authority": "NIST",
            "version": "Rev 5",
        },
    )
    assert resp.status_code == 201, resp.text
    RegulatoryFramework.model_validate(resp.json())  # raises if the shape drifts


async def test_framework_list_matches_contract(client):
    await _mk_framework(client)
    resp = await client.get(f"{BASE}/frameworks")
    assert resp.status_code == 200
    RegulatoryFrameworkListResponse.model_validate(resp.json())


async def test_framework_detail_matches_contract(client):
    fw = await _mk_framework(client)
    resp = await client.get(f"{BASE}/frameworks/{fw['id']}")
    assert resp.status_code == 200
    detail = RegulatoryFrameworkDetail.model_validate(resp.json())
    assert detail.controls == []


async def test_framework_update_matches_contract(client):
    fw = await _mk_framework(client)
    resp = await client.patch(
        f"{BASE}/frameworks/{fw['id']}", json={"authority": "Updated Authority"}
    )
    assert resp.status_code == 200
    updated = RegulatoryFramework.model_validate(resp.json())
    assert updated.authority == "Updated Authority"


async def test_framework_delete_matches_contract(client):
    fw = await _mk_framework(client)
    resp = await client.delete(f"{BASE}/frameworks/{fw['id']}")
    assert resp.status_code == 204
    resp = await client.get(f"{BASE}/frameworks/{fw['id']}")
    assert resp.status_code == 404


# ── Control CRUD (US2) ───────────────────────────────────────────────────────

async def test_control_create_matches_contract(client):
    fw = await _mk_framework(client)
    resp = await client.post(
        f"{BASE}/frameworks/{fw['id']}/controls",
        json={"code": "AC-2", "title": "Account Management", "description": "..."},
    )
    assert resp.status_code == 201, resp.text
    Control.model_validate(resp.json())


async def test_control_update_matches_contract(client):
    fw = await _mk_framework(client)
    ctrl = await _mk_control(client, fw["id"])
    resp = await client.patch(f"{BASE}/controls/{ctrl['id']}", json={"title": "Renamed"})
    assert resp.status_code == 200
    updated = Control.model_validate(resp.json())
    assert updated.title == "Renamed"


async def test_control_delete_matches_contract(client):
    fw = await _mk_framework(client)
    ctrl = await _mk_control(client, fw["id"])
    resp = await client.delete(f"{BASE}/controls/{ctrl['id']}")
    assert resp.status_code == 204
