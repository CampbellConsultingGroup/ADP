"""Unit tests for adp.agentic.store (933-agent-registry, ADP-hii) against a SQLite fixture.

Covers the invariants the store owns: memberships only on agentic applications, no duplicates,
positions kept 0..n-1 per solution through add/reorder/remove/agent-delete, shared agents surviving
membership removal, PATCH semantics, list filters and solution counts, and the search index being
written/cleared at every call site (index_entity/unindex_entity patched to recording stubs, as in
test_value_chains_store.py -- the real index SQL is Postgres-only).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.agentic import store as agstore
from adp.agentic.models import (
    AgentCreate,
    AgentNotFoundError,
    AgentUpdate,
    DuplicateSolutionAgentError,
    MembershipNotFoundError,
    NotAgenticSolutionError,
    OrderMismatchError,
    SolutionNotFoundError,
)
from adp.search import ENTITY_AGENT


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/agentic.db")
    async with engine.begin() as conn:
        await conn.run_sync(agstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        for app_id, name, app_type in [
            ("claims", "Claims Handling", "agentic"),
            ("fraud", "Fraud Review", "agentic"),
            ("crm", "CRM", "cots"),
        ]:
            await s.execute(
                agstore._applications_mirror.insert().values(
                    id=app_id, name=name, application_type=app_type
                )
            )
        yield s
    await engine.dispose()


@pytest.fixture()
def index_calls(monkeypatch):
    calls: list[tuple[str, str, str, str | None]] = []

    async def fake_index(entity_type, entity_id, text, session):
        calls.append(("index", entity_type, entity_id, text))

    async def fake_unindex(entity_type, entity_id, session):
        calls.append(("unindex", entity_type, entity_id, None))

    monkeypatch.setattr(agstore, "index_entity", fake_index)
    monkeypatch.setattr(agstore, "unindex_entity", fake_unindex)
    return calls


async def _agent(session, name="Triage", level=2, **extra):
    return await agstore.create_agent(
        AgentCreate(name=name, autonomy_level=level, human_approval="on_write", **extra), session
    )


async def _positions(session, app_id):
    return [
        (m.agent.name, m.position) for m in await agstore.list_solution_agents(app_id, session)
    ]


# ── Agents ────────────────────────────────────────────────────────────────────


async def test_create_and_get_agent_round_trips_every_field(session, index_calls):
    created = await _agent(
        session,
        description="Routes claims",
        owner="Claims Platform",
        model_provider="Anthropic",
        model_id="claude-sonnet-5-5",
        framework="Claude Agent SDK",
        prompt_ref="triage@v7",
        data_classification_max="confidential",
        a2a_card_url="https://x.example/card.json",
        est_cost_per_run=Decimal("0.0420"),
        runs_per_month=12000,
        external_registry_ref="rt-123",
    )
    got = await agstore.get_agent(created.id, session)
    assert got is not None
    assert got.model_provider == "Anthropic" and got.prompt_ref == "triage@v7"
    assert got.est_cost_per_run == Decimal("0.0420") and got.runs_per_month == 12000
    assert got.solutions == [] and got.solution_count == 0
    assert index_calls[-1][:3] == ("index", ENTITY_AGENT, created.id)
    assert "Anthropic" in index_calls[-1][3] and "Claude Agent SDK" in index_calls[-1][3]


async def test_get_unknown_agent_is_none(session):
    assert await agstore.get_agent("nope", session) is None
    assert await agstore.update_agent("nope", AgentUpdate(owner="x"), session) is None
    assert await agstore.delete_agent("nope", session) is False


async def test_update_patch_semantics(session, index_calls):
    agent = await _agent(session, owner="Team A", model_id="m1")
    updated = await agstore.update_agent(
        agent.id, AgentUpdate(owner=None, autonomy_level=4, name="Triage v2"), session
    )
    assert updated is not None
    assert updated.owner is None  # explicit null clears
    assert updated.model_id == "m1"  # omitted field unchanged
    assert (updated.autonomy_level, updated.name) == (4, "Triage v2")
    # An explicit null on a required field is ignored rather than written.
    again = await agstore.update_agent(agent.id, AgentUpdate(autonomy_level=None), session)
    assert again is not None and again.autonomy_level == 4
    assert index_calls[-1][:3] == ("index", ENTITY_AGENT, agent.id)
    assert "Triage v2" in index_calls[-1][3]


async def test_delete_agent_unindexes(session, index_calls):
    agent = await _agent(session)
    assert await agstore.delete_agent(agent.id, session) is True
    assert index_calls[-1] == ("unindex", ENTITY_AGENT, agent.id, None)
    assert await agstore.get_agent(agent.id, session) is None


# ── Membership ────────────────────────────────────────────────────────────────


async def test_add_members_in_order_with_roles(session, index_calls):
    orch = await _agent(session, "Orchestrator")
    worker = await _agent(session, "Worker")
    await agstore.add_solution_agent("claims", orch.id, "orchestrator", session)
    members = await agstore.add_solution_agent("claims", worker.id, "worker", session)
    assert [(m.agent.name, m.role, m.position) for m in members] == [
        ("Orchestrator", "orchestrator", 0),
        ("Worker", "worker", 1),
    ]


async def test_add_member_errors(session, index_calls):
    agent = await _agent(session)
    with pytest.raises(NotAgenticSolutionError):
        await agstore.add_solution_agent("crm", agent.id, "worker", session)
    with pytest.raises(SolutionNotFoundError):
        await agstore.add_solution_agent("missing", agent.id, "worker", session)
    with pytest.raises(AgentNotFoundError):
        await agstore.add_solution_agent("claims", "missing", "worker", session)
    await agstore.add_solution_agent("claims", agent.id, "worker", session)
    with pytest.raises(DuplicateSolutionAgentError):
        await agstore.add_solution_agent("claims", agent.id, "reviewer", session)


async def test_update_role(session, index_calls):
    agent = await _agent(session)
    await agstore.add_solution_agent("claims", agent.id, "worker", session)
    member = await agstore.update_solution_agent_role("claims", agent.id, "reviewer", session)
    assert member.role == "reviewer"
    with pytest.raises(MembershipNotFoundError):
        await agstore.update_solution_agent_role("fraud", agent.id, "reviewer", session)


async def test_reorder_and_mismatch(session, index_calls):
    a, b, c = [await _agent(session, n) for n in ("A", "B", "C")]
    for agent in (a, b, c):
        await agstore.add_solution_agent("claims", agent.id, "worker", session)
    await agstore.reorder_solution_agents("claims", [c.id, a.id, b.id], session)
    assert await _positions(session, "claims") == [("C", 0), ("A", 1), ("B", 2)]
    for bad in ([a.id, b.id], [a.id, a.id, b.id], [a.id, b.id, "x"]):
        with pytest.raises(OrderMismatchError):
            await agstore.reorder_solution_agents("claims", bad, session)


async def test_remove_member_renormalises_and_keeps_agent(session, index_calls):
    a, b, c = [await _agent(session, n) for n in ("A", "B", "C")]
    for agent in (a, b, c):
        await agstore.add_solution_agent("claims", agent.id, "worker", session)
    await agstore.remove_solution_agent("claims", a.id, session)
    assert await _positions(session, "claims") == [("B", 0), ("C", 1)]
    assert await agstore.get_agent(a.id, session) is not None
    with pytest.raises(MembershipNotFoundError):
        await agstore.remove_solution_agent("claims", a.id, session)


async def test_shared_agent_roles_are_per_solution_and_delete_cleans_up(session, index_calls):
    shared = await _agent(session, "Policy Lookup")
    other = await _agent(session, "Other")
    await agstore.add_solution_agent("claims", shared.id, "worker", session)
    await agstore.add_solution_agent("claims", other.id, "worker", session)
    await agstore.add_solution_agent("fraud", shared.id, "reviewer", session)

    detail = await agstore.get_agent(shared.id, session)
    assert detail is not None and detail.solution_count == 2
    assert [(s.app_name, s.role) for s in detail.solutions] == [
        ("Claims Handling", "worker"),
        ("Fraud Review", "reviewer"),
    ]

    await agstore.delete_agent(shared.id, session)
    assert await _positions(session, "claims") == [("Other", 0)]
    assert await agstore.list_solution_agents("fraud", session) == []


async def test_list_solution_agents_unknown_app(session):
    with pytest.raises(SolutionNotFoundError):
        await agstore.list_solution_agents("missing", session)


# ── List + filters (US2) ──────────────────────────────────────────────────────


async def test_list_filters_and_solution_counts(session, index_calls):
    low = await _agent(session, "Low", level=1, model_provider="Anthropic", owner="Team A")
    high = await _agent(session, "High", level=3, model_provider="OpenAI", owner="Team B")
    top = await _agent(
        session, "Top", level=4, model_provider="Anthropic", lifecycle_status="retired"
    )
    await agstore.add_solution_agent("claims", high.id, "worker", session)
    await agstore.add_solution_agent("fraud", high.id, "worker", session)
    await agstore.add_solution_agent("claims", low.id, "worker", session)

    everything = await agstore.list_agents(session)
    assert {a.name: a.solution_count for a in everything} == {"High": 2, "Low": 1, "Top": 0}

    async def names(**kw):
        return sorted(a.name for a in await agstore.list_agents(session, **kw))

    assert await names(autonomy_min=3) == ["High", "Top"]
    assert await names(autonomy_level=1) == ["Low"]
    assert await names(model_provider="Anthropic") == ["Low", "Top"]
    assert await names(owner="Team B") == ["High"]
    assert await names(lifecycle_status="retired") == ["Top"]
    assert top.id in {a.id for a in everything}
