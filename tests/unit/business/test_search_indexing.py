"""Unit "wiring" tests for adp.business.store's search-index write hooks (ADP-7bo).

Monkeypatches bstore.index_entity/unindex_entity (imported directly into that
module's namespace, so patching the module attribute intercepts every call
site) to recording stubs, then runs the real store functions against a
SQLite-backed fixture and asserts the correct (entity_type, entity_id, text)
was recorded at each call site.

The real SQL round-trip (SearchIndex.upsert's Postgres-only
ON CONFLICT DO UPDATE, which cannot compile against SQLite at all) is covered
separately by the Docker-gated integration tests in
tests/integration/test_search.py -- these tests only verify the store code
calls the index correctly, not that the underlying SQL works, per
research.md D6.

Covers both the new value_stream_stage wiring (this feature) and the
pre-existing 041 wiring for value streams/domains, which had zero test
coverage before this feature (Ground-Truth Correction #6).
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.business import store as bstore
from adp.business.models import (
    BusinessDomainCreate,
    BusinessDomainUpdate,
    StageReorderItem,
    ValueStreamCreate,
    ValueStreamStageCreate,
    ValueStreamStageUpdate,
)
from adp.search import (
    ENTITY_BUSINESS_DOMAIN,
    ENTITY_VALUE_STREAM,
    ENTITY_VALUE_STREAM_STAGE,
)


class _RecordingIndex:
    """Records every index_entity/unindex_entity call instead of touching a
    real search index -- see module docstring."""

    def __init__(self) -> None:
        self.indexed: list[tuple[str, str, str]] = []
        self.unindexed: list[tuple[str, str]] = []

    async def index_entity(self, entity_type: str, entity_id: str, text: str, session) -> None:
        self.indexed.append((entity_type, entity_id, text))

    async def unindex_entity(self, entity_type: str, entity_id: str, session) -> None:
        self.unindexed.append((entity_type, entity_id))


@pytest.fixture()
def recorder(monkeypatch) -> _RecordingIndex:
    rec = _RecordingIndex()
    monkeypatch.setattr(bstore, "index_entity", rec.index_entity)
    monkeypatch.setattr(bstore, "unindex_entity", rec.unindex_entity)
    return rec


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/search_indexing.db")
    async with engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


# ── Value stream (pre-existing 041 wiring, previously untested) ──────────────


async def test_create_value_stream_indexes(session, recorder) -> None:
    vs = await bstore.create_value_stream(ValueStreamCreate(name="Order to Cash"), session)
    assert recorder.indexed == [(ENTITY_VALUE_STREAM, vs.id, "Order to Cash")]


async def test_delete_value_stream_unindexes(session, recorder) -> None:
    vs = await bstore.create_value_stream(ValueStreamCreate(name="Order to Cash"), session)
    recorder.indexed.clear()
    deleted = await bstore.delete_value_stream(vs.id, session)
    assert deleted is True
    assert (ENTITY_VALUE_STREAM, vs.id) in recorder.unindexed


async def test_delete_value_stream_with_no_stages_does_not_raise(session, recorder) -> None:
    vs = await bstore.create_value_stream(ValueStreamCreate(name="No Stages Here"), session)
    deleted = await bstore.delete_value_stream(vs.id, session)
    assert deleted is True
    # Only the value stream itself was unindexed -- no stray stage unindex calls.
    assert recorder.unindexed == [(ENTITY_VALUE_STREAM, vs.id)]


# ── Value stream stage (new in this feature) ─────────────────────────────────


async def test_add_stage_indexes(session, recorder) -> None:
    vs = await bstore.create_value_stream(ValueStreamCreate(name="Claims"), session)
    recorder.indexed.clear()
    stage = await bstore.add_stage(
        vs.id, ValueStreamStageCreate(name="Fraud Triage", description="Initial review"), session
    )
    assert recorder.indexed == [
        (ENTITY_VALUE_STREAM_STAGE, stage.id, "Fraud Triage Initial review")
    ]


async def test_update_stage_reindexes_with_new_text(session, recorder) -> None:
    vs = await bstore.create_value_stream(ValueStreamCreate(name="Claims"), session)
    stage = await bstore.add_stage(vs.id, ValueStreamStageCreate(name="Old Name"), session)
    recorder.indexed.clear()

    await bstore.update_stage(
        vs.id, stage.id, ValueStreamStageUpdate(name="New Name"), session
    )
    assert recorder.indexed == [(ENTITY_VALUE_STREAM_STAGE, stage.id, "New Name")]


async def test_delete_stage_unindexes(session, recorder) -> None:
    vs = await bstore.create_value_stream(ValueStreamCreate(name="Claims"), session)
    stage = await bstore.add_stage(vs.id, ValueStreamStageCreate(name="Fraud Triage"), session)
    recorder.unindexed.clear()

    deleted = await bstore.delete_stage(vs.id, stage.id, session)
    assert deleted is True
    assert recorder.unindexed == [(ENTITY_VALUE_STREAM_STAGE, stage.id)]


async def test_reorder_stages_unindexes_dropped_and_reindexes_renamed(session, recorder) -> None:
    vs = await bstore.create_value_stream(ValueStreamCreate(name="Claims"), session)
    kept = await bstore.add_stage(vs.id, ValueStreamStageCreate(name="Kept Stage"), session)
    dropped = await bstore.add_stage(vs.id, ValueStreamStageCreate(name="Dropped Stage"), session)
    recorder.indexed.clear()
    recorder.unindexed.clear()

    await bstore.reorder_stages(
        vs.id,
        [StageReorderItem(id=kept.id, name="Kept Stage Renamed", description=None)],
        session,
    )

    assert recorder.unindexed == [(ENTITY_VALUE_STREAM_STAGE, dropped.id)]
    assert recorder.indexed == [(ENTITY_VALUE_STREAM_STAGE, kept.id, "Kept Stage Renamed")]


async def test_delete_value_stream_unindexes_its_stages(session, recorder) -> None:
    """The cascade-unindex fix (FR-004/research.md D3): deleting a value stream
    directly (not each stage individually) must still unindex every one of its
    stages, not just the value stream itself."""
    vs = await bstore.create_value_stream(ValueStreamCreate(name="Claims"), session)
    stage1 = await bstore.add_stage(vs.id, ValueStreamStageCreate(name="Stage One"), session)
    stage2 = await bstore.add_stage(vs.id, ValueStreamStageCreate(name="Stage Two"), session)
    recorder.unindexed.clear()

    deleted = await bstore.delete_value_stream(vs.id, session)

    assert deleted is True
    assert set(recorder.unindexed) == {
        (ENTITY_VALUE_STREAM, vs.id),
        (ENTITY_VALUE_STREAM_STAGE, stage1.id),
        (ENTITY_VALUE_STREAM_STAGE, stage2.id),
    }


# ── Business domain org_unit (this feature's FR-006) + pre-existing wiring ───


async def test_create_domain_indexes_name_scope_and_org_unit(session, recorder) -> None:
    domain = await bstore.create_domain(
        BusinessDomainCreate(
            name="Underwriting", classification="strategic",
            scope_statement="Risk assessment", org_unit="Claims Ops",
        ),
        session,
    )
    assert recorder.indexed == [
        (ENTITY_BUSINESS_DOMAIN, domain.id, "Underwriting Risk assessment Claims Ops")
    ]


async def test_update_domain_reindexes_with_new_org_unit(session, recorder) -> None:
    domain = await bstore.create_domain(
        BusinessDomainCreate(name="Underwriting", classification="strategic"), session
    )
    recorder.indexed.clear()

    await bstore.update_domain(
        domain.id, BusinessDomainUpdate(org_unit="New Org Unit"), session
    )
    assert recorder.indexed == [(ENTITY_BUSINESS_DOMAIN, domain.id, "Underwriting New Org Unit")]


async def test_delete_domain_unindexes(session, recorder) -> None:
    domain = await bstore.create_domain(
        BusinessDomainCreate(name="Underwriting", classification="strategic"), session
    )
    recorder.unindexed.clear()

    deleted = await bstore.delete_domain(domain.id, session)
    assert deleted is True
    assert recorder.unindexed == [(ENTITY_BUSINESS_DOMAIN, domain.id)]
