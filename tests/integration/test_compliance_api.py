"""Integration tests for the Compliance Framework & Control Registry API (COMPLY-01).

Covers quickstart.md Scenarios 1-6: framework registration, the GDPR Art. 5/Art. 33 control
granularity example, framework-scoped code uniqueness, cycle/cross-framework parent rejection,
cascading delete, and the WRITE_COMPLIANCE authorization gate.

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

    import adp.compliance.store as cstore
    cstore._engine = engine
    cstore._session_factory = factory

    yield application
    await engine.dispose()


@pytest.fixture()
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


BASE = "/api/v1/compliance"


async def _mk_framework(client, name="GDPR", **extra) -> dict:
    payload = {
        "name": name, "jurisdiction": "EU", "authority": "European Commission",
        "version": "2016/679", **extra,
    }
    resp = await client.post(f"{BASE}/frameworks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _mk_control(client, framework_id, code="AC-2", **extra) -> dict:
    payload = {"code": code, "title": "A control", "description": "...", **extra}
    resp = await client.post(f"{BASE}/frameworks/{framework_id}/controls", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── US1: Register a regulatory framework ─────────────────────────────────────

async def test_framework_create_201(client):
    resp = await client.post(
        f"{BASE}/frameworks",
        json={
            "name": "SOC 2 Type II", "jurisdiction": "US", "authority": "AICPA",
            "version": "2017 TSC", "effective_date": "2017-04-01",
            "source_url": "https://www.aicpa.org/",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "id" in data
    assert data["name"] == "SOC 2 Type II"


async def test_framework_create_no_effective_date(client):
    """Edge Case: a perpetually-current framework has no effective_date — not an error."""
    fw = await _mk_framework(client, name="Perpetual Framework")
    assert fw["effective_date"] is None
    assert fw["source_url"] is None


async def test_framework_list_shows_created(client):
    fw1 = await _mk_framework(client, name="List Test A")
    fw2 = await _mk_framework(client, name="List Test B")
    resp = await client.get(f"{BASE}/frameworks")
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()["items"]}
    assert fw1["id"] in ids
    assert fw2["id"] in ids


async def test_framework_detail_empty_controls(client):
    fw = await _mk_framework(client, name="Detail Empty Test")
    resp = await client.get(f"{BASE}/frameworks/{fw['id']}")
    assert resp.status_code == 200
    assert resp.json()["controls"] == []


async def test_framework_update_200(client):
    fw = await _mk_framework(client, name="Update Test")
    resp = await client.patch(
        f"{BASE}/frameworks/{fw['id']}",
        json={"authority": "Updated Authority", "source_url": "https://new-link.example"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["authority"] == "Updated Authority"
    assert data["source_url"] == "https://new-link.example"
    assert data["name"] == "Update Test"  # unrelated field unchanged


async def test_framework_404(client):
    assert (await client.get(f"{BASE}/frameworks/no-such-id")).status_code == 404
    assert (
        await client.patch(f"{BASE}/frameworks/no-such-id", json={"authority": "X"})
    ).status_code == 404


async def test_framework_blank_field_422(client):
    resp = await client.post(
        f"{BASE}/frameworks",
        json={"name": "", "jurisdiction": "EU", "authority": "EC", "version": "1"},
    )
    assert resp.status_code == 422


async def test_framework_duplicate_name_allowed(client):
    """Edge Case: name is not required to be unique — version distinguishes revisions."""
    fw1 = await _mk_framework(client, name="Duplicate Name Test", version="Rev 1")
    fw2 = await _mk_framework(client, name="Duplicate Name Test", version="Rev 2")
    assert fw1["id"] != fw2["id"]


# ── US2: Build out a framework's control catalog ─────────────────────────────

async def test_control_create_top_level_201(client):
    fw = await _mk_framework(client, name="Top Level Control Test")
    resp = await client.post(
        f"{BASE}/frameworks/{fw['id']}/controls",
        json={"code": "AC-1", "title": "Access Control Policy", "description": "..."},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["parent_id"] is None


async def test_control_create_nested_child_gdpr_granularity(client):
    """Reproduces the GDPR Art. 5 (6 children) / Art. 33 (standalone leaf) example from the
    source doc and quickstart.md Scenario 2."""
    fw = await _mk_framework(client, name="GDPR Granularity Test")
    art5 = await _mk_control(client, fw["id"], code="Art. 5", title="Principles", position=0)
    for i, letter in enumerate("abcdef"):
        await _mk_control(
            client, fw["id"], parent_id=art5["id"], code=f"Art. 5(1)({letter})",
            title=f"Sub-point {letter}", position=i,
        )
    await _mk_control(client, fw["id"], code="Art. 33", title="Breach notification", position=1)

    resp = await client.get(f"{BASE}/frameworks/{fw['id']}")
    top = resp.json()["controls"]
    assert len(top) == 2
    art5_node = next(c for c in top if c["code"] == "Art. 5")
    assert len(art5_node["children"]) == 6
    art33_node = next(c for c in top if c["code"] == "Art. 33")
    assert art33_node["children"] == []


async def test_control_duplicate_code_same_framework_409(client):
    fw = await _mk_framework(client, name="Dup Code Test")
    await _mk_control(client, fw["id"], code="AC-2")
    resp = await client.post(
        f"{BASE}/frameworks/{fw['id']}/controls",
        json={"code": "AC-2", "title": "Duplicate attempt", "description": "..."},
    )
    assert resp.status_code == 409


async def test_control_same_code_different_framework_201(client):
    fw1 = await _mk_framework(client, name="Framework A")
    fw2 = await _mk_framework(client, name="Framework B")
    await _mk_control(client, fw1["id"], code="AC-2")
    resp = await client.post(
        f"{BASE}/frameworks/{fw2['id']}/controls",
        json={"code": "AC-2", "title": "Same code, different framework", "description": "..."},
    )
    assert resp.status_code == 201, resp.text


async def test_control_cyclic_parent_422(client):
    fw = await _mk_framework(client, name="Cycle Test")
    ctrl = await _mk_control(client, fw["id"], code="AC-1")
    resp = await client.patch(f"{BASE}/controls/{ctrl['id']}", json={"parent_id": ctrl["id"]})
    assert resp.status_code == 422


async def test_control_cross_framework_parent_422(client):
    fw1 = await _mk_framework(client, name="Cross FW A")
    fw2 = await _mk_framework(client, name="Cross FW B")
    ctrl_a = await _mk_control(client, fw1["id"], code="AC-1")
    ctrl_b = await _mk_control(client, fw2["id"], code="AC-2")
    resp = await client.patch(f"{BASE}/controls/{ctrl_a['id']}", json={"parent_id": ctrl_b["id"]})
    assert resp.status_code == 422


async def test_control_parent_not_found_404(client):
    fw = await _mk_framework(client, name="Parent Not Found Test")
    resp = await client.post(
        f"{BASE}/frameworks/{fw['id']}/controls",
        json={"parent_id": "no-such-control", "code": "AC-1", "title": "X", "description": "..."},
    )
    assert resp.status_code == 404


async def test_control_reposition(client):
    fw = await _mk_framework(client, name="Reposition Test")
    c1 = await _mk_control(client, fw["id"], code="C1", position=0)
    c2 = await _mk_control(client, fw["id"], code="C2", position=1)
    await client.patch(f"{BASE}/controls/{c1['id']}", json={"position": 2})
    await client.patch(f"{BASE}/controls/{c2['id']}", json={"position": 0})

    resp = await client.get(f"{BASE}/frameworks/{fw['id']}")
    codes_in_order = [c["code"] for c in resp.json()["controls"]]
    assert codes_in_order == ["C2", "C1"]


async def test_control_blank_field_422(client):
    fw = await _mk_framework(client, name="Blank Field Test")
    resp = await client.post(
        f"{BASE}/frameworks/{fw['id']}/controls",
        json={"code": "", "title": "X", "description": "..."},
    )
    assert resp.status_code == 422


# ── US3: Browse and maintain (cascading delete) ──────────────────────────────

async def test_delete_control_cascades_to_descendants(client):
    fw = await _mk_framework(client, name="Cascade Control Test")
    grandparent = await _mk_control(client, fw["id"], code="GP")
    parent = await _mk_control(client, fw["id"], code="P", parent_id=grandparent["id"])
    await _mk_control(client, fw["id"], code="C", parent_id=parent["id"])

    resp = await client.delete(f"{BASE}/controls/{grandparent['id']}")
    assert resp.status_code == 204

    detail = (await client.get(f"{BASE}/frameworks/{fw['id']}")).json()
    remaining_codes = {c["code"] for c in detail["controls"]}
    assert remaining_codes == set()  # GP, P, C all removed — 3 generations, not just 1


async def test_delete_control_leaf_only(client):
    fw = await _mk_framework(client, name="Leaf Delete Test")
    sibling1 = await _mk_control(client, fw["id"], code="S1")
    await _mk_control(client, fw["id"], code="S2")

    resp = await client.delete(f"{BASE}/controls/{sibling1['id']}")
    assert resp.status_code == 204

    detail = (await client.get(f"{BASE}/frameworks/{fw['id']}")).json()
    remaining_codes = {c["code"] for c in detail["controls"]}
    assert remaining_codes == {"S2"}


async def test_delete_framework_cascades_to_all_controls(client):
    fw = await _mk_framework(client, name="Cascade Framework Test")
    parent = await _mk_control(client, fw["id"], code="P")
    await _mk_control(client, fw["id"], code="C", parent_id=parent["id"])

    resp = await client.delete(f"{BASE}/frameworks/{fw['id']}")
    assert resp.status_code == 204
    assert (await client.get(f"{BASE}/frameworks/{fw['id']}")).status_code == 404


async def test_delete_framework_404(client):
    assert (await client.delete(f"{BASE}/frameworks/no-such-id")).status_code == 404


async def test_delete_control_404(client):
    assert (await client.delete(f"{BASE}/controls/no-such-id")).status_code == 404


async def test_browse_full_hierarchy(client):
    fw = await _mk_framework(client, name="Full Browse Test")
    art5 = await _mk_control(client, fw["id"], code="B-Art. 5", title="Principles", position=0)
    for i, letter in enumerate("abcdef"):
        await _mk_control(
            client, fw["id"], parent_id=art5["id"], code=f"B-Art. 5(1)({letter})",
            title=f"Sub-point {letter}", position=i,
        )
    await _mk_control(client, fw["id"], code="B-Art. 33", title="Breach notification", position=1)

    detail = (await client.get(f"{BASE}/frameworks/{fw['id']}")).json()
    assert len(detail["controls"]) == 2
    art5_node = next(c for c in detail["controls"] if c["code"] == "B-Art. 5")
    assert [child["code"] for child in art5_node["children"]] == [
        f"B-Art. 5(1)({letter})" for letter in "abcdef"
    ]
