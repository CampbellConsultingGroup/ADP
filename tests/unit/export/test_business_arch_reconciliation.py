"""Unit tests: the full reconciliation cycle end to end (ADP-SPEC-044).

User Story 1 (T011): correct file tree, correct content, on a fresh business
architecture. User Story 2 (T016-T018): no-op when unchanged, scoped diffs,
and deletion cleanup -- all against the SAME reconciliation cycle, so these
share one file and one seeding fixture rather than duplicating setup.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.business import store as bstore
from adp.export import business_arch

_NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/biz.db")
    async with engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed(factory) -> None:
    async with factory() as session:
        await session.execute(bstore._domains.insert().values(
            id="domain-1", name="Underwriting", scope_statement="...",
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
        await session.commit()


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


# ── User Story 1: correct file tree, correct content ─────────────────────────

async def test_reconciliation_produces_expected_file_tree(tmp_path, session_factory) -> None:
    await _seed(session_factory)
    root = tmp_path / "export"

    async with session_factory() as session:
        await business_arch.run_reconciliation_cycle(root, session)

    base = root / "business-architecture"
    cap1 = _read_json(base / "capabilities" / "cap-1.json")
    assert cap1["name"] == "Risk Assessment"
    assert cap1["domain_id"] == "domain-1"
    assert cap1["strategic_relevance"] == 1
    assert cap1["maturity_level"] is None  # unclassified -> explicit null, not omitted

    cap2 = _read_json(base / "capabilities" / "cap-2.json")
    assert cap2["domain_id"] is None
    assert cap2["strategic_relevance"] is None

    domain = _read_json(base / "domains" / "domain-1.json")
    assert domain["name"] == "Underwriting"

    vs = _read_json(base / "value-streams" / "vs-1" / "value-stream.json")
    assert vs["name"] == "Order-to-Cash"

    stage = _read_json(base / "value-streams" / "vs-1" / "stages" / "stage-1.json")
    assert stage["linked_capability_ids"] == ["cap-1"]

    # exported_at present on every file (contract: readers can see when it was written).
    for f in (cap1, cap2, domain, vs, stage):
        assert "exported_at" in f


# ── User Story 2: no-op when unchanged, scoped diffs, deletion cleanup ───────

async def test_unchanged_data_is_not_rewritten(tmp_path, session_factory) -> None:
    await _seed(session_factory)
    root = tmp_path / "export"
    cap_path = root / "business-architecture" / "capabilities" / "cap-1.json"

    async with session_factory() as session:
        await business_arch.run_reconciliation_cycle(root, session)
    first_mtime = cap_path.stat().st_mtime_ns
    first_content = cap_path.read_text(encoding="utf-8")

    async with session_factory() as session:
        await business_arch.run_reconciliation_cycle(root, session)
    second_mtime = cap_path.stat().st_mtime_ns
    second_content = cap_path.read_text(encoding="utf-8")

    assert second_mtime == first_mtime, "file was rewritten even though nothing changed"
    assert second_content == first_content


async def test_changing_one_capability_only_rewrites_its_own_file(
    tmp_path, session_factory
) -> None:
    await _seed(session_factory)
    root = tmp_path / "export"
    base = root / "business-architecture"
    cap1_path = base / "capabilities" / "cap-1.json"
    cap2_path = base / "capabilities" / "cap-2.json"
    domain_path = base / "domains" / "domain-1.json"

    async with session_factory() as session:
        await business_arch.run_reconciliation_cycle(root, session)
    cap2_before = cap2_path.read_text(encoding="utf-8")
    cap2_mtime_before = cap2_path.stat().st_mtime_ns
    domain_before = domain_path.read_text(encoding="utf-8")
    domain_mtime_before = domain_path.stat().st_mtime_ns

    async with session_factory() as session:
        await session.execute(
            bstore._capabilities.update()
            .where(bstore._capabilities.c.id == "cap-1")
            .values(maturity_level=3)
        )
        await session.commit()
        await business_arch.run_reconciliation_cycle(root, session)

    cap1_after = _read_json(cap1_path)
    assert cap1_after["maturity_level"] == 3

    # Unrelated files: byte-for-byte untouched, not just "same mtime" (mtime
    # equality alone wouldn't catch a rewrite-with-identical-content bug).
    assert cap2_path.read_text(encoding="utf-8") == cap2_before
    assert cap2_path.stat().st_mtime_ns == cap2_mtime_before
    assert domain_path.read_text(encoding="utf-8") == domain_before
    assert domain_path.stat().st_mtime_ns == domain_mtime_before


async def test_deleting_capability_domain_and_stage_removes_their_files(
    tmp_path, session_factory
) -> None:
    await _seed(session_factory)
    root = tmp_path / "export"
    base = root / "business-architecture"

    async with session_factory() as session:
        await business_arch.run_reconciliation_cycle(root, session)

    assert (base / "capabilities" / "cap-2.json").exists()
    assert (base / "domains" / "domain-1.json").exists()
    assert (base / "value-streams" / "vs-1" / "stages" / "stage-1.json").exists()

    async with session_factory() as session:
        await session.execute(
            bstore._capabilities.delete().where(bstore._capabilities.c.id == "cap-2")
        )
        await session.execute(bstore._domains.delete().where(bstore._domains.c.id == "domain-1"))
        await session.execute(
            bstore._stage_caps.delete().where(bstore._stage_caps.c.stage_id == "stage-1")
        )
        await session.execute(bstore._stages.delete().where(bstore._stages.c.id == "stage-1"))
        await session.commit()
        await business_arch.run_reconciliation_cycle(root, session)

    assert not (base / "capabilities" / "cap-2.json").exists()
    assert not (base / "domains" / "domain-1.json").exists()
    assert not (base / "value-streams" / "vs-1" / "stages" / "stage-1.json").exists()
    # The other, un-deleted capability is untouched.
    assert (base / "capabilities" / "cap-1.json").exists()


async def test_deleting_value_stream_removes_its_whole_directory(
    tmp_path, session_factory
) -> None:
    await _seed(session_factory)
    root = tmp_path / "export"
    vs_dir = root / "business-architecture" / "value-streams" / "vs-1"

    async with session_factory() as session:
        await business_arch.run_reconciliation_cycle(root, session)
    assert vs_dir.exists()
    assert (vs_dir / "stages" / "stage-1.json").exists()

    async with session_factory() as session:
        await session.execute(
            bstore._stage_caps.delete().where(bstore._stage_caps.c.stage_id == "stage-1")
        )
        await session.execute(
            bstore._stages.delete().where(bstore._stages.c.value_stream_id == "vs-1")
        )
        await session.execute(
            bstore._value_streams.delete().where(bstore._value_streams.c.id == "vs-1")
        )
        await session.commit()
        await business_arch.run_reconciliation_cycle(root, session)

    assert not vs_dir.exists()
