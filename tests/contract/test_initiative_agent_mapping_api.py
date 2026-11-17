"""Contract tests for ADP-321: initiative linkage for agent compliance mappings.

The real app against one SQLite file shared by five stores. Owners create their tables before any
module that only mirrors them (create_all's checkfirst then skips the narrow mirror): bstore ->
astore (minus its solution_agents / regulatory_frameworks mirrors) -> agstore -> cstore (owns
control_agent_mapping) -> sstore (initiatives, plus its mirrors of everything above).
"""

from __future__ import annotations

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.agentic import store as agstore
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole
from adp.compliance import store as cstore
from adp.strategy import initiatives as _sinit  # noqa: F401 -- registers the link tables
from adp.strategy import store as sstore

AG = "/api/v1/agentic"
COMP = "/api/v1/compliance"
STRAT = "/api/v1/strategy"


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

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/initiative_agent.db")

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
        sstore._metadata.create_all(sync_conn)
        sync_conn.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_icagm ON initiative_control_agent_mapping"
                "(initiative_id, control_id, agent_id)"
            )
        )

    async with engine.begin() as conn:
        await conn.run_sync(_create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    for module in (bstore, astore, agstore, cstore, sstore):
        monkeypatch.setattr(module, "_engine", engine)
        monkeypatch.setattr(module, "_session_factory", factory)

    from adp.api.app import create_app

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield app, c
    await engine.dispose()


async def _post(client, url, body) -> dict:
    resp = await client.post(url, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _setup(client) -> tuple[str, str, str]:
    ag = await _post(
        client, f"{AG}/agents", {"name": "Triage", "autonomy_level": 2, "human_approval": "none"}
    )
    fw = await _post(
        client,
        f"{COMP}/frameworks",
        {"name": "EU AI Act", "jurisdiction": "EU", "authority": "EU", "version": "2024/1689"},
    )
    ct = await _post(
        client,
        f"{COMP}/frameworks/{fw['id']}/controls",
        {"code": "Art. 50", "title": "Transparency", "description": "d"},
    )
    ini = await _post(client, f"{STRAT}/initiatives", {"name": "Disclose AI use"})
    return ag["id"], ct["id"], ini["id"]


@pytest.fixture()
async def client(app_and_client):
    return app_and_client[1]


async def test_link_list_and_unlink(client):
    ag, ct, ini = await _setup(client)
    link = f"{STRAT}/initiatives/{ini}/control-mappings/agents/{ct}/{ag}"

    # No mapping assessed yet: an initiative links to an existing mapping only.
    assert (await client.post(link)).status_code == 404

    resp = await client.put(
        f"{COMP}/controls/{ct}/mappings/agents/{ag}", json={"compliance_status": "non_compliant"}
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(link)
    assert resp.status_code == 201, resp.text
    [ref] = resp.json()["control_mappings"]
    assert (ref["target_type"], ref["target_id"], ref["compliance_status"]) == (
        "agent", ag, "non_compliant",
    )
    assert (await client.post(link)).status_code == 409

    # Status is read live through the link.
    await client.put(
        f"{COMP}/controls/{ct}/mappings/agents/{ag}", json={"compliance_status": "compliant"}
    )
    got = (await client.get(f"{STRAT}/initiatives/{ini}")).json()
    assert got["control_mappings"][0]["compliance_status"] == "compliant"

    reverse = await client.get(f"{COMP}/controls/{ct}/mappings/agents/{ag}/initiatives")
    assert reverse.status_code == 200
    assert [i["id"] for i in reverse.json()["items"]] == [ini]
    missing = await client.get(f"{COMP}/controls/nope/mappings/agents/{ag}/initiatives")
    assert missing.status_code == 404

    assert (await client.delete(link)).status_code == 204
    assert (await client.delete(link)).status_code == 404
    reverse = await client.get(f"{COMP}/controls/{ct}/mappings/agents/{ag}/initiatives")
    assert reverse.json()["items"] == []


async def test_unknown_initiative(client):
    ag, ct, _ = await _setup(client)
    await client.put(
        f"{COMP}/controls/{ct}/mappings/agents/{ag}", json={"compliance_status": "partial"}
    )
    resp = await client.post(f"{STRAT}/initiatives/nope/control-mappings/agents/{ct}/{ag}")
    assert resp.status_code == 404


async def test_reverse_lookup_not_governance_gated(app_and_client):
    """Like the agent mapping itself, the reverse lookup is not hidden behind
    READ_APPLICATION_GOVERNANCE; writes still need WRITE_BUSINESS_ARCH."""
    app, client = app_and_client
    ag, ct, ini = await _setup(client)
    await client.put(
        f"{COMP}/controls/{ct}/mappings/agents/{ag}", json={"compliance_status": "partial"}
    )
    link = f"{STRAT}/initiatives/{ini}/control-mappings/agents/{ct}/{ag}"
    assert (await client.post(link)).status_code == 201
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="u", username="u", email="u@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    reverse = await client.get(f"{COMP}/controls/{ct}/mappings/agents/{ag}/initiatives")
    assert reverse.status_code == 200 and len(reverse.json()["items"]) == 1
    assert (await client.delete(link)).status_code == 403
