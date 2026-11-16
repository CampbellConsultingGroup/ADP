"""Contract tests for regional assessments (942-regional-assessments, ADP-55k.3).

Runs the real app against a SQLite file. Fixture order (as 941): adp.business.store's metadata
first (the full ``business_capabilities`` table, including ``maturity_level``), then the
organization metadata WITHOUT its narrow ``business_capabilities`` mirror.
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
from adp.organization.geodata import geography_seed_rows

B = "/api/v1/business"
RA = f"{B}/regional-assessments"
NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)
EU, AM, BR, DE, GLOBAL = "geo-m49-150", "geo-m49-019", "geo-BR", "geo-DE", "geo-001"

CAPS = [
    ("sell", "Sell", 1, None, 0, 3),
    ("pay", "Payments", 2, "sell", 0, None),
    ("accept", "Accept Payment", 3, "pay", 0, 3),
    ("esocial", "eSocial Reporting", 3, "pay", 1, None),
]


@pytest.fixture()
async def ctx(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    for mod in (ostore, bstore):
        monkeypatch.setattr(mod, "index_entity", _noop)
        monkeypatch.setattr(mod, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/regional_api.db")
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
        await s.execute(ostore._geographies.insert(), geography_seed_rows(NOW))
        for cid, name, level, parent, pos, maturity in CAPS:
            await s.execute(
                bstore._capabilities.insert().values(
                    id=cid,
                    name=name,
                    level=level,
                    parent_id=parent,
                    position=pos,
                    maturity_level=maturity,
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
    app.dependency_overrides[brouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield app, c
    await engine.dispose()


def _reviewer(app) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="r", username="r", email="r@localhost", role=PersonaRole.REVIEWER, groups=[]
    )


async def _put(c, cap: str, geo: str, body: dict, expect: int = 200) -> dict:
    r = await c.put(f"{RA}/{cap}/{geo}", json=body)
    assert r.status_code == expect, r.text
    return r.json()


# ── US1 assessments ────────────────────────────────────────────────────────────


async def test_record_change_remove_and_baseline_untouched(ctx, caplog) -> None:
    _, c = ctx
    caplog.set_level(logging.INFO, logger="adp.organization")
    eu = await _put(c, "accept", EU, {"maturity_level": 4})
    assert eu["geography"]["name"] == "Europe" and eu["maturity_level"] == 4
    br = await _put(c, "accept", BR, {"maturity_level": 2, "note": "eSocial is manual"})
    assert br["geography"]["code"] == "BR" and br["note"] == "eSocial is manual"
    again = await _put(c, "accept", EU, {"maturity_level": 5})
    assert again["id"] == eu["id"] and again["maturity_level"] == 5
    listed = (await c.get(RA, params={"capability_id": "accept"})).json()
    assert listed["total"] == 2
    assert (await c.get(f"{B}/capabilities/accept")).json()["maturity_level"] == 3
    assert (await c.delete(f"{RA}/accept/{BR}")).status_code == 204
    assert (await c.delete(f"{RA}/accept/{BR}")).status_code == 404
    logs = " ".join(rec.getMessage() for rec in caplog.records)
    assert f"regional_assessment.set capability=accept geography={EU} maturity=4" in logs
    assert "note_chars=17" in logs and "eSocial is manual" not in logs
    assert f"regional_assessment.remove capability=accept geography={BR}" in logs


async def test_assessment_errors(ctx) -> None:
    app, c = ctx
    r = await c.put(f"{RA}/accept/{GLOBAL}", json={"maturity_level": 3})
    assert r.status_code == 422 and "baseline" in r.json()["detail"]
    await _put(c, "accept", DE, {}, expect=422)
    await _put(c, "accept", DE, {"maturity_level": 6}, expect=422)
    await _put(c, "accept", DE, {"note": "x" * 1001}, expect=422)
    await _put(c, "nope", DE, {"maturity_level": 3}, expect=404)
    await _put(c, "accept", "geo-ZZ", {"maturity_level": 3}, expect=404)
    await _put(c, "accept", DE, {"maturity_level": 3})
    _reviewer(app)
    await _put(c, "accept", DE, {"maturity_level": 2}, expect=403)
    assert (await c.delete(f"{RA}/accept/{DE}")).status_code == 403


# ── US3 heat map ───────────────────────────────────────────────────────────────


async def test_heatmap(ctx) -> None:
    _, c = ctx
    h = (await c.get(f"{B}/regional-heatmap")).json()
    assert len(h["columns"]) == 5 and h["max_columns"] == 12
    assert [r["capability"]["id"] for r in h["rows"]] == ["sell", "pay", "accept", "esocial"]
    await _put(c, "accept", BR, {"maturity_level": 2})
    h = (await c.get(f"{B}/regional-heatmap", params={"geography_ids": f"{AM},{BR}"})).json()
    assert [col["name"] for col in h["columns"]] == ["Americas", "Brazil"]
    accept = next(r for r in h["rows"] if r["capability"]["id"] == "accept")
    assert accept["baseline"] == 3
    assert [(x["state"], x["maturity_level"], x["delta"]) for x in accept["cells"]] == [
        ("not_assessed", None, None),
        ("assessed", 2, -1),
    ]
    assert (
        await c.get(f"{B}/regional-heatmap", params={"geography_ids": GLOBAL})
    ).status_code == 422
    assert (
        await c.get(f"{B}/regional-heatmap", params={"geography_ids": "nope"})
    ).status_code == 422
    many = ",".join(
        [
            "geo-DE",
            "geo-FR",
            "geo-BR",
            "geo-US",
            "geo-CA",
            "geo-GB",
            "geo-IT",
            "geo-ES",
            "geo-JP",
            "geo-CN",
            "geo-IN",
            "geo-AU",
            "geo-MX",
        ]
    )
    assert (await c.get(f"{B}/regional-heatmap", params={"geography_ids": many})).status_code == 422


# ── US2 region-specific scope ──────────────────────────────────────────────────


async def test_region_scope(ctx, caplog) -> None:
    app, c = ctx
    caplog.set_level(logging.INFO, logger="adp.organization")
    url = f"{B}/capability-region-scope/esocial"
    assert (await c.get(url)).json()["region_specific"] is False
    r = await c.put(url, json={"region_specific": True, "geography_ids": [BR]})
    assert r.status_code == 200 and [g["name"] for g in r.json()["geographies"]] == ["Brazil"]
    h = (await c.get(f"{B}/regional-heatmap", params={"geography_ids": f"{AM},{EU}"})).json()
    esocial = next(x for x in h["rows"] if x["capability"]["id"] == "esocial")
    assert esocial["region_specific"] is True
    assert [x["state"] for x in esocial["cells"]] == ["not_assessed", "not_applicable"]
    assert (
        await c.put(url, json={"region_specific": True, "geography_ids": []})
    ).status_code == 422
    r = await c.put(url, json={"region_specific": True, "geography_ids": [GLOBAL]})
    assert r.status_code == 422
    r = await c.put(url, json={"region_specific": True, "geography_ids": ["geo-ZZ"]})
    assert r.status_code == 422
    assert (await c.get(f"{B}/capability-region-scope/nope")).status_code == 404
    r = await c.put(url, json={"region_specific": False})
    assert r.status_code == 200 and r.json()["geographies"] == []
    logs = " ".join(rec.getMessage() for rec in caplog.records)
    assert f"region_scope.set capability=esocial region_specific=True geographies={BR}" in logs
    _reviewer(app)
    assert (await c.put(url, json={"region_specific": False})).status_code == 403
