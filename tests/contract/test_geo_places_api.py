"""Contract tests for 949 GEO-04: subdivisions on demand, the place matrix and an application's
geography footprint. Same SQLite fixture shape as the 947 legal entity tests, plus migration
060's seed (custom places and the regulatory blocs)."""

from __future__ import annotations

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
BLOCS = "geoh-regulatory-blocs"


@pytest.fixture()
async def ctx(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    for mod in (astore, ostore, legal_entities):
        monkeypatch.setattr(mod, "index_entity", _noop)
        monkeypatch.setattr(mod, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/places_api.db")
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
        now = datetime.now(timezone.utc)
        await ostore.seed_geography(s, now)
        await ostore.seed_blocs(s, now)
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


async def test_add_a_subdivision_from_the_pinned_list(ctx) -> None:
    _, c = ctx
    catalog = (await c.get(f"{B}/geographies/geo-US/subdivisions")).json()
    assert catalog["country_name"] == "United States of America"
    ca = next(i for i in catalog["items"] if i["code"] == "US-CA")
    assert ca == {"code": "US-CA", "name": "California", "type": "State", "added": False}

    geo = await _post(c, f"{B}/geographies/subdivisions", {"code": "us-ca"})
    assert (geo["id"], geo["name"], geo["code"]) == ("geo-US-CA", "California", "US-CA")
    assert geo["place_type"] == "subdivision" and geo["parent_place_id"] == "geo-US"
    assert geo["parent_id"] == "geo-US"
    assert [p["id"] for p in geo["path"]][-1] == "geo-US"

    await _post(c, f"{B}/geographies/subdivisions", {"code": "US-CA"}, expect=409)
    r = await c.post(f"{B}/geographies/subdivisions", json={"code": "US-ZZ"})
    assert r.status_code == 422 and "pinned" in r.text
    catalog = (await c.get(f"{B}/geographies/geo-US/subdivisions")).json()
    assert next(i for i in catalog["items"] if i["code"] == "US-CA")["added"] is True
    assert (await c.get(f"{B}/geographies/geo-bloc-eu/subdivisions")).status_code == 404
    # Places stay read-only.
    r = await c.patch(f"{B}/geographies/geo-US-CA", json={"name": "Calif."})
    assert r.status_code == 409


async def test_seeded_places_and_blocs(ctx) -> None:
    _, c = ctx
    geos = {g["id"]: g for g in (await c.get(f"{B}/geographies")).json()["items"]}
    assert geos["geo-lloyds"]["place_type"] == "authority"
    assert geos["geo-lloyds"]["parent_place_id"] == "geo-GB"
    assert geos["geo-rest-of-world"]["place_type"] == "residual"
    assert geos["geo-DE"]["place_type"] == "country"
    h = (await c.get(f"{B}/geo-hierarchies/{BLOCS}?as_of=2019-06-01")).json()
    assert h["kind"] == "regulatory" and h["shape"] == "dag" and not h["read_only"]
    gb = [m for m in h["memberships"] if m["child_id"] == "geo-GB"]
    assert {(m["parent_id"], m["valid_to"], m["active"]) for m in gb} == {
        ("geo-bloc-eu", "2020-02-01", True),
        ("geo-bloc-eea", "2020-02-01", True),
    }


async def test_place_matrix(ctx) -> None:
    _, c = ctx
    await _post(c, f"{B}/geographies/subdivisions", {"code": "DE-BY"})

    def cells(body: dict, place: str) -> dict:
        row = next(r for r in body["rows"] if r["place"]["id"] == place)
        return {k: [n["name"] for n in v] for k, v in row["cells"].items()}

    m = (await c.get(f"{B}/geographies/matrix?hierarchy_ids={BLOCS}")).json()
    assert [h["id"] for h in m["hierarchies"]] == [BLOCS]
    assert cells(m, "geo-GB") == {}
    assert cells(m, "geo-DE-BY") == {
        BLOCS: ["European Economic Area", "European Union"]
    }
    ids = [r["place"]["id"] for r in m["rows"]]
    assert ids.index("geo-DE-BY") == ids.index("geo-DE") + 1  # under its country
    m = (await c.get(f"{B}/geographies/matrix?as_of=2019-06-01")).json()
    assert m["hierarchies"][0]["id"] == "geoh-m49"
    assert sorted(cells(m, "geo-GB")) == ["geoh-m49", BLOCS]
    assert (await c.get(f"{B}/geographies/matrix?hierarchy_ids=nope")).status_code == 404


async def test_application_footprint(ctx) -> None:
    _, c = ctx
    await _post(c, f"{B}/geographies/subdivisions", {"code": "US-CA"})
    app = await _post(c, APPS, {"name": "Store POS"})
    base = f"{APPS}/{app['id']}"
    await _post(c, f"{base}/geo-links", {"relation": "deployed_in", "geography_id": "geo-US-CA"})
    await _post(
        c,
        f"{base}/geo-links",
        {"relation": "serves_customers_in", "geography_id": "geo-bloc-eea",
         "valid_from": "2030-01-01"},
    )
    le = await _post(c, f"{B}/legal-entities", {"name": "Retail GmbH"})
    await _post(c, f"{base}/legal-entities", {"legal_entity_id": le["id"]})
    await _post(
        c, f"{B}/legal-entities/{le['id']}/geo-links",
        {"relation": "licensed_in", "geography_id": "geo-DE"},
    )

    fp = (await c.get(f"{base}/geo-footprint")).json()
    by_id = {p["place"]["id"]: p for p in fp["places"]}
    assert sorted(by_id) == ["geo-DE", "geo-US-CA"]  # the EEA link starts in 2030
    de = by_id["geo-DE"]
    assert de["links"][0]["via_legal_entity"]["name"] == "Retail GmbH"
    assert de["links"][0]["relation_label"] == "Licensed in"
    kinds = {p["hierarchy_id"]: [n["name"] for n in p["nodes"]] for p in de["placements"]}
    assert kinds[BLOCS] == ["European Economic Area", "European Union"]
    assert "geoh-m49" in kinds
    ca = by_id["geo-US-CA"]["placements"]
    assert ca[0]["hierarchy_id"] == "geoh-m49"  # through the United States

    later = (await c.get(f"{base}/geo-footprint?as_of=2030-06-01")).json()
    assert len(later["places"]) == 31  # California + the 30 EEA countries (Germany once)
    assert (await c.get(f"{APPS}/nope/geo-footprint")).status_code == 404


async def test_reviewer_cannot_add_a_subdivision(ctx) -> None:
    app, c = ctx
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    assert (await c.get(f"{B}/geographies/matrix")).status_code == 200
    r = await c.post(f"{B}/geographies/subdivisions", json={"code": "US-CA"})
    assert r.status_code == 403
