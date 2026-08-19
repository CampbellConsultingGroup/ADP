"""Contract tests for the Strategy Domain Linkage API (925-strategy-compliance-linkage, COMPLY-05).

Full-stack against the real app on a single in-memory SQLite database, mirroring
tests/contract/test_strategy_api_contract.py's own fixture convention. Unlike that file, only
ONE database is needed here (not a second business-scoped one): every route this feature adds --
both the Initiative-side link/unlink routes (adp.strategy.router) and the reverse-lookup routes
(adp.compliance.router) -- reads/writes exclusively through adp.strategy.store's own read-only
compliance-schema mirrors (research.md D2/D3), never touching adp.compliance.store's real tables
at all. `srouter._get_session` and `crouter._get_strategy_session` are both overridden to the same
session factory so both routers see the same mirror-table rows.
"""

from __future__ import annotations

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.compliance import router as crouter
from adp.strategy import router as srouter
from adp.strategy import store as sstore
from adp.strategy.initiatives import StrategyInitiative

_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_theme_name ON strategic_themes(name)",
    "CREATE UNIQUE INDEX uq_iccm "
    "ON initiative_control_capability_mapping(initiative_id, control_id, capability_id)",
    "CREATE UNIQUE INDEX uq_icam "
    "ON initiative_control_application_mapping(initiative_id, control_id, application_id)",
    "CREATE UNIQUE INDEX uq_ocl ON objective_control_links(objective_id, control_id)",
]


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/strategy_compliance_links.db")
    async with engine.begin() as conn:
        await conn.run_sync(sstore._metadata.create_all)
        for ddl in _UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
        # Seed one Control + one assessed ControlMapping (application-targeted), standing in for
        # real COMPLY-01/02 writes -- this fixture never mounts adp.compliance's own router.
        await conn.execute(
            sstore._controls_mirror.insert().values(
                id="CTRL-1", code="AC-2", title="Account Management", framework_id="FW-1"
            )
        )
        await conn.execute(
            sstore._control_application_mapping_mirror.insert().values(
                control_id="CTRL-1", application_id="APP-1", compliance_status="non_compliant",
                evidence_ref=None, assessed_at=None,
            )
        )
        # A second Control with no ControlMapping at all, for the Objective-Control link tests
        # (925-strategy-compliance-linkage US2) -- unlike US1's InitiativeControlMapping, an
        # ObjectiveControlMapping targets the abstract Control, not one of its assessed mappings.
        await conn.execute(
            sstore._controls_mirror.insert().values(
                id="CTRL-2", code="Art. 32", title="Security of processing", framework_id="FW-1"
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[srouter._get_session] = _override
    app.dependency_overrides[crouter._get_strategy_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


BASE = "/api/v1/strategy"
COMPLIANCE_BASE = "/api/v1/compliance"


async def _mk_initiative(client, name: str = "Remediate MFA gap") -> str:
    resp = await client.post(f"{BASE}/initiatives", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _mk_objective(client, statement: str = "GDPR Art. 32 readiness") -> str:
    theme_resp = await client.post(f"{BASE}/themes", json={"name": f"Theme for {statement}"})
    assert theme_resp.status_code == 201, theme_resp.text
    theme_id = theme_resp.json()["id"]
    resp = await client.post(
        f"{BASE}/objectives",
        json={
            "theme_id": theme_id, "owner": "Owner", "statement": statement,
            "fiscal_year": 2026, "period": "Q1",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_link_initiative_to_control_mapping_returns_full_initiative(client):
    initiative_id = await _mk_initiative(client)
    resp = await client.post(
        f"{BASE}/initiatives/{initiative_id}/control-mappings/applications/CTRL-1/APP-1"
    )
    assert resp.status_code == 201, resp.text
    initiative = StrategyInitiative.model_validate(resp.json())
    assert initiative.id == initiative_id
    assert len(initiative.control_mappings) == 1
    ref = initiative.control_mappings[0]
    assert ref.control_id == "CTRL-1"
    assert ref.target_type == "application"
    assert ref.target_id == "APP-1"
    assert ref.compliance_status == "non_compliant"


async def test_link_duplicate_returns_409(client):
    initiative_id = await _mk_initiative(client)
    first = await client.post(
        f"{BASE}/initiatives/{initiative_id}/control-mappings/applications/CTRL-1/APP-1"
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        f"{BASE}/initiatives/{initiative_id}/control-mappings/applications/CTRL-1/APP-1"
    )
    assert second.status_code == 409, second.text


async def test_link_to_nonexistent_control_mapping_returns_404(client):
    initiative_id = await _mk_initiative(client)
    resp = await client.post(
        f"{BASE}/initiatives/{initiative_id}/control-mappings/applications/CTRL-1/does-not-exist"
    )
    assert resp.status_code == 404, resp.text


async def test_link_to_nonexistent_initiative_returns_404(client):
    resp = await client.post(
        f"{BASE}/initiatives/does-not-exist/control-mappings/applications/CTRL-1/APP-1"
    )
    assert resp.status_code == 404, resp.text


async def test_unlink_then_repeat_returns_404(client):
    initiative_id = await _mk_initiative(client)
    link = await client.post(
        f"{BASE}/initiatives/{initiative_id}/control-mappings/applications/CTRL-1/APP-1"
    )
    assert link.status_code == 201, link.text

    unlink = await client.delete(
        f"{BASE}/initiatives/{initiative_id}/control-mappings/applications/CTRL-1/APP-1"
    )
    assert unlink.status_code == 204, unlink.text

    repeat = await client.delete(
        f"{BASE}/initiatives/{initiative_id}/control-mappings/applications/CTRL-1/APP-1"
    )
    assert repeat.status_code == 404, repeat.text


async def test_reverse_lookup_shows_linked_initiative(client):
    initiative_id = await _mk_initiative(client)
    link = await client.post(
        f"{BASE}/initiatives/{initiative_id}/control-mappings/applications/CTRL-1/APP-1"
    )
    assert link.status_code == 201, link.text

    resp = await client.get(
        f"{COMPLIANCE_BASE}/controls/CTRL-1/mappings/applications/APP-1/initiatives"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == initiative_id


async def test_reverse_lookup_unknown_control_returns_404(client):
    resp = await client.get(
        f"{COMPLIANCE_BASE}/controls/does-not-exist/mappings/applications/APP-1/initiatives"
    )
    assert resp.status_code == 404, resp.text


# ── User Story 2: Objective <-> Control (why an objective exists) ───────────────────────────────


async def test_link_objective_to_control_returns_updated_control_ids(client):
    objective_id = await _mk_objective(client)
    resp = await client.post(
        f"{BASE}/objectives/{objective_id}/controls", json={"control_id": "CTRL-2"}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json() == ["CTRL-2"]


async def test_link_objective_to_two_controls_both_coexist(client):
    objective_id = await _mk_objective(client)
    first = await client.post(
        f"{BASE}/objectives/{objective_id}/controls", json={"control_id": "CTRL-1"}
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        f"{BASE}/objectives/{objective_id}/controls", json={"control_id": "CTRL-2"}
    )
    assert second.status_code == 201, second.text
    assert set(second.json()) == {"CTRL-1", "CTRL-2"}


async def test_link_duplicate_returns_409_objective_control(client):
    objective_id = await _mk_objective(client)
    first = await client.post(
        f"{BASE}/objectives/{objective_id}/controls", json={"control_id": "CTRL-2"}
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        f"{BASE}/objectives/{objective_id}/controls", json={"control_id": "CTRL-2"}
    )
    assert second.status_code == 409, second.text


async def test_link_unknown_objective_returns_404(client):
    resp = await client.post(
        f"{BASE}/objectives/does-not-exist/controls", json={"control_id": "CTRL-2"}
    )
    assert resp.status_code == 404, resp.text


async def test_link_unknown_control_returns_404(client):
    objective_id = await _mk_objective(client)
    resp = await client.post(
        f"{BASE}/objectives/{objective_id}/controls", json={"control_id": "does-not-exist"}
    )
    assert resp.status_code == 404, resp.text


async def test_unlink_then_repeat_returns_404_objective_control(client):
    objective_id = await _mk_objective(client)
    link = await client.post(
        f"{BASE}/objectives/{objective_id}/controls", json={"control_id": "CTRL-2"}
    )
    assert link.status_code == 201, link.text

    unlink = await client.delete(f"{BASE}/objectives/{objective_id}/controls/CTRL-2")
    assert unlink.status_code == 204, unlink.text

    repeat = await client.delete(f"{BASE}/objectives/{objective_id}/controls/CTRL-2")
    assert repeat.status_code == 404, repeat.text


async def test_objective_control_reverse_lookup_shows_linked_objective(client):
    objective_id = await _mk_objective(client)
    link = await client.post(
        f"{BASE}/objectives/{objective_id}/controls", json={"control_id": "CTRL-2"}
    )
    assert link.status_code == 201, link.text

    resp = await client.get(f"{COMPLIANCE_BASE}/controls/CTRL-2/objectives")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == objective_id


async def test_objective_control_reverse_lookup_unknown_control_returns_404(client):
    resp = await client.get(f"{COMPLIANCE_BASE}/controls/does-not-exist/objectives")
    assert resp.status_code == 404, resp.text
