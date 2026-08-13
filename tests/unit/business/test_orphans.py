"""Unit tests: adp.business.store orphan-detection (918-strategy-rollups).

Mirrors adp.strategy.store's own established unit-store-test convention:
build the store's own `_metadata` on a throwaway SQLite engine, exercise
the async functions directly. `_strategic_objective_capabilities`/
`_strategic_objective_value_streams` are lightweight read-only mirrors
(research.md Decision 4) -- seeded directly here, mirroring how
adp.strategy.store's own `_designs`/`_applications` mirrors are seeded in
that package's own test file.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.business import store as bstore


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/business.db")
    async with engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _mk_capability(session, cap_id="cap-1", name="Claims Processing", level=1) -> str:
    await session.execute(
        bstore._capabilities.insert().values(
            id=cap_id, name=name, level=level, parent_id=None, position=0,
            created_at=_now(), updated_at=_now(),
        )
    )
    await session.commit()
    return cap_id


async def _mk_value_stream(session, vs_id="vs-1", name="Claim to Payout") -> str:
    await session.execute(
        bstore._value_streams.insert().values(
            id=vs_id, name=name, position=0, created_at=_now(), updated_at=_now(),
        )
    )
    await session.commit()
    return vs_id


async def _link_capability(session, objective_id: str, capability_id: str) -> None:
    await session.execute(
        bstore._strategic_objective_capabilities.insert().values(
            objective_id=objective_id, capability_id=capability_id,
        )
    )
    await session.commit()


async def _link_value_stream(session, objective_id: str, value_stream_id: str) -> None:
    await session.execute(
        bstore._strategic_objective_value_streams.insert().values(
            objective_id=objective_id, value_stream_id=value_stream_id,
        )
    )
    await session.commit()


async def test_linked_capability_excluded_from_orphans(session) -> None:
    cap_id = await _mk_capability(session)
    await _link_capability(session, "obj-1", cap_id)

    orphans = await bstore.list_orphan_capabilities(session)

    assert orphans == []


async def test_unlinked_capability_included_in_orphans(session) -> None:
    cap_id = await _mk_capability(session, cap_id="cap-orphan")

    orphans = await bstore.list_orphan_capabilities(session)

    assert [c.id for c in orphans] == [cap_id]


async def test_orphan_capabilities_empty_when_everything_linked(session) -> None:
    cap1 = await _mk_capability(session, cap_id="cap-1")
    cap2 = await _mk_capability(session, cap_id="cap-2", name="Underwriting")
    await _link_capability(session, "obj-1", cap1)
    await _link_capability(session, "obj-2", cap2)

    orphans = await bstore.list_orphan_capabilities(session)

    assert orphans == []


async def test_linked_value_stream_excluded_from_orphans(session) -> None:
    vs_id = await _mk_value_stream(session)
    await _link_value_stream(session, "obj-1", vs_id)

    orphans = await bstore.list_orphan_value_streams(session)

    assert orphans == []


async def test_unlinked_value_stream_included_in_orphans(session) -> None:
    vs_id = await _mk_value_stream(session, vs_id="vs-orphan")

    orphans = await bstore.list_orphan_value_streams(session)

    assert [v.id for v in orphans] == [vs_id]


async def test_orphan_capabilities_empty_database_returns_empty_list(session) -> None:
    assert await bstore.list_orphan_capabilities(session) == []
    assert await bstore.list_orphan_value_streams(session) == []
