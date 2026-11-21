"""Contract tests for legal entities and typed geography links (947 GEO-02, ADP-bo1.2).

Real app on SQLite: adp.application.store's metadata first (the full ``applications`` table),
then the organization metadata without its narrow mirrors (940 fixture shape).
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
from adp.organization import legal_entities
from adp.organization import router as orouter
from adp.organization import store as ostore

B = "/api/v1/business"
APPS = "/api/v1/applications"
LEI = "529900T8BM49AURSDO55"


@pytest.fixture()
async def ctx(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    for mod in (astore, ostore, legal_entities):
        monkeypatch.setattr(mod, "index_entity", _noop)
        monkeypatch.setattr(mod, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/le_api.db")
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


async def test_relations(ctx) -> None:
    _, c = ctx
    body = (await c.get(f"{B}/geo-link-relations")).json()
    assert set(body["subjects"]) == {"application", "legal_entity", "org_unit"}
    assert [r["relation"] for r in body["subjects"]["application"]] == [
        "deployed_in",
        "stores_data_in",
        "processes_personal_data_of",
        "serves_customers_in",
    ]


async def test_legal_entity_crud(ctx, caplog) -> None:
    _, c = ctx
    caplog.set_level(logging.INFO, logger="adp.organization.router")
    plc = await _post(c, f"{B}/legal-entities", {"name": "Retail Co plc", "lei": LEI})
    gmbh = await _post(c, f"{B}/legal-entities", {"name": "Retail GmbH", "parent_id": plc["id"]})
    assert any("organization.legal_entity.create" in m for m in caplog.messages)
    assert [p["name"] for p in gmbh["path"]] == ["Retail Co plc"]
    await _post(c, f"{B}/legal-entities", {"name": "retail co PLC"}, expect=409)
    await _post(c, f"{B}/legal-entities", {"name": "X", "lei": "BAD"}, expect=422)
    await _post(c, f"{B}/legal-entities", {"name": "X", "parent_id": "nope"}, expect=404)
    listed = (await c.get(f"{B}/legal-entities")).json()
    assert [e["name"] for e in listed["items"]] == ["Retail Co plc", "Retail GmbH"]
    detail = (await c.get(f"{B}/legal-entities/{plc['id']}")).json()
    assert [ch["name"] for ch in detail["children"]] == ["Retail GmbH"]
    r = await c.patch(f"{B}/legal-entities/{plc['id']}", json={"parent_id": gmbh["id"]})
    assert r.status_code == 422 and "subsidiaries" in r.text
    assert (await c.delete(f"{B}/legal-entities/{plc['id']}")).status_code == 409
    r = await c.patch(f"{B}/legal-entities/{gmbh['id']}", json={"registration_number": "HRB 1"})
    assert r.status_code == 200 and r.json()["registration_number"] == "HRB 1"
    assert (await c.delete(f"{B}/legal-entities/{gmbh['id']}")).status_code == 204
    assert (await c.get(f"{B}/legal-entities/{gmbh['id']}")).status_code == 404


async def test_links_to_org_units_and_applications(ctx) -> None:
    _, c = ctx
    le = await _post(c, f"{B}/legal-entities", {"name": "Retail GmbH"})
    ou = await _post(c, f"{B}/org-units", {"name": "Stores"})
    app = await _post(c, APPS, {"name": "Store POS"})
    d = await _post(c, f"{B}/legal-entities/{le['id']}/org-units", {"org_unit_id": ou["id"]})
    assert [o["name"] for o in d["org_units"]] == ["Stores"]
    await _post(c, f"{B}/legal-entities/{le['id']}/org-units", {"org_unit_id": ou["id"]}, 409)
    assert [e["id"] for e in (await c.get(f"{B}/org-units/{ou['id']}/legal-entities")).json()] == [
        le["id"]
    ]
    out = await _post(c, f"{APPS}/{app['id']}/legal-entities", {"legal_entity_id": le["id"]})
    assert [e["name"] for e in out] == ["Retail GmbH"]
    await _post(c, f"{APPS}/nope/legal-entities", {"legal_entity_id": le["id"]}, expect=404)
    assert (await c.get(f"{APPS}/{app['id']}/legal-entities")).json()[0]["id"] == le["id"]
    assert (await c.delete(f"{APPS}/{app['id']}/legal-entities/{le['id']}")).status_code == 204
    assert (await c.delete(f"{APPS}/{app['id']}/legal-entities/{le['id']}")).status_code == 404
    assert (
        await c.delete(f"{B}/legal-entities/{le['id']}/org-units/{ou['id']}")
    ).status_code == 204


@pytest.mark.parametrize(
    ("kind", "relation", "bad_relation"),
    [
        ("application", "processes_personal_data_of", "licensed_in"),
        ("legal_entity", "licensed_in", "deployed_in"),
        ("org_unit", "has_staff_in", "incorporated_in"),
    ],
)
async def test_geo_links(ctx, kind, relation, bad_relation) -> None:
    _, c = ctx
    if kind == "application":
        base = f"{APPS}/{(await _post(c, APPS, {'name': 'POS'}))['id']}"
    elif kind == "legal_entity":
        base = f"{B}/legal-entities/{(await _post(c, f'{B}/legal-entities', {'name': 'Co'}))['id']}"
    else:
        base = f"{B}/org-units/{(await _post(c, f'{B}/org-units', {'name': 'Stores'}))['id']}"
    link = await _post(
        c,
        f"{base}/geo-links",
        {"relation": relation, "geography_id": "geo-DE", "valid_from": "2020-01-01"},
    )
    assert link["geography"]["code"] == "DE" and link["active"]
    await _post(c, f"{base}/geo-links", {"relation": relation, "geography_id": "geo-DE"}, 409)
    r = await c.post(f"{base}/geo-links", json={"relation": bad_relation, "geography_id": "geo-DE"})
    assert r.status_code == 422 and "not allowed" in r.text
    await _post(c, f"{base}/geo-links", {"relation": relation, "geography_id": "geo-ZZ"}, 404)
    r = await c.patch(
        f"{base}/geo-links/{link['id']}",
        json={"valid_from": "2020-01-01", "valid_to": "2021-01-01"},
    )
    assert r.status_code == 200 and not r.json()["active"]
    assert (await c.get(f"{base}/geo-links")).json()["items"] == []
    assert len((await c.get(f"{base}/geo-links?all=true")).json()["items"]) == 1
    then = (await c.get(f"{base}/geo-links?as_of=2020-06-01")).json()
    assert then["as_of"] == "2020-06-01" and len(then["items"]) == 1
    assert (await c.delete(f"{base}/geo-links/{link['id']}")).status_code == 204
    assert (await c.delete(f"{base}/geo-links/{link['id']}")).status_code == 404


async def test_incorporated_in(ctx) -> None:
    _, c = ctx
    le = await _post(c, f"{B}/legal-entities", {"name": "Co"})
    base = f"{B}/legal-entities/{le['id']}/geo-links"
    r = await c.post(base, json={"relation": "incorporated_in", "geography_id": "geo-m49-150"})
    assert r.status_code == 422 and "country" in r.text
    await _post(
        c, base, {"relation": "incorporated_in", "geography_id": "geo-GB", "valid_to": "2020-01-31"}
    )
    await _post(c, base, {"relation": "incorporated_in", "geography_id": "geo-DE"}, expect=409)
    await _post(
        c,
        base,
        {"relation": "incorporated_in", "geography_id": "geo-DE", "valid_from": "2020-01-31"},
    )


async def test_operating_geographies_are_operates_in(ctx) -> None:
    _, c = ctx
    ou = await _post(c, f"{B}/org-units", {"name": "Stores"})
    await _post(c, f"{B}/org-units/{ou['id']}/geographies", {"geography_id": "geo-DE"})
    links = (await c.get(f"{B}/org-units/{ou['id']}/geo-links")).json()["items"]
    assert [(lk["relation"], lk["geography"]["id"]) for lk in links] == [("operates_in", "geo-DE")]
    assert (await c.get(f"{B}/org-units/{ou['id']}")).json()["geography_ids"] == ["geo-DE"]
    assert (await c.delete(f"{B}/org-units/{ou['id']}/geographies/geo-DE")).status_code == 204
    assert (await c.get(f"{B}/org-units/{ou['id']}/geo-links")).json()["items"] == []


async def test_reviewer_reads_but_cannot_write(ctx) -> None:
    app, c = ctx
    le = await _post(c, f"{B}/legal-entities", {"name": "Co"})
    pos = await _post(c, APPS, {"name": "POS"})
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    assert (await c.get(f"{B}/legal-entities")).status_code == 200
    assert (await c.get(f"{APPS}/{pos['id']}/geo-links")).status_code == 200
    assert (await c.post(f"{B}/legal-entities", json={"name": "No"})).status_code == 403
    body = {"relation": "licensed_in", "geography_id": "geo-DE"}
    assert (await c.post(f"{B}/legal-entities/{le['id']}/geo-links", json=body)).status_code == 403
    body = {"relation": "deployed_in", "geography_id": "geo-DE"}
    assert (await c.post(f"{APPS}/{pos['id']}/geo-links", json=body)).status_code == 403
    assert (
        await c.post(f"{APPS}/{pos['id']}/legal-entities", json={"legal_entity_id": le["id"]})
    ).status_code == 403
