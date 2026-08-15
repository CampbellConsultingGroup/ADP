"""Contract tests for the Application Registry API (ADP-SPEC-036).

Runs the applications/tech-caps/integrations routers full-stack against the
real adp.application.store on an in-memory SQLite database, with unique
indexes mirroring the composite primary keys from migration 010 so the
duplicate-link (409) paths behave as they do on PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import router as arouter
from adp.application import store as astore

# Composite PKs from migration 010 (store metadata omits them; Alembic owns schema)
_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_app_cap ON application_capability_links(app_id, capability_id)",
    "CREATE UNIQUE INDEX uq_app_tc ON application_tech_cap_links(app_id, tech_cap_id, usage_type)",
    "CREATE UNIQUE INDEX uq_app_stage ON application_stage_links(app_id, stage_id)",
    "CREATE UNIQUE INDEX uq_app_design ON application_design_links(app_id, design_id)",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/app.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
        for ddl in _UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Seed referenced entities (owned by other specs' stores in production)
    async with factory() as session:
        await session.execute(astore._biz_caps.insert().values(id="CAP-001", name="Billing"))
        await session.execute(astore._stages.insert().values(id="STG-001", name="Quote"))
        await session.execute(astore._domains.insert().values(id="DOM-001", name="Finance"))
        await session.execute(astore._designs.insert().values(id="DSN-001"))
        await session.commit()

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


async def _mk_app(client, name="CRM", **extra) -> dict:
    resp = await client.post("/api/v1/applications", json={"name": name, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _assess(client, app_id: str, **overrides: int) -> dict:
    """PUTs a full six-dimension health assessment, all dimensions defaulting
    to 3 unless overridden -- the resulting health_score is min(scores)."""
    scores = dict(
        stability_incidents=3,
        technical_currency_debt=3,
        security_posture=3,
        support_team_capacity=3,
        documentation_knowledge=3,
        business_value_criticality=3,
    )
    scores.update(overrides)
    resp = await client.put(f"/api/v1/applications/{app_id}/health-assessment", json=scores)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Application CRUD ──────────────────────────────────────────────────────────

async def test_list_applications_empty(client):
    resp = await client.get("/api/v1/applications")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


async def test_create_and_get_application(client):
    app = await _mk_app(
        client,
        name="  CRM  ",
        description="Customer platform",
        vendor="Acme",
        primary_owner="jane",
        time_classification="Invest",
        r_strategy="Refactor",
        pace_layer="Differentiation",
    )
    assert app["name"] == "CRM"  # trimmed
    assert app["time_classification"] == "Invest"

    resp = await client.get(f"/api/v1/applications/{app['id']}")
    assert resp.status_code == 200
    assert resp.json()["vendor"] == "Acme"

    listing = (await client.get("/api/v1/applications")).json()
    assert listing["total"] == 1


async def test_get_application_404(client):
    resp = await client.get("/api/v1/applications/nope")
    assert resp.status_code == 404


async def test_create_application_invalid_enum_422(client):
    resp = await client.post(
        "/api/v1/applications", json={"name": "X", "time_classification": "Keep"}
    )
    assert resp.status_code == 422


async def test_patch_application(client):
    app = await _mk_app(client)
    resp = await client.patch(
        f"/api/v1/applications/{app['id']}",
        json={"r_strategy": "Retire"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["r_strategy"] == "Retire"
    assert body["name"] == app["name"]


async def test_patch_application_rejects_health_score(client):
    # docs/application-health-assessment-spec.md §6 Q5: health_score is only
    # ever set via PUT /applications/{id}/health-assessment.
    app = await _mk_app(client)
    resp = await client.patch(
        f"/api/v1/applications/{app['id']}",
        json={"health_score": 2},
    )
    assert resp.status_code == 422


async def test_patch_application_explicit_null_clears_field(client):
    app = await _mk_app(client, vendor="Acme")
    await _assess(client, app["id"], stability_incidents=4)
    resp = await client.patch(
        f"/api/v1/applications/{app['id']}",
        json={"vendor": None},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["vendor"] is None          # explicit null cleared it
    assert body["health_score"] == 3       # omitted field unchanged (unaffected by PATCH)


async def test_patch_application_404(client):
    resp = await client.patch("/api/v1/applications/nope", json={"vendor": "X"})
    assert resp.status_code == 404


# ── Application Health Assessment ─────────────────────────────────────────────


async def test_get_health_assessment_never_assessed(client):
    app = await _mk_app(client)
    resp = await client.get(f"/api/v1/applications/{app['id']}/health-assessment")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"] == []
    assert body["health_score"] is None


async def test_get_health_assessment_404(client):
    resp = await client.get("/api/v1/applications/nope/health-assessment")
    assert resp.status_code == 404


async def test_put_health_assessment_computes_min_as_health_score(client):
    app = await _mk_app(client)
    body = await _assess(
        client, app["id"],
        stability_incidents=2, technical_currency_debt=5, security_posture=4,
        support_team_capacity=3, documentation_knowledge=5, business_value_criticality=3,
    )
    assert body["health_score"] == 2
    assert len(body["entries"]) == 6

    # The application's own health_score reflects the same value.
    resp = await client.get(f"/api/v1/applications/{app['id']}")
    assert resp.json()["health_score"] == 2


async def test_put_health_assessment_reassessment_upserts_in_place(client):
    app = await _mk_app(client)
    await _assess(client, app["id"], stability_incidents=2)
    first = await client.get(f"/api/v1/applications/{app['id']}/health-assessment")
    assert len(first.json()["entries"]) == 6

    body = await _assess(client, app["id"], stability_incidents=5)
    assert body["health_score"] == 3  # all dimensions now 3 (or 5 for stability)
    assert len(body["entries"]) == 6  # still 6 rows, not 12 -- upserted, not appended


async def test_put_health_assessment_partial_submission_422(client):
    app = await _mk_app(client)
    resp = await client.put(
        f"/api/v1/applications/{app['id']}/health-assessment",
        json={"stability_incidents": 3, "technical_currency_debt": 3},
    )
    assert resp.status_code == 422


async def test_put_health_assessment_out_of_range_422(client):
    app = await _mk_app(client)
    resp = await client.put(
        f"/api/v1/applications/{app['id']}/health-assessment",
        json={
            "stability_incidents": 6, "technical_currency_debt": 3, "security_posture": 3,
            "support_team_capacity": 3, "documentation_knowledge": 3,
            "business_value_criticality": 3,
        },
    )
    assert resp.status_code == 422


async def test_put_health_assessment_404(client):
    resp = await client.put(
        "/api/v1/applications/nope/health-assessment",
        json={
            "stability_incidents": 3, "technical_currency_debt": 3, "security_posture": 3,
            "support_team_capacity": 3, "documentation_knowledge": 3,
            "business_value_criticality": 3,
        },
    )
    assert resp.status_code == 404


# ── Application Business Value Assessment ─────────────────────────────────────


async def _assess_value(client, app_id: str, **overrides: int) -> dict:
    """PUTs a full six-dimension business-value assessment, all dimensions
    defaulting to 3 unless overridden."""
    scores = dict(
        strategic_alignment=3, revenue_cost_impact=3, customer_stakeholder_impact=3,
        competitive_differentiation=3, risk_compliance_contribution=3,
        evidence_measurability=3,
    )
    scores.update(overrides)
    resp = await client.put(
        f"/api/v1/applications/{app_id}/business-value-assessment", json=scores
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_get_business_value_assessment_never_assessed(client):
    app = await _mk_app(client)
    resp = await client.get(f"/api/v1/applications/{app['id']}/business-value-assessment")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"] == []
    assert body["result"] is None


async def test_get_business_value_assessment_404(client):
    resp = await client.get("/api/v1/applications/nope/business-value-assessment")
    assert resp.status_code == 404


async def test_put_business_value_assessment_worked_example_from_spec(client):
    # docs/application-business-value-assessment-spec.md §5.3's own example.
    app = await _mk_app(client)
    body = await _assess_value(
        client, app["id"],
        strategic_alignment=5, revenue_cost_impact=5, customer_stakeholder_impact=4,
        competitive_differentiation=4, risk_compliance_contribution=3,
        evidence_measurability=1,
    )
    assert body["result"]["weighted_average"] == 4.05
    assert body["result"]["cap"] == 2
    assert body["result"]["capped"] is True
    assert body["result"]["business_value"] == 2
    assert len(body["entries"]) == 6

    resp = await client.get(f"/api/v1/applications/{app['id']}")
    assert resp.json()["business_value"] == 2


async def test_put_business_value_assessment_no_cap_when_evidence_strong(client):
    app = await _mk_app(client)
    body = await _assess_value(client, app["id"], evidence_measurability=5)
    assert body["result"]["cap"] is None
    assert body["result"]["capped"] is False
    assert body["result"]["business_value"] == 3


async def test_put_business_value_assessment_reassessment_upserts_in_place(client):
    app = await _mk_app(client)
    await _assess_value(client, app["id"], strategic_alignment=2)
    first = await client.get(f"/api/v1/applications/{app['id']}/business-value-assessment")
    assert len(first.json()["entries"]) == 6

    body = await _assess_value(client, app["id"], strategic_alignment=5)
    assert len(body["entries"]) == 6  # still 6 rows, not 12 -- upserted, not appended


async def test_put_business_value_assessment_partial_submission_422(client):
    app = await _mk_app(client)
    resp = await client.put(
        f"/api/v1/applications/{app['id']}/business-value-assessment",
        json={"strategic_alignment": 3, "revenue_cost_impact": 3},
    )
    assert resp.status_code == 422


async def test_put_business_value_assessment_out_of_range_422(client):
    app = await _mk_app(client)
    resp = await client.put(
        f"/api/v1/applications/{app['id']}/business-value-assessment",
        json={
            "strategic_alignment": 6, "revenue_cost_impact": 3,
            "customer_stakeholder_impact": 3, "competitive_differentiation": 3,
            "risk_compliance_contribution": 3, "evidence_measurability": 3,
        },
    )
    assert resp.status_code == 422


async def test_put_business_value_assessment_404(client):
    resp = await client.put(
        "/api/v1/applications/nope/business-value-assessment",
        json={
            "strategic_alignment": 3, "revenue_cost_impact": 3,
            "customer_stakeholder_impact": 3, "competitive_differentiation": 3,
            "risk_compliance_contribution": 3, "evidence_measurability": 3,
        },
    )
    assert resp.status_code == 404


async def test_delete_application(client):
    app = await _mk_app(client)
    resp = await client.delete(f"/api/v1/applications/{app['id']}")
    assert resp.status_code == 204
    assert (await client.get(f"/api/v1/applications/{app['id']}")).status_code == 404


async def test_delete_application_404(client):
    resp = await client.delete("/api/v1/applications/nope")
    assert resp.status_code == 404


# ── Capability links ──────────────────────────────────────────────────────────

async def test_capability_link_crud(client):
    app = await _mk_app(client)
    base = f"/api/v1/applications/{app['id']}/capability-links"

    resp = await client.post(base, json={"capability_id": "CAP-001", "fit_score": 3})
    assert resp.status_code == 201, resp.text
    assert resp.json()["capability_name"] == "Billing"

    listing = (await client.get(base)).json()
    assert len(listing["items"]) == 1

    resp = await client.patch(f"{base}/CAP-001", json={"fit_score": 5})
    assert resp.status_code == 200
    assert resp.json()["fit_score"] == 5

    resp = await client.delete(f"{base}/CAP-001")
    assert resp.status_code == 204
    assert (await client.get(base)).json()["items"] == []


async def test_capability_link_duplicate_409(client):
    app = await _mk_app(client)
    base = f"/api/v1/applications/{app['id']}/capability-links"
    await client.post(base, json={"capability_id": "CAP-001", "fit_score": 3})
    resp = await client.post(base, json={"capability_id": "CAP-001", "fit_score": 4})
    assert resp.status_code == 409


async def test_capability_link_unknown_capability_404(client):
    app = await _mk_app(client)
    resp = await client.post(
        f"/api/v1/applications/{app['id']}/capability-links",
        json={"capability_id": "CAP-999", "fit_score": 3},
    )
    assert resp.status_code == 404


async def test_capability_link_unknown_app_404(client):
    resp = await client.post(
        "/api/v1/applications/nope/capability-links",
        json={"capability_id": "CAP-001", "fit_score": 3},
    )
    assert resp.status_code == 404


async def test_capability_link_patch_and_delete_404(client):
    app = await _mk_app(client)
    base = f"/api/v1/applications/{app['id']}/capability-links"
    assert (await client.patch(f"{base}/CAP-001", json={"fit_score": 1})).status_code == 404
    assert (await client.delete(f"{base}/CAP-001")).status_code == 404


# ── Technical capability links ────────────────────────────────────────────────

async def _mk_tech_cap(client, name="Messaging", parent_id=None) -> dict:
    resp = await client.post(
        "/api/v1/technical-capabilities",
        json={"name": name, "parent_id": parent_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_tech_cap_link_crud_and_duplicate(client):
    app = await _mk_app(client)
    tc = await _mk_tech_cap(client)
    base = f"/api/v1/applications/{app['id']}/technical-capability-links"

    resp = await client.post(base, json={"tech_cap_id": tc["id"], "usage_type": "provides"})
    assert resp.status_code == 201, resp.text

    listing = (await client.get(base)).json()
    assert len(listing["items"]) == 1

    resp = await client.post(base, json={"tech_cap_id": tc["id"], "usage_type": "provides"})
    assert resp.status_code == 409

    # Same pair with different usage_type is a distinct link (PK includes usage_type)
    resp = await client.post(base, json={"tech_cap_id": tc["id"], "usage_type": "consumes"})
    assert resp.status_code == 201

    resp = await client.delete(f"{base}/{tc['id']}/provides")
    assert resp.status_code == 204
    resp = await client.delete(f"{base}/{tc['id']}/provides")
    assert resp.status_code == 404


async def test_tech_cap_link_unknown_refs_404(client):
    app = await _mk_app(client)
    base = f"/api/v1/applications/{app['id']}/technical-capability-links"
    resp = await client.post(base, json={"tech_cap_id": "TC-999", "usage_type": "provides"})
    assert resp.status_code == 404
    resp = await client.post(
        "/api/v1/applications/nope/technical-capability-links",
        json={"tech_cap_id": "TC-999", "usage_type": "provides"},
    )
    assert resp.status_code == 404


# ── Stage links ───────────────────────────────────────────────────────────────

async def test_stage_link_crud_and_errors(client):
    app = await _mk_app(client)
    base = f"/api/v1/applications/{app['id']}/stage-links"

    resp = await client.post(base, json={"stage_id": "STG-001"})
    assert resp.status_code == 201, resp.text

    assert len((await client.get(base)).json()["items"]) == 1

    assert (await client.post(base, json={"stage_id": "STG-001"})).status_code == 409
    assert (await client.post(base, json={"stage_id": "STG-999"})).status_code == 404

    assert (await client.delete(f"{base}/STG-001")).status_code == 204
    assert (await client.delete(f"{base}/STG-001")).status_code == 404


# ── Domain integrations ───────────────────────────────────────────────────────

async def test_domain_integration_crud_and_errors(client):
    app = await _mk_app(client)
    base = f"/api/v1/applications/{app['id']}/domain-integrations"

    resp = await client.post(
        base, json={"domain_id": "DOM-001", "integration_type": "API", "direction": "outbound"}
    )
    assert resp.status_code == 201, resp.text
    link_id = resp.json()["id"]

    assert len((await client.get(base)).json()["items"]) == 1

    resp = await client.post(
        base, json={"domain_id": "DOM-999", "integration_type": "API", "direction": "inbound"}
    )
    assert resp.status_code == 404

    assert (await client.delete(f"{base}/{link_id}")).status_code == 204
    assert (await client.delete(f"{base}/{link_id}")).status_code == 404


# ── Design links ──────────────────────────────────────────────────────────────

async def test_design_link_crud_and_errors(client):
    app = await _mk_app(client)
    base = f"/api/v1/applications/{app['id']}/design-links"

    resp = await client.post(base, json={"design_id": "DSN-001"})
    assert resp.status_code == 201, resp.text

    assert len((await client.get(base)).json()["items"]) == 1

    assert (await client.post(base, json={"design_id": "DSN-001"})).status_code == 409
    assert (await client.post(base, json={"design_id": "DSN-999"})).status_code == 404

    assert (await client.delete(f"{base}/DSN-001")).status_code == 204
    assert (await client.delete(f"{base}/DSN-001")).status_code == 404


# ── Technical capability CRUD ─────────────────────────────────────────────────

async def test_tech_cap_hierarchy_and_depth_limit(client):
    l1 = await _mk_tech_cap(client, name="Platform")
    assert l1["level"] == 1
    l2 = await _mk_tech_cap(client, name="Messaging", parent_id=l1["id"])
    assert l2["level"] == 2
    l3 = await _mk_tech_cap(client, name="Queues", parent_id=l2["id"])
    assert l3["level"] == 3

    resp = await client.post(
        "/api/v1/technical-capabilities",
        json={"name": "TooDeep", "parent_id": l3["id"]},
    )
    assert resp.status_code == 422

    listing = (await client.get("/api/v1/technical-capabilities")).json()
    assert listing["total"] == 3


async def test_tech_cap_strategic_relevance(client):
    tc = await _mk_tech_cap(client)
    assert tc["strategic_relevance"] is None

    resp = await client.patch(
        f"/api/v1/technical-capabilities/{tc['id']}", json={"strategic_relevance": 2}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["strategic_relevance"] == 2

    resp = await client.patch(
        f"/api/v1/technical-capabilities/{tc['id']}", json={"strategic_relevance": None}
    )
    assert resp.status_code == 200
    assert resp.json()["strategic_relevance"] is None

    resp = await client.post(
        "/api/v1/technical-capabilities", json={"name": "X", "strategic_relevance": 0}
    )
    assert resp.status_code == 422


async def test_tech_cap_unknown_parent_404(client):
    resp = await client.post(
        "/api/v1/technical-capabilities", json={"name": "X", "parent_id": "TC-999"}
    )
    assert resp.status_code == 404


async def test_tech_cap_get_patch_delete(client):
    tc = await _mk_tech_cap(client)
    resp = await client.get(f"/api/v1/technical-capabilities/{tc['id']}")
    assert resp.status_code == 200

    resp = await client.patch(
        f"/api/v1/technical-capabilities/{tc['id']}", json={"name": "Renamed"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"

    assert (await client.delete(f"/api/v1/technical-capabilities/{tc['id']}")).status_code == 204
    assert (await client.get(f"/api/v1/technical-capabilities/{tc['id']}")).status_code == 404
    assert (
        await client.patch(f"/api/v1/technical-capabilities/{tc['id']}", json={"name": "Z"})
    ).status_code == 404


async def test_tech_cap_delete_with_children_409(client):
    parent = await _mk_tech_cap(client, name="Parent")
    await _mk_tech_cap(client, name="Child", parent_id=parent["id"])
    resp = await client.delete(f"/api/v1/technical-capabilities/{parent['id']}")
    assert resp.status_code == 409


# ── Application integrations ──────────────────────────────────────────────────

async def test_integration_crud_and_errors(client):
    src = await _mk_app(client, name="Source")
    tgt = await _mk_app(client, name="Target")

    resp = await client.post(
        "/api/v1/integrations",
        json={
            "source_app_id": src["id"],
            "target_app_id": tgt["id"],
            "integration_type": "API",
        },
    )
    assert resp.status_code == 201, resp.text
    integ = resp.json()

    assert (await client.get("/api/v1/integrations")).json()["total"] == 1
    assert (await client.get(f"/api/v1/integrations/{integ['id']}")).status_code == 200
    assert (await client.get("/api/v1/integrations/nope")).status_code == 404

    resp = await client.patch(
        f"/api/v1/integrations/{integ['id']}", json={"description": "nightly sync"}
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "nightly sync"
    assert (
        await client.patch("/api/v1/integrations/nope", json={"description": "x"})
    ).status_code == 404

    assert (await client.delete(f"/api/v1/integrations/{integ['id']}")).status_code == 204
    assert (await client.delete(f"/api/v1/integrations/{integ['id']}")).status_code == 404


async def test_integration_unknown_apps_404(client):
    src = await _mk_app(client, name="OnlySource")
    resp = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": src["id"], "target_app_id": "nope", "integration_type": "API"},
    )
    assert resp.status_code == 404
    resp = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": "nope", "target_app_id": src["id"], "integration_type": "API"},
    )
    assert resp.status_code == 404


async def test_integration_self_reference_rejected(client):
    app = await _mk_app(client, name="Selfish")
    resp = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": app["id"], "target_app_id": app["id"], "integration_type": "API"},
    )
    assert resp.status_code == 422


# ── ADP-d8u.2: GET /applications/{id}/objectives (reverse lookup) ──────────────


@pytest.fixture()
async def objectives_lookup_client(tmp_path):
    from adp.strategy import store as sstore

    app_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/app.db")
    async with app_engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
        for ddl in _UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
    app_factory = async_sessionmaker(app_engine, expire_on_commit=False)

    strategy_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/strategy.db")
    async with strategy_engine.begin() as conn:
        await conn.run_sync(sstore._metadata.create_all)
        await conn.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_oal "
                "ON objective_application_links(objective_id, application_id)"
            )
        )
    strategy_factory = async_sessionmaker(strategy_engine, expire_on_commit=False)

    from adp.api.app import create_app

    app = create_app()

    async def _app_override():
        async with app_factory() as session:
            yield session

    async def _strategy_override():
        async with strategy_factory() as session:
            yield session

    app.dependency_overrides[arouter._get_session] = _app_override
    app.dependency_overrides[arouter._get_strategy_session] = _strategy_override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app_factory, strategy_factory
    await app_engine.dispose()
    await strategy_engine.dispose()


async def test_get_application_objectives_404_unknown_application(
    objectives_lookup_client,
) -> None:
    c, _, _ = objectives_lookup_client
    resp = await c.get("/api/v1/applications/nonexistent/objectives")
    assert resp.status_code == 404


async def test_get_application_objectives_200_reflects_real_links(
    objectives_lookup_client,
) -> None:
    c, _app_factory, strategy_factory = objectives_lookup_client
    from adp.strategy import store as sstore
    from adp.strategy.models import StrategicObjectiveCreate, StrategicThemeCreate

    # Create the application through the real endpoint (not a raw insert)
    # so every NOT NULL column with a DB-level default gets populated
    # correctly, matching _mk_app's own established convention.
    app = await _mk_app(c, name="CRM")
    application_id = app["id"]

    async with strategy_factory() as session:
        theme = await sstore.create_theme(StrategicThemeCreate(name="Growth"), session)
        objective = await sstore.create_objective(
            StrategicObjectiveCreate(
                theme_id=theme.id, owner="Owner", statement="Statement",
                fiscal_year=2026, period="Q1",
            ),
            session,
        )
        await session.commit()
        await sstore.link_objective_application(objective.id, application_id, session)
        await session.commit()

    resp = await c.get(f"/api/v1/applications/{application_id}/objectives")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == objective.id
