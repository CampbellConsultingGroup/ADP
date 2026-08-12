"""Unit tests: adp.strategy.store CRUD against in-memory SQLite (ADP-d8u.1).

Mirrors adp.diagrams's own unit-store-test convention: build the store's
own `_metadata` on a throwaway SQLite engine, exercise the async functions
directly (no HTTP layer here -- that's tests/contract/test_strategy_api_
contract.py). Cross-package link validation (research.md Decision 2) is
exercised at the router/contract layer since it requires a second,
business-scoped session -- these tests cover strategy.store's own CRUD in
isolation, using link functions directly against pre-seeded ids (existence
checking happens one layer up, in the router).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.strategy import store as sstore
from adp.strategy.models import (
    StrategicObjectiveCreate,
    StrategicObjectiveUpdate,
    StrategicThemeCreate,
)

# Composite PKs from migration 025 (store metadata omits them, mirroring
# adp.business.store's own established convention -- FK/PK constraints live
# only in the migration).
_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_theme_name ON strategic_themes(name)",
    "CREATE UNIQUE INDEX uq_soc ON strategic_objective_capabilities(objective_id, capability_id)",
    "CREATE UNIQUE INDEX uq_sovs "
    "ON strategic_objective_value_streams(objective_id, value_stream_id)",
]


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/strategy.db")
    async with engine.begin() as conn:
        await conn.run_sync(sstore._metadata.create_all)
        for ddl in _UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


# ── Themes ────────────────────────────────────────────────────────────────────


async def test_create_theme_round_trips(session) -> None:
    theme = await sstore.create_theme(StrategicThemeCreate(name="Usage-based pricing"), session)
    await session.commit()
    listed = await sstore.list_themes(session)
    assert listed.total == 1
    assert listed.items[0].id == theme.id
    assert listed.items[0].name == "Usage-based pricing"


async def test_create_theme_duplicate_name_raises(session) -> None:
    await sstore.create_theme(StrategicThemeCreate(name="Growth"), session)
    await session.commit()
    with pytest.raises(sstore.DuplicateThemeNameError):
        await sstore.create_theme(StrategicThemeCreate(name="Growth"), session)


# ── Objectives ────────────────────────────────────────────────────────────────


async def _mk_theme(session, name="Growth") -> str:
    theme = await sstore.create_theme(StrategicThemeCreate(name=name), session)
    await session.commit()
    return theme.id


async def test_create_objective_with_metric_group_round_trips(session) -> None:
    theme_id = await _mk_theme(session)
    created = await sstore.create_objective(
        StrategicObjectiveCreate(
            theme_id=theme_id,
            owner="Claims Platform Team",
            statement="Reduce claims cycle time",
            metric_name="Claims cycle time",
            target_value=Decimal("40"),
            target_unit="%",
            direction="decrease",
            fiscal_year=2026,
            period="Q3",
        ),
        session,
    )
    await session.commit()
    fetched = await sstore.get_objective(created.id, session)
    assert fetched is not None
    assert fetched.theme_id == theme_id
    assert fetched.owner == "Claims Platform Team"
    assert fetched.metric_name == "Claims cycle time"
    assert fetched.target_value == Decimal("40.00")
    assert fetched.target_unit == "%"
    assert fetched.direction == "decrease"
    assert fetched.fiscal_year == 2026
    assert fetched.period == "Q3"
    assert fetched.capability_ids == []
    assert fetched.value_stream_ids == []


async def test_create_objective_without_metric_group_round_trips(session) -> None:
    theme_id = await _mk_theme(session)
    created = await sstore.create_objective(
        StrategicObjectiveCreate(
            theme_id=theme_id,
            owner="Retention Team",
            statement="Grow renewal rate",
            fiscal_year=2027,
            period="FY",
        ),
        session,
    )
    await session.commit()
    fetched = await sstore.get_objective(created.id, session)
    assert fetched is not None
    assert fetched.metric_name is None
    assert fetched.target_value is None
    assert fetched.target_unit is None
    assert fetched.direction is None


async def test_get_objective_unknown_id_returns_none(session) -> None:
    assert await sstore.get_objective("nonexistent", session) is None


async def test_list_objectives_returns_summary_shape(session) -> None:
    theme_id = await _mk_theme(session)
    for i in range(2):
        await sstore.create_objective(
            StrategicObjectiveCreate(
                theme_id=theme_id,
                owner=f"Owner {i}",
                statement=f"Statement {i}",
                fiscal_year=2026,
                period="Q1",
            ),
            session,
        )
    await session.commit()
    listed = await sstore.list_objectives(session)
    assert listed.total == 2
    for item in listed.items:
        assert not hasattr(item, "capability_ids")


async def test_update_objective_persists_partial_change(session) -> None:
    theme_id = await _mk_theme(session)
    created = await sstore.create_objective(
        StrategicObjectiveCreate(
            theme_id=theme_id,
            owner="Original Owner",
            statement="Original statement",
            fiscal_year=2026,
            period="Q1",
        ),
        session,
    )
    await session.commit()
    updated = await sstore.update_objective(
        created.id, StrategicObjectiveUpdate(owner="New Owner"), session
    )
    await session.commit()
    assert updated is not None
    assert updated.owner == "New Owner"
    assert updated.statement == "Original statement"  # untouched


async def test_update_objective_unknown_id_returns_none(session) -> None:
    result = await sstore.update_objective(
        "nonexistent", StrategicObjectiveUpdate(owner="X"), session
    )
    assert result is None


async def test_delete_objective_removes_row(session) -> None:
    # Cascade to strategic_objective_capabilities/value_streams is enforced
    # by the real ON DELETE CASCADE FK, which exists only in the migration
    # (store metadata deliberately omits FK/PK objects, mirroring
    # adp.business.store's convention) and was already verified directly
    # against Postgres via `psql \d` in T003 -- adp.business's own
    # equivalent tests don't re-verify DB-level cascade at the SQLite unit
    # layer either, so this test covers what application code is
    # responsible for: the objective row itself is gone.
    theme_id = await _mk_theme(session)
    created = await sstore.create_objective(
        StrategicObjectiveCreate(
            theme_id=theme_id,
            owner="Owner",
            statement="Statement",
            fiscal_year=2026,
            period="Q1",
        ),
        session,
    )
    await session.commit()
    await sstore.link_objective_capability(created.id, "cap-1", session)
    await session.commit()

    deleted = await sstore.delete_objective(created.id, session)
    await session.commit()
    assert deleted is True
    assert await sstore.get_objective(created.id, session) is None


async def test_delete_objective_unknown_id_returns_false(session) -> None:
    assert await sstore.delete_objective("nonexistent", session) is False


# ── Links ─────────────────────────────────────────────────────────────────────


async def test_link_and_unlink_capability_round_trip(session) -> None:
    theme_id = await _mk_theme(session)
    created = await sstore.create_objective(
        StrategicObjectiveCreate(
            theme_id=theme_id, owner="Owner", statement="Statement",
            fiscal_year=2026, period="Q1",
        ),
        session,
    )
    await session.commit()

    await sstore.link_objective_capability(created.id, "cap-1", session)
    await session.commit()
    fetched = await sstore.get_objective(created.id, session)
    assert fetched is not None
    assert fetched.capability_ids == ["cap-1"]

    await sstore.unlink_objective_capability(created.id, "cap-1", session)
    await session.commit()
    fetched = await sstore.get_objective(created.id, session)
    assert fetched is not None
    assert fetched.capability_ids == []


async def test_link_capability_duplicate_raises(session) -> None:
    theme_id = await _mk_theme(session)
    created = await sstore.create_objective(
        StrategicObjectiveCreate(
            theme_id=theme_id, owner="Owner", statement="Statement",
            fiscal_year=2026, period="Q1",
        ),
        session,
    )
    await session.commit()
    await sstore.link_objective_capability(created.id, "cap-1", session)
    await session.commit()
    with pytest.raises(sstore.DuplicateLinkError):
        await sstore.link_objective_capability(created.id, "cap-1", session)


async def test_unlink_capability_not_found_raises(session) -> None:
    theme_id = await _mk_theme(session)
    created = await sstore.create_objective(
        StrategicObjectiveCreate(
            theme_id=theme_id, owner="Owner", statement="Statement",
            fiscal_year=2026, period="Q1",
        ),
        session,
    )
    await session.commit()
    with pytest.raises(sstore.LinkNotFoundError):
        await sstore.unlink_objective_capability(created.id, "nonexistent-cap", session)


async def test_link_and_unlink_value_stream_round_trip(session) -> None:
    theme_id = await _mk_theme(session)
    created = await sstore.create_objective(
        StrategicObjectiveCreate(
            theme_id=theme_id, owner="Owner", statement="Statement",
            fiscal_year=2026, period="Q1",
        ),
        session,
    )
    await session.commit()

    await sstore.link_objective_value_stream(created.id, "vs-1", session)
    await session.commit()
    fetched = await sstore.get_objective(created.id, session)
    assert fetched is not None
    assert fetched.value_stream_ids == ["vs-1"]

    await sstore.unlink_objective_value_stream(created.id, "vs-1", session)
    await session.commit()
    fetched = await sstore.get_objective(created.id, session)
    assert fetched is not None
    assert fetched.value_stream_ids == []
