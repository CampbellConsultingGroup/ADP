"""Contract tests for geography hierarchies (946 GEO-01, ADP-bo1.1).

Real app on SQLite; business metadata first, then the organization metadata without its narrow
``business_capabilities`` mirror (942 fixture shape), the seeded geography in the 946 shape and
three capabilities.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole
from adp.business import router as brouter
from adp.business import store as bstore
from adp.organization import router as orouter
from adp.organization import store as ostore

B = "/api/v1/business"
NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)
GLOBAL, ASIA, EUROPE = "geo-001", "geo-m49-142", "geo-m49-150"
JP, IN, AU, ZA, DE, FR, IE, GB, NO, BR = (
    "geo-JP", "geo-IN", "geo-AU", "geo-ZA", "geo-DE", "geo-FR", "geo-IE", "geo-GB", "geo-NO",
    "geo-BR",
)
CAPS = [
    ("sell", "Sell", 1, None, 0),
    ("pay", "Payments", 2, "sell", 0),
    ("accept", "Accept Payment", 3, "pay", 0),
]


@pytest.fixture()
async def ctx(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/geo_h.db")
    async with engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
        await conn.run_sync(
            lambda c: ostore._metadata.create_all(
                c,
                tables=[
                    t for t in ostore._metadata.sorted_tables if t.name != "business_capabilities"
                ],
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await ostore.seed_geography(s, NOW)
        for cid, name, level, parent, pos in CAPS:
            await s.execute(
                bstore._capabilities.insert().values(
                    id=cid, name=name, level=level, parent_id=parent, position=pos,
                    created_at=NOW, updated_at=NOW,
                )
            )
        await s.commit()

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[orouter._get_session] = _override
    app.dependency_overrides[brouter._get_session] = _override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield app, c
    await engine.dispose()


async def _ok(resp: httpx.Response, status: int = 200):
    assert resp.status_code == status, resp.text
    return resp.json() if resp.content else None


async def _hierarchy(c, name: str, kind: str, shape: str) -> dict:
    return await _ok(
        await c.post(f"{B}/geo-hierarchies", json={"name": name, "kind": kind, "shape": shape}),
        201,
    )


async def _node(c, h: str, name: str, parent: str | None = None) -> dict:
    body: dict = {"name": name}
    if parent:
        body["parent_id"] = parent
    return await _ok(await c.post(f"{B}/geo-hierarchies/{h}/nodes", json=body), 201)


async def _add(c, h: str, parent: str, children: list[str], expect: int = 201, **dates):
    return await _ok(
        await c.post(
            f"{B}/geo-hierarchies/{h}/memberships",
            json={"parent_id": parent, "child_ids": children, **dates},
        ),
        expect,
    )


# ── US1: existing geography keeps working ──────────────────────────────────────


async def test_reference_hierarchy_is_seeded_and_read_only(ctx) -> None:
    _, c = ctx
    items = (await c.get(f"{B}/geo-hierarchies")).json()["items"]
    ref = next(h for h in items if h["kind"] == "reference")
    assert ref["read_only"] and ref["system_of_record"] == "UN M49" and ref["node_count"] == 6
    detail = (await c.get(f"{B}/geo-hierarchies/{ref['id']}")).json()
    assert {n["name"] for n in detail["nodes"]} >= {"Global", "Europe", "Asia"}
    assert any(m["parent_id"] == EUROPE and m["child_id"] == DE for m in detail["memberships"])

    geos = {g["id"]: g for g in (await c.get(f"{B}/geographies")).json()["items"]}
    assert geos[DE]["entity"] == "place" and geos[DE]["kind"] == "country"
    assert geos[DE]["parent_id"] == EUROPE
    assert [p["name"] for p in geos[DE]["path"]] == ["Global", "Europe"]
    assert geos[EUROPE]["entity"] == "node" and geos[EUROPE]["hierarchy_kind"] == "reference"
    assert geos[GLOBAL]["level"] == 1

    r = await c.post(f"{B}/geo-hierarchies/{ref['id']}/nodes", json={"name": "X"})
    assert r.status_code == 409 and "read-only" in r.json()["detail"]
    await _add(c, ref["id"], EUROPE, [JP], expect=409)


# ── US2: hierarchies, nodes, dated memberships ─────────────────────────────────


async def test_regulatory_dag_with_brexit(ctx, caplog) -> None:
    _, c = ctx
    caplog.set_level(logging.INFO, logger="adp.organization")
    reg = await _hierarchy(c, "Regulatory blocs", "regulatory", "dag")
    eea = await _node(c, reg["id"], "EEA")
    eu = await _node(c, reg["id"], "EU", parent=eea["id"])
    ez = await _node(c, reg["id"], "Eurozone")
    assert eu["entity"] == "node" and eu["hierarchy_name"] == "Regulatory blocs"
    await _add(c, reg["id"], eu["id"], [DE, FR, IE])
    await _add(c, reg["id"], eu["id"], [GB], valid_to="2020-01-31")
    await _add(c, reg["id"], eea["id"], [NO])
    await _add(c, reg["id"], ez["id"], [IE, DE])  # DAG: Ireland in EU and Eurozone

    def members(detail: dict, parent: str) -> set[str]:
        return {
            m["child_id"] for m in detail["memberships"] if m["parent_id"] == parent and m["active"]
        }

    then = (await c.get(f"{B}/geo-hierarchies/{reg['id']}", params={"as_of": "2019-06-01"})).json()
    now = (await c.get(f"{B}/geo-hierarchies/{reg['id']}", params={"as_of": "2026-11-20"})).json()
    assert members(then, eu["id"]) == {DE, FR, IE, GB}
    assert members(now, eu["id"]) == {DE, FR, IE}

    # A cycle is refused; so is a second overlapping identical membership.
    await _add(c, reg["id"], eu["id"], [eea["id"]], expect=422)
    await _add(c, reg["id"], eu["id"], [DE], expect=409)
    # Bad dates.
    await _add(c, reg["id"], ez["id"], [FR], expect=422,
               valid_from="2025-01-01", valid_to="2024-01-01")

    logs = " ".join(r.getMessage() for r in caplog.records)
    assert "geo_hierarchy.create" in logs and "geo_membership.add" in logs


async def test_strict_tree_one_parent_at_a_time(ctx) -> None:
    _, c = ctx
    sales = await _hierarchy(c, "Sales", "sales", "strict_tree")
    apac = await _node(c, sales["id"], "APAC")
    emea = await _node(c, sales["id"], "EMEA")
    await _add(c, sales["id"], apac["id"], [JP], valid_to="2025-01-01")
    r = await c.post(
        f"{B}/geo-hierarchies/{sales['id']}/memberships",
        json={"parent_id": emea["id"], "child_ids": [JP]},
    )
    assert r.status_code == 409 and "already under" in r.json()["detail"]
    moved = await _add(c, sales["id"], emea["id"], [JP], valid_from="2025-01-01")
    # Edit dates, then remove.
    mb = moved[0]["id"]
    await _ok(await c.patch(f"{B}/geo-memberships/{mb}", json={"valid_from": "2025-02-01"}))
    r = await c.patch(f"{B}/geo-memberships/{mb}", json={"valid_from": "2024-06-01"})
    assert r.status_code == 409  # would overlap APAC again
    assert (await c.delete(f"{B}/geo-memberships/{mb}")).status_code == 204
    assert (await c.delete(f"{B}/geo-memberships/{mb}")).status_code == 404

    # A node of another hierarchy can't be a member; a place from the reference tree can.
    reg = await _hierarchy(c, "Reg", "custom", "dag")
    other = await _node(c, reg["id"], "Other")
    await _add(c, sales["id"], emea["id"], [other["id"]], expect=422)


async def test_shape_change_and_deletes(ctx) -> None:
    _, c = ctx
    h = await _hierarchy(c, "Ops", "operational", "dag")
    a = await _node(c, h["id"], "A")
    b = await _node(c, h["id"], "B")
    await _add(c, h["id"], a["id"], [JP])
    await _add(c, h["id"], b["id"], [JP])
    r = await c.patch(f"{B}/geo-hierarchies/{h['id']}", json={"shape": "strict_tree"})
    assert r.status_code == 422 and "two parents" in r.json()["detail"]
    await _ok(await c.patch(f"{B}/geo-hierarchies/{h['id']}", json={"name": "Operations"}))
    assert (await c.post(f"{B}/geo-hierarchies", json={
        "name": "operations", "kind": "custom", "shape": "dag"})).status_code == 409
    assert (await c.post(f"{B}/geo-hierarchies", json={
        "name": "X", "kind": "reference", "shape": "dag"})).status_code == 422
    assert (await c.delete(f"{B}/geo-hierarchies/{h['id']}")).status_code == 409
    for n in (a, b):
        assert (await c.delete(f"{B}/geographies/{n['id']}")).status_code == 204
    assert (await c.delete(f"{B}/geo-hierarchies/{h['id']}")).status_code == 204


async def test_permission_by_kind(ctx) -> None:
    app, c = ctx
    sales = await _hierarchy(c, "Sales", "sales", "strict_tree")
    reg = await _hierarchy(c, "Regulatory", "regulatory", "dag")
    app.dependency_overrides[orouter._can_write_compliance] = lambda: False
    r = await c.post(f"{B}/geo-hierarchies/{reg['id']}/nodes", json={"name": "EU"})
    assert r.status_code == 403 and "write_compliance" in r.json()["detail"]
    assert (await c.post(f"{B}/geo-hierarchies", json={
        "name": "Tax", "kind": "tax", "shape": "dag"})).status_code == 403
    await _node(c, sales["id"], "APAC")  # sales needs only business architecture
    app.dependency_overrides.pop(orouter._can_write_compliance)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    assert (await c.post(f"{B}/geo-hierarchies/{sales['id']}/nodes",
                         json={"name": "EMEA"})).status_code == 403
    assert (await c.get(f"{B}/geo-hierarchies")).status_code == 200


# ── US3: any node anywhere, containment across hierarchies ─────────────────────


async def test_nodes_work_as_link_targets(ctx) -> None:
    _, c = ctx
    sales = await _hierarchy(c, "Sales", "sales", "strict_tree")
    apac = await _node(c, sales["id"], "APAC")
    await _add(c, sales["id"], apac["id"], [JP, IN, AU, ZA])

    # Org unit operating in APAC: Japan inside, Brazil and Asia not (Asia has non-APAC countries).
    unit = await _ok(await c.post(f"{B}/org-units", json={"name": "Retail Co"}), 201)
    await _ok(await c.post(f"{B}/org-units/{unit['id']}/geographies",
                           json={"geography_id": apac["id"]}), 201)
    for geo in (JP, BR, ASIA):
        await _ok(await c.post(f"{B}/capability-org-mappings", json={
            "capability_id": "accept", "org_unit_id": unit["id"], "role": "performer",
            "geography_id": geo,
        }), 201)
    views = (await c.get(f"{B}/capability-org-mappings")).json()["items"]
    view = next(v for v in views if v["capability_id"] == "accept")
    notes = {p["geography"]["id"]: p["outside_operating_geographies"] for p in view["performers"]}
    assert notes == {JP: False, BR: True, ASIA: True}

    # Regional heat map: a Japan-only capability applies in APAC, not in Europe.
    await _ok(await c.put(f"{B}/capability-region-scope/accept",
                          json={"region_specific": True, "geography_ids": [JP]}))
    hm = (await c.get(f"{B}/regional-heatmap",
                      params={"geography_ids": f"{apac['id']},{EUROPE}"})).json()
    row = next(r for r in hm["rows"] if r["capability"]["id"] == "accept")
    assert [cell["state"] for cell in row["cells"]] == ["not_assessed", "not_applicable"]
    # Default columns are still the five UN regions.
    default = (await c.get(f"{B}/regional-heatmap")).json()
    assert len(default["columns"]) == 5 and apac["id"] not in [x["id"] for x in default["columns"]]

    # An assessment can name the node; Global is still refused.
    await _ok(await c.put(f"{B}/regional-assessments/accept/{apac['id']}",
                          json={"maturity_level": 4}))
    r = await c.put(f"{B}/regional-assessments/accept/{GLOBAL}", json={"maturity_level": 4})
    assert r.status_code == 422

    # Deleting the node cleans its uses up.
    assert (await c.delete(f"{B}/geographies/{apac['id']}")).status_code == 204
    after = (await c.get(f"{B}/org-units/{unit['id']}")).json()
    assert after["geography_ids"] == []
