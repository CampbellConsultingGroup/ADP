"""Integration tests for Application Regulatory Framework Tags (932-regulatory-framework-tags,
ADP-bkg).

Covers quickstart.md's Scenario 6 (cascade delete, both directions) -- the one case the
SQLite-backed contract test (tests/contract/test_apm_risk_api.py) cannot exercise, since SQLite has
no real FK/CASCADE enforcement without extra pragmas this project doesn't set up in that fixture.
Mirrors tests/integration/test_theme_framework_links_api.py's fixture exactly.

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

    # adp.application.router's own _get_session resolves through astore._get_session_factory()
    # (research.md D1); adp.compliance.store is also needed here (unlike the SQLite contract
    # test) since these tests create and delete a real Framework through the real compliance API.
    import adp.application.store as astore
    import adp.compliance.store as cstore

    for module in (astore, cstore):
        module._engine = engine
        module._session_factory = factory

    yield application
    await engine.dispose()


@pytest.fixture()
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


APPLICATIONS = "/api/v1/applications"
COMPLIANCE = "/api/v1/compliance"


async def _mk_app(client, name="Test App") -> dict:
    resp = await client.post(APPLICATIONS, json={"name": name})
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


async def test_tag_persists_against_real_postgres(client):
    app = await _mk_app(client, "Persist Test App")
    framework = await _mk_framework(client, "Persist Test Framework")

    put_resp = await client.put(
        f"{APPLICATIONS}/{app['id']}/risk", json={"regulatory_tags": [framework["id"]]}
    )
    assert put_resp.status_code == 200, put_resp.text
    assert put_resp.json()["regulatory_tags"] == [framework["id"]]

    get_resp = await client.get(f"{APPLICATIONS}/{app['id']}/risk")
    assert get_resp.json()["regulatory_tags"] == [framework["id"]]


async def test_delete_framework_cascades_the_tag(client):
    app = await _mk_app(client, "Framework-Cascade App")
    framework = await _mk_framework(client, "Doomed Framework")
    link = await client.put(
        f"{APPLICATIONS}/{app['id']}/risk", json={"regulatory_tags": [framework["id"]]}
    )
    assert link.status_code == 200, link.text

    del_resp = await client.delete(f"{COMPLIANCE}/frameworks/{framework['id']}")
    assert del_resp.status_code == 204, del_resp.text

    # The tag is gone with the framework (no orphan) -- the surviving Application's own
    # regulatory_tags no longer includes it, and the Application itself is untouched.
    risk_resp = await client.get(f"{APPLICATIONS}/{app['id']}/risk")
    assert risk_resp.status_code == 200
    assert risk_resp.json()["regulatory_tags"] == []

    app_resp = await client.get(f"{APPLICATIONS}/{app['id']}")
    assert app_resp.status_code == 200


async def test_delete_application_cascades_the_tag(client):
    app = await _mk_app(client, "Application-Cascade App")
    framework = await _mk_framework(client, "Surviving Framework")
    link = await client.put(
        f"{APPLICATIONS}/{app['id']}/risk", json={"regulatory_tags": [framework["id"]]}
    )
    assert link.status_code == 200, link.text

    del_resp = await client.delete(f"{APPLICATIONS}/{app['id']}")
    assert del_resp.status_code == 204, del_resp.text

    # No "get a deleted application's risk" endpoint exists (404s like the application itself
    # does), so the absence of an orphaned row is confirmed via a direct row count instead.
    import sqlalchemy as sa

    import adp.application.store as astore

    async with astore._session_factory() as session:
        result = await session.execute(
            sa.select(astore._application_framework_tags).where(
                astore._application_framework_tags.c.application_id == app["id"]
            )
        )
        assert result.first() is None

    # The surviving Framework itself is untouched.
    fw_resp = await client.get(f"{COMPLIANCE}/frameworks/{framework['id']}")
    assert fw_resp.status_code == 200
