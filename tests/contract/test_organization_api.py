"""Contract tests for org units and geography (940-org-units-geography, ADP-55k.1).

Runs the real app against a SQLite file. Fixture order matters (research R2): create
adp.application.store's metadata first (the full ``applications`` table), then the organization
metadata WITHOUT its narrow ``applications`` mirror.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import router as arouter
from adp.application import store as astore
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole
from adp.organization import router as orouter
from adp.organization import store as ostore
from adp.organization.geodata import geography_seed_rows

B = "/api/v1/business"
APPS = "/api/v1/applications"


@pytest.fixture()
async def ctx(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    for mod in (astore, ostore):
        monkeypatch.setattr(mod, "index_entity", _noop)
        monkeypatch.setattr(mod, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/org_api.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
        await conn.run_sync(
            lambda c: ostore._metadata.create_all(
                c,
                tables=[
                    t
                    for t in ostore._metadata.sorted_tables
                    if t.name not in ("applications", "business_capabilities")
                ],
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await ostore.seed_geography(s, datetime.now(timezone.utc))
        await s.commit()

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[orouter._get_session] = _override
    app.dependency_overrides[arouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield app, c
    await engine.dispose()


async def _post(c, url, body, expect=201) -> dict:
    r = await c.post(url, json=body)
    assert r.status_code == expect, r.text
    return r.json() if r.content else {}


def _reviewer(app) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )


async def _app(c, name: str, bu: str | None = None) -> str:
    body: dict = {"name": name}
    if bu is not None:
        body["owning_business_unit"] = bu
    return (await _post(c, APPS, body))["id"]


# ── US1 org units ─────────────────────────────────────────────────────────────


async def test_org_units_crud(ctx) -> None:
    _, c = ctx
    rc = await _post(c, f"{B}/org-units", {"name": "Retail Co"})
    corp = await _post(c, f"{B}/org-units", {"name": "Corporate", "parent_id": rc["id"]})
    fin = await _post(c, f"{B}/org-units", {"name": "Finance", "parent_id": corp["id"]})
    assert (rc["kind"], corp["kind"], fin["kind"]) == ("enterprise", "division", "function")
    assert [p["name"] for p in fin["path"]] == ["Retail Co", "Corporate"]
    await _post(c, f"{B}/org-units", {"name": "Team", "parent_id": fin["id"]}, expect=422)
    await _post(c, f"{B}/org-units", {"name": "retail co"}, expect=409)
    await _post(c, f"{B}/org-units", {"name": "X", "parent_id": "nope"}, expect=404)
    await _post(c, f"{B}/org-units", {"name": "  "}, expect=422)
    listed = (await c.get(f"{B}/org-units")).json()
    assert listed["total"] == 3
    r = await c.patch(f"{B}/org-units/{corp['id']}", json={"name": "Corporate Functions"})
    assert r.status_code == 200 and r.json()["name"] == "Corporate Functions"
    assert (await c.delete(f"{B}/org-units/{rc['id']}")).status_code == 409
    assert (await c.delete(f"{B}/org-units/{fin['id']}")).status_code == 204
    assert (await c.get(f"{B}/org-units/{fin['id']}")).status_code == 404
    assert (await c.patch(f"{B}/org-units/nope", json={"name": "x"})).status_code == 404
    assert (await c.delete(f"{B}/org-units/nope")).status_code == 404


async def test_org_units_reviewer_reads_but_cannot_write(ctx) -> None:
    app, c = ctx
    await _post(c, f"{B}/org-units", {"name": "Retail Co"})
    _reviewer(app)
    assert (await c.get(f"{B}/org-units")).status_code == 200
    assert (await c.post(f"{B}/org-units", json={"name": "Nope"})).status_code == 403
    assert (
        await c.post(f"{B}/org-units/unmatched/resolve", json={"value": "x", "org_unit_id": "y"})
    ).status_code == 403
    assert (
        await c.post(
            f"{B}/geo-hierarchies", json={"name": "Sales", "kind": "sales", "shape": "dag"}
        )
    ).status_code == 403


# ── US2 geography ─────────────────────────────────────────────────────────────


async def test_geographies(ctx) -> None:
    _, c = ctx
    body = (await c.get(f"{B}/geographies")).json()
    assert body["total"] == len(geography_seed_rows(datetime.now(timezone.utc)))
    de = next(g for g in body["items"] if g["code"] == "DE")
    assert [p["name"] for p in de["path"]] == ["Global", "Europe"] and de["kind"] == "country"
    # 946: places and the reference hierarchy are read-only; no geography is created here.
    assert (await c.post(f"{B}/geographies", json={"name": "EMEA"})).status_code == 405
    assert (await c.patch(f"{B}/geographies/geo-m49-150", json={"name": "x"})).status_code == 409
    assert (await c.delete(f"{B}/geographies/geo-DE")).status_code == 409
    assert (await c.patch(f"{B}/geographies/nope", json={"name": "x"})).status_code == 404
    assert (await c.delete(f"{B}/geographies/nope")).status_code == 404


# ── US3 links ─────────────────────────────────────────────────────────────────


async def test_links(ctx) -> None:
    _, c = ctx
    st = await _post(c, f"{B}/org-units", {"name": "Stores"})
    for g in ("geo-US", "geo-CA", "geo-DE"):
        await _post(c, f"{B}/org-units/{st['id']}/geographies", {"geography_id": g})
    await _post(c, f"{B}/org-units/{st['id']}/geographies", {"geography_id": "geo-US"}, expect=409)
    await _post(c, f"{B}/org-units/{st['id']}/geographies", {"geography_id": "geo-ZZ"}, expect=404)
    detail = (await c.get(f"{B}/org-units/{st['id']}")).json()
    assert {g["id"] for g in detail["geographies"]} == {"geo-US", "geo-CA", "geo-DE"}
    rev = (await c.get(f"{B}/geographies/geo-DE/org-units")).json()
    assert [o["name"] for o in rev] == ["Stores"]
    assert (await c.get(f"{B}/geographies/geo-ZZ/org-units")).status_code == 404
    assert (await c.delete(f"{B}/org-units/{st['id']}/geographies/geo-DE")).status_code == 204
    assert (await c.delete(f"{B}/org-units/{st['id']}/geographies/geo-DE")).status_code == 404
    r = await c.patch(f"{B}/org-units/{st['id']}", json={"primary_geography_id": "geo-m49-019"})
    assert r.json()["primary_geography_id"] == "geo-m49-019"
    r = await c.patch(f"{B}/org-units/{st['id']}", json={"primary_geography_id": None})
    assert r.json()["primary_geography_id"] is None


# ── US4 review queue ──────────────────────────────────────────────────────────


async def test_unmatched_and_resolve(ctx, caplog) -> None:
    _, c = ctx
    ids = [await _app(c, f"App {i}", "Store Systems") for i in range(3)]
    odd = await _app(c, "App odd", "Store systems")
    await _app(c, "No BU")
    st = await _post(c, f"{B}/org-units", {"name": "Stores"})
    body = (await c.get(f"{B}/org-units/unmatched")).json()
    assert [(u["value"], u["application_count"]) for u in body["items"]] == [
        ("Store Systems", 3),
        ("Store systems", 1),
    ]

    caplog.set_level(logging.INFO, logger="adp.organization.router")
    r = await c.post(
        f"{B}/org-units/unmatched/resolve", json={"value": "Store Systems", "org_unit_id": st["id"]}
    )
    assert r.status_code == 200 and r.json()["updated_count"] == 3
    assert any("organization.unmatched.resolve" in m and "count=3" in m for m in caplog.messages)
    for app_id in ids:
        app = (await c.get(f"{APPS}/{app_id}")).json()
        assert app["owning_org_unit_id"] == st["id"]
        assert app["owning_business_unit"] == "Store Systems"  # SC-004

    r = await c.post(
        f"{B}/org-units/unmatched/resolve",
        json={"value": "Store systems", "create": {"name": "Store Ops"}},
    )
    assert r.status_code == 200 and r.json()["org_unit"]["name"] == "Store Ops"
    assert (await c.get(f"{APPS}/{odd}")).json()["owning_org_unit_id"] == r.json()["org_unit"]["id"]
    assert (await c.get(f"{B}/org-units/unmatched")).json()["items"] == []

    assert (
        await c.post(f"{B}/org-units/unmatched/resolve", json={"value": "x"})
    ).status_code == 422
    assert (
        await c.post(f"{B}/org-units/unmatched/resolve", json={"value": "x", "org_unit_id": "nope"})
    ).status_code == 404
    assert (
        await c.post(
            f"{B}/org-units/unmatched/resolve", json={"value": "x", "create": {"name": "Stores"}}
        )
    ).status_code == 409


# ── US5 application field ────────────────────────────────────────────────────


async def test_application_owning_org_unit(ctx) -> None:
    _, c = ctx
    st = await _post(c, f"{B}/org-units", {"name": "Stores"})
    app = await _post(c, APPS, {"name": "POS", "owning_org_unit_id": st["id"]})
    assert app["owning_org_unit_id"] == st["id"]
    bad = await c.post(APPS, json={"name": "Bad", "owning_org_unit_id": "nope"})
    assert bad.status_code == 422 and "Org unit 'nope' not found" in bad.text
    r = await c.patch(f"{APPS}/{app['id']}", json={"owning_org_unit_id": None})
    assert r.status_code == 200 and r.json()["owning_org_unit_id"] is None
    r = await c.patch(f"{APPS}/{app['id']}", json={"owning_org_unit_id": "nope"})
    assert r.status_code == 422
    r = await c.patch(f"{APPS}/{app['id']}", json={"owning_org_unit_id": st["id"]})
    assert r.json()["owning_org_unit_id"] == st["id"]
    # Deleting the org unit clears the link and keeps the application (FR-013).
    assert (await c.delete(f"{B}/org-units/{st['id']}")).status_code == 204
    assert (await c.get(f"{APPS}/{app['id']}")).json()["owning_org_unit_id"] is None
