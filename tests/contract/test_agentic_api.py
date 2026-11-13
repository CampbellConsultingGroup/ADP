"""Contract tests for the agent registry API (933-agent-registry, ADP-hii), /api/v1/agentic, plus
the agentic reclassify guard on PATCH /api/v1/applications/{id}.

Runs the real app against a SQLite file. Fixture order matters (research.md D3): adp.application's
metadata is created first WITHOUT its narrow solution_agents mirror, then adp.agentic's metadata
(full solution_agents; its narrow applications mirror is skipped because the full table exists).
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.agentic import router as agrouter
from adp.agentic import store as agstore
from adp.application import router as arouter
from adp.application import store as astore
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole

AG = "/api/v1/agentic"
APPS = "/api/v1/applications"


@pytest.fixture()
async def app_and_client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/agentic_api.db")

    def _create(sync_conn):
        astore._metadata.create_all(
            sync_conn,
            tables=[t for t in astore._metadata.sorted_tables if t.name != "solution_agents"],
        )
        agstore._metadata.create_all(sync_conn)

    async with engine.begin() as conn:
        await conn.run_sync(_create)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[agrouter._get_session] = _override
    app.dependency_overrides[arouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield app, c
    await engine.dispose()


@pytest.fixture()
async def client(app_and_client):
    return app_and_client[1]


def _as_role(app, role: PersonaRole) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="u", username="u", email="u@localhost", role=role, groups=[]
    )


async def _app(client, name="Claims", app_type="agentic") -> str:
    resp = await client.post(APPS, json={"name": name, "application_type": app_type})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _agent(client, name="Triage", **extra) -> dict:
    body = {"name": name, "autonomy_level": 2, "human_approval": "on_write", **extra}
    resp = await client.post(f"{AG}/agents", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _join(client, app_id, agent_id, role="worker"):
    return await client.post(
        f"{AG}/solutions/{app_id}/agents", json={"agent_id": agent_id, "role": role}
    )


# ── Agents (US1) ──────────────────────────────────────────────────────────────


async def test_agent_crud(client):
    agent = await _agent(
        client, model_provider="Anthropic", est_cost_per_run=0.042, runs_per_month=100
    )
    assert agent["cost_visible"] is True and agent["solution_count"] == 0
    assert agent["est_cost_per_run"] in ("0.0420", "0.042")

    detail = (await client.get(f"{AG}/agents/{agent['id']}")).json()
    assert detail["solutions"] == [] and detail["model_provider"] == "Anthropic"

    resp = await client.patch(f"{AG}/agents/{agent['id']}", json={"autonomy_level": 4})
    assert resp.status_code == 200 and resp.json()["autonomy_level"] == 4

    assert (await client.delete(f"{AG}/agents/{agent['id']}")).status_code == 204
    assert (await client.get(f"{AG}/agents/{agent['id']}")).status_code == 404


@pytest.mark.parametrize(
    "override",
    [
        {"autonomy_level": 5},
        {"human_approval": "sometimes"},
        {"a2a_card_url": "javascript:alert(1)"},
        {"est_cost_per_run": -1},
        {"name": "  "},
    ],
)
async def test_invalid_agent_is_422_and_not_stored(client, override):
    body = {"name": "x", "autonomy_level": 1, "human_approval": "none", **override}
    assert (await client.post(f"{AG}/agents", json=body)).status_code == 422
    assert (await client.get(f"{AG}/agents")).json()["total"] == 0


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/agents/nope", None),
        ("PATCH", "/agents/nope", {"owner": "x"}),
        ("DELETE", "/agents/nope", None),
        ("GET", "/solutions/nope/agents", None),
        ("PUT", "/solutions/nope/agents/order", {"agent_ids": []}),
        ("PATCH", "/solutions/nope/agents/a", {"role": "worker"}),
        ("DELETE", "/solutions/nope/agents/a", None),
    ],
)
async def test_unknown_ids_are_404(client, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    assert (await client.request(method, f"{AG}{path}", **kwargs)).status_code == 404


# ── Membership (US1) ──────────────────────────────────────────────────────────


async def test_membership_lifecycle(client):
    app_id = await _app(client)
    orch, worker = await _agent(client, "Orchestrator"), await _agent(client, "Worker")

    assert (await _join(client, app_id, orch["id"], "orchestrator")).status_code == 201
    resp = await _join(client, app_id, worker["id"])
    assert [(m["agent"]["name"], m["position"]) for m in resp.json()["items"]] == [
        ("Orchestrator", 0),
        ("Worker", 1),
    ]
    assert (await _join(client, app_id, worker["id"])).status_code == 409

    resp = await client.put(
        f"{AG}/solutions/{app_id}/agents/order", json={"agent_ids": [worker["id"], orch["id"]]}
    )
    assert resp.status_code == 200
    assert [m["agent"]["name"] for m in resp.json()["items"]] == ["Worker", "Orchestrator"]
    resp = await client.put(
        f"{AG}/solutions/{app_id}/agents/order", json={"agent_ids": [orch["id"]]}
    )
    assert resp.status_code == 422

    resp = await client.patch(
        f"{AG}/solutions/{app_id}/agents/{worker['id']}", json={"role": "reviewer"}
    )
    assert resp.status_code == 200 and resp.json()["role"] == "reviewer"

    assert (
        await client.delete(f"{AG}/solutions/{app_id}/agents/{worker['id']}")
    ).status_code == 204
    listed = (await client.get(f"{AG}/solutions/{app_id}/agents")).json()
    assert [(m["agent"]["name"], m["position"]) for m in listed["items"]] == [("Orchestrator", 0)]
    assert (await client.get(f"{AG}/agents/{worker['id']}")).status_code == 200


async def test_agents_only_on_agentic_applications(client):
    crm = await _app(client, "CRM", "cots")
    agent = await _agent(client)
    assert (await _join(client, crm, agent["id"])).status_code == 422
    app_id = await _app(client)
    assert (await _join(client, app_id, "missing")).status_code == 404


async def test_reclassify_guard_and_application_delete(client):
    app_id = await _app(client)
    agent = await _agent(client)
    await _join(client, app_id, agent["id"])

    resp = await client.patch(f"{APPS}/{app_id}", json={"application_type": "custom"})
    assert resp.status_code == 409 and "1 agent" in resp.json()["detail"]

    assert (await client.delete(f"{APPS}/{app_id}")).status_code == 204
    detail = (await client.get(f"{AG}/agents/{agent['id']}")).json()
    assert detail["solution_count"] == 0  # the agent survives its solution


# ── Estate-wide list and shared agents (US2) ──────────────────────────────────


async def test_list_filters_and_shared_agent_detail(client):
    claims, fraud = await _app(client, "Claims"), await _app(client, "Fraud")
    shared = await _agent(client, "Policy Lookup", autonomy_level=3, model_provider="Anthropic")
    await _agent(client, "Drafting", autonomy_level=1, model_provider="OpenAI")
    await _join(client, claims, shared["id"], "worker")
    await _join(client, fraud, shared["id"], "reviewer")

    listed = (await client.get(f"{AG}/agents")).json()
    assert {a["name"]: a["solution_count"] for a in listed["items"]} == {
        "Drafting": 0,
        "Policy Lookup": 2,
    }
    high = (await client.get(f"{AG}/agents", params={"autonomy_min": 3})).json()
    assert [a["name"] for a in high["items"]] == ["Policy Lookup"]
    by_provider = (await client.get(f"{AG}/agents", params={"model_provider": "OpenAI"})).json()
    assert [a["name"] for a in by_provider["items"]] == ["Drafting"]
    assert (await client.get(f"{AG}/agents", params={"autonomy_min": 9})).status_code == 422

    detail = (await client.get(f"{AG}/agents/{shared['id']}")).json()
    assert sorted((s["app_name"], s["role"]) for s in detail["solutions"]) == [
        ("Claims", "worker"),
        ("Fraud", "reviewer"),
    ]


# ── Cost gating (Clarification Q2) ────────────────────────────────────────────


async def test_cost_redacted_for_callers_without_cost_read(app_and_client):
    app, client = app_and_client
    app_id = await _app(client)
    agent = await _agent(client, est_cost_per_run=0.5, runs_per_month=10, owner="Team")
    await _join(client, app_id, agent["id"])

    _as_role(app, PersonaRole.REVIEWER)
    try:
        detail = (await client.get(f"{AG}/agents/{agent['id']}")).json()
        listed = (await client.get(f"{AG}/agents")).json()["items"][0]
        member = (await client.get(f"{AG}/solutions/{app_id}/agents")).json()["items"][0]
        for view in (detail, listed, member["agent"]):
            assert view["est_cost_per_run"] is None and view["runs_per_month"] is None
            assert view["cost_visible"] is False
            assert view["owner"] == "Team"  # the rest of the agent stays visible
        # REVIEWER lacks WRITE_APPLICATION entirely -- the prefix rule blocks writes.
        assert (
            await client.patch(f"{AG}/agents/{agent['id']}", json={"owner": "x"})
        ).status_code == 403
    finally:
        del app.dependency_overrides[get_current_user]


async def test_setting_cost_requires_cost_write(app_and_client, monkeypatch):
    """No current persona holds WRITE_APPLICATION without WRITE_APPLICATION_COST, so the inline
    gate is exercised by denying only that one action."""
    from adp.authz.roles import ActionType

    _, client = app_and_client
    agent = await _agent(client)
    real = agrouter.is_permitted
    monkeypatch.setattr(
        agrouter,
        "is_permitted",
        lambda role, action: action != ActionType.WRITE_APPLICATION_COST and real(role, action),
    )
    path = f"{AG}/agents/{agent['id']}"
    assert (await client.patch(path, json={"est_cost_per_run": 1})).status_code == 403
    assert (await client.patch(path, json={"runs_per_month": 1})).status_code == 403
    assert (await client.patch(path, json={"owner": "ok"})).status_code == 200
    body = {"name": "x", "autonomy_level": 0, "human_approval": "always", "runs_per_month": 5}
    assert (await client.post(f"{AG}/agents", json=body)).status_code == 403
