"""Unit tests for the agent "automates" links (944-agent-traceability, ADP-12x, US1) against a
SQLite fixture. Targets are inserted straight into adp.agentic.store's narrow mirrors of the
business tables (research.md R1), so the fixture needs no adp.business metadata.

Covers: add/list per kind with context (capability path, stage's stream, activity's chain and
category), the L3 rule, duplicates, unknown agent/target, removal, delete_agent clearing links,
reverse lookups sorted by agent name, ordering, and dangling links never surfacing.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.agentic import store as agstore
from adp.agentic.models import (
    AgentCreate,
    AgentNotFoundError,
    DuplicateLinkError,
    LevelRuleError,
    LinkNotFoundError,
    TargetNotFoundError,
)


@pytest.fixture(autouse=True)
def _no_search(monkeypatch):
    async def _noop(*_a, **_k):
        return None

    monkeypatch.setattr(agstore, "index_entity", _noop)
    monkeypatch.setattr(agstore, "unindex_entity", _noop)


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/automates.db")
    async with engine.begin() as conn:
        await conn.run_sync(agstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        for cid, name, level, parent in [
            ("l1", "Commerce", 1, None),
            ("l2", "Checkout", 2, "l1"),
            ("l3", "Process Payment", 3, "l2"),
            ("l3b", "Apply Promotions", 3, "l2"),
        ]:
            await s.execute(
                agstore._capabilities_mirror.insert().values(
                    id=cid, name=name, level=level, parent_id=parent
                )
            )
        streams = agstore._value_streams_mirror
        await s.execute(streams.insert().values(id="vs1", name="Order to Cash"))
        await s.execute(agstore._value_streams_mirror.insert().values(id="vs0", name="Acquire"))
        for sid, vs, name, pos in [
            ("st2", "vs1", "Ship", 1),
            ("st1", "vs1", "Take Order", 0),
            ("st0", "vs0", "Attract", 0),
        ]:
            await s.execute(
                agstore._stages_mirror.insert().values(
                    id=sid, value_stream_id=vs, name=name, position=pos
                )
            )
        await s.execute(agstore._value_chains_mirror.insert().values(id="ch1", name="Retail"))
        for aid, name, cat, pos in [
            ("a-sup", "Procurement", "support", 0),
            ("a-pri", "Inbound Logistics", "primary", 0),
        ]:
            await s.execute(
                agstore._activities_mirror.insert().values(
                    id=aid, value_chain_id="ch1", name=name, category=cat, position=pos
                )
            )
        yield s
    await engine.dispose()


async def _agent(session, name="Triage", **extra) -> str:
    body = {"name": name, "autonomy_level": 2, "human_approval": "on_write", **extra}
    return (await agstore.create_agent(AgentCreate(**body), session)).id


async def test_capability_link_with_path(session):
    ag = await _agent(session)
    out = await agstore.add_link("capability", ag, "l3", session)
    assert [(c.id, c.name, c.level, c.path) for c in out.capabilities] == [
        ("l3", "Process Payment", 3, ["Commerce", "Checkout"])
    ]
    assert out.stages == [] and out.activities == []
    assert (await agstore.get_automates(ag, session)) == out


@pytest.mark.parametrize("cap_id", ["l1", "l2"])
async def test_capability_link_refuses_non_l3(session, cap_id):
    ag = await _agent(session)
    with pytest.raises(LevelRuleError, match="L3 only"):
        await agstore.add_link("capability", ag, cap_id, session)


async def test_stage_and_activity_links_with_context(session):
    ag = await _agent(session)
    await agstore.add_link("stage", ag, "st2", session)
    await agstore.add_link("stage", ag, "st1", session)
    await agstore.add_link("stage", ag, "st0", session)
    await agstore.add_link("activity", ag, "a-sup", session)
    out = await agstore.add_link("activity", ag, "a-pri", session)
    # Stages by stream name, then position.
    assert [(s.id, s.value_stream_name) for s in out.stages] == [
        ("st0", "Acquire"), ("st1", "Order to Cash"), ("st2", "Order to Cash"),
    ]
    # Activities: primary first, then support.
    assert [(a.id, a.category, a.value_chain_name) for a in out.activities] == [
        ("a-pri", "primary", "Retail"), ("a-sup", "support", "Retail"),
    ]


async def test_capabilities_ordered_by_path_then_name(session):
    ag = await _agent(session)
    await agstore.add_link("capability", ag, "l3", session)
    out = await agstore.add_link("capability", ag, "l3b", session)
    assert [c.name for c in out.capabilities] == ["Apply Promotions", "Process Payment"]


@pytest.mark.parametrize(
    "kind,target", [("capability", "l3"), ("stage", "st1"), ("activity", "a-pri")]
)
async def test_duplicate_link_refused(session, kind, target):
    ag = await _agent(session)
    await agstore.add_link(kind, ag, target, session)
    with pytest.raises(DuplicateLinkError):
        await agstore.add_link(kind, ag, target, session)


@pytest.mark.parametrize("kind", ["capability", "stage", "activity"])
async def test_unknown_target_and_agent(session, kind):
    ag = await _agent(session)
    with pytest.raises(TargetNotFoundError):
        await agstore.add_link(kind, ag, "nope", session)
    with pytest.raises(AgentNotFoundError):
        await agstore.add_link(kind, "no-agent", "l3", session)
    with pytest.raises(TargetNotFoundError):
        await agstore.list_agents_for(kind, "nope", session)


async def test_get_automates_unknown_agent(session):
    with pytest.raises(AgentNotFoundError):
        await agstore.get_automates("no-agent", session)


async def test_remove_link(session):
    ag = await _agent(session)
    await agstore.add_link("capability", ag, "l3", session)
    await agstore.remove_link("capability", ag, "l3", session)
    assert (await agstore.get_automates(ag, session)).capabilities == []
    assert await agstore.list_agents_for("capability", "l3", session) == []
    with pytest.raises(LinkNotFoundError):
        await agstore.remove_link("capability", ag, "l3", session)


async def test_reverse_lookup_sorted_by_agent_name(session):
    zed = await _agent(session, "Zed")
    amy = await _agent(session, "Amy", autonomy_level=4, human_approval="none")
    for ag in (zed, amy):
        await agstore.add_link("capability", ag, "l3", session)
    found = await agstore.list_agents_for("capability", "l3", session)
    assert [a.name for a in found] == ["Amy", "Zed"]
    assert found[0].autonomy_level == 4 and found[0].lifecycle_status == "active"
    assert found[0].agentic_risk.band == "high"


async def test_delete_agent_clears_links(session):
    ag = await _agent(session)
    await agstore.add_link("capability", ag, "l3", session)
    await agstore.add_link("stage", ag, "st1", session)
    await agstore.add_link("activity", ag, "a-pri", session)
    assert await agstore.delete_agent(ag, session)
    for table in (
        agstore._agent_capability_links, agstore._agent_stage_links, agstore._agent_activity_links,
    ):
        assert (await session.execute(table.select())).first() is None


async def test_dangling_link_never_surfaces(session):
    """SQLite doesn't enforce the migration's CASCADE: a link whose target row is gone must not
    appear (reads inner-join the mirrors)."""
    ag = await _agent(session)
    await session.execute(
        agstore._agent_capability_links.insert().values(
            agent_id=ag, capability_id="gone", created_at=datetime.now(timezone.utc)
        )
    )
    assert (await agstore.get_automates(ag, session)).capabilities == []
