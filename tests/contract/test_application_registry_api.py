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
        health_score=4,
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
        json={"health_score": 2, "r_strategy": "Retire"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["health_score"] == 2
    assert body["r_strategy"] == "Retire"
    assert body["name"] == app["name"]


async def test_patch_application_explicit_null_clears_field(client):
    app = await _mk_app(client, vendor="Acme", health_score=4)
    resp = await client.patch(
        f"/api/v1/applications/{app['id']}",
        json={"vendor": None},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["vendor"] is None          # explicit null cleared it
    assert body["health_score"] == 4       # omitted field unchanged


async def test_patch_application_404(client):
    resp = await client.patch("/api/v1/applications/nope", json={"health_score": 1})
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
