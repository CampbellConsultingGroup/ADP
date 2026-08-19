"""Contract tests for Compliance Rollup Reporting (COMPLY-04).

Runs the /api/v1/compliance router full-stack against the real adp.compliance.store on an
in-memory SQLite database, mirroring tests/contract/test_compliance_mappings_api.py's `client`
fixture shape exactly.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.compliance import router as crouter
from adp.compliance import store as cstore
from adp.compliance.models import ComplianceSummaryResponse, FrameworkCoverageRollup


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/compliance_rollup.db")
    async with engine.begin() as conn:
        await conn.run_sync(cstore._metadata.create_all)
        await conn.execute(cstore._capabilities_mirror.insert().values(id="cap-1"))
        await conn.execute(cstore._applications_mirror.insert().values(id="app-1"))
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
    ctrl = ctrl_resp.json()
    ctrl["framework_id"] = framework_id
    return ctrl


# ── GET /frameworks/{id}/rollup (US1) ───────────────────────────────────────


async def test_framework_rollup_matches_contract(client):
    ctrl = await _mk_control(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/capabilities/cap-1",
        json={"compliance_status": "compliant"},
    )
    resp = await client.get(f"{BASE}/frameworks/{ctrl['framework_id']}/rollup")
    assert resp.status_code == 200, resp.text
    rollup = FrameworkCoverageRollup.model_validate(resp.json())
    assert rollup.entity_counts.compliant_count == 1
    assert rollup.organization_status is None


async def test_framework_rollup_404_for_unknown_framework(client):
    resp = await client.get(f"{BASE}/frameworks/does-not-exist/rollup")
    assert resp.status_code == 404


async def test_framework_rollup_excludes_application_for_reviewer(client):
    """FR-007, US1 AS4: never a 403 -- a caller lacking READ_APPLICATION_GOVERNANCE still gets
    200, just with Application-targeted entities excluded from the counts. Contrasts
    deliberately with GET /applications/{id}/compliance-mappings's own route-level-403
    precedent (research.md D2 chose filtering, matching list_control_mappings instead)."""
    from adp.auth.deps import get_current_user
    from adp.auth.models import AuthenticatedUser
    from adp.authz.roles import PersonaRole

    ctrl = await _mk_control(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/app-1",
        json={"compliance_status": "non_compliant"},
    )

    resp_privileged = await client.get(f"{BASE}/frameworks/{ctrl['framework_id']}/rollup")
    assert resp_privileged.json()["entity_counts"]["non_compliant_count"] == 1

    app_under_test = client._transport.app  # type: ignore[attr-defined]
    app_under_test.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    try:
        resp_reviewer = await client.get(f"{BASE}/frameworks/{ctrl['framework_id']}/rollup")
        assert resp_reviewer.status_code == 200
        assert resp_reviewer.json()["entity_counts"]["non_compliant_count"] == 0
    finally:
        del app_under_test.dependency_overrides[get_current_user]


# ── GET /summary (US2) ──────────────────────────────────────────────────────


async def test_compliance_summary_matches_contract(client):
    resp = await client.get(f"{BASE}/summary")
    assert resp.status_code == 200, resp.text
    summary = ComplianceSummaryResponse.model_validate(resp.json())
    assert summary.framework_count == 0
    assert summary.coverage_percent is None
    assert summary.at_risk_count == 0


async def test_compliance_summary_excludes_application_for_reviewer(client):
    from adp.auth.deps import get_current_user
    from adp.auth.models import AuthenticatedUser
    from adp.authz.roles import PersonaRole

    ctrl = await _mk_control(client)
    await client.put(
        f"{BASE}/controls/{ctrl['id']}/mappings/applications/app-1",
        json={"compliance_status": "non_compliant"},
    )

    resp_privileged = await client.get(f"{BASE}/summary")
    assert resp_privileged.json()["at_risk_count"] == 1

    app_under_test = client._transport.app  # type: ignore[attr-defined]
    app_under_test.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    try:
        resp_reviewer = await client.get(f"{BASE}/summary")
        assert resp_reviewer.status_code == 200
        assert resp_reviewer.json()["at_risk_count"] == 0
    finally:
        del app_under_test.dependency_overrides[get_current_user]
