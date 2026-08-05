"""Unit tests: atomic file writes, bulk reads, and failure isolation for
business architecture export (ADP-SPEC-044 T005/T007/T009).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.business import store as bstore
from adp.export import business_arch

_NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)


# ── T005: atomic file write ──────────────────────────────────────────────────

def test_write_file_atomic_creates_file(tmp_path) -> None:
    target = tmp_path / "sub" / "cap-1.json"
    business_arch._write_file_atomic(target, '{"id": "cap-1"}')
    assert target.read_text(encoding="utf-8") == '{"id": "cap-1"}'


def test_write_file_atomic_leaves_no_partial_file_on_failure(tmp_path) -> None:
    target = tmp_path / "cap-1.json"
    target.write_text('{"id": "cap-1", "version": "old"}', encoding="utf-8")

    with patch.object(os, "replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            business_arch._write_file_atomic(target, '{"id": "cap-1", "version": "new"}')

    # The previously-good file is untouched -- never a half-written "new" file.
    assert target.read_text(encoding="utf-8") == '{"id": "cap-1", "version": "old"}'
    # No leftover temp file in the directory.
    leftovers = [p for p in tmp_path.iterdir() if p.name != "cap-1.json"]
    assert leftovers == []


# ── T007: bulk read ───────────────────────────────────────────────────────────

@pytest.fixture()
async def seeded_session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/biz.db")
    async with engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        await session.execute(bstore._domains.insert().values(
            id="domain-1", name="Underwriting", scope_statement=None,
            classification="strategic", org_unit=None, risk_flags=[],
            created_at=_NOW, updated_at=_NOW,
        ))
        await session.execute(bstore._capabilities.insert().values(
            id="cap-1", name="Risk Assessment", description=None, level=1,
            parent_id=None, position=0, created_at=_NOW, updated_at=_NOW,
            domain_id="domain-1", strategic_relevance=1, maturity_level=None,
        ))
        await session.execute(bstore._capabilities.insert().values(
            id="cap-2", name="Pricing", description=None, level=1,
            parent_id=None, position=1, created_at=_NOW, updated_at=_NOW,
            domain_id=None, strategic_relevance=None, maturity_level=None,
        ))
        await session.execute(bstore._value_streams.insert().values(
            id="vs-1", name="Order-to-Cash", description=None, stakeholder=None,
            position=0, created_at=_NOW, updated_at=_NOW,
        ))
        await session.execute(bstore._stages.insert().values(
            id="stage-1", value_stream_id="vs-1", name="Quote", description=None, position=0,
        ))
        await session.execute(bstore._stage_caps.insert().values(
            stage_id="stage-1", capability_id="cap-1",
        ))
        await session.execute(bstore._stage_caps.insert().values(
            stage_id="stage-1", capability_id="cap-2",
        ))
        await session.commit()

    async with factory() as session:
        yield session
    await engine.dispose()


async def test_fetch_all_returns_complete_snapshot(seeded_session) -> None:
    snapshot = await business_arch._fetch_all(seeded_session)

    assert {c.id for c in snapshot.capabilities} == {"cap-1", "cap-2"}
    assert {d.id for d in snapshot.domains} == {"domain-1"}
    assert {vs.id for vs in snapshot.value_streams} == {"vs-1"}
    assert {s.id for s in snapshot.stages} == {"stage-1"}
    assert snapshot.stage_links["stage-1"] == ["cap-1", "cap-2"]


async def test_fetch_all_stage_with_no_links_has_empty_list(seeded_session) -> None:
    await seeded_session.execute(bstore._stages.insert().values(
        id="stage-2", value_stream_id="vs-1", name="Bind", description=None, position=1,
    ))
    await seeded_session.commit()

    snapshot = await business_arch._fetch_all(seeded_session)
    assert snapshot.stage_links["stage-2"] == []


# ── T009: failure isolation ───────────────────────────────────────────────────

async def test_run_reconciliation_cycle_logs_and_does_not_raise_on_failure(
    seeded_session, tmp_path, caplog
) -> None:
    import logging

    with patch.object(business_arch, "_fetch_all", side_effect=RuntimeError("boom")):
        with caplog.at_level(logging.WARNING, logger="adp.export.business_arch"):
            await business_arch.run_reconciliation_cycle(tmp_path, seeded_session)  # must not raise

    assert any(
        "business_arch_export" in r.message and r.levelno >= logging.WARNING
        for r in caplog.records
    )
