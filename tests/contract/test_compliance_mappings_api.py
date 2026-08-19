"""Contract tests for the Control Mappings API (COMPLY-02).

Runs the /api/v1/compliance router full-stack against the real adp.compliance.store on an
in-memory SQLite database, mirroring tests/contract/test_compliance_registry_api.py's fixture
shape. The mapping tables' PKs are declared directly on the store.py Table() objects (unlike
COMPLY-01's UNIQUE(framework_id, code), which lives only in the migration), so create_all()
reproduces them with no extra DDL needed. Target existence is validated against narrow mirror
tables (business_capabilities/applications/designs/knowledge_items) sharing this same in-memory
database and metadata (research.md D4) -- seeded directly here since no real domain router is
mounted in this fixture.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.compliance import router as crouter
from adp.compliance import store as cstore
from adp.compliance.models import ControlMapping, ControlMappingListResponse


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/compliance_mappings.db")
    async with engine.begin() as conn:
        await conn.run_sync(cstore._metadata.create_all)
        # Seed one row per mirror table so upsert/lookup tests have a real target to map to.
        await conn.execute(cstore._capabilities_mirror.insert().values(id="cap-1"))
        await conn.execute(cstore._applications_mirror.insert().values(id="app-1"))
        await conn.execute(cstore._designs_mirror.insert().values(id="design-1"))
        await conn.execute(
            cstore._knowledge_items_mirror.insert().values(id="pattern-1", kind="pattern")
        )
        await conn.execute(
            cstore._knowledge_items_mirror.insert().values(id="standard-1", kind="standard")
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[crouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


BASE = "/api/v1/compliance"


async def _mk_control(client) -> dict:
    fw_resp = await client.post(
        f"{BASE}/frameworks",
        json={
            "name": "GDPR", "jurisdiction": "EU", "authority": "European Commission",
            "version": "2016/679",
        },
    )
    assert fw_resp.status_code == 201, fw_resp.text
    framework_id = fw_resp.json()["id"]
    ctrl_resp = await client.post(
        f"{BASE}/frameworks/{framework_id}/controls",
        json={"code": "Art. 32", "title": "Security of processing", "description": "..."},
    )
    assert ctrl_resp.status_code == 201, ctrl_resp.text
    return ctrl_resp.json()


# ── PUT (upsert) contract shape — one per target shape ──────────────────────

async def test_capability_mapping_upsert_matches_contract(client):
    ctrl = await _mk_control(client)
    resp = await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/cap-1",
        json={"compliance_status": "compliant"},
    )
    assert resp.status_code == 200, resp.text
    mapping = ControlMapping.model_validate(resp.json())
    assert mapping.target_type == "capability"
    assert mapping.target_id == "cap-1"


async def test_application_mapping_upsert_matches_contract(client):
    ctrl = await _mk_control(client)
    resp = await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/app-1",
        json={"compliance_status": "partial", "evidence_ref": "doc-ref"},
    )
    assert resp.status_code == 200, resp.text
    mapping = ControlMapping.model_validate(resp.json())
    assert mapping.target_type == "application"
    assert mapping.target_id == "app-1"


async def test_design_mapping_upsert_matches_contract(client):
    ctrl = await _mk_control(client)
    resp = await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/designs/design-1",
        json={"compliance_status": "not_assessed"},
    )
    assert resp.status_code == 200, resp.text
    mapping = ControlMapping.model_validate(resp.json())
    assert mapping.target_type == "design"
    assert mapping.target_id == "design-1"


async def test_pattern_mapping_upsert_matches_contract(client):
    ctrl = await _mk_control(client)
    resp = await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/patterns/pattern-1",
        json={"compliance_status": "compliant"},
    )
    assert resp.status_code == 200, resp.text
    mapping = ControlMapping.model_validate(resp.json())
    assert mapping.target_type == "pattern"
    assert mapping.target_id == "pattern-1"


async def test_organization_mapping_upsert_matches_contract(client):
    ctrl = await _mk_control(client)
    resp = await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/organization",
        json={"compliance_status": "partial"},
    )
    assert resp.status_code == 200, resp.text
    mapping = ControlMapping.model_validate(resp.json())
    assert mapping.target_type == "organization"
    assert mapping.target_id is None


# ── GET forward lookup contract shape ────────────────────────────────────────

async def test_control_mappings_list_matches_contract(client):
    ctrl = await _mk_control(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/cap-1",
        json={"compliance_status": "compliant"},
    )
    resp = await client.get(f"{BASE}/controls/{ctrl['id']}/mappings")
    assert resp.status_code == 200
    ControlMappingListResponse.model_validate(resp.json())


# ── Write access requires WRITE_COMPLIANCE (already covered by the existing prefix rule,
# but confirmed here at the HTTP boundary rather than assumed) ─────────────────

async def test_mapping_write_without_permission_403(client):
    from adp.api.app import create_app
    from adp.auth.deps import get_current_user
    from adp.auth.models import AuthenticatedUser
    from adp.authz.roles import PersonaRole

    ctrl = await _mk_control(client)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    factory = async_sessionmaker(
        create_async_engine("sqlite+aiosqlite:///:memory:"), expire_on_commit=False
    )
    app.dependency_overrides[crouter._get_session] = lambda: factory()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as reviewer_client:
        resp = await reviewer_client.put(
            f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/cap-1",
            json={"compliance_status": "compliant"},
        )
    assert resp.status_code == 403


# ── Reverse lookups (US3) — a full-stack fixture wiring business/application/compliance
# stores to one shared SQLite file, unlike `client` above (which only ever needed the
# lightweight mirror tables). Design and Pattern reverse lookups are covered instead by the
# Docker-gated integration test (creating a real Design/knowledge item is heavier here) --
# a deliberate scoping call, not an oversight.

@pytest.fixture()
async def full_client(tmp_path):
    import adp.application.store as astore
    import adp.business.store as bstore

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/full.db")
    async with engine.begin() as conn:
        # Real domain schemas first; cstore's mirror tables of the same name are then
        # skipped by create_all()'s default checkfirst=True.
        await conn.run_sync(bstore._metadata.create_all)
        await conn.run_sync(astore._metadata.create_all)
        await conn.run_sync(cstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    for module in (bstore, astore, cstore):
        module._engine = engine
        module._session_factory = factory

    from adp.api.app import create_app

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def test_capability_compliance_mappings_reverse_lookup_matches_contract(full_client):
    cap_resp = await full_client.post(
        "/api/v1/business/capabilities", json={"name": "IAM", "level": 1}
    )
    assert cap_resp.status_code == 201, cap_resp.text
    cap_id = cap_resp.json()["id"]

    ctrl = await _mk_control(full_client)
    await full_client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/{cap_id}",
        json={"compliance_status": "compliant"},
    )
    resp = await full_client.get(f"/api/v1/business/capabilities/{cap_id}/compliance-mappings")
    assert resp.status_code == 200
    ControlMappingListResponse.model_validate(resp.json())


async def test_application_compliance_mappings_reverse_lookup_matches_contract(full_client):
    app_resp = await full_client.post("/api/v1/applications", json={"name": "App"})
    assert app_resp.status_code == 201, app_resp.text
    app_id = app_resp.json()["id"]

    ctrl = await _mk_control(full_client)
    await full_client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/{app_id}",
        json={"compliance_status": "partial"},
    )
    resp = await full_client.get(f"/api/v1/applications/{app_id}/compliance-mappings")
    assert resp.status_code == 200
    ControlMappingListResponse.model_validate(resp.json())


async def test_application_compliance_mappings_requires_governance_read(full_client):
    from adp.auth.deps import get_current_user
    from adp.auth.models import AuthenticatedUser
    from adp.authz.roles import PersonaRole

    app_resp = await full_client.post("/api/v1/applications", json={"name": "App"})
    app_id = app_resp.json()["id"]

    app_under_test = full_client._transport.app  # type: ignore[attr-defined]
    app_under_test.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    try:
        resp = await full_client.get(f"/api/v1/applications/{app_id}/compliance-mappings")
        assert resp.status_code == 403
    finally:
        del app_under_test.dependency_overrides[get_current_user]
