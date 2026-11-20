"""943-mapping-rationale: the two read-only geography helpers the application store uses."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.organization import store as ostore

NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/geo.db")
    async with engine.begin() as conn:
        await conn.run_sync(ostore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await ostore.seed_geography(s, NOW)
        yield s
    await engine.dispose()


async def test_geography_level(session):
    assert await ostore.geography_level("geo-001", session) == 1
    assert await ostore.geography_level("geo-m49-150", session) == 2
    assert await ostore.geography_level("geo-DE", session) == 3
    assert await ostore.geography_level("nope", session) is None


async def test_geography_index(session):
    index = await ostore.geography_index(session)
    assert len(index) == 255
    de = index["geo-DE"]
    assert (de.parent_id, de.name, de.code) == ("geo-m49-150", "Germany", "DE")
    assert index["geo-001"].parent_id is None
