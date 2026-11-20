"""Contract tests for capability <-> org unit mappings (941-capability-org-mappings, ADP-55k.2).

Runs the real app against a SQLite file. Fixture order: adp.business.store's metadata first (the
full ``business_capabilities`` table), then the organization metadata WITHOUT its narrow
``business_capabilities`` mirror (its narrow ``applications`` mirror stands in for the real one).
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
from adp.business import store as bstore
from adp.organization import router as orouter
from adp.organization import store as ostore

B = "/api/v1/business"
M = f"{B}/capability-org-mappings"
NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)

CAPS = [
    ("sell", "Sell", 1, None, 0),
    ("pay", "Payments", 2, "sell", 0),
    ("accept", "Accept Payment", 3, "pay", 0),
    ("refund", "Refund", 3, "pay", 1),
]


@pytest.fixture()
async def ctx(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(ostore, "index_entity", _noop)
    monkeypatch.setattr(ostore, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/capmap_api.db")
    async with engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
        await conn.run_sync(
            lambda c: ostore._metadata.create_all(
                c,
                tables=[
                    t
                    for t in ostore._metadata.sorted_tables
                    if t.name != "business_capabilities"
                ],
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await ostore.seed_geography(s, NOW)
        for cid, name, level, parent, pos in CAPS:
            await s.execute(
                bstore._capabilities.insert().values(
                    id=cid,
                    name=name,
                    level=level,
                    parent_id=parent,
                    position=pos,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        await s.commit()

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[orouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield app, c
    await engine.dispose()


def _reviewer(app) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )


async def _ou(c, name: str, parent: str | None = None) -> str:
    r = await c.post(f"{B}/org-units", json={"name": name, "parent_id": parent})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add(c, cap: str, ou: str, role: str = "performer", geo: str | None = None, expect=201):
    body = {"capability_id": cap, "org_unit_id": ou, "role": role}
    if geo:
        body["geography_id"] = geo
    r = await c.post(M, json=body)
    assert r.status_code == expect, r.text
    return r.json()


def _views(c_json: dict) -> dict[str, dict]:
    return {v["capability_id"]: v for v in c_json["items"]}


# ── US1 owner ─────────────────────────────────────────────────────────────────


async def test_owner_set_replace_clear_and_inherit(ctx, caplog) -> None:
    _, c = ctx
    rc, st = await _ou(c, "Retail Co"), await _ou(c, "Supply Chain")
    caplog.set_level(logging.INFO, logger="adp.organization")
    r = await c.put(f"{M}/pay/owner", json={"org_unit_id": rc})
    assert r.status_code == 200 and r.json()["owner"]["id"] == rc
    r = await c.put(f"{M}/pay/owner", json={"org_unit_id": st})
    assert r.json()["owner"]["name"] == "Supply Chain"
    views = _views((await c.get(M)).json())
    assert views["accept"]["effective_owner"]["id"] == st
    assert views["accept"]["owner_inherited_from"]["id"] == "pay"
    r = await c.put(f"{M}/pay/owner", json={"org_unit_id": None})
    assert r.status_code == 200 and r.json()["owner"] is None
    logs = " ".join(rec.getMessage() for rec in caplog.records)
    assert "capability_mapping.set_owner capability=pay" in logs
    assert f"previous={rc}" in logs
    assert "capability_mapping.clear_owner capability=pay" in logs


async def test_owner_errors(ctx) -> None:
    app, c = ctx
    rc = await _ou(c, "Retail Co")
    r = await c.put(f"{M}/accept/owner", json={"org_unit_id": rc})
    assert r.status_code == 422 and "L2 or L1" in r.json()["detail"]
    assert (await c.put(f"{M}/nope/owner", json={"org_unit_id": rc})).status_code == 404
    assert (await c.put(f"{M}/pay/owner", json={"org_unit_id": "nope"})).status_code == 422
    assert (await c.put(f"{M}/pay/owner", json={"org_unit_id": rc, "x": 1})).status_code == 422
    _reviewer(app)
    assert (await c.put(f"{M}/pay/owner", json={"org_unit_id": rc})).status_code == 403


# ── US2 performers and contributors ───────────────────────────────────────────


async def test_performers_and_contributors(ctx, caplog) -> None:
    _, c = ctx
    st = await _ou(c, "Stores")
    await c.post(f"{B}/org-units/{st}/geographies", json={"geography_id": "geo-m49-150"})
    caplog.set_level(logging.INFO, logger="adp.organization")
    de = await _add(c, "accept", st, geo="geo-DE")
    br = await _add(c, "accept", st, geo="geo-BR")
    assert de["geography"]["name"] == "Germany" and de["outside_operating_geographies"] is False
    assert br["outside_operating_geographies"] is True
    await _add(c, "accept", st, geo="geo-DE", expect=409)
    contrib = await _add(c, "accept", st, role="contributor")
    view = _views((await c.get(M)).json())["accept"]
    assert len(view["performers"]) == 2 and len(view["contributors"]) == 1
    assert (await c.delete(f"{M}/{contrib['id']}")).status_code == 204
    assert (await c.delete(f"{M}/{contrib['id']}")).status_code == 404
    logs = " ".join(rec.getMessage() for rec in caplog.records)
    assert "capability_mapping.add capability=accept" in logs and "geography=geo-DE" in logs
    assert "capability_mapping.remove mapping=" in logs and "role=contributor" in logs


async def test_mapping_errors(ctx) -> None:
    app, c = ctx
    st = await _ou(c, "Stores")
    r = await c.post(M, json={"capability_id": "pay", "org_unit_id": st, "role": "performer"})
    assert r.status_code == 422 and "mapped at L3" in r.json()["detail"]
    r = await c.post(M, json={"capability_id": "accept", "org_unit_id": st, "role": "owner"})
    assert r.status_code == 422
    r = await c.post(
        M,
        json={
            "capability_id": "accept",
            "org_unit_id": st,
            "role": "contributor",
            "geography_id": "geo-DE",
        },
    )
    assert r.status_code == 422
    await _add(c, "accept", "nope", expect=422)
    await _add(c, "accept", st, geo="geo-ZZ", expect=422)
    await _add(c, "nope", st, expect=404)
    added = await _add(c, "accept", st)
    _reviewer(app)
    await _add(c, "accept", st, role="contributor", expect=403)
    assert (await c.delete(f"{M}/{added['id']}")).status_code == 403


# ── US3 findings ──────────────────────────────────────────────────────────────


async def test_findings_reflect_the_current_mappings(ctx) -> None:
    _, c = ctx
    st, ec = await _ou(c, "Stores"), await _ou(c, "E-commerce")
    f = (await c.get(f"{M}/findings")).json()
    assert [x["id"] for x in f["no_owner"]] == ["sell", "pay"]
    assert [x["id"] for x in f["unmapped"]] == ["accept", "refund"]
    assert f["counts"]["l3_total"] == 2
    await c.put(f"{M}/pay/owner", json={"org_unit_id": st})
    await _add(c, "accept", st)
    await _add(c, "accept", ec)
    f = (await c.get(f"{M}/findings")).json()
    assert [x["id"] for x in f["no_owner"]] == ["sell"]
    assert [x["capability"]["id"] for x in f["shared_service"]] == ["accept"]
    assert f["shared_service"][0]["branches"] == 2
    assert [x["id"] for x in f["owned_no_performer"]] == ["refund"]
    assert f["unmapped"] == []


# ── US4 footprint ─────────────────────────────────────────────────────────────


async def test_footprint(ctx) -> None:
    _, c = ctx
    rc = await _ou(c, "Retail Co")
    st = await _ou(c, "Stores", rc)
    await c.put(f"{M}/pay/owner", json={"org_unit_id": rc})
    await _add(c, "accept", st, geo="geo-DE")
    r = await c.get(f"{B}/org-units/{rc}/footprint")
    assert r.status_code == 200
    fp = r.json()
    assert fp["l3_total"] == 1 and fp["includes_descendants"] is True
    l3 = fp["performs"][0]["l2s"][0]["l3s"][0]
    assert l3["capability"]["name"] == "Accept Payment"
    assert l3["performed_by"][0]["org_unit"]["name"] == "Stores"
    assert l3["performed_by"][0]["geographies"][0]["name"] == "Germany"
    assert [e["capability"]["name"] for e in fp["owns"]] == ["Payments"]
    assert (await c.get(f"{B}/org-units/nope/footprint")).status_code == 404
    # The unmatched route is still a literal route, not an org unit id.
    assert (await c.get(f"{B}/org-units/unmatched")).status_code == 200
