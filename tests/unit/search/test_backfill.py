"""Unit tests: adp.search.backfill.reindex_all() (ADP-7bo).

Monkeypatches adp.search.backfill.default_index() to return a small recording
fake exposing an async upsert(entity_type, entity_id, text, session) -- never
touching real SearchIndex/pgvector/Postgres-dialect SQL at all, since
SearchIndex.upsert's ON CONFLICT DO UPDATE construct cannot compile against
SQLite (research.md D7). The entity data itself comes from a real SQLite-
backed bstore/astore fixture, combining both stores' metadata onto one
engine (unlike tests/unit/chat/test_tools.py's two-separate-engines fixture,
which doesn't need a single session to see both stores at once the way
reindex_all's single-session signature does).

The real upsert SQL path is covered separately by the Docker-gated
integration test in tests/integration/test_search.py.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import store as astore
from adp.application.models import ApplicationCreate, TechnicalCapabilityCreate
from adp.business import store as bstore
from adp.business.models import (
    BusinessCapabilityCreate,
    BusinessDomainCreate,
    ValueStreamCreate,
    ValueStreamStageCreate,
)
from adp.search import backfill as bf
from adp.search.index import (
    ENTITY_APPLICATION,
    ENTITY_BUSINESS_CAPABILITY,
    ENTITY_BUSINESS_DOMAIN,
    ENTITY_TECHNICAL_CAPABILITY,
    ENTITY_VALUE_STREAM,
    ENTITY_VALUE_STREAM_STAGE,
)


class _RecordingIndex:
    def __init__(self) -> None:
        self.upserted: list[tuple[str, str, str]] = []

    async def upsert(self, entity_type: str, entity_id: str, text: str, session) -> None:
        self.upserted.append((entity_type, entity_id, text))


@pytest.fixture()
def recording_index(monkeypatch) -> _RecordingIndex:
    rec = _RecordingIndex()
    monkeypatch.setattr(bf, "default_index", lambda: rec)
    return rec


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/backfill.db")
    async with engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_reindex_all_covers_every_entity_type(session, recording_index) -> None:
    cap = await bstore.create_capability(
        BusinessCapabilityCreate(name="Risk Assessment", level=1), session
    )
    tc = await astore.create_technical_capability(
        TechnicalCapabilityCreate(name="Rules Engine"), session
    )
    app = await astore.create_application(ApplicationCreate(name="Claims Core"), session)
    vs = await bstore.create_value_stream(ValueStreamCreate(name="Order to Cash"), session)
    stage = await bstore.add_stage(vs.id, ValueStreamStageCreate(name="Quote"), session)
    domain = await bstore.create_domain(
        BusinessDomainCreate(name="Underwriting", classification="strategic"), session
    )

    counts = await bf.reindex_all(session)

    upserted_ids = {(et, eid) for et, eid, _ in recording_index.upserted}
    assert (ENTITY_BUSINESS_CAPABILITY, cap.id) in upserted_ids
    assert (ENTITY_TECHNICAL_CAPABILITY, tc.id) in upserted_ids
    assert (ENTITY_APPLICATION, app.id) in upserted_ids
    assert (ENTITY_VALUE_STREAM, vs.id) in upserted_ids
    assert (ENTITY_VALUE_STREAM_STAGE, stage.id) in upserted_ids
    assert (ENTITY_BUSINESS_DOMAIN, domain.id) in upserted_ids

    assert counts == {
        ENTITY_BUSINESS_CAPABILITY: 1,
        ENTITY_TECHNICAL_CAPABILITY: 1,
        ENTITY_APPLICATION: 1,
        ENTITY_VALUE_STREAM: 1,
        ENTITY_VALUE_STREAM_STAGE: 1,
        ENTITY_BUSINESS_DOMAIN: 1,
    }


async def test_reindex_all_domain_text_includes_org_unit(session, recording_index) -> None:
    domain = await bstore.create_domain(
        BusinessDomainCreate(
            name="Underwriting", classification="strategic", org_unit="Claims Ops"
        ),
        session,
    )

    await bf.reindex_all(session)

    domain_upserts = [u for u in recording_index.upserted if u[0] == ENTITY_BUSINESS_DOMAIN]
    assert domain_upserts == [(ENTITY_BUSINESS_DOMAIN, domain.id, "Underwriting Claims Ops")]


async def test_reindex_all_empty_database_returns_zero_counts(session, recording_index) -> None:
    counts = await bf.reindex_all(session)
    assert counts == {
        ENTITY_BUSINESS_CAPABILITY: 0,
        ENTITY_TECHNICAL_CAPABILITY: 0,
        ENTITY_APPLICATION: 0,
        ENTITY_VALUE_STREAM: 0,
        ENTITY_VALUE_STREAM_STAGE: 0,
        ENTITY_BUSINESS_DOMAIN: 0,
    }
    assert recording_index.upserted == []
