"""Contract tests for agent traceability (944-agent-traceability, ADP-12x).

US1: /api/v1/agentic automates links + reverse lookups. US2: agent compliance mappings under
/api/v1/compliance. US3: agentic_risk / solution_risk on agentic reads.

Runs the real app against one SQLite file shared by four stores. Create order matters: each
module that OWNS a table creates it before any module that only mirrors it (create_all's
checkfirst then skips the narrow mirror): bstore (business tables) -> astore (applications;
minus its narrow solution_agents / regulatory_frameworks mirrors) -> agstore (agents,
solution_agents, links) -> cstore (frameworks, controls, mappings).
"""

from __future__ import annotations

import logging

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.agentic import store as agstore
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole
from adp.compliance import store as cstore

AG = "/api/v1/agentic"
BIZ = "/api/v1/business"
COMP = "/api/v1/compliance"


@pytest.fixture()
async def app_and_client(tmp_path, monkeypatch):
    import adp.application.store as astore
    import adp.business.store as bstore

    async def _noop(*_a, **_k):
        return None

    for module in (agstore, bstore, astore):
        for fn in ("index_entity", "unindex_entity"):
            if hasattr(module, fn):
                monkeypatch.setattr(module, fn, _noop)

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/traceability.db")

    def _create(sync_conn):
        bstore._metadata.create_all(sync_conn)
        astore._metadata.create_all(
            sync_conn,
            tables=[
                t for t in astore._metadata.sorted_tables
                if t.name not in ("solution_agents", "regulatory_frameworks")
            ],
        )
        agstore._metadata.create_all(sync_conn)
        cstore._metadata.create_all(sync_conn)

    async with engine.begin() as conn:
        await conn.run_sync(_create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    for module in (bstore, astore, agstore, cstore):
        monkeypatch.setattr(module, "_engine", engine)
        monkeypatch.setattr(module, "_session_factory", factory)

    from adp.api.app import create_app

    app = create_app()
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


async def _post(client, url, body) -> dict:
    resp = await client.post(url, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _agent(client, name="Triage", **extra) -> dict:
    body = {"name": name, "autonomy_level": 2, "human_approval": "on_write", **extra}
    return await _post(client, f"{AG}/agents", body)


async def _caps(client) -> dict[str, str]:
    l1 = await _post(client, f"{BIZ}/capabilities", {"name": "Commerce", "level": 1})
    l2 = await _post(
        client, f"{BIZ}/capabilities", {"name": "Checkout", "level": 2, "parent_id": l1["id"]}
    )
    l3 = await _post(
        client,
        f"{BIZ}/capabilities",
        {"name": "Process Payment", "level": 3, "parent_id": l2["id"]},
    )
    return {"l1": l1["id"], "l2": l2["id"], "l3": l3["id"]}


async def _stage(client) -> str:
    vs = await _post(client, f"{BIZ}/value-streams", {"name": "Order to Cash"})
    st = await _post(client, f"{BIZ}/value-streams/{vs['id']}/stages", {"name": "Take Order"})
    return st["id"]


async def _activity(client) -> str:
    ch = await _post(client, f"{BIZ}/value-chains", {"name": "Retail"})
    act = await _post(
        client,
        f"{BIZ}/value-chains/{ch['id']}/activities",
        {"name": "Inbound Logistics", "category": "primary"},
    )
    return act["id"]


async def _control(client, code="Art. 50") -> dict:
    fw = await _post(
        client,
        f"{COMP}/frameworks",
        {"name": f"EU AI Act {code}", "jurisdiction": "EU", "authority": "EU",
         "version": "2024/1689"},
    )
    return await _post(
        client,
        f"{COMP}/frameworks/{fw['id']}/controls",
        {"code": code, "title": "Transparency", "description": "d"},
    )


# ── US1: automates links ──────────────────────────────────────────────────────


async def test_capability_link_round_trip(client, caplog):
    ag = await _agent(client)
    caps = await _caps(client)
    caplog.set_level(logging.INFO, logger="adp.agentic.router")
    resp = await client.post(
        f"{AG}/agents/{ag['id']}/automates/capabilities", json={"capability_id": caps["l3"]}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["capabilities"] == [
        {"id": caps["l3"], "name": "Process Payment", "level": 3,
         "path": ["Commerce", "Checkout"]}
    ]
    assert body["stages"] == [] and body["activities"] == []
    assert "agentic.automates.create" in caplog.text and "kind=capability" in caplog.text

    assert (await client.get(f"{AG}/agents/{ag['id']}/automates")).json() == body
    rev = (await client.get(f"{AG}/capabilities/{caps['l3']}/agents")).json()
    assert rev["total"] == 1 and rev["items"][0]["id"] == ag["id"]
    assert rev["items"][0]["agentic_risk"]["band"] == "medium"

    resp = await client.delete(f"{AG}/agents/{ag['id']}/automates/capabilities/{caps['l3']}")
    assert resp.status_code == 204
    assert "agentic.automates.delete" in caplog.text
    resp = await client.delete(f"{AG}/agents/{ag['id']}/automates/capabilities/{caps['l3']}")
    assert resp.status_code == 404


async def test_capability_link_errors(client):
    ag = await _agent(client)
    caps = await _caps(client)
    url = f"{AG}/agents/{ag['id']}/automates/capabilities"
    resp = await client.post(url, json={"capability_id": caps["l2"]})
    assert resp.status_code == 422
    assert "L3 only" in resp.json()["detail"]
    assert (await client.post(url, json={"capability_id": "nope"})).status_code == 404
    bad_agent = f"{AG}/agents/nope/automates/capabilities"
    assert (await client.post(bad_agent, json={"capability_id": caps["l3"]})).status_code == 404
    assert (await client.post(url, json={"capability_id": caps["l3"]})).status_code == 201
    assert (await client.post(url, json={"capability_id": caps["l3"]})).status_code == 409
    extra = {"capability_id": caps["l3"], "x": 1}
    assert (await client.post(url, json=extra)).status_code == 422
    assert (await client.get(f"{AG}/agents/nope/automates")).status_code == 404
    assert (await client.get(f"{AG}/capabilities/nope/agents")).status_code == 404


async def test_stage_and_activity_links(client):
    ag = await _agent(client)
    stage_id = await _stage(client)
    activity_id = await _activity(client)
    base = f"{AG}/agents/{ag['id']}/automates"
    resp = await client.post(f"{base}/stages", json={"stage_id": stage_id})
    assert resp.status_code == 201, resp.text
    assert resp.json()["stages"][0]["value_stream_name"] == "Order to Cash"
    resp = await client.post(f"{base}/activities", json={"activity_id": activity_id})
    assert resp.status_code == 201, resp.text
    act = resp.json()["activities"][0]
    assert (act["category"], act["value_chain_name"]) == ("primary", "Retail")

    assert (await client.get(f"{AG}/value-stream-stages/{stage_id}/agents")).json()["total"] == 1
    url = f"{AG}/value-chain-activities/{activity_id}/agents"
    assert (await client.get(url)).json()["total"] == 1
    assert (await client.post(f"{base}/stages", json={"stage_id": stage_id})).status_code == 409
    assert (await client.post(f"{base}/stages", json={"stage_id": "nope"})).status_code == 404
    assert (await client.get(f"{AG}/value-stream-stages/nope/agents")).status_code == 404
    assert (await client.get(f"{AG}/value-chain-activities/nope/agents")).status_code == 404
    assert (await client.delete(f"{base}/stages/{stage_id}")).status_code == 204
    assert (await client.delete(f"{base}/activities/{activity_id}")).status_code == 204


async def test_reviewer_cannot_write_links(app_and_client):
    app, client = app_and_client
    ag = await _agent(client)
    caps = await _caps(client)
    _as_role(app, PersonaRole.REVIEWER)
    url = f"{AG}/agents/{ag['id']}/automates/capabilities"
    assert (await client.post(url, json={"capability_id": caps["l3"]})).status_code == 403
    assert (await client.delete(f"{url}/{caps['l3']}")).status_code == 403
    # Reads stay open.
    assert (await client.get(f"{AG}/agents/{ag['id']}/automates")).status_code == 200


# ── US2: agent compliance mappings ────────────────────────────────────────────


async def test_agent_mapping_round_trip(client):
    ag = await _agent(client)
    c1 = await _control(client, "Art. 50")
    c2 = await _control(client, "Art. 13")
    url = f"{COMP}/controls/{c1['id']}/mappings/agents/{ag['id']}"
    resp = await client.put(url, json={"compliance_status": "compliant", "evidence_ref": "E-1"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["target_type"] == "agent" and resp.json()["target_id"] == ag["id"]
    resp = await client.put(
        f"{COMP}/controls/{c2['id']}/mappings/agents/{ag['id']}",
        json={"compliance_status": "non_compliant"},
    )
    assert resp.status_code == 200

    body = (await client.get(f"{COMP}/agents/{ag['id']}/mappings")).json()
    assert body["total"] == 2 and body["status"] == "non_compliant"
    ctrl = (await client.get(f"{COMP}/controls/{c1['id']}/mappings")).json()
    assert [m["target_type"] for m in ctrl["items"]] == ["agent"]

    other = await _agent(client, "Spare")
    resp = await client.get(f"{COMP}/agents/statuses", params={"ids": f"{ag['id']},{other['id']}"})
    assert resp.status_code == 200
    assert resp.json()["items"] == [
        {"agent_id": ag["id"], "status": "non_compliant"},
        {"agent_id": other["id"], "status": "not_assessed"},
    ]

    assert (await client.delete(url)).status_code == 204
    assert (await client.delete(url)).status_code == 404


async def test_agent_mapping_errors(client):
    ag = await _agent(client)
    c1 = await _control(client)
    bad_agent = f"{COMP}/controls/{c1['id']}/mappings/agents/nope"
    assert (await client.put(bad_agent, json={"compliance_status": "compliant"})).status_code == 404
    bad_control = f"{COMP}/controls/nope/mappings/agents/{ag['id']}"
    resp = await client.put(bad_control, json={"compliance_status": "compliant"})
    assert resp.status_code == 404
    assert (await client.get(f"{COMP}/agents/nope/mappings")).status_code == 404
    too_many = ",".join(f"a{i}" for i in range(201))
    resp = await client.get(f"{COMP}/agents/statuses", params={"ids": too_many})
    assert resp.status_code == 422


async def test_agent_mappings_visible_without_governance_read(app_and_client):
    """Agents are not Applications: READ_APPLICATION_GOVERNANCE filtering never hides them."""
    app, client = app_and_client
    ag = await _agent(client)
    c1 = await _control(client)
    await client.put(
        f"{COMP}/controls/{c1['id']}/mappings/agents/{ag['id']}",
        json={"compliance_status": "partial"},
    )
    _as_role(app, PersonaRole.REVIEWER)
    ctrl = (await client.get(f"{COMP}/controls/{c1['id']}/mappings")).json()
    assert [m["target_type"] for m in ctrl["items"]] == ["agent"]
    url = f"{COMP}/controls/{c1['id']}/mappings/agents/{ag['id']}"
    assert (await client.put(url, json={"compliance_status": "compliant"})).status_code == 403
    assert (await client.delete(url)).status_code == 403


# ── US3: agentic risk ─────────────────────────────────────────────────────────


async def test_agentic_risk_on_agent_reads(client):
    ag = await _agent(client, autonomy_level=4, human_approval="none")
    risk = ag["agentic_risk"]
    assert risk["band"] == "high"
    assert [f["code"] for f in risk["factors"]] == ["autonomy", "no_human_approval"]
    assert risk["missing"] == ["data_classification"]
    assert risk["not_considered"] == ["tool_side_effects"]
    listed = (await client.get(f"{AG}/agents")).json()["items"][0]
    assert listed["agentic_risk"]["band"] == "high"
    detail = (await client.get(f"{AG}/agents/{ag['id']}")).json()
    assert detail["agentic_risk"] == risk
    patched = await client.patch(
        f"{AG}/agents/{ag['id']}",
        json={"human_approval": "always", "data_classification_max": "internal"},
    )
    assert patched.json()["agentic_risk"]["band"] == "medium"


async def test_solution_risk_follows_agents(client):
    app = await _post(
        client, "/api/v1/applications", {"name": "Claims", "application_type": "agentic"}
    )
    url = f"{AG}/solutions/{app['id']}/agents"
    empty = (await client.get(url)).json()["solution_risk"]
    assert empty["band"] is None and empty["agents"] == []

    low = await _agent(client, "Lookup", autonomy_level=1, human_approval="always")
    high = await _agent(client, "Payer", autonomy_level=4, human_approval="none")
    for a in (low, high):
        resp = await client.post(url, json={"agent_id": a["id"], "role": "worker"})
        assert resp.status_code == 201, resp.text
    risk = (await client.get(url)).json()["solution_risk"]
    assert risk["band"] == "high"
    assert risk["agents"] == [{"id": high["id"], "name": "Payer"}]

    # Retiring the high agent drops the band, with nothing stored to refresh.
    await client.patch(f"{AG}/agents/{high['id']}", json={"lifecycle_status": "retired"})
    risk = (await client.get(url)).json()["solution_risk"]
    assert risk["band"] == "low" and [a["name"] for a in risk["agents"]] == ["Lookup"]
