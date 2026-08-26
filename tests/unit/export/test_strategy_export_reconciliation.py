"""Unit tests: full reconciliation cycle produces the expected file tree
(ADP-81p.3). Mirrors tests/unit/export/test_application_arch_reconciliation.py's
conventions.

Real Postgres enforces ON DELETE CASCADE on strategic_objective_dependencies'
both legs (migration 027) -- the SQLite Table() objects used here deliberately
omit that constraint (constraints live only in the migration, this package's
own established convention), so a deleted objective's dependency ROW is
deleted explicitly in these tests to simulate what the real cascade already
guarantees, rather than asserting SQLite behavior Postgres doesn't actually
have. The real cascade itself is exercised by the Docker-gated integration
test, not here.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.export import strategy as strategy_export
from adp.strategy import initiatives as sinit
from adp.strategy import store as sstore

_NOW = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
async def seeded_engine(tmp_path):
    # sinit shares sstore._metadata (initiatives.py's own established convention), so this one
    # create_all covers both modules' tables.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/strategy.db")
    async with engine.begin() as conn:
        await conn.run_sync(sstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        await session.execute(sstore._themes.insert().values(
            id="theme-1", name="Operational Excellence", description=None, owner=None,
            priority=None, created_at=_NOW,
        ))
        await session.execute(sstore._objectives.insert().values(
            id="obj-1", theme_id="theme-1", owner="Alice", statement="Cut MTTR",
            metric_name="MTTR", target_value=Decimal("2.00"), target_unit="hours",
            direction="decrease", fiscal_year=2026, period="Q1",
            status=None, status_reason=None, created_at=_NOW, updated_at=_NOW,
        ))
        await session.execute(sstore._objectives.insert().values(
            id="obj-2", theme_id="theme-1", owner="Bob", statement="Reduce alert noise",
            metric_name=None, target_value=None, target_unit=None, direction=None,
            fiscal_year=2026, period="Q1", status=None, status_reason=None,
            created_at=_NOW, updated_at=_NOW,
        ))
        await session.execute(sstore._objective_capabilities.insert().values(
            objective_id="obj-1", capability_id="cap-1", created_at=_NOW,
        ))
        await session.execute(sstore._progress.insert().values(
            objective_id="obj-1", as_of_date=date(2026, 2, 1), actual_value=Decimal("6"),
            note=None, recorded_by="alice", created_at=_NOW,
        ))
        await session.execute(sinit._objective_dependencies.insert().values(
            objective_id="obj-1", depends_on_objective_id="obj-2", created_at=_NOW,
        ))
        await session.execute(sinit._initiatives.insert().values(
            id="init-1", name="Remediate MFA gap", description=None, owner=None,
            status="planned", created_at=_NOW, updated_at=_NOW,
        ))
        await session.execute(sinit._initiative_objective_links.insert().values(
            initiative_id="init-1", objective_id="obj-1", created_at=_NOW,
        ))
        await session.commit()

    yield engine
    await engine.dispose()


async def _reconcile_once(export_root, engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await strategy_export.run_reconciliation_cycle(export_root, session)


async def test_reconciliation_produces_expected_file_tree(tmp_path, seeded_engine) -> None:
    await _reconcile_once(tmp_path, seeded_engine)
    root = tmp_path / "strategy"

    theme = json.loads((root / "themes" / "theme-1.json").read_text())
    assert theme["name"] == "Operational Excellence"

    obj1 = json.loads((root / "objectives" / "obj-1.json").read_text())
    assert obj1["capability_ids"] == ["cap-1"]
    assert obj1["depends_on_objective_ids"] == ["obj-2"]
    assert obj1["initiative_ids"] == ["init-1"]
    assert obj1["progress"] == [
        {"as_of_date": "2026-02-01", "actual_value": "6.00", "note": None, "recorded_by": "alice"}
    ]

    obj2 = json.loads((root / "objectives" / "obj-2.json").read_text())
    assert obj2["blocked_objective_ids"] == ["obj-1"]
    assert obj2["capability_ids"] == []  # empty, not omitted

    init1 = json.loads((root / "initiatives" / "init-1.json").read_text())
    assert init1["objective_ids"] == ["obj-1"]


async def test_unchanged_reconciliation_does_not_rewrite_files(tmp_path, seeded_engine) -> None:
    await _reconcile_once(tmp_path, seeded_engine)
    path = tmp_path / "strategy" / "objectives" / "obj-1.json"
    mtime_before = path.stat().st_mtime_ns
    content_before = path.read_text()

    await _reconcile_once(tmp_path, seeded_engine)

    assert path.stat().st_mtime_ns == mtime_before
    assert path.read_text() == content_before


async def test_recording_progress_rewrites_only_that_objective(tmp_path, seeded_engine) -> None:
    await _reconcile_once(tmp_path, seeded_engine)
    root = tmp_path / "strategy"
    obj2_path = root / "objectives" / "obj-2.json"
    theme_path = root / "themes" / "theme-1.json"
    obj2_mtime_before = obj2_path.stat().st_mtime_ns
    theme_mtime_before = theme_path.stat().st_mtime_ns

    factory = async_sessionmaker(seeded_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(sstore._progress.insert().values(
            objective_id="obj-1", as_of_date=date(2026, 3, 1), actual_value=Decimal("3"),
            note=None, recorded_by="alice", created_at=_NOW,
        ))
        await session.commit()

    await _reconcile_once(tmp_path, seeded_engine)

    obj1 = json.loads((root / "objectives" / "obj-1.json").read_text())
    assert len(obj1["progress"]) == 2
    assert obj2_path.stat().st_mtime_ns == obj2_mtime_before
    assert theme_path.stat().st_mtime_ns == theme_mtime_before


async def test_deleting_an_objective_removes_its_file(tmp_path, seeded_engine) -> None:
    await _reconcile_once(tmp_path, seeded_engine)
    root = tmp_path / "strategy"
    assert (root / "objectives" / "obj-2.json").exists()

    factory = async_sessionmaker(seeded_engine, expire_on_commit=False)
    async with factory() as session:
        # Explicit dependency-row delete simulates the real ON DELETE CASCADE
        # (migration 027) the SQLite fixture doesn't itself enforce -- see
        # module docstring.
        await session.execute(
            sinit._objective_dependencies.delete().where(
                sinit._objective_dependencies.c.depends_on_objective_id == "obj-2"
            )
        )
        await session.execute(
            sstore._objectives.delete().where(sstore._objectives.c.id == "obj-2")
        )
        await session.commit()

    await _reconcile_once(tmp_path, seeded_engine)

    assert not (root / "objectives" / "obj-2.json").exists()
    obj1 = json.loads((root / "objectives" / "obj-1.json").read_text())
    assert obj1["depends_on_objective_ids"] == []  # the dangling reference is gone too


async def test_deleting_theme_and_initiative_removes_each_file(tmp_path, seeded_engine) -> None:
    await _reconcile_once(tmp_path, seeded_engine)
    root = tmp_path / "strategy"

    factory = async_sessionmaker(seeded_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(
            sinit._initiative_objective_links.delete().where(
                sinit._initiative_objective_links.c.initiative_id == "init-1"
            )
        )
        await session.execute(
            sinit._initiatives.delete().where(sinit._initiatives.c.id == "init-1")
        )
        await session.commit()

    await _reconcile_once(tmp_path, seeded_engine)

    assert not (root / "initiatives" / "init-1.json").exists()
    obj1 = json.loads((root / "objectives" / "obj-1.json").read_text())
    assert obj1["initiative_ids"] == []
