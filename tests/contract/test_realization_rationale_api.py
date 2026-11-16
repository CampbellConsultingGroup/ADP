"""Contract tests for 943-mapping-rationale: POST /{ac_id}/applications with a rationale and
geography, and PATCH /{ac_id}/applications/{app_id}. Real app over SQLite; the organization
metadata supplies the geography tree."""

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
from adp.organization import store as ostore
from adp.organization.geodata import geography_seed_rows

AC = "/api/v1/application-capabilities"
APPS = "/api/v1/applications"
NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)


@pytest.fixture()
async def ctx(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/rationale_api.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
        await conn.run_sync(ostore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(ostore._geographies.insert(), geography_seed_rows(NOW))
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


async def _post(client, url, body, expect=201) -> dict:
    resp = await client.post(url, json=body)
    assert resp.status_code == expect, resp.text
    return resp.json()


async def _setup(client) -> tuple[str, str, str]:
    l1 = (await _post(client, AC, {"name": "Commerce"}))["id"]
    l2 = (await _post(client, AC, {"name": "Promotions", "parent_id": l1}))["id"]
    l3 = (await _post(client, AC, {"name": "Promotion Evaluation", "parent_id": l2}))["id"]
    pos = (await _post(client, APPS, {"name": "Store POS"}))["id"]
    ecom = (await _post(client, APPS, {"name": "Commerce Cloud"}))["id"]
    return l3, pos, ecom


def _by_name(detail: dict) -> dict:
    return {r["name"]: r for r in detail["realized_by"]}


async def test_post_with_rationale_and_geography(ctx) -> None:
    _, client = ctx
    l3, pos, ecom = await _setup(client)
    await _post(client, f"{AC}/{l3}/applications", {"app_id": pos})
    detail = await _post(
        client,
        f"{AC}/{l3}/applications",
        {"app_id": ecom, "rationale": "tactical", "geography_id": "geo-m49-019"},
    )
    rows = _by_name(detail)
    assert rows["Store POS"]["rationale"] is None and rows["Store POS"]["geography"] is None
    assert rows["Commerce Cloud"]["rationale"] == "tactical"
    assert rows["Commerce Cloud"]["geography"]["id"] == "geo-m49-019"


async def test_patch_omit_vs_null(ctx, caplog) -> None:
    _, client = ctx
    l3, pos, _ = await _setup(client)
    await _post(client, f"{AC}/{l3}/applications", {"app_id": pos})
    url = f"{AC}/{l3}/applications/{pos}"

    with caplog.at_level(logging.INFO):
        resp = await client.patch(url, json={"rationale": "target", "geography_id": "geo-DE"})
    assert resp.status_code == 200, resp.text
    row = _by_name(resp.json())["Store POS"]
    assert (row["rationale"], row["geography"]["id"]) == ("target", "geo-DE")
    assert any(
        "app_capability.realization.update" in r.getMessage()
        and "rationale=None->target" in r.getMessage()
        and "geography=None->geo-DE" in r.getMessage()
        for r in caplog.records
    )

    row = _by_name((await client.patch(url, json={"geography_id": None})).json())["Store POS"]
    assert (row["rationale"], row["geography"]) == ("target", None)
    row = _by_name((await client.patch(url, json={"rationale": None})).json())["Store POS"]
    assert row["rationale"] is None


@pytest.mark.parametrize(
    "body",
    [{}, {"rationale": "maybe"}, {"geography_id": "geo-001"}, {"geography_id": "nope"}, {"x": 1}],
)
async def test_patch_refusals(ctx, body) -> None:
    _, client = ctx
    l3, pos, _ = await _setup(client)
    await _post(client, f"{AC}/{l3}/applications", {"app_id": pos})
    resp = await client.patch(f"{AC}/{l3}/applications/{pos}", json=body)
    assert resp.status_code == 422, resp.text


async def test_global_refused_with_rule_message(ctx) -> None:
    _, client = ctx
    l3, pos, _ = await _setup(client)
    resp = await client.post(
        f"{AC}/{l3}/applications", json={"app_id": pos, "geography_id": "geo-001"}
    )
    assert resp.status_code == 422
    assert "No geography already means everywhere" in resp.json()["detail"]


async def test_patch_unknown_link_is_404(ctx) -> None:
    _, client = ctx
    l3, pos, _ = await _setup(client)
    resp = await client.patch(f"{AC}/{l3}/applications/{pos}", json={"rationale": "target"})
    assert resp.status_code == 404


async def test_reviewer_cannot_patch(ctx) -> None:
    app, client = ctx
    l3, pos, _ = await _setup(client)
    await _post(client, f"{AC}/{l3}/applications", {"app_id": pos})
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )
    resp = await client.patch(f"{AC}/{l3}/applications/{pos}", json={"rationale": "target"})
    assert resp.status_code == 403
