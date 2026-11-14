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


# ── US2: lifecycle ────────────────────────────────────────────────────────────────
ONE_SOR = (FIX / "valid" / "ea.data.one-sor-per-capability@1.0.0.yaml").read_text()


async def _make_resolvable(client) -> None:
    """Import the backbone's related patterns; principles are stripped so R1 cannot block."""
    await _import(client, MESH)
    await _import(client, ONE_SOR)


def _no_principles(text: str) -> str:
    return re.sub(r"^  principles: .*$", "  principles: []", text, count=1, flags=re.M)


async def _transition(client, version: str, to: str, **extra) -> httpx.Response:
    body = {"to": to, "reason": "ARB review 2026-11-14", "confirmation_id": f"c-{to}", **extra}
    return await client.post(f"{API}/{KEY}/versions/{version}/lifecycle", json=body)


async def test_lifecycle_happy_path_and_swap(client) -> None:
    await _make_resolvable(client)
    await _import(client, _no_principles(BACKBONE))
    assert (await _transition(client, "1.0.0", "proposed")).status_code == 200
    promoted = await _transition(client, "1.0.0", "current")
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["lifecycle"] == "current"
    assert promoted.json()["allowed_transitions"] == ["deprecated"]

    await _import(client, with_version(_no_principles(BACKBONE), "1.1.0"))
    await _transition(client, "1.1.0", "proposed")
    assert (await _transition(client, "1.1.0", "current")).status_code == 200
    old = (await client.get(f"{API}/{KEY}/versions/1.0.0")).json()
    assert old["lifecycle"] == "deprecated"
    assert [(e["from_state"], e["to_state"]) for e in old["history"]] == [
        ("draft", "proposed"),
        ("proposed", "current"),
        ("current", "deprecated"),
    ]


async def test_illegal_transition_is_409(client) -> None:
    await _import(client)
    resp = await _transition(client, "1.0.0", "current")
    assert resp.status_code == 409
    assert "not allowed" in resp.json()["detail"]


async def test_blocked_promotion_is_422_with_issues(client) -> None:
    await _import(client)
    await _transition(client, "1.0.0", "proposed")
    resp = await _transition(client, "1.0.0", "current")
    assert resp.status_code == 422
    codes = {i["code"] for i in resp.json()["detail"]["issues"]}
    assert codes == {"R1.unresolved_principle", "R3.unresolved_relation"}


@pytest.mark.parametrize(
    "body",
    [
        {"to": "proposed", "confirmation_id": "c"},
        {"to": "proposed", "reason": "", "confirmation_id": "c"},
        {"to": "proposed", "reason": "ok"},
        {"to": "proposed", "reason": "ok", "confirmation_id": "   "},
        {"to": "proposed", "reason": "x" * 501, "confirmation_id": "c"},
    ],
)
async def test_reason_and_confirmation_are_required(client, body) -> None:
    await _import(client)
    resp = await client.post(f"{API}/{KEY}/versions/1.0.0/lifecycle", json=body)
    assert resp.status_code == 422
    detail = (await client.get(f"{API}/{KEY}/versions/1.0.0")).json()
    assert detail["lifecycle"] == "draft"


@pytest.mark.parametrize(
    "role",
    [PersonaRole.REVIEWER, PersonaRole.SOLUTION_ARCHITECT, PersonaRole.TECHNICAL_ARCHITECT],
)
async def test_lifecycle_forbidden_for_non_ea(app_and_client, role) -> None:
    app, client = app_and_client
    await _import(client)
    _as_role(app, role)
    assert (await _transition(client, "1.0.0", "proposed")).status_code == 403


async def test_lifecycle_unknown_version_is_404(client) -> None:
    await _import(client)
    assert (await _transition(client, "9.9.9", "proposed")).status_code == 404


# ── US4: views ────────────────────────────────────────────────────────────────────
async def test_structure_view(client) -> None:
    await _import(client)
    resp = await client.get(f"{API}/{KEY}/versions/1.0.0/views/structure")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["view"] == "structure"
    assert body["flowchart"].startswith(f"%% adp-pattern {KEY}@1.0.0 view=structure digest=")
    assert body["digest"] == (await client.get(f"{API}/{KEY}/versions/1.0.0")).json()["digest"]
    assert body["truncated"] == []
    tb = await client.get(f"{API}/{KEY}/versions/1.0.0/views/structure", params={"direction": "TB"})
    assert tb.json()["flowchart"].splitlines()[1] == "flowchart TB"


async def test_catalog_view_depth(client) -> None:
    await _import(client)
    await _import(client, MESH)
    one = await client.get(f"{API}/{KEY}/versions/1.0.0/views/catalog", params={"depth": 1})
    assert one.status_code == 200
    text = one.json()["flowchart"]
    assert "Point-to-Point Mesh · 1.0.0" in text
    assert "ea.data.one-sor-per-capability · not in registry" in text
    bad = await client.get(f"{API}/{KEY}/versions/1.0.0/views/catalog", params={"depth": 4})
    assert bad.status_code == 422


async def test_traceability_view_marks_unresolved(client) -> None:
    await _import(client)
    resp = await client.get(f"{API}/{KEY}/versions/1.0.0/views/traceability")
    assert resp.status_code == 200
    assert "P-API-FIRST · not found" in resp.json()["flowchart"]


async def test_unknown_view_is_422_and_missing_version_404(client) -> None:
    await _import(client)
    assert (await client.get(f"{API}/{KEY}/versions/1.0.0/views/conformance")).status_code == 422
    assert (await client.get(f"{API}/{KEY}/versions/9.9.9/views/structure")).status_code == 404


async def test_dry_run_render_stores_nothing(client) -> None:
    resp = await client.post(f"{API}/render", json={"yaml": BACKBONE, "view": "structure"})
    assert resp.status_code == 200, resp.text
    assert "r_backbone" in resp.json()["flowchart"]
    assert (await client.get(API)).json()["total"] == 0
    bad = await client.post(f"{API}/render", json={"yaml": INVALID, "view": "structure"})
    assert bad.status_code == 422
    assert bad.json()["detail"]["issues"][0]["code"].startswith("V2")


async def test_dry_run_render_forbidden_for_reviewer(app_and_client) -> None:
    app, client = app_and_client
    _as_role(app, PersonaRole.REVIEWER)
    resp = await client.post(f"{API}/render", json={"yaml": BACKBONE, "view": "structure"})
    assert resp.status_code == 403
