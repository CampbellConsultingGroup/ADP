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

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.strategy import store as sstore
from adp.strategy.models import (
    ObjectiveProgressCreate,
    ObjectiveProgressUpdate,
    StrategicObjectiveCreate,
    StrategicObjectiveUpdate,
    StrategicThemeCreate,
    StrategicThemeUpdate,
)

# Composite PKs from migration 025 (store metadata omits them, mirroring
# adp.business.store's own established convention -- FK/PK constraints live
# only in the migration).
_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_theme_name ON strategic_themes(name)",
    "CREATE UNIQUE INDEX uq_soc ON strategic_objective_capabilities(objective_id, capability_id)",
    "CREATE UNIQUE INDEX uq_sovs "
    "ON strategic_objective_value_streams(objective_id, value_stream_id)",
    "CREATE UNIQUE INDEX uq_progress ON strategic_objective_progress(objective_id, as_of_date)",
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


async def test_create_theme_with_description_owner_priority(session) -> None:
    theme = await sstore.create_theme(
        StrategicThemeCreate(
            name="Digital Channels", description="Customer-facing", owner="jane", priority=2
        ),
        session,
    )
    await session.commit()
    assert theme.description == "Customer-facing"
    assert theme.owner == "jane"
    assert theme.priority == 2


async def test_get_theme_returns_row(session) -> None:
    theme = await sstore.create_theme(StrategicThemeCreate(name="Growth"), session)
    await session.commit()
    fetched = await sstore.get_theme(theme.id, session)
    assert fetched is not None
    assert fetched.name == "Growth"


async def test_get_theme_unknown_id_returns_none(session) -> None:
    assert await sstore.get_theme("nonexistent", session) is None


async def test_update_theme_persists_fields(session) -> None:
    theme = await sstore.create_theme(StrategicThemeCreate(name="Growth"), session)
    await session.commit()
    updated = await sstore.update_theme(
        theme.id, StrategicThemeUpdate(priority=1, owner="jane"), session
    )
    await session.commit()
    assert updated is not None
    assert updated.priority == 1
    assert updated.owner == "jane"


async def test_update_theme_unknown_id_returns_none(session) -> None:
    result = await sstore.update_theme("nonexistent", StrategicThemeUpdate(priority=1), session)
    assert result is None


async def test_delete_theme_succeeds_when_unreferenced(session) -> None:
    theme = await sstore.create_theme(StrategicThemeCreate(name="Unused"), session)
    await session.commit()
    await sstore.delete_theme(theme.id, session)
    await session.commit()
    assert await sstore.get_theme(theme.id, session) is None


async def test_delete_theme_raises_when_referenced(session) -> None:
    theme = await sstore.create_theme(StrategicThemeCreate(name="In Use"), session)
    await session.commit()
    await sstore.create_objective(
        StrategicObjectiveCreate(
            theme_id=theme.id, owner="Owner", statement="Statement",
            fiscal_year=2026, period="Q1",
        ),
        session,
    )
    await session.commit()
    with pytest.raises(sstore.ThemeInUseError):
        await sstore.delete_theme(theme.id, session)


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


# ── Progress (ADP-d8u.5) ────────────────────────────────────────────────────
#
# Cascade-delete-removes-progress-rows (FR-016) is NOT re-verified here --
# mirrors test_delete_objective_removes_row's own established precedent
# above: the real ON DELETE CASCADE FK exists only in the migration (store
# metadata deliberately omits FK/PK objects), already confirmed directly
# against Postgres (pg_constraint.confdeltype = 'c', T007). This file's
# SQLite fixture has no FK enforcement to meaningfully re-test that against.


async def _mk_objective_with_target(session, direction="increase") -> str:
    theme_id = await _mk_theme(session, name=f"Theme-{direction}")
    created = await sstore.create_objective(
        StrategicObjectiveCreate(
            theme_id=theme_id,
            owner="Owner",
            statement="Statement",
            metric_name="Metric",
            target_value=Decimal("100"),
            target_unit="%",
            direction=direction,
            fiscal_year=2026,
            period="Q1",
        ),
        session,
    )
    await session.commit()
    return created.id


async def test_create_progress_entry_round_trips(session) -> None:
    obj_id = await _mk_objective_with_target(session)
    entry = await sstore.create_progress_entry(
        obj_id,
        ObjectiveProgressCreate(as_of_date=date(2026, 8, 1), actual_value=Decimal("40")),
        actor="jane",
        session=session,
    )
    await session.commit()
    assert entry.objective_id == obj_id
    assert entry.as_of_date == date(2026, 8, 1)
    assert entry.actual_value == Decimal("40.00")
    assert entry.recorded_by == "jane"


async def test_create_progress_entry_duplicate_date_raises(session) -> None:
    obj_id = await _mk_objective_with_target(session)
    await sstore.create_progress_entry(
        obj_id,
        ObjectiveProgressCreate(as_of_date=date(2026, 8, 1), actual_value=Decimal("40")),
        actor="jane",
        session=session,
    )
    await session.commit()
    with pytest.raises(sstore.DuplicateProgressEntryError):
        await sstore.create_progress_entry(
            obj_id,
            ObjectiveProgressCreate(as_of_date=date(2026, 8, 1), actual_value=Decimal("99")),
            actor="jane",
            session=session,
        )


async def test_update_progress_entry_edits_value_and_note_in_place(session) -> None:
    obj_id = await _mk_objective_with_target(session)
    await sstore.create_progress_entry(
        obj_id,
        ObjectiveProgressCreate(as_of_date=date(2026, 8, 1), actual_value=Decimal("40")),
        actor="jane",
        session=session,
    )
    await session.commit()
    updated = await sstore.update_progress_entry(
        obj_id,
        date(2026, 8, 1),
        ObjectiveProgressUpdate(actual_value=Decimal("55"), note="corrected typo"),
        session,
    )
    await session.commit()
    assert updated is not None
    assert updated.actual_value == Decimal("55.00")
    assert updated.note == "corrected typo"
    assert updated.as_of_date == date(2026, 8, 1)  # unchanged


async def test_update_progress_entry_unknown_date_returns_none(session) -> None:
    obj_id = await _mk_objective_with_target(session)
    result = await sstore.update_progress_entry(
        obj_id, date(2099, 1, 1), ObjectiveProgressUpdate(actual_value=Decimal("1")), session
    )
    assert result is None


async def test_list_progress_entries_ordered_by_date_ascending(session) -> None:
    obj_id = await _mk_objective_with_target(session)
    for day, value in [(15, "70"), (1, "40"), (8, "55")]:
        await sstore.create_progress_entry(
            obj_id,
            ObjectiveProgressCreate(as_of_date=date(2026, 8, day), actual_value=Decimal(value)),
            actor="jane",
            session=session,
        )
        await session.commit()
    listed = await sstore.list_progress_entries(obj_id, session)
    assert listed.total == 3
    assert [e.as_of_date.day for e in listed.items] == [1, 8, 15]


async def test_get_objective_includes_computed_status(session) -> None:
    obj_id = await _mk_objective_with_target(session, direction="increase")
    fetched = await sstore.get_objective(obj_id, session)
    assert fetched is not None
    assert fetched.status == "proposed"  # no progress yet

    await sstore.create_progress_entry(
        obj_id,
        ObjectiveProgressCreate(as_of_date=date(2026, 8, 1), actual_value=Decimal("100")),
        actor="jane",
        session=session,
    )
    await session.commit()
    fetched = await sstore.get_objective(obj_id, session)
    assert fetched is not None
    assert fetched.status == "achieved"


async def test_list_objectives_summary_includes_computed_status(session) -> None:
    await _mk_objective_with_target(session, direction="increase")
    listed = await sstore.list_objectives(session)
    assert listed.total == 1
    assert listed.items[0].status == "proposed"


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


# ── get_summary_stats (051-strategy-landing-card) ──────────────────────────────
#
# Mirrors adp.api.routers.portfolio's own established test pattern
# (tests/contract/test_portfolio_api.py's client_factory/_make_session_mock)
# for a Postgres-only-syntax aggregate: mocks session.execute()'s return value
# rather than running the real query -- the query itself uses NOW()/EXTRACT(),
# which SQLite (this file's other fixture) can't execute. The actual SQL text
# is verified separately against a real local Postgres instance (T005), the
# same way migration 025's schema was verified via direct psql inspection
# rather than a SQLite-backed pytest.


def _mock_session_returning(row: MagicMock) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.first = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=result)
    return session


async def test_get_summary_stats_maps_all_seven_fields() -> None:
    row = MagicMock()
    row.__getitem__.side_effect = lambda k: {
        "total_themes": 4,
        "total_objectives": 12,
        "linked_count": 9,
        "unlinked_count": 3,
        "current_period_count": 5,
        "upcoming_count": 4,
        "past_due_count": 3,
    }[k]
    session = _mock_session_returning(row)

    result = await sstore.get_summary_stats(session)

    assert result.total_themes == 4
    assert result.total_objectives == 12
    assert result.linked_count == 9
    assert result.unlinked_count == 3
    assert result.current_period_count == 5
    assert result.upcoming_count == 4
    assert result.past_due_count == 3


async def test_get_summary_stats_all_zero_on_empty_database() -> None:
    row = MagicMock()
    row.__getitem__.side_effect = lambda k: 0
    session = _mock_session_returning(row)

    result = await sstore.get_summary_stats(session)

    assert result.total_objectives == 0
    assert result.total_themes == 0
    assert result.linked_count == 0
    assert result.unlinked_count == 0
    assert result.current_period_count == 0
    assert result.upcoming_count == 0
    assert result.past_due_count == 0


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
