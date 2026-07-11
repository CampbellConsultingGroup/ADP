"""Integration tests for the Business Architecture API (ADP-SPEC-033/034/035).

Covers Quickstart Scenarios 1–5: capability hierarchy CRUD, depth guard,
parent-level consistency, value stream lifecycle, and cascade delete.
Also covers ADP-SPEC-034 traceability links and ADP-SPEC-035 domain registry
and stage-capability mapping.

Requires Docker (testcontainers). Skipped automatically when Docker is unavailable.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="session")
async def app(db_url: str, db_engine):
    """FastAPI test app wired to the test database (migrations run via db_engine)."""
    import os
    from adp.api.app import create_app

    # Expose the testcontainer URL so DesignStore and knowledge stores find the DB.
    # Convert asyncpg URL back to psycopg2/sync URL for DesignStore (uses asyncpg directly).
    os.environ["ADP_DATABASE_URL"] = db_url

    application = create_app()

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    import adp.business.store as bstore
    bstore._engine = engine
    bstore._session_factory = factory

    # Reset KB session factory so it re-reads the new ADP_DATABASE_URL
    import adp.api.deps as deps
    deps._kb_engine = None
    deps._kb_session_factory = None

    yield application
    await engine.dispose()


@pytest.fixture()
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── Scenario 1: Full 3-level hierarchy CRUD ───────────────────────────────────

async def test_create_level1_capability(client):
    r = await client.post("/api/v1/business/capabilities", json={"name": "Customer Engagement", "level": 1})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Customer Engagement"
    assert data["level"] == 1
    assert data["parent_id"] is None
    assert "id" in data


async def test_create_3_level_hierarchy(client):
    r1 = await client.post("/api/v1/business/capabilities", json={"name": "L1", "level": 1})
    assert r1.status_code == 201
    l1_id = r1.json()["id"]

    r2 = await client.post("/api/v1/business/capabilities", json={"name": "L2", "level": 2, "parent_id": l1_id})
    assert r2.status_code == 201
    l2_id = r2.json()["id"]

    r3 = await client.post("/api/v1/business/capabilities", json={"name": "L3", "level": 3, "parent_id": l2_id})
    assert r3.status_code == 201

    r_list = await client.get("/api/v1/business/capabilities")
    assert r_list.status_code == 200
    ids = {item["id"] for item in r_list.json()["items"]}
    assert l1_id in ids
    assert l2_id in ids


async def test_update_capability(client):
    r = await client.post("/api/v1/business/capabilities", json={"name": "Original", "level": 1})
    cap_id = r.json()["id"]

    r_update = await client.put(f"/api/v1/business/capabilities/{cap_id}", json={"name": "Updated"})
    assert r_update.status_code == 200
    assert r_update.json()["name"] == "Updated"


async def test_delete_leaf_capability(client):
    r = await client.post("/api/v1/business/capabilities", json={"name": "Leaf", "level": 1})
    cap_id = r.json()["id"]

    r_del = await client.delete(f"/api/v1/business/capabilities/{cap_id}")
    assert r_del.status_code == 204

    r_get = await client.get(f"/api/v1/business/capabilities/{cap_id}")
    assert r_get.status_code == 404


# ── Scenario 2: Delete guard — parent with children ──────────────────────────

async def test_delete_capability_with_children_blocked(client):
    r1 = await client.post("/api/v1/business/capabilities", json={"name": "Parent", "level": 1})
    parent_id = r1.json()["id"]
    await client.post("/api/v1/business/capabilities", json={"name": "Child", "level": 2, "parent_id": parent_id})

    r_del = await client.delete(f"/api/v1/business/capabilities/{parent_id}")
    assert r_del.status_code == 409
    assert "child" in r_del.json()["detail"].lower()


# ── Scenario 3: Parent level mismatch ────────────────────────────────────────

async def test_create_level2_under_level2_rejected(client):
    r1 = await client.post("/api/v1/business/capabilities", json={"name": "L1", "level": 1})
    l1_id = r1.json()["id"]
    r2 = await client.post("/api/v1/business/capabilities", json={"name": "L2", "level": 2, "parent_id": l1_id})
    l2_id = r2.json()["id"]

    r_bad = await client.post("/api/v1/business/capabilities", json={"name": "Bad", "level": 2, "parent_id": l2_id})
    assert r_bad.status_code == 422


async def test_create_level4_rejected(client):
    r = await client.post("/api/v1/business/capabilities", json={"name": "Too Deep", "level": 4})
    assert r.status_code == 422


async def test_get_capability_not_found(client):
    r = await client.get("/api/v1/business/capabilities/nonexistent-id")
    assert r.status_code == 404


# ── Scenario 4: Full value stream lifecycle ───────────────────────────────────

async def test_create_value_stream(client):
    r = await client.post("/api/v1/business/value-streams", json={"name": "Order to Cash", "stakeholder": "Customer"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Order to Cash"
    assert data["stakeholder"] == "Customer"


async def test_value_stream_full_lifecycle(client):
    r = await client.post("/api/v1/business/value-streams", json={"name": "Order to Cash"})
    vs_id = r.json()["id"]

    # Add stages
    s1 = await client.post(f"/api/v1/business/value-streams/{vs_id}/stages", json={"name": "Order Capture", "position": 0})
    assert s1.status_code == 201
    s1_id = s1.json()["id"]

    s2 = await client.post(f"/api/v1/business/value-streams/{vs_id}/stages", json={"name": "Fulfilment", "position": 1})
    s2_id = s2.json()["id"]

    s3 = await client.post(f"/api/v1/business/value-streams/{vs_id}/stages", json={"name": "Invoicing", "position": 2})
    s3_id = s3.json()["id"]

    # Get with stages
    r_detail = await client.get(f"/api/v1/business/value-streams/{vs_id}")
    assert r_detail.status_code == 200
    stages = r_detail.json()["stages"]
    assert len(stages) == 3
    assert [s["name"] for s in stages] == ["Order Capture", "Fulfilment", "Invoicing"]

    # Reorder stages
    r_reorder = await client.put(
        f"/api/v1/business/value-streams/{vs_id}/stages",
        json={"stages": [
            {"id": s3_id, "name": "Invoicing", "description": None},
            {"id": s1_id, "name": "Order Capture", "description": None},
            {"id": s2_id, "name": "Fulfilment", "description": None},
        ]},
    )
    assert r_reorder.status_code == 200
    reordered = r_reorder.json()["stages"]
    assert reordered[0]["name"] == "Invoicing"
    assert reordered[1]["name"] == "Order Capture"

    # Edit a stage
    r_edit = await client.put(
        f"/api/v1/business/value-streams/{vs_id}/stages/{s1_id}",
        json={"name": "Order Intake"},
    )
    assert r_edit.status_code == 200
    assert r_edit.json()["name"] == "Order Intake"

    # Delete a stage
    r_del_stage = await client.delete(f"/api/v1/business/value-streams/{vs_id}/stages/{s3_id}")
    assert r_del_stage.status_code == 204

    r_detail2 = await client.get(f"/api/v1/business/value-streams/{vs_id}")
    assert len(r_detail2.json()["stages"]) == 2


# ── Scenario 5: Cascade delete of stages ─────────────────────────────────────

async def test_delete_value_stream_cascades_stages(client):
    r = await client.post("/api/v1/business/value-streams", json={"name": "VS Cascade"})
    vs_id = r.json()["id"]

    for i, name in enumerate(["Stage A", "Stage B", "Stage C"]):
        await client.post(f"/api/v1/business/value-streams/{vs_id}/stages", json={"name": name, "position": i})

    r_del = await client.delete(f"/api/v1/business/value-streams/{vs_id}")
    assert r_del.status_code == 204

    r_get = await client.get(f"/api/v1/business/value-streams/{vs_id}")
    assert r_get.status_code == 404


async def test_value_stream_not_found(client):
    r = await client.get("/api/v1/business/value-streams/no-such-id")
    assert r.status_code == 404


# ── Scenario 6: Capability–Design Links (ADP-SPEC-034 US1) ───────────────────

async def _create_design(client, title: str = "Test Design") -> str:
    """Create a minimal design and return its id."""
    r = await client.post("/api/v1/designs", json={"title": title, "description": None})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_capability(client, name: str = "Order Processing") -> str:
    r = await client.post("/api/v1/business/capabilities", json={"name": name, "level": 1})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_value_stream(client, name: str = "Order to Cash") -> str:
    r = await client.post("/api/v1/business/value-streams", json={"name": name, "stakeholder": "Finance"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_link_design_to_capability(client):
    cap_id = await _create_capability(client, "Cap Link Test")
    des_id = await _create_design(client, "Design Link Test")

    r = await client.post(f"/api/v1/business/capabilities/{cap_id}/designs", json={"design_id": des_id})
    assert r.status_code == 201
    items = r.json()["items"]
    assert any(i["design_id"] == des_id for i in items)


async def test_list_designs_linked_to_capability(client):
    cap_id = await _create_capability(client, "Cap List Test")
    des_id = await _create_design(client, "Design List Test")
    await client.post(f"/api/v1/business/capabilities/{cap_id}/designs", json={"design_id": des_id})

    r = await client.get(f"/api/v1/business/capabilities/{cap_id}/designs")
    assert r.status_code == 200
    assert any(i["design_id"] == des_id for i in r.json()["items"])


async def test_unlink_design_from_capability(client):
    cap_id = await _create_capability(client, "Cap Unlink Test")
    des_id = await _create_design(client, "Design Unlink Test")
    await client.post(f"/api/v1/business/capabilities/{cap_id}/designs", json={"design_id": des_id})

    r = await client.delete(f"/api/v1/business/capabilities/{cap_id}/designs/{des_id}")
    assert r.status_code == 204

    r_list = await client.get(f"/api/v1/business/capabilities/{cap_id}/designs")
    assert all(i["design_id"] != des_id for i in r_list.json()["items"])


async def test_duplicate_capability_link_returns_409(client):
    cap_id = await _create_capability(client, "Cap Dup Test")
    des_id = await _create_design(client, "Design Dup Test")
    await client.post(f"/api/v1/business/capabilities/{cap_id}/designs", json={"design_id": des_id})

    r = await client.post(f"/api/v1/business/capabilities/{cap_id}/designs", json={"design_id": des_id})
    assert r.status_code == 409


async def test_link_to_nonexistent_capability_returns_404(client):
    des_id = await _create_design(client, "Design 404 Cap Test")
    r = await client.post("/api/v1/business/capabilities/nonexistent-id/designs", json={"design_id": des_id})
    assert r.status_code == 404


async def test_link_nonexistent_design_to_capability_returns_404(client):
    cap_id = await _create_capability(client, "Cap 404 Des Test")
    r = await client.post(f"/api/v1/business/capabilities/{cap_id}/designs", json={"design_id": "nonexistent-design"})
    assert r.status_code == 404


# ── Scenario 7: Value Stream–Design Links (ADP-SPEC-034 US2) ─────────────────

async def test_link_design_to_value_stream(client):
    vs_id = await _create_value_stream(client, "VS Link Test")
    des_id = await _create_design(client, "Design VS Link Test")

    r = await client.post(f"/api/v1/business/value-streams/{vs_id}/designs", json={"design_id": des_id})
    assert r.status_code == 201
    assert any(i["design_id"] == des_id for i in r.json()["items"])


async def test_list_designs_linked_to_value_stream(client):
    vs_id = await _create_value_stream(client, "VS List Test")
    des_id = await _create_design(client, "Design VS List Test")
    await client.post(f"/api/v1/business/value-streams/{vs_id}/designs", json={"design_id": des_id})

    r = await client.get(f"/api/v1/business/value-streams/{vs_id}/designs")
    assert r.status_code == 200
    assert any(i["design_id"] == des_id for i in r.json()["items"])


async def test_unlink_design_from_value_stream(client):
    vs_id = await _create_value_stream(client, "VS Unlink Test")
    des_id = await _create_design(client, "Design VS Unlink Test")
    await client.post(f"/api/v1/business/value-streams/{vs_id}/designs", json={"design_id": des_id})

    r = await client.delete(f"/api/v1/business/value-streams/{vs_id}/designs/{des_id}")
    assert r.status_code == 204

    r_list = await client.get(f"/api/v1/business/value-streams/{vs_id}/designs")
    assert all(i["design_id"] != des_id for i in r_list.json()["items"])


async def test_duplicate_vs_link_returns_409(client):
    vs_id = await _create_value_stream(client, "VS Dup Test")
    des_id = await _create_design(client, "Design VS Dup Test")
    await client.post(f"/api/v1/business/value-streams/{vs_id}/designs", json={"design_id": des_id})

    r = await client.post(f"/api/v1/business/value-streams/{vs_id}/designs", json={"design_id": des_id})
    assert r.status_code == 409


async def test_link_to_nonexistent_vs_returns_404(client):
    des_id = await _create_design(client, "Design 404 VS Test")
    r = await client.post("/api/v1/business/value-streams/nonexistent-vs/designs", json={"design_id": des_id})
    assert r.status_code == 404


# ── Scenario 8: Design Business Context — Reverse Lookup (ADP-SPEC-034 US3) ──

async def test_design_context_empty_when_no_links(client):
    des_id = await _create_design(client, "Design Context Empty")
    r = await client.get(f"/api/v1/business/designs/{des_id}/context")
    assert r.status_code == 200
    data = r.json()
    assert data["design_id"] == des_id
    assert data["capabilities"] == []
    assert data["value_streams"] == []


async def test_design_context_shows_linked_capability(client):
    cap_id = await _create_capability(client, "Cap Context Test")
    des_id = await _create_design(client, "Design Context Cap")
    await client.post(f"/api/v1/business/capabilities/{cap_id}/designs", json={"design_id": des_id})

    r = await client.get(f"/api/v1/business/designs/{des_id}/context")
    assert r.status_code == 200
    cap_ids = [c["capability_id"] for c in r.json()["capabilities"]]
    assert cap_id in cap_ids


async def test_design_context_shows_linked_value_stream(client):
    vs_id = await _create_value_stream(client, "VS Context Test")
    des_id = await _create_design(client, "Design Context VS")
    await client.post(f"/api/v1/business/value-streams/{vs_id}/designs", json={"design_id": des_id})

    r = await client.get(f"/api/v1/business/designs/{des_id}/context")
    assert r.status_code == 200
    vs_ids = [v["value_stream_id"] for v in r.json()["value_streams"]]
    assert vs_id in vs_ids


async def test_design_context_shows_both_cap_and_vs(client):
    cap_id = await _create_capability(client, "Cap Both Test")
    vs_id = await _create_value_stream(client, "VS Both Test")
    des_id = await _create_design(client, "Design Both Test")
    await client.post(f"/api/v1/business/capabilities/{cap_id}/designs", json={"design_id": des_id})
    await client.post(f"/api/v1/business/value-streams/{vs_id}/designs", json={"design_id": des_id})

    r = await client.get(f"/api/v1/business/designs/{des_id}/context")
    assert r.status_code == 200
    data = r.json()
    assert len(data["capabilities"]) >= 1
    assert len(data["value_streams"]) >= 1


async def test_design_context_nonexistent_design_returns_404(client):
    r = await client.get("/api/v1/business/designs/nonexistent-design/context")
    assert r.status_code == 404


async def test_cascade_delete_vs_removes_link_from_context(client):
    vs_id = await _create_value_stream(client, "VS Cascade Context")
    des_id = await _create_design(client, "Design Cascade Context")
    await client.post(f"/api/v1/business/value-streams/{vs_id}/designs", json={"design_id": des_id})

    # Delete value stream — cascade removes link
    r_del = await client.delete(f"/api/v1/business/value-streams/{vs_id}")
    assert r_del.status_code == 204

    r_ctx = await client.get(f"/api/v1/business/designs/{des_id}/context")
    assert r_ctx.status_code == 200
    assert all(v["value_stream_id"] != vs_id for v in r_ctx.json()["value_streams"])


# ── ADP-SPEC-035: Domain CRUD helper ─────────────────────────────────────────

async def _create_domain(client, name: str = "Customer", classification: str = "strategic", **kwargs) -> str:
    payload = {"name": name, "classification": classification, **kwargs}
    r = await client.post("/api/v1/business/domains", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── US1: Domain CRUD ──────────────────────────────────────────────────────────

async def test_domain_create_201(client):
    r = await client.post("/api/v1/business/domains", json={
        "name": "Finance Domain",
        "scope_statement": "In: billing. Out: collections.",
        "classification": "strategic",
        "org_unit": "CFO Office",
        "risk_flags": ["PII", "GDPR"],
    })
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Finance Domain"
    assert data["classification"] == "strategic"
    assert data["risk_flags"] == ["PII", "GDPR"]
    assert data["scope_statement"] == "In: billing. Out: collections."
    assert "id" in data


async def test_domain_list_ordered_by_name(client):
    await _create_domain(client, name="Zeta Domain", classification="commodity")
    await _create_domain(client, name="Alpha Domain", classification="differentiating")
    r = await client.get("/api/v1/business/domains")
    assert r.status_code == 200
    names = [d["name"] for d in r.json()["items"]]
    assert names == sorted(names)


async def test_domain_list_capability_count_zero_for_new(client):
    dom_id = await _create_domain(client, name="Fresh Domain", classification="commodity")
    r = await client.get("/api/v1/business/domains")
    assert r.status_code == 200
    dom = next(d for d in r.json()["items"] if d["id"] == dom_id)
    assert dom["capability_count"] == 0


async def test_domain_detail_200(client):
    dom_id = await _create_domain(client, name="Detail Domain", classification="differentiating",
                                   scope_statement="Scope here")
    r = await client.get(f"/api/v1/business/domains/{dom_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["scope_statement"] == "Scope here"
    assert data["capabilities"] == []


async def test_domain_update_200(client):
    dom_id = await _create_domain(client, name="Update Domain", classification="strategic")
    r = await client.put(f"/api/v1/business/domains/{dom_id}", json={
        "scope_statement": "Updated scope",
        "risk_flags": ["CIFIUS"],
    })
    assert r.status_code == 200
    assert r.json()["scope_statement"] == "Updated scope"
    assert r.json()["risk_flags"] == ["CIFIUS"]


async def test_domain_delete_204_capability_survives(client):
    dom_id = await _create_domain(client, name="Delete Domain", classification="commodity")
    cap_id = await _create_capability(client, "Cap For Delete Domain Test")
    # Assign cap to domain (US2 endpoint — tested fully in US2 block; here used as setup)
    r_assign = await client.patch(f"/api/v1/business/capabilities/{cap_id}/domain",
                                   json={"domain_id": dom_id})
    assert r_assign.status_code == 200

    # Delete domain
    r_del = await client.delete(f"/api/v1/business/domains/{dom_id}")
    assert r_del.status_code == 204

    # Domain gone
    assert (await client.get(f"/api/v1/business/domains/{dom_id}")).status_code == 404

    # Capability survives with domain_id null
    r_cap = await client.get(f"/api/v1/business/capabilities/{cap_id}")
    assert r_cap.status_code == 200
    assert r_cap.json()["domain_id"] is None


async def test_domain_not_found(client):
    assert (await client.get("/api/v1/business/domains/nonexistent-domain")).status_code == 404
    assert (await client.put("/api/v1/business/domains/nonexistent-domain",
                              json={"name": "x"})).status_code == 404
    assert (await client.delete("/api/v1/business/domains/nonexistent-domain")).status_code == 404


async def test_domain_invalid_classification(client):
    r = await client.post("/api/v1/business/domains",
                           json={"name": "Bad Domain", "classification": "premium"})
    assert r.status_code == 422


async def test_domain_blank_name(client):
    r = await client.post("/api/v1/business/domains",
                           json={"name": "", "classification": "strategic"})
    assert r.status_code == 422


# ── US2: Capability-Domain Assignment ────────────────────────────────────────

async def test_assign_l1_to_domain(client):
    dom_id = await _create_domain(client, name="Assign Domain", classification="strategic")
    cap_id = await _create_capability(client, "Assignable L1 Cap")
    r = await client.patch(f"/api/v1/business/capabilities/{cap_id}/domain",
                            json={"domain_id": dom_id})
    assert r.status_code == 200
    data = r.json()
    assert data["domain_id"] == dom_id
    assert data["domain_name"] == "Assign Domain"


async def test_assign_clears_previous_domain(client):
    dom_a = await _create_domain(client, name="Domain A", classification="strategic")
    dom_b = await _create_domain(client, name="Domain B", classification="differentiating")
    cap_id = await _create_capability(client, "Cap For Reassign")

    await client.patch(f"/api/v1/business/capabilities/{cap_id}/domain",
                        json={"domain_id": dom_a})

    # Reassign to B
    await client.patch(f"/api/v1/business/capabilities/{cap_id}/domain",
                        json={"domain_id": dom_b})

    r_a = await client.get(f"/api/v1/business/domains/{dom_a}")
    r_b = await client.get(f"/api/v1/business/domains/{dom_b}")
    cap_ids_a = [c["capability_id"] for c in r_a.json()["capabilities"]]
    cap_ids_b = [c["capability_id"] for c in r_b.json()["capabilities"]]
    assert cap_id not in cap_ids_a
    assert cap_id in cap_ids_b


async def test_assign_l2_capability_rejected(client):
    dom_id = await _create_domain(client, name="L2 Reject Domain", classification="commodity")
    cap_l1 = await _create_capability(client, "L1 Parent For L2 Test")
    r_l2 = await client.post("/api/v1/business/capabilities",
                               json={"name": "L2 Child", "level": 2, "parent_id": cap_l1})
    l2_id = r_l2.json()["id"]
    r = await client.patch(f"/api/v1/business/capabilities/{l2_id}/domain",
                            json={"domain_id": dom_id})
    assert r.status_code == 422


async def test_assign_nonexistent_domain_returns_404(client):
    cap_id = await _create_capability(client, "Cap For Bad Domain")
    r = await client.patch(f"/api/v1/business/capabilities/{cap_id}/domain",
                            json={"domain_id": "does-not-exist"})
    assert r.status_code == 404


async def test_clear_domain_assignment(client):
    dom_id = await _create_domain(client, name="Clear Domain", classification="commodity")
    cap_id = await _create_capability(client, "Cap To Clear")
    await client.patch(f"/api/v1/business/capabilities/{cap_id}/domain",
                        json={"domain_id": dom_id})

    r = await client.patch(f"/api/v1/business/capabilities/{cap_id}/domain",
                            json={"domain_id": None})
    assert r.status_code == 200
    assert r.json()["domain_id"] is None
    assert r.json()["domain_name"] is None


async def test_domain_detail_capability_count_after_assign(client):
    dom_id = await _create_domain(client, name="Count Domain", classification="strategic")
    cap_id = await _create_capability(client, "Counted Cap")
    await client.patch(f"/api/v1/business/capabilities/{cap_id}/domain",
                        json={"domain_id": dom_id})

    r_list = await client.get("/api/v1/business/domains")
    dom_item = next(d for d in r_list.json()["items"] if d["id"] == dom_id)
    assert dom_item["capability_count"] == 1

    r_detail = await client.get(f"/api/v1/business/domains/{dom_id}")
    assert len(r_detail.json()["capabilities"]) == 1
    assert r_detail.json()["capabilities"][0]["capability_id"] == cap_id


# ── US3: Stage-Capability Mapping ────────────────────────────────────────────

async def _create_vs_with_stage(client, vs_name: str = "Test VS", stage_name: str = "Stage 1"):
    vs_id = await _create_value_stream(client, vs_name)
    r = await client.post(f"/api/v1/business/value-streams/{vs_id}/stages",
                           json={"name": stage_name, "position": 0})
    assert r.status_code == 201, r.text
    return vs_id, r.json()["id"]


async def test_link_cap_to_stage_201(client):
    vs_id, stage_id = await _create_vs_with_stage(client, "VS Stage Cap 1")
    cap_id = await _create_capability(client, "Stage Cap 1")

    r = await client.post(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities",
        json={"capability_id": cap_id},
    )
    assert r.status_code == 201
    items = r.json()["items"]
    assert any(i["capability_id"] == cap_id for i in items)


async def test_duplicate_stage_cap_returns_409(client):
    vs_id, stage_id = await _create_vs_with_stage(client, "VS Dup Cap")
    cap_id = await _create_capability(client, "Dup Stage Cap")

    await client.post(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities",
        json={"capability_id": cap_id},
    )
    r2 = await client.post(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities",
        json={"capability_id": cap_id},
    )
    assert r2.status_code == 409


async def test_get_stage_capabilities(client):
    vs_id, stage_id = await _create_vs_with_stage(client, "VS Get Caps")
    cap_id = await _create_capability(client, "Get Stage Cap")
    await client.post(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities",
        json={"capability_id": cap_id},
    )

    r = await client.get(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities"
    )
    assert r.status_code == 200
    assert any(i["capability_id"] == cap_id for i in r.json()["items"])


async def test_unlink_stage_cap_204(client):
    vs_id, stage_id = await _create_vs_with_stage(client, "VS Unlink Cap")
    cap_id = await _create_capability(client, "Unlink Stage Cap")
    await client.post(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities",
        json={"capability_id": cap_id},
    )

    r = await client.delete(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities/{cap_id}"
    )
    assert r.status_code == 204

    r_get = await client.get(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities"
    )
    assert not any(i["capability_id"] == cap_id for i in r_get.json()["items"])


async def test_link_nonexistent_stage_returns_404(client):
    vs_id = await _create_value_stream(client, "VS For Bad Stage")
    cap_id = await _create_capability(client, "Cap For Bad Stage")
    r = await client.post(
        f"/api/v1/business/value-streams/{vs_id}/stages/nonexistent-stage/capabilities",
        json={"capability_id": cap_id},
    )
    assert r.status_code == 404


async def test_link_nonexistent_cap_to_stage_returns_404(client):
    vs_id, stage_id = await _create_vs_with_stage(client, "VS For Bad Cap")
    r = await client.post(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities",
        json={"capability_id": "does-not-exist"},
    )
    assert r.status_code == 404


async def test_cascade_delete_stage_removes_stage_cap_links(client):
    vs_id, stage_id = await _create_vs_with_stage(client, "VS Cascade Stage")
    cap_id = await _create_capability(client, "Cap Cascade Stage")
    await client.post(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities",
        json={"capability_id": cap_id},
    )

    # Delete the stage — cascade removes links
    r_del = await client.delete(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}"
    )
    assert r_del.status_code == 204

    # Stage no longer exists so GET 404 (stage gone, links gone)
    r_get = await client.get(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities"
    )
    assert r_get.status_code == 404


async def test_cascade_delete_capability_removes_stage_cap_links(client):
    vs_id, stage_id = await _create_vs_with_stage(client, "VS Cascade Cap")
    cap_id = await _create_capability(client, "Cap Cascade Cap Delete")
    await client.post(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities",
        json={"capability_id": cap_id},
    )

    # Delete the capability
    await client.delete(f"/api/v1/business/capabilities/{cap_id}")

    # Stage-cap link gone (GET returns empty items)
    r_get = await client.get(
        f"/api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities"
    )
    assert r_get.status_code == 200
    assert not any(i["capability_id"] == cap_id for i in r_get.json()["items"])
