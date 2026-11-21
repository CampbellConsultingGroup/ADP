"""Contract tests for framework jurisdiction and applicability (948 GEO-03, ADP-bo1.3).

Real app on SQLite with every store's tables (``tests.support.schema.create_schema``), the 946
geography seed, and a regulatory hierarchy where the EU holds Germany and, until 2020-01-31, the
United Kingdom.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import adp.compliance.jurisdiction  # noqa: F401 -- registers the jurisdiction tables
from adp.application import router as arouter
from adp.application import store as astore
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole
from adp.compliance import router as crouter
from adp.organization import hierarchies, legal_entities
from adp.organization import router as orouter
from adp.organization import store as ostore
from adp.organization.models import AddMemberships, GeoHierarchyCreate, GeoNodeCreate
from tests.support.schema import create_schema

B = "/api/v1/business"
C = "/api/v1/compliance"
APPS = "/api/v1/applications"


@pytest.fixture()
async def ctx(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    for mod in (astore, ostore, legal_entities):
        monkeypatch.setattr(mod, "index_entity", _noop)
        monkeypatch.setattr(mod, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/applicability.db")
    async with engine.begin() as conn:
        await conn.run_sync(create_schema)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await ostore.seed_geography(s, datetime.now(timezone.utc))
        h = await hierarchies.create_hierarchy(
            GeoHierarchyCreate(name="Regulatory blocs", kind="regulatory", shape="dag"), s
        )
        eu = await hierarchies.create_node(h.id, GeoNodeCreate(name="EU"), s)
        await hierarchies.add_memberships(
            h.id, AddMemberships(parent_id=eu.id, child_ids=["geo-DE", "geo-IE"]), s
        )
        await hierarchies.add_memberships(
            h.id,
            AddMemberships(parent_id=eu.id, child_ids=["geo-GB"], valid_to=date(2020, 1, 31)),
            s,
        )
        await s.commit()

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    for r in (orouter, arouter, crouter):
        app.dependency_overrides[r._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield app, c, eu.id
    await engine.dispose()


async def _post(c, url, body, expect=201) -> dict:
    r = await c.post(url, json=body)
    assert r.status_code == expect, r.text
    return r.json() if r.content else {}


async def _framework(c, name="GDPR", **over) -> str:
    body = {
        "name": name,
        "jurisdiction": "European Union",
        "authority": "EU",
        "version": "2016/679",
    }
    return (await _post(c, f"{C}/frameworks", body | over))["id"]


async def test_jurisdiction_get_and_put(ctx, caplog) -> None:
    _, c, eu = ctx
    fw = await _framework(c)
    empty = (await c.get(f"{C}/frameworks/{fw}/jurisdiction")).json()
    assert empty == {"framework_id": fw, "configured": False, "geographies": [], "triggers": []}
    caplog.set_level(logging.INFO, logger="adp.compliance.router")
    body = {
        "geography_ids": [eu, "geo-NO"],
        "triggers": [
            {"subject_type": "application", "relation": "processes_personal_data_of"},
            {"subject_type": "legal_entity", "relation": "has_establishment_in"},
        ],
    }
    r = await c.put(f"{C}/frameworks/{fw}/jurisdiction", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["configured"] and [g["name"] for g in out["geographies"]] == ["EU", "Norway"]
    assert out["triggers"][0]["label"] == "Processes personal data of people in"
    assert any("compliance.framework.jurisdiction" in m for m in caplog.messages)
    bad = {"geography_ids": ["geo-ZZ"], "triggers": []}
    assert (await c.put(f"{C}/frameworks/{fw}/jurisdiction", json=bad)).status_code == 422
    bad = {
        "geography_ids": [],
        "triggers": [{"subject_type": "application", "relation": "licensed_in"}],
    }
    r = await c.put(f"{C}/frameworks/{fw}/jurisdiction", json=bad)
    assert r.status_code == 422 and "not a application relation" in r.text
    assert (await c.get(f"{C}/frameworks/nope/jurisdiction")).status_code == 404


async def test_applicability_end_to_end(ctx) -> None:
    _, c, eu = ctx
    gdpr = await _framework(c, effective_date="2018-05-25")
    await c.put(
        f"{C}/frameworks/{gdpr}/jurisdiction",
        json={
            "geography_ids": [eu],
            "triggers": [{"subject_type": "application", "relation": "processes_personal_data_of"}],
        },
    )
    ins = await _framework(c, name="German insurance supervision", jurisdiction="Germany")
    await c.put(
        f"{C}/frameworks/{ins}/jurisdiction",
        json={
            "geography_ids": ["geo-DE"],
            "triggers": [{"subject_type": "legal_entity", "relation": "licensed_in"}],
        },
    )
    unset = await _framework(c, name="No scope yet")

    crm = await _post(c, APPS, {"name": "CRM"})
    uk_app = await _post(c, APPS, {"name": "UK Loyalty"})
    await _post(
        c,
        f"{APPS}/{crm['id']}/geo-links",
        {"relation": "processes_personal_data_of", "geography_id": "geo-DE"},
    )
    await _post(
        c,
        f"{APPS}/{uk_app['id']}/geo-links",
        {"relation": "processes_personal_data_of", "geography_id": "geo-GB"},
    )
    gmbh = await _post(c, f"{B}/legal-entities", {"name": "Retail GmbH"})
    await _post(
        c,
        f"{B}/legal-entities/{gmbh['id']}/geo-links",
        {"relation": "licensed_in", "geography_id": "geo-DE"},
    )
    await _post(c, f"{APPS}/{crm['id']}/legal-entities", {"legal_entity_id": gmbh["id"]})

    res = (await c.get(f"{C}/applications/{crm['id']}/applicability")).json()
    by = {i["framework"]["name"]: i for i in res["items"]}
    assert by["GDPR"]["status"] == "applies"
    ev = by["GDPR"]["evidence"][0]
    assert (ev["geography"]["code"], ev["jurisdiction_geography"]["name"], ev["how"]) == (
        "DE",
        "EU",
        "inside",
    )
    assert ev["path"] == ["Germany", "EU"] and ev["via_legal_entity"] is None
    ins_ev = by["German insurance supervision"]["evidence"][0]
    assert ins_ev["via_legal_entity"]["name"] == "Retail GmbH" and ins_ev["how"] == "same"
    assert by["No scope yet"]["status"] == "unknown"
    # Ordered: applies, unknown, does not apply.
    assert [i["status"] for i in res["items"]] == ["applies", "applies", "unknown"]

    uk_now = (await c.get(f"{C}/applications/{uk_app['id']}/applicability")).json()
    uk_then = (
        await c.get(f"{C}/applications/{uk_app['id']}/applicability?as_of=2019-06-01")
    ).json()
    gdpr_of = lambda res: next(i for i in res["items"] if i["framework"]["id"] == gdpr)  # noqa: E731
    assert gdpr_of(uk_now)["status"] == "does_not_apply"
    assert gdpr_of(uk_then)["status"] == "applies"
    before = (await c.get(f"{C}/applications/{crm['id']}/applicability?as_of=2017-01-01")).json()
    assert gdpr_of(before)["reason"] == "Not in force until 2018-05-25"

    le = (await c.get(f"{C}/legal-entities/{gmbh['id']}/applicability")).json()
    assert {i["framework"]["name"]: i["status"] for i in le["items"]} == {
        "German insurance supervision": "applies",
        "GDPR": "unknown",
        "No scope yet": "unknown",
    }

    fw = (await c.get(f"{C}/frameworks/{gdpr}/applicability")).json()
    assert fw["configured"] and fw["counts"] == {"applies": 1, "does_not_apply": 1, "unknown": 1}
    assert {(i["subject_type"], i["subject"]["name"], i["status"]) for i in fw["items"]} == {
        ("application", "CRM", "applies"),
        ("application", "UK Loyalty", "does_not_apply"),
        ("legal_entity", "Retail GmbH", "unknown"),
    }
    assert (await c.get(f"{C}/frameworks/{unset}/applicability")).json()["configured"] is False
    assert (await c.get(f"{C}/applications/nope/applicability")).status_code == 404
    assert (await c.get(f"{C}/legal-entities/nope/applicability")).status_code == 404
    assert (await c.get(f"{C}/frameworks/nope/applicability")).status_code == 404


async def test_reviewer_reads_but_cannot_set_jurisdiction(ctx) -> None:
    app, c, eu = ctx
    fw = await _framework(c)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    assert (await c.get(f"{C}/frameworks/{fw}/applicability")).status_code == 200
    r = await c.put(f"{C}/frameworks/{fw}/jurisdiction", json={"geography_ids": [eu]})
    assert r.status_code == 403
