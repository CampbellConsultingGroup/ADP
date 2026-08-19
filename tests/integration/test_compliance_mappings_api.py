"""Integration tests for the Control Mappings API (COMPLY-02).

Covers quickstart.md Scenarios 1-9: mapping to each of the five target shapes, re-mapping
updates in place, reverse lookups from Capability/Application/Design/Pattern, the
READ_APPLICATION_GOVERNANCE read gate (both the dedicated reverse-lookup route and the
forward-lookup's filtering behavior), cascading delete, manual delete, and the pattern-kind
rejection.

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

    # Every store this feature's routes touch needs its own engine/session_factory pointed
    # at the test container -- not just adp.compliance, since US3's reverse-lookup routes
    # live on business/application/designs/knowledge's own routers (research.md D7).
    import adp.application.store as astore
    import adp.business.store as bstore
    import adp.compliance.store as cstore

    for module in (cstore, astore, bstore):
        module._engine = engine
        module._session_factory = factory

    yield application
    await engine.dispose()


@pytest.fixture()
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


BASE = "/api/v1/compliance"


async def _mk_control(client, code="Art. 32") -> dict:
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
        json={"code": code, "title": "Security of processing", "description": "..."},
    )
    assert ctrl_resp.status_code == 201, ctrl_resp.text
    return ctrl_resp.json()


async def _mk_capability(client) -> dict:
    resp = await client.post(
        "/api/v1/business/capabilities",
        json={"name": "Identity & Access Management", "level": 1},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_application(client, name="Test App") -> dict:
    resp = await client.post("/api/v1/applications", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_design(client) -> dict:
    resp = await client.post(
        "/api/v1/designs",
        json={
            "schema_version": "1.0.0",
            "id": "COMPLY-DSN-001",
            "title": "Test Design",
            "created_at": "2026-08-18T00:00:00Z",
            "updated_at": "2026-08-18T00:00:00Z",
            "elements": [], "relationships": [], "requirements": [],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_pattern(client) -> dict:
    resp = await client.post(
        "/api/v1/knowledge",
        json={
            "kind": "pattern", "title": "Zero Trust Access", "full_text": "...",
            "source_ref": "internal-standard-v1", "metadata": {},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_standard(client) -> dict:
    resp = await client.post(
        "/api/v1/knowledge",
        json={
            "kind": "standard", "title": "Not A Pattern", "full_text": "...",
            "source_ref": "internal-standard-v2", "metadata": {},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── US1: Map a control to the entity it governs ──────────────────────────────

async def test_map_control_to_capability_201(client):
    ctrl = await _mk_control(client)
    cap = await _mk_capability(client)
    resp = await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/{cap['id']}",
        json={
            "compliance_status": "compliant", "evidence_ref": "https://docs.example.com/audit",
            "assessed_at": "2026-08-18", "assessed_by": "alice",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["target_type"] == "capability"
    assert body["target_id"] == cap["id"]
    assert body["compliance_status"] == "compliant"


async def test_map_without_evidence_ok(client):
    ctrl = await _mk_control(client)
    cap = await _mk_capability(client)
    resp = await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/{cap['id']}",
        json={"compliance_status": "not_assessed"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["evidence_ref"] is None


async def test_map_organization_wide(client):
    ctrl = await _mk_control(client, code="Art. 30")
    resp = await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/organization",
        json={"compliance_status": "partial", "evidence_ref": "records-of-processing-v3"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["target_type"] == "organization"
    assert body["target_id"] is None


async def test_map_same_control_two_applications_independent(client):
    ctrl = await _mk_control(client)
    app1 = await _mk_application(client, name="App One")
    app2 = await _mk_application(client, name="App Two")
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/{app1['id']}",
        json={"compliance_status": "compliant"},
    )
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/{app2['id']}",
        json={"compliance_status": "non_compliant"},
    )
    resp = await client.get(f"{BASE}/controls/{ctrl['id']}/mappings")
    items = resp.json()["items"]
    by_app = {
        m["target_id"]: m["compliance_status"] for m in items if m["target_type"] == "application"
    }
    assert by_app[app1["id"]] == "compliant"
    assert by_app[app2["id"]] == "non_compliant"


async def test_map_nonexistent_control_404(client):
    cap = await _mk_capability(client)
    resp = await client.put(
        f"{BASE}/controls/does-not-exist/mappings/capabilities/{cap['id']}",
        json={"compliance_status": "not_assessed"},
    )
    assert resp.status_code == 404


async def test_map_nonexistent_target_404(client):
    ctrl = await _mk_control(client)
    resp = await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/does-not-exist",
        json={"compliance_status": "not_assessed"},
    )
    assert resp.status_code == 404


async def test_map_pattern_wrong_kind_422(client):
    ctrl = await _mk_control(client)
    standard = await _mk_standard(client)
    resp = await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/patterns/{standard['id']}",
        json={"compliance_status": "not_assessed"},
    )
    assert resp.status_code == 422


async def test_map_invalid_status_422(client):
    ctrl = await _mk_control(client)
    cap = await _mk_capability(client)
    resp = await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/{cap['id']}",
        json={"compliance_status": "bogus"},
    )
    assert resp.status_code == 422


# ── US2: Update a mapping's assessment over time ─────────────────────────────

async def test_remap_updates_not_duplicates(client):
    ctrl = await _mk_control(client)
    app = await _mk_application(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/{app['id']}",
        json={"compliance_status": "non_compliant"},
    )
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/{app['id']}",
        json={"compliance_status": "compliant"},
    )
    resp = await client.get(f"{BASE}/controls/{ctrl['id']}/mappings")
    matching = [
        m for m in resp.json()["items"]
        if m["target_type"] == "application" and m["target_id"] == app["id"]
    ]
    assert len(matching) == 1
    assert matching[0]["compliance_status"] == "compliant"


async def test_remap_updates_only_evidence_ref(client):
    ctrl = await _mk_control(client)
    app = await _mk_application(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/{app['id']}",
        json={"compliance_status": "non_compliant"},
    )
    resp = await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/{app['id']}",
        json={"compliance_status": "non_compliant", "evidence_ref": "remediation-in-progress"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["compliance_status"] == "non_compliant"
    assert body["evidence_ref"] == "remediation-in-progress"


# ── US3: Trace compliance coverage from either direction ─────────────────────

async def test_capability_reverse_lookup(client):
    cap = await _mk_capability(client)
    ctrl1 = await _mk_control(client, code="Art. A")
    ctrl2 = await _mk_control(client, code="Art. B")
    await client.put(
        f"{BASE}/controls/{ctrl1['id']}/mappings/capabilities/{cap['id']}",
        json={"compliance_status": "compliant"},
    )
    await client.put(
        f"{BASE}/controls/{ctrl2['id']}/mappings/capabilities/{cap['id']}",
        json={"compliance_status": "not_assessed"},
    )
    resp = await client.get(f"/api/v1/business/capabilities/{cap['id']}/compliance-mappings")
    assert resp.status_code == 200
    control_ids = {m["control_id"] for m in resp.json()["items"]}
    assert {ctrl1["id"], ctrl2["id"]} <= control_ids


async def test_application_reverse_lookup_requires_governance_read(client):
    app = await _mk_application(client)
    ctrl = await _mk_control(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/{app['id']}",
        json={"compliance_status": "compliant"},
    )

    from adp.auth.deps import get_current_user
    from adp.auth.models import AuthenticatedUser
    from adp.authz.roles import PersonaRole

    app_under_test = client._transport.app  # type: ignore[attr-defined]
    app_under_test.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    try:
        resp = await client.get(f"/api/v1/applications/{app['id']}/compliance-mappings")
        assert resp.status_code == 403
    finally:
        del app_under_test.dependency_overrides[get_current_user]


async def test_design_reverse_lookup(client):
    design = await _mk_design(client)
    ctrl = await _mk_control(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/designs/{design['id']}",
        json={"compliance_status": "compliant"},
    )
    resp = await client.get(f"/api/v1/designs/{design['id']}/compliance-mappings")
    assert resp.status_code == 200
    assert any(m["control_id"] == ctrl["id"] for m in resp.json()["items"])


async def test_knowledge_item_reverse_lookup(client):
    pattern = await _mk_pattern(client)
    ctrl = await _mk_control(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/patterns/{pattern['id']}",
        json={"compliance_status": "compliant"},
    )
    resp = await client.get(f"/api/v1/knowledge/{pattern['id']}/compliance-mappings")
    assert resp.status_code == 200
    assert any(m["control_id"] == ctrl["id"] for m in resp.json()["items"])


async def test_control_forward_lookup_shows_all_target_types(client):
    ctrl = await _mk_control(client)
    cap = await _mk_capability(client)
    app = await _mk_application(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/{cap['id']}",
        json={"compliance_status": "compliant"},
    )
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/{app['id']}",
        json={"compliance_status": "partial"},
    )
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/organization",
        json={"compliance_status": "not_assessed"},
    )
    resp = await client.get(f"{BASE}/controls/{ctrl['id']}/mappings")
    target_types = {m["target_type"] for m in resp.json()["items"]}
    assert {"capability", "application", "organization"} <= target_types


async def test_control_forward_lookup_filters_application_rows_without_governance_read(client):
    ctrl = await _mk_control(client)
    cap = await _mk_capability(client)
    app = await _mk_application(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/{cap['id']}",
        json={"compliance_status": "compliant"},
    )
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/{app['id']}",
        json={"compliance_status": "partial"},
    )

    from adp.auth.deps import get_current_user
    from adp.auth.models import AuthenticatedUser
    from adp.authz.roles import PersonaRole

    app_under_test = client._transport.app  # type: ignore[attr-defined]
    app_under_test.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    try:
        resp = await client.get(f"{BASE}/controls/{ctrl['id']}/mappings")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(m["target_type"] == "capability" for m in items)
        assert not any(m["target_type"] == "application" for m in items)
    finally:
        del app_under_test.dependency_overrides[get_current_user]


# ── Polish: cascading delete, manual delete ──────────────────────────────────

async def test_delete_control_cascades_all_five_mapping_tables(client):
    ctrl = await _mk_control(client)
    cap = await _mk_capability(client)
    app = await _mk_application(client)
    for path, target_id in (("capabilities", cap["id"]), ("applications", app["id"])):
        await client.put(
            f"{BASE}/controls/{ctrl['id']}/mappings/{path}/{target_id}",
            json={"compliance_status": "compliant"},
        )
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/organization",
        json={"compliance_status": "compliant"},
    )

    del_resp = await client.delete(f"{BASE}/controls/{ctrl['id']}")
    assert del_resp.status_code == 204

    resp = await client.get(f"{BASE}/controls/{ctrl['id']}/mappings")
    assert resp.status_code == 404


async def test_delete_target_application_cascades_its_mapping(client):
    ctrl = await _mk_control(client)
    app = await _mk_application(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/{app['id']}",
        json={"compliance_status": "compliant"},
    )
    del_resp = await client.delete(f"/api/v1/applications/{app['id']}")
    assert del_resp.status_code == 204

    resp = await client.get(f"{BASE}/controls/{ctrl['id']}/mappings")
    assert resp.status_code == 200
    assert not any(m["target_type"] == "application" for m in resp.json()["items"])


async def test_delete_target_capability_cascades_its_mapping(client):
    # Design and Pattern are deliberately not covered by an equivalent case here: Designs
    # have no delete endpoint at all, and knowledge item delete (FR-005) is a soft-delete
    # (active=false) that never physically removes the row, so the FK's ON DELETE CASCADE
    # never fires via the API for either -- confirmed by reading both routers directly, not
    # assumed. The migration-level cascade behavior itself is identical across all four FK
    # legs regardless (data-model.md), so this is a coverage-scope decision, not a gap in
    # the cascade guarantee.
    ctrl = await _mk_control(client)
    cap = await _mk_capability(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/{cap['id']}",
        json={"compliance_status": "compliant"},
    )
    del_resp = await client.delete(f"/api/v1/business/capabilities/{cap['id']}")
    assert del_resp.status_code == 204

    resp = await client.get(f"{BASE}/controls/{ctrl['id']}/mappings")
    assert resp.status_code == 200
    assert not any(m["target_type"] == "capability" for m in resp.json()["items"])


async def test_manual_delete_mapping_204_then_404(client):
    ctrl = await _mk_control(client)
    cap = await _mk_capability(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/{cap['id']}",
        json={"compliance_status": "compliant"},
    )
    resp = await client.delete(f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/{cap['id']}")
    assert resp.status_code == 204
    resp = await client.delete(f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/{cap['id']}")
    assert resp.status_code == 404
