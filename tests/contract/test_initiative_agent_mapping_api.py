"""Contract tests for ADP-321: initiative linkage for agent compliance mappings.

The real app against one SQLite file shared by every store (tests.support.schema.create_schema).
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
from tests.support.schema import create_schema

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
        # ADP-blp.26: one helper creates every store's tables once, each from its widest
        # declaration. This replaced a hand-ordered sequence of create_all calls with mirrors
        # excluded by name (bstore -> astore -> agstore -> cstore -> sstore).
        create_schema(sync_conn)
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


async def test_application_mappings_hidden_without_governance_read(app_and_client):
    """ADP-blp.4: an initiative embeds its linked control mappings. Rows targeting an
    Application carry governance data, so a caller without READ_APPLICATION_GOVERNANCE gets the
    initiative with those rows removed -- on every route that returns an initiative."""
    app, client = app_and_client
    ag, ct, ini = await _setup(client)
    application = await _post(client, "/api/v1/applications", {"name": "Billing"})
    app_id = application["id"]
    for target in (f"agents/{ag}", f"applications/{app_id}"):
        resp = await client.put(
            f"{COMP}/controls/{ct}/mappings/{target}", json={"compliance_status": "non_compliant"}
        )
        assert resp.status_code == 200, resp.text
    for target in (f"agents/{ct}/{ag}", f"applications/{ct}/{app_id}"):
        resp = await client.post(f"{STRAT}/initiatives/{ini}/control-mappings/{target}")
        assert resp.status_code == 201, resp.text

    def _types(initiative: dict) -> set[str]:
        return {m["target_type"] for m in initiative["control_mappings"]}

    # The default caller (Enterprise Architect) sees both.
    assert _types((await client.get(f"{STRAT}/initiatives/{ini}")).json()) == {
        "agent", "application",
    }

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="u", username="u", email="u@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    assert _types((await client.get(f"{STRAT}/initiatives/{ini}")).json()) == {"agent"}
    listed = (await client.get(f"{STRAT}/initiatives")).json()["items"]
    assert [_types(i) for i in listed] == [{"agent"}]
    reverse = await client.get(f"{COMP}/controls/{ct}/mappings/agents/{ag}/initiatives")
    assert [_types(i) for i in reverse.json()["items"]] == [{"agent"}]
    # The application-targeted reverse lookup stays refused outright.
    gated = await client.get(f"{COMP}/controls/{ct}/mappings/applications/{app_id}/initiatives")
    assert gated.status_code == 403


async def test_framework_control_objectives_in_one_request(client):
    """ADP-blp.35: the control tree's "Regulatory driver for" lines, for a whole framework."""
    fw = await _post(
        client,
        f"{COMP}/frameworks",
        {"name": "GDPR", "jurisdiction": "EU", "authority": "EU", "version": "2016/679"},
    )
    controls = [
        await _post(
            client,
            f"{COMP}/frameworks/{fw['id']}/controls",
            {"code": code, "title": code, "description": "d"},
        )
        for code in ("Art. 5", "Art. 33")
    ]
    theme = await _post(client, f"{STRAT}/themes", {"name": "Trust"})
    objective = await _post(
        client,
        f"{STRAT}/objectives",
        {
            "theme_id": theme["id"], "owner": "CISO", "statement": "Cut breach risk",
            "fiscal_year": 2027, "period": "FY",
        },
    )
    resp = await client.post(
        f"{STRAT}/objectives/{objective['id']}/controls", json={"control_id": controls[0]["id"]}
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get(f"{COMP}/frameworks/{fw['id']}/control-objectives")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "items": [
            {
                "control_id": controls[0]["id"],
                "objectives": [{"id": objective["id"], "statement": "Cut breach risk"}],
            }
        ]
    }
    missing = await client.get(f"{COMP}/frameworks/nope/control-objectives")
    assert missing.status_code == 404
