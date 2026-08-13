"""Unit tests: adp.strategy.initiatives CRUD against in-memory SQLite (ADP-d8u.6).

Mirrors test_strategy_store.py's exact fixture convention -- `initiatives.py`
shares `store.py`'s `_metadata` object (research.md Decision 1), so
`sstore._metadata.create_all` already creates these new tables too; this
file only needs to add its own composite-PK unique-index DDL, the same
workaround `test_strategy_store.py` already uses for every other join table
(store metadata omits composite PKs -- they live only in the migration).
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.strategy import initiatives as sinit
from adp.strategy import store as sstore
from adp.strategy.initiatives import StrategyInitiativeCreate, StrategyInitiativeUpdate
from adp.strategy.models import StrategicObjectiveCreate, StrategicThemeCreate

_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_theme_name ON strategic_themes(name)",
    "CREATE UNIQUE INDEX uq_soc ON strategic_objective_capabilities(objective_id, capability_id)",
    "CREATE UNIQUE INDEX uq_sovs "
    "ON strategic_objective_value_streams(objective_id, value_stream_id)",
    "CREATE UNIQUE INDEX uq_progress ON strategic_objective_progress(objective_id, as_of_date)",
    "CREATE UNIQUE INDEX uq_sio_links "
    "ON strategy_initiative_objective_links(initiative_id, objective_id)",
    "CREATE UNIQUE INDEX uq_objective_deps "
    "ON strategic_objective_dependencies(objective_id, depends_on_objective_id)",
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


async def _mk_theme(session, name="Growth") -> str:
    theme = await sstore.create_theme(StrategicThemeCreate(name=name), session)
    await session.commit()
    return theme.id


async def _mk_objective(session, name="Objective") -> str:
    theme_id = await _mk_theme(session, name=f"Theme-{name}")
    created = await sstore.create_objective(
        StrategicObjectiveCreate(
            theme_id=theme_id, owner="Owner", statement=name, fiscal_year=2026, period="Q1",
        ),
        session,
    )
    await session.commit()
    return created.id


# ── Initiative CRUD ─────────────────────────────────────────────────────────


async def test_create_initiative_round_trips(session) -> None:
    initiative = await sinit.create_initiative(
        StrategyInitiativeCreate(name="Claims Automation", description="Q3-Q4", owner="jane"),
        session,
    )
    await session.commit()
    assert initiative.name == "Claims Automation"
    assert initiative.description == "Q3-Q4"
    assert initiative.owner == "jane"
    assert initiative.status == "planned"
    assert initiative.objective_ids == []


async def test_get_initiative_unknown_id_returns_none(session) -> None:
    assert await sinit.get_initiative("nonexistent", session) is None


async def test_list_initiatives_returns_all(session) -> None:
    await sinit.create_initiative(StrategyInitiativeCreate(name="A"), session)
    await sinit.create_initiative(StrategyInitiativeCreate(name="B"), session)
    await session.commit()
    listed = await sinit.list_initiatives(session)
    assert listed.total == 2


async def test_update_initiative_persists_partial_change(session) -> None:
    created = await sinit.create_initiative(StrategyInitiativeCreate(name="A"), session)
    await session.commit()
    updated = await sinit.update_initiative(
        created.id, StrategyInitiativeUpdate(status="in_progress"), session
    )
    await session.commit()
    assert updated is not None
    assert updated.status == "in_progress"
    assert updated.name == "A"  # untouched


async def test_update_initiative_unknown_id_returns_none(session) -> None:
    result = await sinit.update_initiative(
        "nonexistent", StrategyInitiativeUpdate(status="complete"), session
    )
    assert result is None


async def test_delete_initiative_is_unconditional_even_with_links(session) -> None:
    # FR-011: deleting an initiative is NOT blocked by existing links,
    # unlike theme delete's in-use block (ADP-d8u.5).
    initiative = await sinit.create_initiative(StrategyInitiativeCreate(name="A"), session)
    await session.commit()
    objective_id = await _mk_objective(session)
    await sinit.link_initiative_objective(initiative.id, objective_id, session)
    await session.commit()

    deleted = await sinit.delete_initiative(initiative.id, session)
    await session.commit()
    assert deleted is True
    assert await sinit.get_initiative(initiative.id, session) is None


async def test_delete_initiative_unknown_id_returns_false(session) -> None:
    assert await sinit.delete_initiative("nonexistent", session) is False


# ── Initiative <-> Objective links ──────────────────────────────────────────


async def test_link_and_unlink_round_trip_both_directions(session) -> None:
    initiative = await sinit.create_initiative(StrategyInitiativeCreate(name="A"), session)
    await session.commit()
    objective_id = await _mk_objective(session)

    await sinit.link_initiative_objective(initiative.id, objective_id, session)
    await session.commit()

    fetched = await sinit.get_initiative(initiative.id, session)
    assert fetched is not None
    assert fetched.objective_ids == [objective_id]

    reverse = await sinit.list_objective_initiative_ids(objective_id, session)
    assert reverse == [initiative.id]

    await sinit.unlink_initiative_objective(initiative.id, objective_id, session)
    await session.commit()

    fetched = await sinit.get_initiative(initiative.id, session)
    assert fetched is not None
    assert fetched.objective_ids == []


async def test_link_duplicate_raises(session) -> None:
    initiative = await sinit.create_initiative(StrategyInitiativeCreate(name="A"), session)
    await session.commit()
    objective_id = await _mk_objective(session)
    await sinit.link_initiative_objective(initiative.id, objective_id, session)
    await session.commit()
    with pytest.raises(sinit.DuplicateLinkError):
        await sinit.link_initiative_objective(initiative.id, objective_id, session)


async def test_unlink_not_found_raises(session) -> None:
    initiative = await sinit.create_initiative(StrategyInitiativeCreate(name="A"), session)
    await session.commit()
    objective_id = await _mk_objective(session)
    with pytest.raises(sinit.LinkNotFoundError):
        await sinit.unlink_initiative_objective(initiative.id, objective_id, session)


async def test_unlink_one_link_leaves_others_on_same_initiative_untouched(session) -> None:
    initiative = await sinit.create_initiative(StrategyInitiativeCreate(name="A"), session)
    await session.commit()
    obj1 = await _mk_objective(session, name="Obj1")
    obj2 = await _mk_objective(session, name="Obj2")
    await sinit.link_initiative_objective(initiative.id, obj1, session)
    await sinit.link_initiative_objective(initiative.id, obj2, session)
    await session.commit()

    await sinit.unlink_initiative_objective(initiative.id, obj1, session)
    await session.commit()

    fetched = await sinit.get_initiative(initiative.id, session)
    assert fetched is not None
    assert fetched.objective_ids == [obj2]
