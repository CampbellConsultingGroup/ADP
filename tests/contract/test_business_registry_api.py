"""Contract tests for the Business Architecture API (ADP-SPEC-033/034/035).

Runs the /api/v1/business router full-stack against the real
adp.business.store on an in-memory SQLite database, with unique indexes
mirroring the composite primary keys from migrations 008/009 so the
duplicate-link (409) paths behave as they do on PostgreSQL.
"""

from __future__ import annotations

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.business import router as brouter
from adp.business import store as bstore

# Composite PKs from migrations 008/009 (store metadata omits them)
_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_cap_design ON capability_design_links(capability_id, design_id)",
    "CREATE UNIQUE INDEX uq_vs_design ON value_stream_design_links(value_stream_id, design_id)",
    "CREATE UNIQUE INDEX uq_stage_cap ON value_stream_stage_capabilities(stage_id, capability_id)",
]


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/biz.db")
    async with engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
        for ddl in _UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Seed a design row (owned by DesignStore in production)
    async with factory() as session:
        await session.execute(
            bstore._designs.insert().values(
                id="DSN-001", title="Payments Design", lifecycle_status="draft"
            )
        )
        await session.commit()

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[brouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


BASE = "/api/v1/business"


async def _mk_cap(client, name="Billing", level=1, parent_id=None) -> dict:
    resp = await client.post(
        f"{BASE}/capabilities",
        json={"name": name, "level": level, "parent_id": parent_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_vs(client, name="Order to Cash", **extra) -> dict:
    resp = await client.post(f"{BASE}/value-streams", json={"name": name, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_stage(client, vs_id, name="Quote") -> dict:
    resp = await client.post(f"{BASE}/value-streams/{vs_id}/stages", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_domain(client, name="Finance", **extra) -> dict:
    payload = {"name": name, "classification": "strategic", **extra}
    resp = await client.post(f"{BASE}/domains", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Capabilities ──────────────────────────────────────────────────────────────

async def test_capability_crud(client):
    assert (await client.get(f"{BASE}/capabilities")).json()["items"] == []

    cap = await _mk_cap(client)
    assert cap["level"] == 1

    resp = await client.get(f"{BASE}/capabilities/{cap['id']}")
    assert resp.status_code == 200
    assert (await client.get(f"{BASE}/capabilities/nope")).status_code == 404

    resp = await client.put(
        f"{BASE}/capabilities/{cap['id']}", json={"name": "Invoicing", "position": 2}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Invoicing"
    assert (
        await client.put(f"{BASE}/capabilities/nope", json={"name": "X"})
    ).status_code == 404

    assert (await client.delete(f"{BASE}/capabilities/{cap['id']}")).status_code == 204
    assert (await client.delete(f"{BASE}/capabilities/{cap['id']}")).status_code == 404


async def test_capability_hierarchy_rules(client):
    l1 = await _mk_cap(client, name="Sales")
    l2 = await _mk_cap(client, name="Quoting", level=2, parent_id=l1["id"])
    assert l2["parent_id"] == l1["id"]

    # level-1 with a parent / level-2 without one → model-level 422
    resp = await client.post(
        f"{BASE}/capabilities", json={"name": "Bad", "level": 1, "parent_id": l1["id"]}
    )
    assert resp.status_code == 422
    # NOTE: omitting parent_id entirely passes (Pydantic skips validators on
    # defaults); an explicit null is rejected. Gap tracked separately.
    resp = await client.post(
        f"{BASE}/capabilities", json={"name": "Bad", "level": 2, "parent_id": None}
    )
    assert resp.status_code == 422

    # unknown parent → store-level 422
    resp = await client.post(
        f"{BASE}/capabilities", json={"name": "Bad", "level": 2, "parent_id": "nope"}
    )
    assert resp.status_code == 422

    # deleting a capability with children → 409
    assert (await client.delete(f"{BASE}/capabilities/{l1['id']}")).status_code == 409


# ── Value streams and stages ──────────────────────────────────────────────────

async def test_value_stream_crud(client):
    assert (await client.get(f"{BASE}/value-streams")).json()["items"] == []

    vs = await _mk_vs(client, stakeholder="CFO")
    resp = await client.get(f"{BASE}/value-streams/{vs['id']}")
    assert resp.status_code == 200
    assert resp.json()["stages"] == []
    assert (await client.get(f"{BASE}/value-streams/nope")).status_code == 404

    resp = await client.put(
        f"{BASE}/value-streams/{vs['id']}", json={"name": "Procure to Pay"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Procure to Pay"
    assert (
        await client.put(f"{BASE}/value-streams/nope", json={"name": "X"})
    ).status_code == 404

    assert (await client.delete(f"{BASE}/value-streams/{vs['id']}")).status_code == 204
    assert (await client.delete(f"{BASE}/value-streams/{vs['id']}")).status_code == 404


async def test_stage_crud(client):
    vs = await _mk_vs(client)
    stage = await _mk_stage(client, vs["id"])

    assert (
        await client.post(f"{BASE}/value-streams/nope/stages", json={"name": "X"})
    ).status_code == 404

    resp = await client.put(
        f"{BASE}/value-streams/{vs['id']}/stages/{stage['id']}", json={"name": "Bind"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Bind"
    assert (
        await client.put(f"{BASE}/value-streams/nope/stages/{stage['id']}", json={"name": "X"})
    ).status_code == 404
    assert (
        await client.put(f"{BASE}/value-streams/{vs['id']}/stages/nope", json={"name": "X"})
    ).status_code == 404

    resp = await client.delete(f"{BASE}/value-streams/{vs['id']}/stages/{stage['id']}")
    assert resp.status_code == 204
    assert (
        await client.delete(f"{BASE}/value-streams/{vs['id']}/stages/{stage['id']}")
    ).status_code == 404
    assert (
        await client.delete(f"{BASE}/value-streams/nope/stages/{stage['id']}")
    ).status_code == 404


async def test_stage_reorder(client):
    vs = await _mk_vs(client)
    s1 = await _mk_stage(client, vs["id"], name="First")
    s2 = await _mk_stage(client, vs["id"], name="Second")

    resp = await client.put(
        f"{BASE}/value-streams/{vs['id']}/stages",
        json={"stages": [
            {"id": s2["id"], "name": "Second"},
            {"id": s1["id"], "name": "First"},
        ]},
    )
    assert resp.status_code == 200, resp.text
    names = [s["name"] for s in resp.json()["stages"]]
    assert names == ["Second", "First"]

    resp = await client.put(
        f"{BASE}/value-streams/nope/stages", json={"stages": []}
    )
    assert resp.status_code == 404

    resp = await client.put(
        f"{BASE}/value-streams/{vs['id']}/stages",
        json={"stages": [{"id": "nope", "name": "Ghost"}]},
    )
    assert resp.status_code == 422


# ── Design traceability links (ADP-SPEC-034) ──────────────────────────────────

async def test_capability_design_links(client):
    cap = await _mk_cap(client)
    base = f"{BASE}/capabilities/{cap['id']}/designs"

    assert (await client.get(base)).json()["items"] == []
    assert (await client.get(f"{BASE}/capabilities/nope/designs")).status_code == 404

    resp = await client.post(base, json={"design_id": "DSN-001"})
    assert resp.status_code == 201, resp.text
    assert (await client.get(base)).json()["items"][0]["design_id"] == "DSN-001"

    assert (await client.post(base, json={"design_id": "DSN-001"})).status_code == 409
    assert (await client.post(base, json={"design_id": "DSN-999"})).status_code == 404
    assert (
        await client.post(f"{BASE}/capabilities/nope/designs", json={"design_id": "DSN-001"})
    ).status_code == 404

    assert (await client.delete(f"{base}/DSN-001")).status_code == 204
    assert (await client.delete(f"{base}/DSN-001")).status_code == 404
    assert (
        await client.delete(f"{BASE}/capabilities/nope/designs/DSN-001")
    ).status_code == 404


async def test_value_stream_design_links(client):
    vs = await _mk_vs(client)
    base = f"{BASE}/value-streams/{vs['id']}/designs"

    assert (await client.get(base)).json()["items"] == []
    assert (await client.get(f"{BASE}/value-streams/nope/designs")).status_code == 404

    resp = await client.post(base, json={"design_id": "DSN-001"})
    assert resp.status_code == 201, resp.text

    assert (await client.post(base, json={"design_id": "DSN-001"})).status_code == 409
    assert (await client.post(base, json={"design_id": "DSN-999"})).status_code == 404
    assert (
        await client.post(f"{BASE}/value-streams/nope/designs", json={"design_id": "DSN-001"})
    ).status_code == 404

    assert (await client.delete(f"{base}/DSN-001")).status_code == 204
    assert (await client.delete(f"{base}/DSN-001")).status_code == 404


async def test_design_business_context(client):
    cap = await _mk_cap(client)
    vs = await _mk_vs(client)
    await client.post(f"{BASE}/capabilities/{cap['id']}/designs", json={"design_id": "DSN-001"})
    await client.post(f"{BASE}/value-streams/{vs['id']}/designs", json={"design_id": "DSN-001"})

    resp = await client.get(f"{BASE}/designs/DSN-001/context")
    assert resp.status_code == 200
    body = resp.json()
    assert [c["capability_id"] for c in body["capabilities"]] == [cap["id"]]
    assert [v["value_stream_id"] for v in body["value_streams"]] == [vs["id"]]

    assert (await client.get(f"{BASE}/designs/DSN-999/context")).status_code == 404


# ── Domains (ADP-SPEC-035) ────────────────────────────────────────────────────

async def test_domain_crud(client):
    assert (await client.get(f"{BASE}/domains")).json()["items"] == []

    domain = await _mk_domain(client, risk_flags=["pci", "pci", "gdpr"])
    assert domain["risk_flags"] == ["pci", "gdpr"]  # deduped, order preserved

    resp = await client.get(f"{BASE}/domains/{domain['id']}")
    assert resp.status_code == 200
    assert (await client.get(f"{BASE}/domains/nope")).status_code == 404

    resp = await client.put(
        f"{BASE}/domains/{domain['id']}",
        json={"classification": "commodity", "risk_flags": ["sox"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["classification"] == "commodity"
    assert body["risk_flags"] == ["sox"]
    assert (
        await client.put(f"{BASE}/domains/nope", json={"name": "X"})
    ).status_code == 404

    assert (await client.delete(f"{BASE}/domains/{domain['id']}")).status_code == 204
    assert (await client.delete(f"{BASE}/domains/{domain['id']}")).status_code == 404


async def test_domain_invalid_classification_422(client):
    resp = await client.post(
        f"{BASE}/domains", json={"name": "X", "classification": "vital"}
    )
    assert resp.status_code == 422


async def test_capability_domain_assignment(client):
    domain = await _mk_domain(client)
    l1 = await _mk_cap(client)
    l2 = await _mk_cap(client, name="Sub", level=2, parent_id=l1["id"])

    resp = await client.patch(
        f"{BASE}/capabilities/{l1['id']}/domain", json={"domain_id": domain["id"]}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["domain_id"] == domain["id"]

    # clear the assignment
    resp = await client.patch(f"{BASE}/capabilities/{l1['id']}/domain", json={"domain_id": None})
    assert resp.status_code == 200
    assert resp.json()["domain_id"] is None

    # only level-1 capabilities may be assigned
    resp = await client.patch(
        f"{BASE}/capabilities/{l2['id']}/domain", json={"domain_id": domain["id"]}
    )
    assert resp.status_code == 422

    assert (
        await client.patch(f"{BASE}/capabilities/{l1['id']}/domain", json={"domain_id": "nope"})
    ).status_code == 404
    assert (
        await client.patch(f"{BASE}/capabilities/nope/domain", json={"domain_id": domain["id"]})
    ).status_code == 404


# ── Stage-capability links (ADP-SPEC-035) ─────────────────────────────────────

async def test_stage_capability_links(client):
    vs = await _mk_vs(client)
    stage = await _mk_stage(client, vs["id"])
    cap = await _mk_cap(client)
    base = f"{BASE}/value-streams/{vs['id']}/stages/{stage['id']}/capabilities"

    assert (await client.get(base)).json()["items"] == []
    assert (
        await client.get(f"{BASE}/value-streams/{vs['id']}/stages/nope/capabilities")
    ).status_code == 404

    resp = await client.post(base, json={"capability_id": cap["id"]})
    assert resp.status_code == 201, resp.text
    assert resp.json()["items"][0]["capability_id"] == cap["id"]

    assert (await client.post(base, json={"capability_id": cap["id"]})).status_code == 409
    assert (await client.post(base, json={"capability_id": "nope"})).status_code == 404
    assert (
        await client.post(
            f"{BASE}/value-streams/{vs['id']}/stages/nope/capabilities",
            json={"capability_id": cap["id"]},
        )
    ).status_code == 404

    assert (await client.delete(f"{base}/{cap['id']}")).status_code == 204
    assert (await client.delete(f"{base}/{cap['id']}")).status_code == 404
