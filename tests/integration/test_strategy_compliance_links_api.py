"""Integration tests for the Strategy Domain Linkage API (925-strategy-compliance-linkage,
COMPLY-05).

Covers quickstart.md's scenarios not already exercised by the SQLite-backed contract test
(tests/contract/test_strategy_compliance_links_api.py): real composite-FK cascade behavior on
Control/ControlMapping/Objective/Initiative delete, and the real reverse lookups against a live
Postgres.

Requires Docker (testcontainers). Skipped automatically when Docker is unavailable.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="session")
async def app(db_url: str, db_engine):
    """FastAPI test app wired to the test database (migrations run via db_engine)."""
    import os

    from adp.api.app import create_app

    os.environ["ADP_DATABASE_URL"] = db_url

    application = create_app()

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # adp.strategy.store's own engine covers every route this feature adds on both routers --
    # adp.strategy.router's _get_session and adp.compliance.router's _get_strategy_session both
    # resolve through sstore._get_session_factory() (research.md D2). adp.compliance.store is
    # also needed here (unlike the SQLite contract test) since these tests create real
    # Frameworks/Controls/ControlMappings through the real compliance API, not seeded mirrors.
    import adp.compliance.store as cstore
    import adp.strategy.store as sstore

    for module in (cstore, sstore):
        module._engine = engine
        module._session_factory = factory

    yield application
    await engine.dispose()


@pytest.fixture()
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


COMPLIANCE = "/api/v1/compliance"
STRATEGY = "/api/v1/strategy"


async def _mk_control(client, code="Art. 32") -> dict:
    fw_resp = await client.post(
        f"{COMPLIANCE}/frameworks",
        json={
            "name": "GDPR", "jurisdiction": "EU", "authority": "European Commission",
            "version": "2016/679",
        },
    )
    assert fw_resp.status_code == 201, fw_resp.text
    framework_id = fw_resp.json()["id"]
    ctrl_resp = await client.post(
        f"{COMPLIANCE}/frameworks/{framework_id}/controls",
        json={"code": code, "title": "Security of processing", "description": "..."},
    )
    assert ctrl_resp.status_code == 201, ctrl_resp.text
    return ctrl_resp.json()


async def _mk_application(client, name="Test App") -> dict:
    resp = await client.post("/api/v1/applications", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_objective(client, statement="GDPR Art. 32 readiness") -> dict:
    theme_resp = await client.post(f"{STRATEGY}/themes", json={"name": f"Theme for {statement}"})
    assert theme_resp.status_code == 201, theme_resp.text
    resp = await client.post(
        f"{STRATEGY}/objectives",
        json={
            "theme_id": theme_resp.json()["id"], "owner": "Owner", "statement": statement,
            "fiscal_year": 2026, "period": "Q1",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_initiative(client, name="Remediate MFA gap") -> dict:
    resp = await client.post(f"{STRATEGY}/initiatives", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_mapping(client, control_id: str, application_id: str, status="non_compliant") -> None:
    resp = await client.put(
        f"{COMPLIANCE}/controls/{control_id}/mappings/applications/{application_id}",
        json={"compliance_status": status},
    )
    assert resp.status_code == 200, resp.text


async def test_link_and_reverse_lookup_round_trip(client):
    """Sanity check against a real Postgres before the cascade tests below: both link types and
    both reverse lookups work end to end (quickstart.md Scenarios 1, 3, 6)."""
    ctrl = await _mk_control(client)
    app = await _mk_application(client)
    await _mk_mapping(client, ctrl["id"], app["id"])
    objective = await _mk_objective(client)
    initiative = await _mk_initiative(client)

    link_obj = await client.post(
        f"{STRATEGY}/objectives/{objective['id']}/controls", json={"control_id": ctrl["id"]}
    )
    assert link_obj.status_code == 201, link_obj.text

    link_init = await client.post(
        f"{STRATEGY}/initiatives/{initiative['id']}/control-mappings/applications/"
        f"{ctrl['id']}/{app['id']}"
    )
    assert link_init.status_code == 201, link_init.text
    assert link_init.json()["control_mappings"][0]["compliance_status"] == "non_compliant"

    reverse_obj = await client.get(f"{COMPLIANCE}/controls/{ctrl['id']}/objectives")
    assert reverse_obj.status_code == 200, reverse_obj.text
    assert reverse_obj.json()["items"][0]["id"] == objective["id"]

    reverse_init = await client.get(
        f"{COMPLIANCE}/controls/{ctrl['id']}/mappings/applications/{app['id']}/initiatives"
    )
    assert reverse_init.status_code == 200, reverse_init.text
    assert reverse_init.json()["items"][0]["id"] == initiative["id"]


async def test_delete_control_cascades_objective_link_and_initiative_mapping_link(client):
    ctrl = await _mk_control(client)
    app = await _mk_application(client)
    await _mk_mapping(client, ctrl["id"], app["id"])
    objective = await _mk_objective(client)
    initiative = await _mk_initiative(client)

    await client.post(
        f"{STRATEGY}/objectives/{objective['id']}/controls", json={"control_id": ctrl["id"]}
    )
    await client.post(
        f"{STRATEGY}/initiatives/{initiative['id']}/control-mappings/applications/"
        f"{ctrl['id']}/{app['id']}"
    )

    del_resp = await client.delete(f"{COMPLIANCE}/controls/{ctrl['id']}")
    assert del_resp.status_code == 204, del_resp.text

    # The link rows are gone (both tables cascade from the same Control delete)...
    reverse_obj = await client.get(f"{COMPLIANCE}/controls/{ctrl['id']}/objectives")
    assert reverse_obj.status_code == 404  # control itself is gone -- 404, not an empty list

    # ...but the Objective and Initiative themselves survive untouched.
    obj_resp = await client.get(f"{STRATEGY}/objectives/{objective['id']}")
    assert obj_resp.status_code == 200
    assert obj_resp.json()["control_ids"] == []

    init_resp = await client.get(f"{STRATEGY}/initiatives/{initiative['id']}")
    assert init_resp.status_code == 200
    assert init_resp.json()["control_mappings"] == []


async def test_delete_control_mapping_cascades_only_its_own_initiative_link(client):
    """Deleting one ControlMapping row (via COMPLY-02's own DELETE mapping endpoint) removes only
    the InitiativeControlMapping referencing that specific (control_id, target) pair -- a sibling
    link on a *different* target for the same Control survives untouched."""
    ctrl = await _mk_control(client)
    app1 = await _mk_application(client, name="App One")
    app2 = await _mk_application(client, name="App Two")
    await _mk_mapping(client, ctrl["id"], app1["id"])
    await _mk_mapping(client, ctrl["id"], app2["id"])
    initiative = await _mk_initiative(client)

    await client.post(
        f"{STRATEGY}/initiatives/{initiative['id']}/control-mappings/applications/"
        f"{ctrl['id']}/{app1['id']}"
    )
    await client.post(
        f"{STRATEGY}/initiatives/{initiative['id']}/control-mappings/applications/"
        f"{ctrl['id']}/{app2['id']}"
    )

    del_resp = await client.delete(
        f"{COMPLIANCE}/controls/{ctrl['id']}/mappings/applications/{app1['id']}"
    )
    assert del_resp.status_code == 204, del_resp.text

    init_resp = await client.get(f"{STRATEGY}/initiatives/{initiative['id']}")
    assert init_resp.status_code == 200
    remaining = init_resp.json()["control_mappings"]
    assert len(remaining) == 1
    assert remaining[0]["target_id"] == app2["id"]


async def test_delete_objective_cascades_its_own_link_only(client):
    ctrl = await _mk_control(client)
    objective = await _mk_objective(client)
    await client.post(
        f"{STRATEGY}/objectives/{objective['id']}/controls", json={"control_id": ctrl["id"]}
    )

    del_resp = await client.delete(f"{STRATEGY}/objectives/{objective['id']}")
    assert del_resp.status_code == 204, del_resp.text

    # The Control and its (now-empty) reverse lookup survive.
    reverse_obj = await client.get(f"{COMPLIANCE}/controls/{ctrl['id']}/objectives")
    assert reverse_obj.status_code == 200
    assert reverse_obj.json()["items"] == []


async def test_delete_initiative_cascades_its_own_link_only(client):
    ctrl = await _mk_control(client)
    app = await _mk_application(client)
    await _mk_mapping(client, ctrl["id"], app["id"])
    initiative = await _mk_initiative(client)
    await client.post(
        f"{STRATEGY}/initiatives/{initiative['id']}/control-mappings/applications/{ctrl['id']}/{app['id']}"
    )

    del_resp = await client.delete(f"{STRATEGY}/initiatives/{initiative['id']}")
    assert del_resp.status_code == 204, del_resp.text

    # The ControlMapping and its (now-empty) reverse lookup survive.
    reverse_init = await client.get(
        f"{COMPLIANCE}/controls/{ctrl['id']}/mappings/applications/{app['id']}/initiatives"
    )
    assert reverse_init.status_code == 200
    assert reverse_init.json()["items"] == []
