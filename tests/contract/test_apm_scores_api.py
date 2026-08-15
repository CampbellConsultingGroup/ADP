"""Contract tests for APM US1 — business-value scores + rationalization (ADP-SPEC-038).

Runs the applications router full-stack against the real store on in-memory
SQLite (store metadata picks up the new columns via create_all).
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import router as arouter
from adp.application import store as astore


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/apm.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[arouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def _mk_app(client, name, **extra) -> dict:
    resp = await client.post("/api/v1/applications", json={"name": name, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _assess(client, app_id: str, score: int) -> dict:
    """PUTs a full six-dimension health assessment with every dimension set
    to `score`, so the resulting health_score is exactly `score`."""
    body = {
        "stability_incidents": score, "technical_currency_debt": score,
        "security_posture": score, "support_team_capacity": score,
        "documentation_knowledge": score, "business_value_criticality": score,
    }
    resp = await client.put(f"/api/v1/applications/{app_id}/health-assessment", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _assess_value(client, app_id: str, score: int) -> dict:
    """PUTs a full six-dimension business-value assessment with every
    dimension set to `score`. A uniform score never triggers the evidence
    cap tighter than itself (docs/application-business-value-assessment-
    spec.md §5), so the resulting business_value is exactly `score`."""
    body = {
        "strategic_alignment": score, "revenue_cost_impact": score,
        "customer_stakeholder_impact": score, "competitive_differentiation": score,
        "risk_compliance_contribution": score, "evidence_measurability": score,
    }
    resp = await client.put(
        f"/api/v1/applications/{app_id}/business-value-assessment", json=body
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_create_with_scores(client):
    app = await _mk_app(client, "CRM", business_criticality=4)
    await _assess_value(client, app["id"], 5)
    await _assess(client, app["id"], 2)
    assert app["business_criticality"] == 4

    refreshed = (await client.get(f"/api/v1/applications/{app['id']}")).json()
    assert refreshed["business_value"] == 5
    assert refreshed["health_score"] == 2


async def test_scores_default_null(client):
    app = await _mk_app(client, "ERP")
    assert app["business_value"] is None
    assert app["business_criticality"] is None


async def test_patch_score(client):
    app = await _mk_app(client, "WMS")
    resp = await client.patch(
        f"/api/v1/applications/{app['id']}", json={"business_criticality": 3}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["business_criticality"] == 3


async def test_patch_rejects_business_value(client):
    # docs/application-business-value-assessment-spec.md §7: business_value
    # is only ever set via PUT .../business-value-assessment.
    app = await _mk_app(client, "WMS")
    resp = await client.patch(
        f"/api/v1/applications/{app['id']}", json={"business_value": 3}
    )
    assert resp.status_code == 422


async def test_score_out_of_range_rejected(client):
    app = await _mk_app(client, "HRIS")
    resp = await client.patch(
        f"/api/v1/applications/{app['id']}", json={"business_criticality": 0}
    )
    assert resp.status_code == 422


async def test_rationalization_places_assessed_and_separates_unassessed(client):
    alpha = await _mk_app(client, "Alpha")  # invest
    await _assess_value(client, alpha["id"], 5)
    await _assess(client, alpha["id"], 4)
    beta = await _mk_app(client, "Beta")  # migrate
    await _assess_value(client, beta["id"], 4)
    await _assess(client, beta["id"], 1)
    gamma = await _mk_app(client, "Gamma")  # unassessed: no value
    await _assess(client, gamma["id"], 5)
    delta = await _mk_app(client, "Delta")  # unassessed: no health
    await _assess_value(client, delta["id"], 2)

    resp = await client.get("/api/v1/applications/rationalization")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["total"] == 4
    placed = {e["app_id"]: e["quadrant"] for e in body["assessed"]}
    assert placed[alpha["id"]] == "invest"
    assert placed[beta["id"]] == "migrate"

    unassessed_ids = {e["app_id"] for e in body["unassessed"]}
    assert unassessed_ids == {gamma["id"], delta["id"]}
    assert all(e["quadrant"] is None for e in body["unassessed"])


async def test_rationalization_route_not_shadowed_by_app_id(client):
    # Ensure GET /applications/rationalization hits the projection, not get_application.
    resp = await client.get("/api/v1/applications/rationalization")
    assert resp.status_code == 200
    assert set(resp.json()) == {"assessed", "unassessed", "total"}
