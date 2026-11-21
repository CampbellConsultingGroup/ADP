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

from adp.agentic import store as agstore
from adp.agentic.models import AgentCreate
from adp.application import app_capabilities as acstore
from adp.application import store as astore
from adp.application.app_capability_models import ApplicationCapabilityCreate
from adp.application.models import ApplicationCreate, TechnicalCapabilityCreate
from adp.business import store as bstore
from adp.business import value_chains as vcstore
from adp.business.models import (
    BusinessCapabilityCreate,
    BusinessDomainCreate,
    ValueChainActivityCreate,
    ValueChainCreate,
    ValueStreamCreate,
    ValueStreamStageCreate,
)
from adp.organization import store as ostore
from adp.organization.models import OrgUnitCreate
from adp.search import backfill as bf
from adp.search.index import (
    ENTITY_AGENT,
    ENTITY_APPLICATION,
    ENTITY_APPLICATION_CAPABILITY,
    ENTITY_BUSINESS_CAPABILITY,
    ENTITY_BUSINESS_DOMAIN,
    ENTITY_LEGAL_ENTITY,
    ENTITY_ORG_UNIT,
    ENTITY_TECHNICAL_CAPABILITY,
    ENTITY_VALUE_CHAIN,
    ENTITY_VALUE_CHAIN_ACTIVITY,
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
        # astore's narrow solution_agents mirror is skipped so agstore's full table wins (933).
        await conn.run_sync(
            lambda c: astore._metadata.create_all(
                c, tables=[t for t in astore._metadata.sorted_tables if t.name != "solution_agents"]
            )
        )
        await conn.run_sync(agstore._metadata.create_all)
        # 940: the organization tables, minus its narrow applications mirror (astore's wins).
        await conn.run_sync(
            lambda c: ostore._metadata.create_all(
                c,
                tables=[
                    t
                    for t in ostore._metadata.sorted_tables
                    if t.name not in ("applications", "business_capabilities")
                ],
            )
        )
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
    chain = await vcstore.create_value_chain(ValueChainCreate(name="Retail"), session)
    activity = await vcstore.add_activity(
        chain.id, ValueChainActivityCreate(name="Operations", category="primary"), session
    )

    agent = await agstore.create_agent(
        AgentCreate(
            name="Claims Triage", autonomy_level=2, human_approval="none", framework="LangGraph"
        ),
        session,
    )

    l1 = await acstore.create_app_capability(
        ApplicationCapabilityCreate(name="Transaction Processing"), session
    )
    l2 = await acstore.create_app_capability(
        ApplicationCapabilityCreate(name="Payments", parent_id=l1.id), session
    )

    rc = await ostore.create_org_unit(OrgUnitCreate(name="Retail Co"), session)
    stores = await ostore.create_org_unit(OrgUnitCreate(name="Stores", parent_id=rc.id), session)
    # 947: legal entities, text = name, registration number, LEI, description, parent path.
    from adp.organization import legal_entities
    from adp.organization.models import LegalEntityCreate

    plc = await legal_entities.create_legal_entity(LegalEntityCreate(name="Retail Co plc"), session)
    gmbh = await legal_entities.create_legal_entity(
        LegalEntityCreate(name="Retail Co GmbH", registration_number="HRB 1", parent_id=plc.id),
        session,
    )

    counts = await bf.reindex_all(session)

    assert (
        ENTITY_LEGAL_ENTITY,
        gmbh.id,
        "Retail Co GmbH HRB 1 Retail Co plc",
    ) in recording_index.upserted

    assert (ENTITY_ORG_UNIT, stores.id, "Stores Retail Co") in recording_index.upserted
    assert (
        ENTITY_APPLICATION_CAPABILITY,
        l2.id,
        "Payments Transaction Processing",
    ) in recording_index.upserted
    upserted_ids = {(et, eid) for et, eid, _ in recording_index.upserted}
    assert (ENTITY_BUSINESS_CAPABILITY, cap.id) in upserted_ids
    assert (ENTITY_TECHNICAL_CAPABILITY, tc.id) in upserted_ids
    assert (ENTITY_APPLICATION, app.id) in upserted_ids
    assert (ENTITY_VALUE_STREAM, vs.id) in upserted_ids
    assert (ENTITY_VALUE_STREAM_STAGE, stage.id) in upserted_ids
    assert (ENTITY_BUSINESS_DOMAIN, domain.id) in upserted_ids
    assert (ENTITY_VALUE_CHAIN, chain.id) in upserted_ids
    assert (ENTITY_VALUE_CHAIN_ACTIVITY, activity.id) in upserted_ids
    assert (ENTITY_AGENT, agent.id, "Claims Triage LangGraph") in recording_index.upserted

    assert counts == {
        ENTITY_BUSINESS_CAPABILITY: 1,
        ENTITY_TECHNICAL_CAPABILITY: 1,
        ENTITY_APPLICATION: 1,
        ENTITY_VALUE_STREAM: 1,
        ENTITY_VALUE_STREAM_STAGE: 1,
        ENTITY_BUSINESS_DOMAIN: 1,
        ENTITY_VALUE_CHAIN: 1,
        ENTITY_VALUE_CHAIN_ACTIVITY: 1,
        ENTITY_AGENT: 1,
        ENTITY_APPLICATION_CAPABILITY: 2,
        ENTITY_ORG_UNIT: 2,
        ENTITY_LEGAL_ENTITY: 2,
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
        ENTITY_VALUE_CHAIN: 0,
        ENTITY_VALUE_CHAIN_ACTIVITY: 0,
        ENTITY_AGENT: 0,
        ENTITY_ORG_UNIT: 0,
        ENTITY_LEGAL_ENTITY: 0,
        ENTITY_APPLICATION_CAPABILITY: 0,
    }
    assert recording_index.upserted == []
