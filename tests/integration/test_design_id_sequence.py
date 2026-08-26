"""Integration test: DesignStore.next_design_id() is race-free under real concurrency
(ADP-3fh, follow-up to ADP-twl).

Requires Docker (testcontainers). Skipped automatically when Docker is unavailable.

The SQLite-backed unit/contract fixtures used throughout this codebase cannot exercise this at
all -- SQLite has no CREATE SEQUENCE/nextval(), and the whole point of migration 038's
design_id_seq is genuine concurrent-request safety, which only a real Postgres instance (or,
here, testcontainers' own real Postgres) can actually prove. This mirrors the live stress test
already run by hand against the real local dev Postgres during this fix (40 concurrent
POST /api/v1/designs, 40/40 succeeded, zero duplicate ids) as a permanent, automated regression
guard instead of a one-off manual check.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="session")
async def app(db_url: str, db_engine):
    """FastAPI test app wired to the test database (migrations, incl. 038, run via db_engine)."""
    import os

    from adp.api.app import create_app

    os.environ["ADP_DATABASE_URL"] = db_url

    application = create_app()

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    import adp.store.store as store_module

    store_module._engine = engine
    store_module._session_factory = factory

    yield application
    await engine.dispose()


@pytest.fixture()
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_concurrent_design_creation_never_collides(client):
    """40 genuinely concurrent POST /api/v1/designs -- every one must succeed (201) with a
    unique id. Pre-migration-038, this class of load reliably produced 500s (a raw
    IntegrityError on design_versions_pkey) and, even with ADP-twl's 5-attempt retry loop in
    place, could still exhaust it and surface a 503 -- confirmed by direct reproduction before
    this fix existed."""
    async def _create(i: int):
        return await client.post("/api/v1/designs", json={"title": f"ConcurrentSeq-{i}"})

    responses = await asyncio.gather(*(_create(i) for i in range(40)))

    statuses = [r.status_code for r in responses]
    assert all(s == 201 for s in statuses), f"expected all 201, got {statuses}"

    ids = [r.json()["id"] for r in responses]
    assert len(ids) == len(set(ids)), f"duplicate design id assigned under concurrency: {ids}"
