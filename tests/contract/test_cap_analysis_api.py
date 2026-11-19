"""Contract tests for capability-model analysis (938-capability-model-analysis, ADP-6et.2).

Runs the real app against a SQLite file with a small Store POS model built through the API:

    Sales (L1) > In-Store (L2) > Process Checkout, Apply Promotions (L3)
    Basket Calculation -> Offline Sync          (realized by Store POS)
    Price Rule Evaluation -> Caching            (realized by Store POS)
    Online Promotion -> Caching                 (realized by Commerce; also serves Apply Promotions)
"""

from __future__ import annotations

import logging

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import app_capabilities_router as acrouter
from adp.application import router as arouter
from adp.application import store as astore
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import ActionType, PersonaRole

AC = "/api/v1/application-capabilities"
AN = f"{AC}/analysis"


def _numeric_values(node: object) -> list[float]:
    """Every JSON value in ``node`` that reads as a number (strings like "1000.00" included)."""
    if isinstance(node, dict):
        return [v for child in node.values() for v in _numeric_values(child)]
    if isinstance(node, list):
        return [v for child in node for v in _numeric_values(child)]
    if isinstance(node, bool) or node is None:
        return []
    try:
        return [float(node)]  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return []
TC = "/api/v1/technical-capabilities"
APPS = "/api/v1/applications"


@pytest.fixture()
async def ctx(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/cap_analysis.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        for cid, name, level, parent in (
            ("b1", "Sales", 1, None),
            ("b2", "In-Store", 2, "b1"),
            ("b3", "Process Checkout", 3, "b2"),
            ("b4", "Apply Promotions", 3, "b2"),
            ("b5", "Process Returns", 3, "b2"),
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
        ids = await _seed(c, factory)
        yield app, c, ids
    await engine.dispose()


async def _post(client, url, body, expect=201) -> dict:
    resp = await client.post(url, json=body)
    assert resp.status_code == expect, resp.text
    return resp.json() if resp.content else {}


async def _seed(c, factory) -> dict[str, str]:
    t1 = (await _post(c, TC, {"name": "Integration"}))["id"]
    t2 = (await _post(c, TC, {"name": "Data Storage", "parent_id": t1}))["id"]
    sync = (
        await _post(
            c,
            TC,
            {
                "name": "Offline Sync",
                "parent_id": t2,
                "lifecycle_status": "retiring",
                "end_of_life_date": "2027-06-30",
            },
        )
    )["id"]
    cache = (await _post(c, TC, {"name": "Caching", "parent_id": t2}))["id"]
    a1 = (await _post(c, AC, {"name": "Transaction Processing"}))["id"]
    a2 = (await _post(c, AC, {"name": "Checkout", "parent_id": a1}))["id"]
    basket = (await _post(c, AC, {"name": "Basket Calculation", "parent_id": a2}))["id"]
    price = (await _post(c, AC, {"name": "Price Rule Evaluation", "parent_id": a2}))["id"]
    online = (await _post(c, AC, {"name": "Online Promotion", "parent_id": a2}))["id"]
    pos = (await _post(c, APPS, {"name": "Store POS"}))["id"]
    commerce = (await _post(c, APPS, {"name": "Commerce"}))["id"]
    for ac, biz, tc, app in (
        (basket, "b3", sync, pos),
        (price, "b4", cache, pos),
        (online, "b4", cache, commerce),
    ):
        await _post(c, f"{AC}/{ac}/business-capabilities", {"business_capability_id": biz})
        await _post(c, f"{AC}/{ac}/technical-capabilities", {"tech_cap_id": tc})
        await _post(c, f"{AC}/{ac}/applications", {"app_id": app})
    async with factory() as s:
        await s.execute(
            astore._applications.update()
            .where(astore._applications.c.id == pos)
            .values(health_score=2)
        )
        await s.execute(
            astore._applications.update()
            .where(astore._applications.c.id == commerce)
            .values(health_score=4)
        )
        await s.commit()
    assert (await c.put(f"{APPS}/{pos}/risk", json={"security_posture": "weak"})).status_code == 200
    cost = {"acquisition": {"one_time": "1000", "annual": "0"}}
    assert (await c.put(f"{APPS}/{pos}/cost", json=cost)).status_code == 200
    return {
        "sync": sync,
        "cache": cache,
        "t2": t2,
        "basket": basket,
        "pos": pos,
        "commerce": commerce,
    }


def _as(app, role: PersonaRole) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="u", username="u", email="u@localhost", role=role, groups=[]
    )


def _items(body: dict) -> dict[str, dict]:
    return {i["name"]: i for i in body["items"]}


# ── US1 roll-up ───────────────────────────────────────────────────────────────


async def test_business_rollup_shape_and_values(ctx) -> None:
    _, client, _ = ctx
    resp = await client.get(f"{AN}/business-rollup")
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_available"] is True and body["cost_available"] is True
    items = _items(body)
    assert set(items) == {
        "Sales",
        "In-Store",
        "Process Checkout",
        "Apply Promotions",
        "Process Returns",
    }
    assert items["Process Checkout"]["health"]["worst"] == 2
    assert items["Apply Promotions"]["health"]["worst"] == 2  # POS (2) and Commerce (4)
    assert items["Sales"]["health"]["worst"] == 2
    assert items["In-Store"]["health"]["spread"]["2"] == 2
    assert items["In-Store"]["health"]["spread"]["no_data"] == 1  # Process Returns
    assert items["Process Checkout"]["risk"]["worst"] == "high"
    assert items["Process Checkout"]["cost"]["total_tco"] == "1000.00"
    assert items["Apply Promotions"]["cost"]["apps_without_cost"] == 1
    assert items["Process Checkout"]["exposure"]["worst"] == "retiring"
    assert items["Process Returns"]["health"]["worst"] is None
    names = [a["name"] for a in items["Apply Promotions"]["contributing_apps"]]
    assert names == ["Commerce", "Store POS"]


async def test_business_rollup_reviewer_sees_no_cost_or_risk(ctx) -> None:
    app, client, _ = ctx
    _as(app, PersonaRole.REVIEWER)
    resp = await client.get(f"{AN}/business-rollup")
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_available"] is False and body["cost_available"] is False
    assert all(i["risk"] is None and i["cost"] is None for i in body["items"])
    assert all(i["health"] is not None for i in body["items"])
    text = resp.text
    assert "total_tco" not in text and '"high"' not in text
    # The seeded cost (1000) must not appear as any value. Compare parsed numbers, not
    # substrings: the response carries random UUIDs, and one may contain "1000".
    assert 1000 not in _numeric_values(body)


@pytest.mark.parametrize(
    "hidden", [ActionType.READ_APPLICATION_COST, ActionType.READ_APPLICATION_RISK]
)
async def test_business_rollup_gates_are_independent(ctx, monkeypatch, hidden) -> None:
    _, client, _ = ctx
    real = acrouter.is_permitted
    monkeypatch.setattr(
        acrouter, "is_permitted", lambda role, action: action != hidden and real(role, action)
    )
    body = (await client.get(f"{AN}/business-rollup")).json()
    assert body["cost_available"] is (hidden != ActionType.READ_APPLICATION_COST)
    assert body["risk_available"] is (hidden != ActionType.READ_APPLICATION_RISK)
    for item in body["items"]:
        assert (item["cost"] is None) is (hidden == ActionType.READ_APPLICATION_COST)
        assert (item["risk"] is None) is (hidden == ActionType.READ_APPLICATION_RISK)


async def test_retired_application_is_excluded(ctx) -> None:
    _, client, ids = ctx
    assert (
        await client.patch(f"{APPS}/{ids['pos']}", json={"lifecycle_status": "retired"})
    ).status_code == 200
    items = _items((await client.get(f"{AN}/business-rollup")).json())
    assert items["Process Checkout"]["health"]["worst"] is None
    assert [a["name"] for a in items["Process Checkout"]["excluded_retired_apps"]] == ["Store POS"]
    assert items["Apply Promotions"]["health"]["worst"] == 4


# ── US2 lifecycle ─────────────────────────────────────────────────────────────


async def test_tech_cap_lifecycle_patch_and_log(ctx, caplog) -> None:
    _, client, ids = ctx
    caplog.set_level(logging.INFO, logger="adp.application.router")
    resp = await client.patch(
        f"{TC}/{ids['cache']}",
        json={"lifecycle_status": "contained", "end_of_life_date": "2028-01-31"},
    )
    assert resp.status_code == 200
    got = (await client.get(f"{TC}/{ids['cache']}")).json()
    assert got["lifecycle_status"] == "contained" and got["end_of_life_date"] == "2028-01-31"
    lines = [
        r.getMessage() for r in caplog.records if "technical_capability.lifecycle" in r.getMessage()
    ]
    assert len(lines) == 1 and "from=current to=contained" in lines[0]

    caplog.clear()
    assert (
        await client.patch(f"{TC}/{ids['cache']}", json={"name": "Distributed Caching"})
    ).status_code == 200
    assert not [r for r in caplog.records if "technical_capability.lifecycle" in r.getMessage()]

    cleared = await client.patch(f"{TC}/{ids['cache']}", json={"end_of_life_date": None})
    assert (
        cleared.json()["end_of_life_date"] is None
        and cleared.json()["lifecycle_status"] == "contained"
    )


@pytest.mark.parametrize("body", [{"lifecycle_status": "bogus"}, {"lifecycle_status": None}])
async def test_tech_cap_lifecycle_invalid(ctx, body) -> None:
    _, client, ids = ctx
    assert (await client.patch(f"{TC}/{ids['cache']}", json=body)).status_code == 422


async def test_tech_cap_lifecycle_reviewer_cannot_write(ctx) -> None:
    app, client, ids = ctx
    _as(app, PersonaRole.REVIEWER)
    assert (await client.get(f"{TC}/{ids['cache']}")).json()["lifecycle_status"] == "current"
    resp = await client.patch(f"{TC}/{ids['cache']}", json={"lifecycle_status": "retired"})
    assert resp.status_code == 403


# ── US3 impact ────────────────────────────────────────────────────────────────


async def test_impact_pos_chain(ctx) -> None:
    _, client, ids = ctx
    resp = await client.get(f"{AN}/technical-capabilities/{ids['sync']}/impact")
    assert resp.status_code == 200
    body = resp.json()
    assert [a["name"] for a in body["application_capabilities"]] == ["Basket Calculation"]
    assert [a["name"] for a in body["applications"]] == ["Store POS"]
    assert [b["name"] for b in body["business_capabilities"]] == ["Process Checkout"]
    assert [p["name"] for p in body["business_capabilities"][0]["path"]] == ["Sales", "In-Store"]
    for gated in ("tco", "security_posture", "risk", "cost"):
        assert f'"{gated}"' not in resp.text


async def test_impact_l2_covers_children(ctx) -> None:
    _, client, ids = ctx
    body = (await client.get(f"{AN}/technical-capabilities/{ids['t2']}/impact")).json()
    assert {b["name"] for b in body["business_capabilities"]} == {
        "Process Checkout",
        "Apply Promotions",
    }


async def test_impact_unknown_is_404(ctx) -> None:
    _, client, _ = ctx
    assert (await client.get(f"{AN}/technical-capabilities/nope/impact")).status_code == 404


# ── US4 technology dependencies ──────────────────────────────────────────────


async def test_technology_dependencies(ctx) -> None:
    _, client, _ = ctx
    body = (await client.get(f"{AN}/business-capabilities/b3/technology")).json()
    assert [(d["technical"]["name"], d["effective_band"]) for d in body["items"]] == [
        ("Offline Sync", "retiring")
    ]
    parent = (await client.get(f"{AN}/business-capabilities/b2/technology")).json()
    assert {d["via_business_capability"]["name"] for d in parent["items"]} == {
        "Process Checkout",
        "Apply Promotions",
    }
    assert (await client.get(f"{AN}/business-capabilities/nope/technology")).status_code == 404


# ── US5 findings ──────────────────────────────────────────────────────────────


async def test_findings(ctx) -> None:
    app, client, ids = ctx
    body = (await client.get(f"{AN}/findings")).json()
    assert [o["business"]["name"] for o in body["overlaps"]] == ["Apply Promotions"]
    assert [b["name"] for b in body["gaps"]["business_without_app_capability"]] == [
        "Process Returns"
    ]
    assert body["gaps"]["app_capability_without_business"] == []
    assert body["shared"] == [] and body["shared_threshold"] == 3
    for gated in ("tco", "security_posture", "cost"):
        assert f'"{gated}"' not in json_text(body)
    _as(app, PersonaRole.REVIEWER)
    assert (await client.get(f"{AN}/findings")).json() == body

    # Removing the extra realization clears the overlap (SC-003).
    online = next(
        a["via"][0]["id"] for a in body["overlaps"][0]["applications"] if a["name"] == "Commerce"
    )
    app.dependency_overrides.pop(get_current_user, None)
    resp = await client.delete(f"{AC}/{online}/applications/{ids['commerce']}")
    assert resp.status_code == 204
    assert (await client.get(f"{AN}/findings")).json()["overlaps"] == []


def json_text(body: dict) -> str:
    import json

    return json.dumps(body)


# ── 943-mapping-rationale: overlap status, reasons and the redundant list ─────


async def test_findings_overlap_status_and_redundant(ctx) -> None:
    _, client, _ = ctx
    body = (await client.get(f"{AN}/findings")).json()
    overlap = body["overlaps"][0]
    assert overlap["status"] == "needs_attention"
    assert [r["code"] for r in overlap["reasons"]] == ["unclassified"]
    assert body["redundant"] == []
    vias = {a["name"]: (a["id"], a["mappings"][0]["via"]["id"]) for a in overlap["applications"]}
    assert all(a["mappings"][0]["rationale"] is None for a in overlap["applications"])

    async def classify(name: str, rationale: str) -> None:
        app_id, ac_id = vias[name]
        resp = await client.patch(
            f"{AC}/{ac_id}/applications/{app_id}", json={"rationale": rationale}
        )
        assert resp.status_code == 200, resp.text

    await classify("Store POS", "target")
    await classify("Commerce", "tactical")
    overlap = (await client.get(f"{AN}/findings")).json()["overlaps"][0]
    assert (overlap["status"], overlap["reasons"]) == ("explained", [])

    await classify("Commerce", "redundant")
    body = (await client.get(f"{AN}/findings")).json()
    assert [r["code"] for r in body["overlaps"][0]["reasons"]] == ["redundant"]
    assert [g["business"]["name"] for g in body["redundant"]] == ["Apply Promotions"]
    assert body["redundant"][0]["entries"][0]["application"]["name"] == "Commerce"
