"""Contract tests for the EA pattern registry API, /api/v1/patterns (935-pattern-registry).

Runs the real app against a SQLite file with the patterns store metadata (including its narrow
applications/controls/knowledge_items mirrors). The embedder is faked so no model is loaded.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole
from adp.patterns import router as prouter
from adp.patterns import store as pstore

API = "/api/v1/patterns"
FIX = Path(__file__).resolve().parents[1] / "unit" / "patterns" / "fixtures"
BACKBONE = (FIX / "valid" / "ea.integration.domain-event-backbone@1.0.0.yaml").read_text()
MESH = (FIX / "valid" / "ea.integration.point-to-point-mesh@1.0.0.yaml").read_text()
INVALID = (FIX / "invalid" / "V2.unknown_role-relationship.yaml").read_text()
KEY = "ea.integration.domain-event-backbone"
YAML_HEADERS = {"Content-Type": "application/yaml"}


def with_version(text: str, version: str) -> str:
    return re.sub(r"^version: .*$", f"version: {version}", text, count=1, flags=re.M)


@pytest.fixture()
async def app_and_client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/patterns_api.db")
    async with engine.begin() as conn:
        await conn.run_sync(pstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[prouter._get_session] = _override
    app.dependency_overrides[prouter._get_embed] = lambda: lambda title, text: [0.0] * 384
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield app, c
    await engine.dispose()


@pytest.fixture()
async def client(app_and_client):
    return app_and_client[1]


def _as_role(app, role: PersonaRole) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="u", username="u", email="u@localhost", role=role, groups=[]
    )


async def _import(client, text: str = BACKBONE) -> httpx.Response:
    return await client.post(f"{API}/import", content=text.encode(), headers=YAML_HEADERS)


# ── US1: import ───────────────────────────────────────────────────────────────────
async def test_import_created_unchanged_rejected(client) -> None:
    created = await _import(client)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "created"
    assert body["version"]["lifecycle"] == "draft"
    assert {i["code"] for i in body["issues"]} == {
        "R1.unresolved_principle",
        "R3.unresolved_relation",
    }

    again = await _import(client)
    assert again.status_code == 200
    assert again.json()["status"] == "unchanged"

    bad = await _import(client, INVALID)
    assert bad.status_code == 422
    assert bad.json()["status"] == "rejected"
    assert bad.json()["issues"][0]["code"].startswith("V2")


async def test_import_accepts_text_plain(client) -> None:
    resp = await client.post(
        f"{API}/import", content=BACKBONE.encode(), headers={"Content-Type": "text/plain"}
    )
    assert resp.status_code == 201


async def test_import_too_large_is_413(client) -> None:
    resp = await client.post(
        f"{API}/import", content=b"a: " + b"x" * (256 * 1024), headers=YAML_HEADERS
    )
    assert resp.status_code == 413


@pytest.mark.parametrize(
    "role",
    [PersonaRole.REVIEWER, PersonaRole.SOLUTION_ARCHITECT, PersonaRole.TECHNICAL_ARCHITECT],
)
async def test_import_forbidden_for_non_ea(app_and_client, role) -> None:
    app, client = app_and_client
    _as_role(app, role)
    assert (await _import(client)).status_code == 403
    assert (await client.get(API)).status_code == 200  # reads stay open


async def test_import_allowed_for_platform_admin(app_and_client) -> None:
    app, client = app_and_client
    _as_role(app, PersonaRole.PLATFORM_ADMIN)
    assert (await _import(client)).status_code == 201


# ── US1: reads ────────────────────────────────────────────────────────────────────
async def test_list_family_detail_yaml(client) -> None:
    await _import(client)
    await _import(client, with_version(BACKBONE, "1.1.0"))
    await _import(client, MESH)

    listing = (await client.get(API, params={"kind": "reference-architecture"})).json()
    assert listing["total"] == 2
    assert [v["version"] for v in listing["items"]] == ["1.1.0", "1.0.0"]
    assert (await client.get(API, params={"q": "mesh"})).json()["total"] == 1
    assert (await client.get(API, params={"tag": "event-driven"})).json()["total"] == 2
    assert (await client.get(API, params={"lifecycle": "current"})).json()["total"] == 0

    family = await client.get(f"{API}/{KEY}")
    assert family.status_code == 200
    assert [v["version"] for v in family.json()["versions"]] == ["1.1.0", "1.0.0"]
    assert family.json()["current_version"] is None

    detail = (await client.get(f"{API}/{KEY}/versions/1.0.0")).json()
    assert detail["definition"]["pattern"] == KEY
    assert detail["allowed_transitions"] == ["proposed"]
    assert detail["history"] == []
    mesh_rel = next(
        r
        for r in detail["relations"]
        if r["target_pattern_key"] == "ea.integration.point-to-point-mesh"
    )
    assert mesh_rel["target_resolved"] is True

    yml = await client.get(f"{API}/{KEY}/versions/1.0.0/yaml")
    assert yml.status_code == 200
    assert yml.headers["content-type"].startswith("application/yaml")
    assert f'filename="{KEY}@1.0.0.yaml"' in yml.headers["content-disposition"]
    assert yml.text.startswith("pattern: ea.integration.domain-event-backbone\n")

    relations = (await client.get(f"{API}/relations", params={"key": KEY})).json()
    assert len(relations) == 4  # two versions x two relations


async def test_not_found(client) -> None:
    assert (await client.get(f"{API}/ea.no.such")).status_code == 404
    await _import(client)
    assert (await client.get(f"{API}/{KEY}/versions/9.9.9")).status_code == 404
    assert (await client.get(f"{API}/{KEY}/versions/9.9.9/yaml")).status_code == 404
