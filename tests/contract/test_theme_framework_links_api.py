"""Contract tests for Theme–Framework Mapping (927-theme-framework-mapping, COMPLY-05 link #3).

Full-stack against the real app on a single in-memory SQLite database, mirroring
tests/contract/test_strategy_compliance_links_api.py's own fixture convention exactly. Every route
this feature adds -- the theme-side link/unlink routes (adp.strategy.router) and the reverse-lookup
route (adp.compliance.router) -- reads/writes exclusively through adp.strategy.store's own
read-only _regulatory_frameworks mirror (research.md D1), never touching adp.compliance.store's
real tables at all.
"""

from __future__ import annotations

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.compliance import router as crouter
from adp.strategy import router as srouter
from adp.strategy import store as sstore

_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_theme_name ON strategic_themes(name)",
    "CREATE UNIQUE INDEX uq_tfl ON theme_framework_links(theme_id, framework_id)",
]


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/theme_framework_links.db")
    async with engine.begin() as conn:
        await conn.run_sync(sstore._metadata.create_all)
        for ddl in _UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
        # Seed two Frameworks, standing in for real COMPLY-01 writes -- this fixture never mounts
        # adp.compliance's own router.
        await conn.execute(
            sstore._regulatory_frameworks.insert().values(id="FRM-1", name="GDPR")
        )
        await conn.execute(
            sstore._regulatory_frameworks.insert().values(id="FRM-2", name="SOC 2 Type II")
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[srouter._get_session] = _override
    app.dependency_overrides[crouter._get_strategy_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


BASE = "/api/v1/strategy"
COMPLIANCE_BASE = "/api/v1/compliance"


async def _mk_theme(client, name: str = "Regulatory & Compliance") -> str:
    resp = await client.post(f"{BASE}/themes", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_link_returns_framework_ids_list(client):
    theme_id = await _mk_theme(client)
    resp = await client.post(f"{BASE}/themes/{theme_id}/frameworks", json={"framework_id": "FRM-1"})
    assert resp.status_code == 201, resp.text
    assert resp.json() == ["FRM-1"]


async def test_link_duplicate_returns_409(client):
    theme_id = await _mk_theme(client)
    first = await client.post(f"{BASE}/themes/{theme_id}/frameworks", json={"framework_id": "FRM-1"})
    assert first.status_code == 201, first.text
    second = await client.post(f"{BASE}/themes/{theme_id}/frameworks", json={"framework_id": "FRM-1"})
    assert second.status_code == 409, second.text


async def test_link_to_nonexistent_framework_returns_404(client):
    theme_id = await _mk_theme(client)
    resp = await client.post(
        f"{BASE}/themes/{theme_id}/frameworks", json={"framework_id": "does-not-exist"}
    )
    assert resp.status_code == 404, resp.text


async def test_link_to_nonexistent_theme_returns_404(client):
    resp = await client.post(
        f"{BASE}/themes/does-not-exist/frameworks", json={"framework_id": "FRM-1"}
    )
    assert resp.status_code == 404, resp.text


async def test_theme_get_reflects_link(client):
    theme_id = await _mk_theme(client)
    link = await client.post(f"{BASE}/themes/{theme_id}/frameworks", json={"framework_id": "FRM-1"})
    assert link.status_code == 201, link.text

    resp = await client.get(f"{BASE}/themes/{theme_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["framework_ids"] == ["FRM-1"]


async def test_theme_list_reflects_link(client):
    theme_id = await _mk_theme(client)
    link = await client.post(f"{BASE}/themes/{theme_id}/frameworks", json={"framework_id": "FRM-1"})
    assert link.status_code == 201, link.text

    resp = await client.get(f"{BASE}/themes")
    assert resp.status_code == 200, resp.text
    theme = next(t for t in resp.json()["items"] if t["id"] == theme_id)
    assert theme["framework_ids"] == ["FRM-1"]


async def test_reverse_lookup_shows_linked_theme(client):
    theme_id = await _mk_theme(client)
    link = await client.post(f"{BASE}/themes/{theme_id}/frameworks", json={"framework_id": "FRM-1"})
    assert link.status_code == 201, link.text

    resp = await client.get(f"{COMPLIANCE_BASE}/frameworks/FRM-1/themes")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == theme_id


async def test_reverse_lookup_empty_when_none_linked(client):
    resp = await client.get(f"{COMPLIANCE_BASE}/frameworks/FRM-2/themes")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"items": [], "total": 0}


async def test_reverse_lookup_nonexistent_framework_returns_404(client):
    resp = await client.get(f"{COMPLIANCE_BASE}/frameworks/does-not-exist/themes")
    assert resp.status_code == 404, resp.text


async def test_theme_untagged_has_empty_framework_ids(client):
    theme_id = await _mk_theme(client, "Untagged Theme")
    resp = await client.get(f"{BASE}/themes/{theme_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["framework_ids"] == []


async def test_unlink_then_repeat_returns_404(client):
    theme_id = await _mk_theme(client)
    link = await client.post(f"{BASE}/themes/{theme_id}/frameworks", json={"framework_id": "FRM-1"})
    assert link.status_code == 201, link.text

    unlink = await client.delete(f"{BASE}/themes/{theme_id}/frameworks/FRM-1")
    assert unlink.status_code == 204, unlink.text

    repeat = await client.delete(f"{BASE}/themes/{theme_id}/frameworks/FRM-1")
    assert repeat.status_code == 404, repeat.text


async def test_unlink_removes_from_both_read_directions(client):
    theme_id = await _mk_theme(client)
    link = await client.post(f"{BASE}/themes/{theme_id}/frameworks", json={"framework_id": "FRM-1"})
    assert link.status_code == 201, link.text

    unlink = await client.delete(f"{BASE}/themes/{theme_id}/frameworks/FRM-1")
    assert unlink.status_code == 204, unlink.text

    theme_resp = await client.get(f"{BASE}/themes/{theme_id}")
    assert theme_resp.json()["framework_ids"] == []

    reverse_resp = await client.get(f"{COMPLIANCE_BASE}/frameworks/FRM-1/themes")
    assert reverse_resp.json() == {"items": [], "total": 0}
