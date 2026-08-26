"""Integration tests for Theme–Framework Mapping (927-theme-framework-mapping, COMPLY-05 link #3).

Covers quickstart.md's Scenario 8 (cascade delete, both directions) -- the one case the SQLite-backed
contract test (tests/contract/test_theme_framework_links_api.py) cannot exercise, since SQLite has no
real FK/CASCADE enforcement without extra pragmas this project doesn't set up in that fixture.

Requires Docker (testcontainers). Skipped automatically when Docker is unavailable.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="session")
async def app(db_url: str, db_engine):
    """FastAPI test app wired to the test database (migrations run via db_engine)."""
    import os

    from adp.api.app import create_app

    os.environ["ADP_DATABASE_URL"] = db_url

    application = create_app()

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # adp.strategy.store's own engine covers every route this feature adds on both routers --
    # adp.strategy.router's _get_session and adp.compliance.router's _get_strategy_session both
    # resolve through sstore._get_session_factory() (research.md D1). adp.compliance.store is
    # also needed here (unlike the SQLite contract test) since these tests create a real
    # Framework through the real compliance API, not a seeded mirror row.
    import adp.compliance.store as cstore
    import adp.strategy.store as sstore

    for module in (cstore, sstore):
        module._engine = engine
        module._session_factory = factory

    yield application
    await engine.dispose()


@pytest.fixture()
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


COMPLIANCE = "/api/v1/compliance"
STRATEGY = "/api/v1/strategy"


async def _mk_theme(client, name="Regulatory & Compliance") -> dict:
    resp = await client.post(f"{STRATEGY}/themes", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_framework(client, name="GDPR") -> dict:
    resp = await client.post(
        f"{COMPLIANCE}/frameworks",
        json={
            "name": name, "jurisdiction": "EU", "authority": "European Commission",
            "version": "2016/679",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_link_and_reverse_lookup_against_real_postgres(client):
    theme = await _mk_theme(client)
    framework = await _mk_framework(client)

    link = await client.post(
        f"{STRATEGY}/themes/{theme['id']}/frameworks", json={"framework_id": framework["id"]}
    )
    assert link.status_code == 201, link.text

    reverse = await client.get(f"{COMPLIANCE}/frameworks/{framework['id']}/themes")
    assert reverse.status_code == 200
    assert reverse.json()["items"][0]["id"] == theme["id"]


async def test_delete_theme_cascades_the_link(client):
    theme = await _mk_theme(client, "Doomed Theme")
    framework = await _mk_framework(client, "SOC 2 Type II")
    link = await client.post(
        f"{STRATEGY}/themes/{theme['id']}/frameworks", json={"framework_id": framework["id"]}
    )
    assert link.status_code == 201, link.text

    del_resp = await client.delete(f"{STRATEGY}/themes/{theme['id']}")
    assert del_resp.status_code == 204, del_resp.text

    # The link row is gone with the theme (no orphan) -- reverse lookup on the surviving
    # Framework side shows nothing, and the Framework itself is untouched.
    reverse = await client.get(f"{COMPLIANCE}/frameworks/{framework['id']}/themes")
    assert reverse.status_code == 200
    assert reverse.json() == {"items": [], "total": 0}

    fw_resp = await client.get(f"{COMPLIANCE}/frameworks/{framework['id']}")
    assert fw_resp.status_code == 200


async def test_delete_framework_cascades_the_link(client):
    theme = await _mk_theme(client, "Surviving Theme")
    framework = await _mk_framework(client, "Doomed Framework")
    link = await client.post(
        f"{STRATEGY}/themes/{theme['id']}/frameworks", json={"framework_id": framework["id"]}
    )
    assert link.status_code == 201, link.text

    del_resp = await client.delete(f"{COMPLIANCE}/frameworks/{framework['id']}")
    assert del_resp.status_code == 204, del_resp.text

    # The link row is gone with the framework -- the surviving Theme's own framework_ids no
    # longer includes it, and the Theme itself is untouched.
    theme_resp = await client.get(f"{STRATEGY}/themes/{theme['id']}")
    assert theme_resp.status_code == 200
    assert theme_resp.json()["framework_ids"] == []
