"""Contract tests for /api/v1/application-capabilities (937-application-capabilities).

Runs the real app against a SQLite file. Business capabilities are inserted straight into
adp.application.store's narrow business_capabilities mirror (the business router isn't needed).
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import router as arouter
from adp.application import store as astore
from adp.application.app_capability_models import RULE_APP_CAP_L3, RULE_BUSINESS_L3, RULE_TECH_L2_L3
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole

AC = "/api/v1/application-capabilities"
TC = "/api/v1/technical-capabilities"


@pytest.fixture()
async def ctx(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/appcap_api.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        for cid, name, level, parent in (
            ("b1", "Sales & Customer Transactions", 1, None),
            ("b2", "In-Store Transaction Management", 2, "b1"),
            ("b3", "Accept Payment", 3, "b2"),
        ):
            await s.execute(
                astore._biz_caps.insert().values(id=cid, name=name, level=level, parent_id=parent)
            )
        await s.commit()

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[arouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield app, c
    await engine.dispose()


@pytest.fixture()
async def client(ctx):
    return ctx[1]


async def _post(client, url, body, expect=201) -> dict:
    resp = await client.post(url, json=body)
    assert resp.status_code == expect, resp.text
    return resp.json()


async def _branch(client) -> dict[str, str]:
    l1 = (await _post(client, AC, {"name": "Transaction Processing"}))["id"]
    l2 = (await _post(client, AC, {"name": "Payments", "parent_id": l1}))["id"]
    l3 = (await _post(client, AC, {"name": "Tender Authorization", "parent_id": l2}))["id"]
    return {"l1": l1, "l2": l2, "l3": l3}


async def _tech(client) -> dict[str, str]:
    l1 = (await _post(client, TC, {"name": "Integration & Data Services"}))["id"]
    l2 = (await _post(client, TC, {"name": "Security", "parent_id": l1}))["id"]
    l3 = (await _post(client, TC, {"name": "Payment Tokenization (P2PE)", "parent_id": l2}))["id"]
    return {"l1": l1, "l2": l2, "l3": l3}


async def test_crud_and_errors(client) -> None:
    b = await _branch(client)
    listing = (await client.get(AC)).json()
    assert listing["total"] == 3
    assert {i["level"] for i in listing["items"]} == {1, 2, 3}

    assert (await client.post(AC, json={"name": "Deep", "parent_id": b["l3"]})).status_code == 422
    assert (await client.post(AC, json={"name": "x", "parent_id": "nope"})).status_code == 404
    assert (
        await client.post(AC, json={"name": "payments", "parent_id": b["l1"]})
    ).status_code == 409
    assert (await client.post(AC, json={"name": " "})).status_code == 422
    assert (await client.post(AC, json={"name": "x", "level": 2})).status_code == 422  # extra field

    resp = await client.patch(f"{AC}/{b['l2']}", json={"description": "card and cash"})
    assert resp.status_code == 200 and resp.json()["description"] == "card and cash"
    assert (await client.patch(f"{AC}/{b['l2']}", json={"parent_id": "x"})).status_code == 422
    assert (await client.patch(f"{AC}/nope", json={"name": "x"})).status_code == 404

    assert (await client.delete(f"{AC}/{b['l2']}")).status_code == 409  # has children
    assert (await client.delete(f"{AC}/{b['l3']}")).status_code == 204
    assert (await client.get(f"{AC}/{b['l3']}")).status_code == 404
    assert (await client.delete(f"{AC}/{b['l3']}")).status_code == 404


async def test_links_level_rules_and_warning(client) -> None:
    b, t = await _branch(client), await _tech(client)
    app_id = (await _post(client, "/api/v1/applications", {"name": "Store POS"}))["id"]

    detail = (await client.get(f"{AC}/{b['l3']}")).json()
    assert detail["warnings"] == ["missing_technical_capability"]
    gaps = (await client.get(AC, params={"warning": "missing_technical_capability"})).json()
    assert [i["id"] for i in gaps["items"]] == [b["l3"]]

    d = await _post(
        client, f"{AC}/{b['l3']}/business-capabilities", {"business_capability_id": "b3"}
    )
    assert [c["name"] for c in d["business_capabilities"]] == ["Accept Payment"]
    d = await _post(client, f"{AC}/{b['l3']}/technical-capabilities", {"tech_cap_id": t["l3"]})
    assert d["warnings"] == [] and d["technical_capability_count"] == 1
    d = await _post(client, f"{AC}/{b['l3']}/applications", {"app_id": app_id})
    assert [a["name"] for a in d["realized_by"]] == ["Store POS"]

    # Level rules: 422 with the rule message.
    r = await client.post(
        f"{AC}/{b['l2']}/business-capabilities", json={"business_capability_id": "b3"}
    )
    assert r.status_code == 422 and r.json()["detail"] == RULE_APP_CAP_L3
    r = await client.post(
        f"{AC}/{b['l3']}/business-capabilities", json={"business_capability_id": "b2"}
    )
    assert r.status_code == 422 and r.json()["detail"] == RULE_BUSINESS_L3
    r = await client.post(f"{AC}/{b['l3']}/technical-capabilities", json={"tech_cap_id": t["l1"]})
    assert r.status_code == 422 and r.json()["detail"] == RULE_TECH_L2_L3
    # Duplicates and missing ends.
    r = await client.post(f"{AC}/{b['l3']}/technical-capabilities", json={"tech_cap_id": t["l3"]})
    assert r.status_code == 409
    r = await client.post(f"{AC}/{b['l3']}/applications", json={"app_id": "ghost"})
    assert r.status_code == 404

    # Unlink brings the warning back; a second unlink is 404.
    assert (
        await client.delete(f"{AC}/{b['l3']}/technical-capabilities/{t['l3']}")
    ).status_code == 204
    assert (
        await client.delete(f"{AC}/{b['l3']}/technical-capabilities/{t['l3']}")
    ).status_code == 404
    assert (await client.get(f"{AC}/{b['l3']}")).json()["warnings"] == [
        "missing_technical_capability"
    ]
    assert (await client.delete(f"{AC}/{b['l3']}/business-capabilities/b3")).status_code == 204
    assert (await client.delete(f"{AC}/{b['l3']}/applications/{app_id}")).status_code == 204


async def test_reverse_lookups_not_captured_by_id_route(client) -> None:
    b, t = await _branch(client), await _tech(client)
    app_id = (await _post(client, "/api/v1/applications", {"name": "Store POS"}))["id"]
    await _post(client, f"{AC}/{b['l3']}/business-capabilities", {"business_capability_id": "b3"})
    await _post(client, f"{AC}/{b['l3']}/technical-capabilities", {"tech_cap_id": t["l2"]})
    await _post(client, f"{AC}/{b['l3']}/applications", {"app_id": app_id})

    by_biz = (await client.get(f"{AC}/by-business-capability/b3")).json()
    assert [(s["name"], [a["name"] for a in s["realized_by"]]) for s in by_biz] == [
        ("Tender Authorization", ["Store POS"])
    ]
    assert [
        s["name"] for s in (await client.get(f"{AC}/by-technical-capability/{t['l2']}")).json()
    ] == ["Tender Authorization"]
    assert [s["name"] for s in (await client.get(f"{AC}/by-application/{app_id}")).json()] == [
        "Tender Authorization"
    ]
    assert (await client.get(f"{AC}/by-application/unknown")).json() == []


async def test_reviewer_can_read_but_not_write(ctx) -> None:
    app, client = ctx
    await _branch(client)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    assert (await client.get(AC)).status_code == 200
    assert (await client.post(AC, json={"name": "Nope"})).status_code == 403
