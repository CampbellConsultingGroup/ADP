"""ADP-blp.17: Strategy list reads use a fixed number of queries, whatever the row count."""

from __future__ import annotations

from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.strategy import initiatives as sinit
from adp.strategy import store as sstore
from adp.strategy.initiatives import StrategyInitiativeCreate
from adp.strategy.models import (
    ObjectiveProgressCreate,
    StrategicObjectiveCreate,
    StrategicThemeCreate,
)


@pytest.fixture()
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/bulk.db")
    async with engine.begin() as conn:
        await conn.run_sync(sstore._metadata.create_all)
    counter = {"n": 0}

    @sa.event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _count(*_args, **_kwargs):
        counter["n"] += 1

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session, counter
    await engine.dispose()


async def _seed(session, objectives: int) -> list[str]:
    theme = await sstore.create_theme(StrategicThemeCreate(name=f"Theme {objectives}"), session)
    ids = []
    for n in range(objectives):
        obj = await sstore.create_objective(
            StrategicObjectiveCreate(
                theme_id=theme.id,
                owner="o",
                statement=f"Objective {objectives}-{n}",
                fiscal_year=2027,
                period="FY",
                metric_name="m",
                target_value=100,
                target_unit="%",
                direction="increase",
            ),
            session,
        )
        for day, value in ((1, 10 + n), (2, 5 if n % 2 else 20 + n)):
            await sstore.create_progress_entry(
                obj.id,
                ObjectiveProgressCreate(as_of_date=date(2027, 1, day), actual_value=value),
                "tester",
                session,
            )
        initiative = await sinit.create_initiative(
            StrategyInitiativeCreate(name=f"Initiative {objectives}-{n}"), session
        )
        await sinit.link_initiative_objective(initiative.id, obj.id, session)
        ids.append(obj.id)
    await session.commit()
    return ids


async def _queries(counter, coro):
    before = counter["n"]
    result = await coro
    return counter["n"] - before, result


async def test_query_count_does_not_grow_with_rows(db):
    session, counter = db
    await _seed(session, 3)
    small = {
        "objectives": (await _queries(counter, sstore.list_objectives(session)))[0],
        "themes": (await _queries(counter, sstore.list_themes(session)))[0],
        "heatmap": (await _queries(counter, sstore.get_strategy_heatmap(session)))[0],
        "tally": (await _queries(counter, sstore._tally_objective_statuses(session)))[0],
        "initiatives": (await _queries(counter, sinit.list_initiatives(session)))[0],
    }
    await _seed(session, 12)
    large = {
        "objectives": (await _queries(counter, sstore.list_objectives(session)))[0],
        "themes": (await _queries(counter, sstore.list_themes(session)))[0],
        "heatmap": (await _queries(counter, sstore.get_strategy_heatmap(session)))[0],
        "tally": (await _queries(counter, sstore._tally_objective_statuses(session)))[0],
        "initiatives": (await _queries(counter, sinit.list_initiatives(session)))[0],
    }
    assert large == small
    assert small["objectives"] == 2
    assert small["themes"] == 2
    assert small["initiatives"] == 2 + 1 + len(sinit._LINK_TABLE_BY_TARGET_TYPE)


async def test_bulk_results_match_the_single_row_paths(db):
    session, _counter = db
    objective_ids = await _seed(session, 5)

    listed = {o.id: o for o in (await sstore.list_objectives(session)).items}
    for oid in objective_ids:
        single = await sstore.get_objective(oid, session)
        assert listed[oid].status == single.status

    for initiative in (await sinit.list_initiatives(session)).items:
        assert initiative == await sinit.get_initiative(initiative.id, session)

    # Order follows the ids given; unknown ids are skipped.
    some = [i.id for i in (await sinit.list_initiatives(session)).items][:3]
    picked = await sinit.get_initiatives([some[2], "nope", some[0]], session)
    assert [i.id for i in picked] == [some[2], some[0]]
    assert await sinit.get_initiatives([], session) == []


async def test_control_objectives_for_framework_is_one_query(db):
    """ADP-blp.35: the control tree's per-control lookups, in one query."""
    session, counter = db
    objective_ids = await _seed(session, 3)
    for cid, fw in (("c1", "fw1"), ("c2", "fw1"), ("c3", "fw2")):
        await session.execute(
            sstore._controls_mirror.insert().values(id=cid, code=cid, title=cid, framework_id=fw)
        )
    await sstore.link_objective_control(objective_ids[0], "c1", session)
    await sstore.link_objective_control(objective_ids[1], "c1", session)
    await sstore.link_objective_control(objective_ids[2], "c3", session)
    await session.commit()

    queries, by_control = await _queries(
        counter, sstore.list_control_objectives_for_framework("fw1", session)
    )
    assert queries == 1
    assert set(by_control) == {"c1"}  # c2 has no objective; c3 is another framework
    assert {oid for oid, _statement in by_control["c1"]} == set(objective_ids[:2])
