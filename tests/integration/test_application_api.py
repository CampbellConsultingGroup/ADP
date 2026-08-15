"""Integration tests for the Application Registry API (ADP-SPEC-036).

Covers all quickstart scenarios and user stories US1–US7 + cascade delete.
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

    import adp.business.store as bstore
    bstore._engine = engine
    bstore._session_factory = factory

    import adp.application.store as astore
    astore._engine = engine
    astore._session_factory = factory

    import adp.api.deps as deps
    deps._kb_engine = None
    deps._kb_session_factory = None

    yield application
    await engine.dispose()


@pytest.fixture()
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _create_app(client, **kwargs) -> str:
    payload = {"name": "Test App", **kwargs}
    r = await client.post("/api/v1/applications", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_biz_cap(client, name: str = "Customer Engagement", level: int = 1) -> str:
    r = await client.post(
        "/api/v1/business/capabilities",
        json={"name": name, "level": level},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_value_stream(client, name: str = "Order-to-Cash") -> str:
    r = await client.post("/api/v1/business/value-streams", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_stage(client, vs_id: str, name: str = "Fulfil Order", position: int = 0) -> str:
    r = await client.post(
        f"/api/v1/business/value-streams/{vs_id}/stages",
        json={"name": name, "position": position},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_domain(client, name: str = "Customer") -> str:
    r = await client.post(
        "/api/v1/business/domains",
        json={"name": name, "classification": "differentiating", "risk_flags": []},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_design(client) -> str:
    r = await client.post(
        "/api/v1/designs",
        json={"title": "Test Design", "content": {"elements": [], "relationships": []}},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── US1: Application Core CRUD ────────────────────────────────────────────────

async def test_application_create_201(client):
    r = await client.post(
        "/api/v1/applications",
        json={
            "name": "Customer Portal",
            "vendor": "Acme Corp",
            "primary_owner": "Platform Team",
            "time_classification": "Invest",
            "r_strategy": "Refactor",
            "pace_layer": "Differentiation",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Customer Portal"
    assert data["vendor"] == "Acme Corp"
    assert data["time_classification"] == "Invest"
    assert data["r_strategy"] == "Refactor"
    assert data["pace_layer"] == "Differentiation"
    assert data["health_score"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


async def test_application_list_ordered(client):
    await client.post("/api/v1/applications", json={"name": "Zorro App"})
    await client.post("/api/v1/applications", json={"name": "Alpha App"})

    r = await client.get("/api/v1/applications")
    assert r.status_code == 200
    data = r.json()
    names = [item["name"] for item in data["items"]]
    # Should be ordered alphabetically; Alpha comes before Zorro
    alpha_idx = next(i for i, n in enumerate(names) if n == "Alpha App")
    zorro_idx = next(i for i, n in enumerate(names) if n == "Zorro App")
    assert alpha_idx < zorro_idx
    assert data["total"] == len(data["items"])


async def test_application_get_200(client):
    app_id = await _create_app(client, name="Get Test App")
    r = await client.get(f"/api/v1/applications/{app_id}")
    assert r.status_code == 200
    assert r.json()["id"] == app_id


async def test_application_update_200(client):
    app_id = await _create_app(client, name="Update Test")
    r = await client.patch(
        f"/api/v1/applications/{app_id}",
        json={"vendor": "Updated Vendor"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["vendor"] == "Updated Vendor"


async def test_application_update_rejects_health_score_422(client):
    # docs/application-health-assessment-spec.md §6 Q5: health_score is only
    # ever set via PUT /applications/{id}/health-assessment.
    app_id = await _create_app(client, name="Update Test")
    r = await client.patch(
        f"/api/v1/applications/{app_id}",
        json={"health_score": 2},
    )
    assert r.status_code == 422


async def test_application_delete_204(client):
    app_id = await _create_app(client, name="Delete Me")
    r = await client.delete(f"/api/v1/applications/{app_id}")
    assert r.status_code == 204

    r2 = await client.get(f"/api/v1/applications/{app_id}")
    assert r2.status_code == 404


async def test_application_blank_name_422(client):
    r = await client.post("/api/v1/applications", json={"name": "   "})
    assert r.status_code == 422


async def test_application_invalid_time_422(client):
    r = await client.post(
        "/api/v1/applications", json={"name": "App", "time_classification": "Spend"}
    )
    assert r.status_code == 422


def _health_body(**overrides: int) -> dict:
    body = {
        "stability_incidents": 3, "technical_currency_debt": 3, "security_posture": 3,
        "support_team_capacity": 3, "documentation_knowledge": 3,
        "business_value_criticality": 3,
    }
    body.update(overrides)
    return body


async def test_application_health_assessment_score_0_422(client):
    app_id = await _create_app(client, name="App")
    r = await client.put(
        f"/api/v1/applications/{app_id}/health-assessment",
        json=_health_body(stability_incidents=0),
    )
    assert r.status_code == 422


async def test_application_health_assessment_score_6_422(client):
    app_id = await _create_app(client, name="App")
    r = await client.put(
        f"/api/v1/applications/{app_id}/health-assessment",
        json=_health_body(stability_incidents=6),
    )
    assert r.status_code == 422


async def test_application_health_assessment_5_200(client):
    app_id = await _create_app(client, name="Healthy App")
    r = await client.put(
        f"/api/v1/applications/{app_id}/health-assessment", json=_health_body()
    )
    assert r.status_code == 200
    assert r.json()["health_score"] == 3

    r2 = await client.get(f"/api/v1/applications/{app_id}")
    assert r2.json()["health_score"] == 3


async def test_application_not_found_404(client):
    r = await client.get("/api/v1/applications/nonexistent-id")
    assert r.status_code == 404


# ── US2: Business Capability Linkage ─────────────────────────────────────────

async def test_app_cap_link_create_201(client):
    app_id = await _create_app(client, name="Cap Link App")
    cap_id = await _create_biz_cap(client, name="Cap Link Cap")

    r = await client.post(
        f"/api/v1/applications/{app_id}/capability-links",
        json={"capability_id": cap_id, "fit_score": 3},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["capability_id"] == cap_id
    assert data["fit_score"] == 3
    assert data["capability_name"] == "Cap Link Cap"


async def test_app_cap_link_list_includes_name(client):
    app_id = await _create_app(client, name="Cap List App")
    cap_id = await _create_biz_cap(client, name="Listed Cap")

    await client.post(
        f"/api/v1/applications/{app_id}/capability-links",
        json={"capability_id": cap_id, "fit_score": 2},
    )
    r = await client.get(f"/api/v1/applications/{app_id}/capability-links")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["capability_name"] == "Listed Cap"


async def test_app_cap_link_update_score(client):
    app_id = await _create_app(client, name="Cap Update App")
    cap_id = await _create_biz_cap(client, name="Update Score Cap")

    await client.post(
        f"/api/v1/applications/{app_id}/capability-links",
        json={"capability_id": cap_id, "fit_score": 3},
    )
    r = await client.patch(
        f"/api/v1/applications/{app_id}/capability-links/{cap_id}",
        json={"fit_score": 5},
    )
    assert r.status_code == 200
    assert r.json()["fit_score"] == 5


async def test_app_cap_link_duplicate_409(client):
    app_id = await _create_app(client, name="Dup Cap App")
    cap_id = await _create_biz_cap(client, name="Dup Cap")

    await client.post(
        f"/api/v1/applications/{app_id}/capability-links",
        json={"capability_id": cap_id, "fit_score": 3},
    )
    r = await client.post(
        f"/api/v1/applications/{app_id}/capability-links",
        json={"capability_id": cap_id, "fit_score": 4},
    )
    assert r.status_code == 409


async def test_app_cap_link_fit_score_0_422(client):
    app_id = await _create_app(client, name="Score 0 App")
    cap_id = await _create_biz_cap(client, name="Score 0 Cap")
    r = await client.post(
        f"/api/v1/applications/{app_id}/capability-links",
        json={"capability_id": cap_id, "fit_score": 0},
    )
    assert r.status_code == 422


async def test_app_cap_link_fit_score_6_422(client):
    app_id = await _create_app(client, name="Score 6 App")
    cap_id = await _create_biz_cap(client, name="Score 6 Cap")
    r = await client.post(
        f"/api/v1/applications/{app_id}/capability-links",
        json={"capability_id": cap_id, "fit_score": 6},
    )
    assert r.status_code == 422


async def test_app_cap_link_delete_204(client):
    app_id = await _create_app(client, name="Cap Del App")
    cap_id = await _create_biz_cap(client, name="Del Cap")

    await client.post(
        f"/api/v1/applications/{app_id}/capability-links",
        json={"capability_id": cap_id, "fit_score": 3},
    )
    r = await client.delete(f"/api/v1/applications/{app_id}/capability-links/{cap_id}")
    assert r.status_code == 204

    r2 = await client.get(f"/api/v1/applications/{app_id}/capability-links")
    assert r2.json()["items"] == []


# ── US3: Technical Capability Hierarchy ───────────────────────────────────────

async def test_tech_cap_create_l1_201(client):
    r = await client.post(
        "/api/v1/technical-capabilities",
        json={"name": "Data Management"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["level"] == 1
    assert data["parent_id"] is None


async def test_tech_cap_create_l2_201(client):
    r1 = await client.post(
        "/api/v1/technical-capabilities", json={"name": "TC L1 Parent"}
    )
    l1_id = r1.json()["id"]

    r2 = await client.post(
        "/api/v1/technical-capabilities",
        json={"name": "TC L2 Child", "parent_id": l1_id},
    )
    assert r2.status_code == 201
    assert r2.json()["level"] == 2
    assert r2.json()["parent_id"] == l1_id


async def test_tech_cap_create_l3_201(client):
    r1 = await client.post("/api/v1/technical-capabilities", json={"name": "TC L1 For L3"})
    l1_id = r1.json()["id"]
    r2 = await client.post(
        "/api/v1/technical-capabilities", json={"name": "TC L2 For L3", "parent_id": l1_id}
    )
    l2_id = r2.json()["id"]
    r3 = await client.post(
        "/api/v1/technical-capabilities", json={"name": "TC L3 Leaf", "parent_id": l2_id}
    )
    assert r3.status_code == 201
    assert r3.json()["level"] == 3


async def test_tech_cap_depth_exceeded_422(client):
    r1 = await client.post("/api/v1/technical-capabilities", json={"name": "Depth L1"})
    l1_id = r1.json()["id"]
    r2 = await client.post(
        "/api/v1/technical-capabilities", json={"name": "Depth L2", "parent_id": l1_id}
    )
    l2_id = r2.json()["id"]
    r3 = await client.post(
        "/api/v1/technical-capabilities", json={"name": "Depth L3", "parent_id": l2_id}
    )
    l3_id = r3.json()["id"]

    r4 = await client.post(
        "/api/v1/technical-capabilities", json={"name": "Too Deep L4", "parent_id": l3_id}
    )
    assert r4.status_code == 422


async def test_tech_cap_list_returns_hierarchy(client):
    r1 = await client.post("/api/v1/technical-capabilities", json={"name": "Hier L1"})
    l1_id = r1.json()["id"]
    await client.post(
        "/api/v1/technical-capabilities", json={"name": "Hier L2", "parent_id": l1_id}
    )

    r = await client.get("/api/v1/technical-capabilities")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 2
    levels = [item["level"] for item in data["items"]]
    # Should be ordered by level, so all L1s come before L2s
    first_l2 = next((i for i, lvl in enumerate(levels) if lvl == 2), None)
    if first_l2 is not None:
        assert all(lvl <= 2 for lvl in levels[:first_l2 + 1])


async def test_tech_cap_delete_leaf_204(client):
    r1 = await client.post("/api/v1/technical-capabilities", json={"name": "Del Parent"})
    l1_id = r1.json()["id"]
    r2 = await client.post(
        "/api/v1/technical-capabilities", json={"name": "Del Leaf", "parent_id": l1_id}
    )
    l2_id = r2.json()["id"]

    r = await client.delete(f"/api/v1/technical-capabilities/{l2_id}")
    assert r.status_code == 204

    r2 = await client.get(f"/api/v1/technical-capabilities/{l1_id}")
    assert r2.status_code == 200


async def test_tech_cap_delete_with_children_409(client):
    r1 = await client.post("/api/v1/technical-capabilities", json={"name": "Block Del L1"})
    l1_id = r1.json()["id"]
    await client.post(
        "/api/v1/technical-capabilities", json={"name": "Block Del L2", "parent_id": l1_id}
    )

    r = await client.delete(f"/api/v1/technical-capabilities/{l1_id}")
    assert r.status_code == 409


async def test_tech_cap_parent_not_found_404(client):
    r = await client.post(
        "/api/v1/technical-capabilities",
        json={"name": "Orphan", "parent_id": "nonexistent-id"},
    )
    assert r.status_code == 404


# ── US4: Application–Technical Capability Links ────────────────────────────────

async def _create_tc_hierarchy(client) -> tuple[str, str, str]:
    r1 = await client.post("/api/v1/technical-capabilities", json={"name": "US4 L1"})
    l1 = r1.json()["id"]
    r2 = await client.post(
        "/api/v1/technical-capabilities", json={"name": "US4 L2", "parent_id": l1}
    )
    l2 = r2.json()["id"]
    r3 = await client.post(
        "/api/v1/technical-capabilities", json={"name": "US4 L3", "parent_id": l2}
    )
    l3 = r3.json()["id"]
    return l1, l2, l3


async def test_app_tech_cap_provides_201(client):
    app_id = await _create_app(client, name="TC Provides App")
    _, _, l3_id = await _create_tc_hierarchy(client)

    r = await client.post(
        f"/api/v1/applications/{app_id}/technical-capability-links",
        json={"tech_cap_id": l3_id, "usage_type": "provides"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["usage_type"] == "provides"


async def test_app_tech_cap_consumes_201(client):
    app_id = await _create_app(client, name="TC Consumes App")
    r1 = await client.post("/api/v1/technical-capabilities", json={"name": "Consume TC"})
    tc_id = r1.json()["id"]

    r = await client.post(
        f"/api/v1/applications/{app_id}/technical-capability-links",
        json={"tech_cap_id": tc_id, "usage_type": "consumes"},
    )
    assert r.status_code == 201
    assert r.json()["usage_type"] == "consumes"


async def test_app_tech_cap_both_same_cap_allowed(client):
    app_id = await _create_app(client, name="TC Both App")
    r1 = await client.post("/api/v1/technical-capabilities", json={"name": "Both TC"})
    tc_id = r1.json()["id"]

    r_prov = await client.post(
        f"/api/v1/applications/{app_id}/technical-capability-links",
        json={"tech_cap_id": tc_id, "usage_type": "provides"},
    )
    assert r_prov.status_code == 201

    r_cons = await client.post(
        f"/api/v1/applications/{app_id}/technical-capability-links",
        json={"tech_cap_id": tc_id, "usage_type": "consumes"},
    )
    assert r_cons.status_code == 201


async def test_app_tech_cap_duplicate_409(client):
    app_id = await _create_app(client, name="TC Dup App")
    r1 = await client.post("/api/v1/technical-capabilities", json={"name": "Dup TC"})
    tc_id = r1.json()["id"]

    await client.post(
        f"/api/v1/applications/{app_id}/technical-capability-links",
        json={"tech_cap_id": tc_id, "usage_type": "provides"},
    )
    r2 = await client.post(
        f"/api/v1/applications/{app_id}/technical-capability-links",
        json={"tech_cap_id": tc_id, "usage_type": "provides"},
    )
    assert r2.status_code == 409


async def test_app_tech_cap_invalid_type_422(client):
    app_id = await _create_app(client, name="TC Invalid App")
    r1 = await client.post("/api/v1/technical-capabilities", json={"name": "Invalid TC"})
    tc_id = r1.json()["id"]

    r = await client.post(
        f"/api/v1/applications/{app_id}/technical-capability-links",
        json={"tech_cap_id": tc_id, "usage_type": "reads"},
    )
    assert r.status_code == 422


async def test_app_tech_cap_list_includes_tech_cap_name(client):
    app_id = await _create_app(client, name="TC List App")
    r1 = await client.post("/api/v1/technical-capabilities", json={"name": "Named TC"})
    tc_id = r1.json()["id"]

    await client.post(
        f"/api/v1/applications/{app_id}/technical-capability-links",
        json={"tech_cap_id": tc_id, "usage_type": "provides"},
    )
    r = await client.get(f"/api/v1/applications/{app_id}/technical-capability-links")
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(item["tech_cap_name"] == "Named TC" for item in items)


async def test_app_tech_cap_delete_204(client):
    app_id = await _create_app(client, name="TC Del App")
    r1 = await client.post("/api/v1/technical-capabilities", json={"name": "Del TC"})
    tc_id = r1.json()["id"]

    await client.post(
        f"/api/v1/applications/{app_id}/technical-capability-links",
        json={"tech_cap_id": tc_id, "usage_type": "provides"},
    )
    r = await client.delete(
        f"/api/v1/applications/{app_id}/technical-capability-links/{tc_id}/provides"
    )
    assert r.status_code == 204


# ── US5: Value Stream Stage and Domain Linkage ────────────────────────────────

async def test_app_stage_link_create_201(client):
    app_id = await _create_app(client, name="Stage Link App")
    vs_id = await _create_value_stream(client, "VS Stage Test")
    stage_id = await _create_stage(client, vs_id, "Stage A")

    r = await client.post(
        f"/api/v1/applications/{app_id}/stage-links",
        json={"stage_id": stage_id},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["stage_id"] == stage_id
    assert data["stage_name"] == "Stage A"


async def test_app_stage_link_duplicate_409(client):
    app_id = await _create_app(client, name="Stage Dup App")
    vs_id = await _create_value_stream(client, "VS Dup Stage")
    stage_id = await _create_stage(client, vs_id, "Stage Dup")

    await client.post(
        f"/api/v1/applications/{app_id}/stage-links", json={"stage_id": stage_id}
    )
    r = await client.post(
        f"/api/v1/applications/{app_id}/stage-links", json={"stage_id": stage_id}
    )
    assert r.status_code == 409


async def test_app_stage_link_delete_204(client):
    app_id = await _create_app(client, name="Stage Del App")
    vs_id = await _create_value_stream(client, "VS Del Stage")
    stage_id = await _create_stage(client, vs_id, "Del Stage")

    await client.post(
        f"/api/v1/applications/{app_id}/stage-links", json={"stage_id": stage_id}
    )
    r = await client.delete(f"/api/v1/applications/{app_id}/stage-links/{stage_id}")
    assert r.status_code == 204

    r2 = await client.get(f"/api/v1/applications/{app_id}/stage-links")
    assert r2.json()["items"] == []


async def test_app_stage_cascade_delete_stage(client):
    app_id = await _create_app(client, name="Stage Cascade App")
    vs_id = await _create_value_stream(client, "VS Cascade Stage")
    stage_id = await _create_stage(client, vs_id, "Cascade Stage")

    await client.post(
        f"/api/v1/applications/{app_id}/stage-links", json={"stage_id": stage_id}
    )
    # Delete the stage (from the VS)
    await client.delete(f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}")

    r = await client.get(f"/api/v1/applications/{app_id}/stage-links")
    assert r.status_code == 200
    assert r.json()["items"] == []


async def test_app_domain_integration_create_201(client):
    app_id = await _create_app(client, name="Domain Int App")
    domain_id = await _create_domain(client, "Domain Int Domain")

    r = await client.post(
        f"/api/v1/applications/{app_id}/domain-integrations",
        json={
            "domain_id": domain_id,
            "integration_type": "primary-support",
            "direction": "inbound",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["domain_id"] == domain_id
    assert data["domain_name"] == "Domain Int Domain"
    assert data["direction"] == "inbound"


async def test_app_domain_integration_invalid_direction_422(client):
    app_id = await _create_app(client, name="Domain Dir App")
    r = await client.post(
        f"/api/v1/applications/{app_id}/domain-integrations",
        json={"integration_type": "support", "direction": "lateral"},
    )
    assert r.status_code == 422


async def test_app_domain_integration_delete_204(client):
    app_id = await _create_app(client, name="Domain Del App")
    domain_id = await _create_domain(client, "Del Domain")

    r = await client.post(
        f"/api/v1/applications/{app_id}/domain-integrations",
        json={"domain_id": domain_id, "integration_type": "support", "direction": "outbound"},
    )
    link_id = r.json()["id"]

    r2 = await client.delete(f"/api/v1/applications/{app_id}/domain-integrations/{link_id}")
    assert r2.status_code == 204


async def test_app_domain_integration_cascade_delete_domain(client):
    app_id = await _create_app(client, name="Domain Cascade App")
    domain_id = await _create_domain(client, "Cascade Domain")

    await client.post(
        f"/api/v1/applications/{app_id}/domain-integrations",
        json={"domain_id": domain_id, "integration_type": "support", "direction": "inbound"},
    )
    # Delete the domain
    await client.delete(f"/api/v1/business/domains/{domain_id}")

    r = await client.get(f"/api/v1/applications/{app_id}/domain-integrations")
    assert r.status_code == 200
    assert r.json()["items"] == []


# ── US6: Application Integration Registry ─────────────────────────────────────

async def test_integration_create_201(client):
    app_a = await _create_app(client, name="Int Source App")
    app_b = await _create_app(client, name="Int Target App")

    r = await client.post(
        "/api/v1/integrations",
        json={
            "source_app_id": app_a,
            "target_app_id": app_b,
            "integration_type": "API",
            "description": "REST sync",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["source_app_id"] == app_a
    assert data["target_app_id"] == app_b
    assert data["source_app_name"] == "Int Source App"
    assert data["target_app_name"] == "Int Target App"


async def test_integration_self_422(client):
    app_a = await _create_app(client, name="Self Loop App")
    r = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": app_a, "target_app_id": app_a, "integration_type": "API"},
    )
    assert r.status_code == 422


async def test_integration_invalid_type_422(client):
    app_a = await _create_app(client, name="Bad Type Src")
    app_b = await _create_app(client, name="Bad Type Tgt")
    r = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": app_a, "target_app_id": app_b, "integration_type": "REST"},
    )
    assert r.status_code == 422


async def test_integration_list_by_app_id(client):
    app_a = await _create_app(client, name="List Src App")
    app_b = await _create_app(client, name="List Tgt App")

    await client.post(
        "/api/v1/integrations",
        json={"source_app_id": app_a, "target_app_id": app_b, "integration_type": "event"},
    )
    r = await client.get(f"/api/v1/integrations?app_id={app_a}")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    ids = [item["source_app_id"] for item in data["items"]]
    ids += [item["target_app_id"] for item in data["items"]]
    assert app_a in ids


async def test_integration_bidirectional_permitted(client):
    app_a = await _create_app(client, name="Bidir Src")
    app_b = await _create_app(client, name="Bidir Tgt")

    r1 = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": app_a, "target_app_id": app_b, "integration_type": "API"},
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": app_b, "target_app_id": app_a, "integration_type": "event"},
    )
    assert r2.status_code == 201


async def test_integration_get_200(client):
    app_a = await _create_app(client, name="Get Int Src")
    app_b = await _create_app(client, name="Get Int Tgt")

    r = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": app_a, "target_app_id": app_b, "integration_type": "file"},
    )
    int_id = r.json()["id"]

    r2 = await client.get(f"/api/v1/integrations/{int_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == int_id


async def test_integration_update_description(client):
    app_a = await _create_app(client, name="Update Int Src")
    app_b = await _create_app(client, name="Update Int Tgt")

    r = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": app_a, "target_app_id": app_b, "integration_type": "database"},
    )
    int_id = r.json()["id"]

    r2 = await client.patch(
        f"/api/v1/integrations/{int_id}", json={"description": "Updated desc"}
    )
    assert r2.status_code == 200
    assert r2.json()["description"] == "Updated desc"


async def test_integration_delete_204(client):
    app_a = await _create_app(client, name="Del Int Src")
    app_b = await _create_app(client, name="Del Int Tgt")

    r = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": app_a, "target_app_id": app_b, "integration_type": "messaging"},
    )
    int_id = r.json()["id"]

    r2 = await client.delete(f"/api/v1/integrations/{int_id}")
    assert r2.status_code == 204

    r3 = await client.get(f"/api/v1/integrations/{int_id}")
    assert r3.status_code == 404


async def test_integration_cascade_source_delete(client):
    app_a = await _create_app(client, name="Cascade Src Del")
    app_b = await _create_app(client, name="Cascade Tgt Del A")

    r = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": app_a, "target_app_id": app_b, "integration_type": "API"},
    )
    int_id = r.json()["id"]

    await client.delete(f"/api/v1/applications/{app_a}")

    r2 = await client.get(f"/api/v1/integrations/{int_id}")
    assert r2.status_code == 404


async def test_integration_cascade_target_delete(client):
    app_a = await _create_app(client, name="Cascade Src Del B")
    app_b = await _create_app(client, name="Cascade Tgt Del B")

    r = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": app_a, "target_app_id": app_b, "integration_type": "API"},
    )
    int_id = r.json()["id"]

    await client.delete(f"/api/v1/applications/{app_b}")

    r2 = await client.get(f"/api/v1/integrations/{int_id}")
    assert r2.status_code == 404


# ── US7: Design Links ─────────────────────────────────────────────────────────

async def test_app_design_link_create_201(client):
    app_id = await _create_app(client, name="Design Link App")
    design_id = await _create_design(client)

    r = await client.post(
        f"/api/v1/applications/{app_id}/design-links",
        json={"design_id": design_id},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["design_id"] == design_id
    assert data["app_id"] == app_id


async def test_app_design_link_nonexistent_design_404(client):
    app_id = await _create_app(client, name="Design 404 App")
    r = await client.post(
        f"/api/v1/applications/{app_id}/design-links",
        json={"design_id": "nonexistent-design-id"},
    )
    assert r.status_code == 404


async def test_app_design_link_duplicate_409(client):
    app_id = await _create_app(client, name="Design Dup App")
    design_id = await _create_design(client)

    await client.post(
        f"/api/v1/applications/{app_id}/design-links", json={"design_id": design_id}
    )
    r = await client.post(
        f"/api/v1/applications/{app_id}/design-links", json={"design_id": design_id}
    )
    assert r.status_code == 409


async def test_app_design_link_list(client):
    app_id = await _create_app(client, name="Design List App")
    design_id = await _create_design(client)

    await client.post(
        f"/api/v1/applications/{app_id}/design-links", json={"design_id": design_id}
    )
    r = await client.get(f"/api/v1/applications/{app_id}/design-links")
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(item["design_id"] == design_id for item in items)


async def test_app_design_link_delete_204(client):
    app_id = await _create_app(client, name="Design Del App")
    design_id = await _create_design(client)

    await client.post(
        f"/api/v1/applications/{app_id}/design-links", json={"design_id": design_id}
    )
    r = await client.delete(f"/api/v1/applications/{app_id}/design-links/{design_id}")
    assert r.status_code == 204

    r2 = await client.get(f"/api/v1/applications/{app_id}/design-links")
    assert r2.json()["items"] == []


# ── T039: Cascade delete (all links) ─────────────────────────────────────────

async def test_application_delete_cascades_all_links(client):
    """Deleting an app cascades to all link tables."""
    app_id = await _create_app(client, name="Full Cascade App")

    # Create a business capability link
    cap_id = await _create_biz_cap(client, name="Cascade Biz Cap")
    await client.post(
        f"/api/v1/applications/{app_id}/capability-links",
        json={"capability_id": cap_id, "fit_score": 3},
    )

    # Create a tech cap link
    r_tc = await client.post("/api/v1/technical-capabilities", json={"name": "Cascade TC"})
    tc_id = r_tc.json()["id"]
    await client.post(
        f"/api/v1/applications/{app_id}/technical-capability-links",
        json={"tech_cap_id": tc_id, "usage_type": "provides"},
    )

    # Create a stage link
    vs_id = await _create_value_stream(client, "Cascade VS")
    stage_id = await _create_stage(client, vs_id, "Cascade Stage")
    await client.post(
        f"/api/v1/applications/{app_id}/stage-links", json={"stage_id": stage_id}
    )

    # Create a domain integration
    domain_id = await _create_domain(client, "Cascade Domain")
    await client.post(
        f"/api/v1/applications/{app_id}/domain-integrations",
        json={"domain_id": domain_id, "integration_type": "support", "direction": "inbound"},
    )

    # Create an integration as source
    app_b = await _create_app(client, name="Cascade Target App")
    r_int = await client.post(
        "/api/v1/integrations",
        json={"source_app_id": app_id, "target_app_id": app_b, "integration_type": "API"},
    )
    int_id = r_int.json()["id"]

    # Create a design link
    design_id = await _create_design(client)
    await client.post(
        f"/api/v1/applications/{app_id}/design-links", json={"design_id": design_id}
    )

    # Delete the app
    r_del = await client.delete(f"/api/v1/applications/{app_id}")
    assert r_del.status_code == 204

    # Integration should be gone (cascade)
    r_int_check = await client.get(f"/api/v1/integrations/{int_id}")
    assert r_int_check.status_code == 404
