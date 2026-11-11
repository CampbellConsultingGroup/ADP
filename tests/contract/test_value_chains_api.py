"""Contract tests for the value chain endpoints (ADP-nag), /api/v1/business/value-chains.

Runs the real router and adp.business.value_chains against an in-memory-style SQLite database,
mirroring test_business_registry_api.py's fixture. A unique index stands in for migration 042's
composite primary key so the duplicate-link (409) path behaves as it does on PostgreSQL.
"""

from __future__ import annotations

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.business import router as brouter
from adp.business import store as bstore

BASE = "/api/v1/business"


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/vc.db")
    async with engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
        await conn.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_vc_activity_cap"
                " ON value_chain_activity_capabilities(activity_id, capability_id)"
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)

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


async def _mk_chain(client, name="Retail", **extra) -> dict:
    resp = await client.post(f"{BASE}/value-chains", json={"name": name, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_activity(client, chain_id, name, category="primary", **extra) -> dict:
    resp = await client.post(
        f"{BASE}/value-chains/{chain_id}/activities",
        json={"name": name, "category": category, **extra},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_cap(client, name) -> dict:
    resp = await client.post(f"{BASE}/capabilities", json={"name": name, "level": 1})
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Chains ────────────────────────────────────────────────────────────────────


async def test_create_list_get_update_delete_chain(client):
    chain = await _mk_chain(client, description="Stores and online")
    assert chain["margin_label"] == "Margin"
    assert set(chain) == {
        "id", "name", "description", "margin_label", "position", "created_at", "updated_at",
    }

    listed = (await client.get(f"{BASE}/value-chains")).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == chain["id"]

    detail = (await client.get(f"{BASE}/value-chains/{chain['id']}")).json()
    assert detail["primary_activities"] == [] and detail["support_activities"] == []

    resp = await client.put(
        f"{BASE}/value-chains/{chain['id']}", json={"name": "Retail EU", "margin_label": "Profit"}
    )
    assert resp.status_code == 200
    assert (resp.json()["name"], resp.json()["margin_label"]) == ("Retail EU", "Profit")

    assert (await client.delete(f"{BASE}/value-chains/{chain['id']}")).status_code == 204
    assert (await client.get(f"{BASE}/value-chains/{chain['id']}")).status_code == 404


@pytest.mark.parametrize(
    "body",
    [{"name": "  "}, {"name": "x", "margin_label": ""}, {"name": "x", "unexpected": 1}, {}],
)
async def test_create_chain_rejects_invalid_bodies(client, body):
    assert (await client.post(f"{BASE}/value-chains", json=body)).status_code == 422


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/value-chains/nope"),
        ("put", "/value-chains/nope"),
        ("delete", "/value-chains/nope"),
        ("post", "/value-chains/nope/activities"),
        ("put", "/value-chains/nope/activities"),
        ("put", "/value-chains/nope/activities/nope"),
        ("delete", "/value-chains/nope/activities/nope"),
        ("get", "/value-chains/nope/activities/nope/capabilities"),
    ],
)
async def test_unknown_chain_or_activity_is_404(client, method, path):
    bodies = {
        "put /value-chains/nope": {"name": "x"},
        "post /value-chains/nope/activities": {"name": "x", "category": "primary"},
        "put /value-chains/nope/activities": {"category": "primary", "activity_ids": []},
        "put /value-chains/nope/activities/nope": {"name": "x"},
    }
    body = bodies.get(f"{method} {path}")
    kwargs = {"json": body} if body is not None else {}
    resp = await client.request(method.upper(), f"{BASE}{path}", **kwargs)
    assert resp.status_code == 404, resp.text


# ── Activities ────────────────────────────────────────────────────────────────


async def test_activities_appear_in_their_category_in_order(client):
    chain = await _mk_chain(client)
    for name in ["Inbound Logistics", "Operations", "Outbound Logistics"]:
        await _mk_activity(client, chain["id"], name)
    await _mk_activity(client, chain["id"], "Procurement", "support")

    detail = (await client.get(f"{BASE}/value-chains/{chain['id']}")).json()
    assert [(a["name"], a["position"]) for a in detail["primary_activities"]] == [
        ("Inbound Logistics", 0), ("Operations", 1), ("Outbound Logistics", 2),
    ]
    assert [a["name"] for a in detail["support_activities"]] == ["Procurement"]
    assert detail["primary_activities"][0]["capabilities"] == []


async def test_activity_with_unknown_category_is_422(client):
    chain = await _mk_chain(client)
    resp = await client.post(
        f"{BASE}/value-chains/{chain['id']}/activities", json={"name": "x", "category": "core"}
    )
    assert resp.status_code == 422


async def test_move_activity_to_the_other_category(client):
    chain = await _mk_chain(client)
    a = await _mk_activity(client, chain["id"], "Technology")
    resp = await client.put(
        f"{BASE}/value-chains/{chain['id']}/activities/{a['id']}", json={"category": "support"}
    )
    assert resp.status_code == 200 and resp.json()["category"] == "support"
    detail = (await client.get(f"{BASE}/value-chains/{chain['id']}")).json()
    assert detail["primary_activities"] == []
    assert [x["name"] for x in detail["support_activities"]] == ["Technology"]


async def test_reorder_activities(client):
    chain = await _mk_chain(client)
    ids = [(await _mk_activity(client, chain["id"], n))["id"] for n in ["A", "B", "C"]]
    resp = await client.put(
        f"{BASE}/value-chains/{chain['id']}/activities",
        json={"category": "primary", "activity_ids": [ids[2], ids[0], ids[1]]},
    )
    assert resp.status_code == 200
    assert [a["name"] for a in resp.json()["primary_activities"]] == ["C", "A", "B"]


async def test_reorder_with_a_mismatched_id_list_is_422(client):
    chain = await _mk_chain(client)
    a = await _mk_activity(client, chain["id"], "A")
    await _mk_activity(client, chain["id"], "B")
    resp = await client.put(
        f"{BASE}/value-chains/{chain['id']}/activities",
        json={"category": "primary", "activity_ids": [a["id"]]},
    )
    assert resp.status_code == 422


async def test_delete_activity(client):
    chain = await _mk_chain(client)
    a = await _mk_activity(client, chain["id"], "A")
    path = f"{BASE}/value-chains/{chain['id']}/activities/{a['id']}"
    assert (await client.delete(path)).status_code == 204
    assert (await client.delete(path)).status_code == 404


# ── Activity capabilities ─────────────────────────────────────────────────────


async def test_link_list_unlink_capability(client):
    chain = await _mk_chain(client)
    a = await _mk_activity(client, chain["id"], "Operations")
    cap = await _mk_cap(client, "Inventory Management")
    path = f"{BASE}/value-chains/{chain['id']}/activities/{a['id']}/capabilities"

    resp = await client.post(path, json={"capability_id": cap["id"]})
    assert resp.status_code == 201
    assert resp.json()["items"][0]["name"] == "Inventory Management"

    detail = (await client.get(f"{BASE}/value-chains/{chain['id']}")).json()
    linked = detail["primary_activities"][0]["capabilities"]
    assert [c["capability_id"] for c in linked] == [cap["id"]]

    assert (await client.post(path, json={"capability_id": cap["id"]})).status_code == 409
    assert (await client.delete(f"{path}/{cap['id']}")).status_code == 204
    assert (await client.delete(f"{path}/{cap['id']}")).status_code == 404
    assert (await client.get(path)).json()["items"] == []


async def test_link_unknown_capability_is_404(client):
    chain = await _mk_chain(client)
    a = await _mk_activity(client, chain["id"], "Operations")
    resp = await client.post(
        f"{BASE}/value-chains/{chain['id']}/activities/{a['id']}/capabilities",
        json={"capability_id": "nope"},
    )
    assert resp.status_code == 404
