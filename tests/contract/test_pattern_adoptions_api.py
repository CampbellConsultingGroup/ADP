"""Contract tests: adoptions, conformance, discovery and dry-run evaluate (936; REST contract).

Real app against SQLite: the patterns store metadata (registry tables, adoption tables and the
registry mirrors) seeded with a small estate. The embedder and the cost loader are faked.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole
from adp.patterns import adoptions_router as arouter
from adp.patterns import router as prouter
from adp.patterns import snapshot_store as ss
from adp.patterns import store as pstore

API = "/api/v1/patterns"
FIX = Path(__file__).resolve().parents[1] / "unit" / "patterns" / "fixtures" / "valid"
BACKBONE_KEY = "ea.integration.domain-event-backbone"
MESH_KEY = "ea.integration.point-to-point-mesh"
TRANSITION_KEY = "ea.integration.mesh-to-backbone"
HUB_PIN = {"role_key": "backbone", "element_type": "application", "element_id": "hub"}


def _fixture(name: str) -> str:
    text = (FIX / name).read_text()
    return re.sub(r"^  principles: .*$", "  principles: []", text, flags=re.M)


async def _insert(s, table, rows) -> None:  # type: ignore[no-untyped-def]
    for row in rows:
        await s.execute(table.insert().values(**row))


async def _seed_estate(s) -> None:  # type: ignore[no-untyped-def]
    await _insert(
        s,
        ss._domains,
        [
            {"id": "claims", "name": "Claims", "classification": "strategic", "risk_flags": []},
            {"id": "billing", "name": "Billing", "classification": "commodity", "risk_flags": []},
        ],
    )
    await _insert(
        s,
        ss._capabilities,
        [
            {"id": "c-claims", "name": "Claims", "level": 1, "domain_id": "claims"},
            {"id": "c-bill", "name": "Billing", "level": 1, "domain_id": "billing"},
        ],
    )
    apps = [
        ("core", "Claims Core", "Invest", "custom"),
        ("portal", "Claims Portal", "Tolerate", "custom"),
        ("bill", "Billing", "Invest", "custom"),
        ("hub", "Enterprise Event Hub", "Invest", "cots"),
    ]
    await _insert(
        s,
        pstore._applications_mirror,
        [
            {
                "id": a,
                "name": n,
                "lifecycle_status": "active",
                "time_classification": t,
                "application_type": at,
                "tech_debt_flags": [],
            }
            for a, n, t, at in apps
        ],
    )
    await _insert(
        s,
        ss._cap_links,
        [
            {"app_id": "core", "capability_id": "c-claims"},
            {"app_id": "portal", "capability_id": "c-claims"},
            {"app_id": "bill", "capability_id": "c-bill"},
        ],
    )
    rows = []
    for app in ("core", "portal", "bill"):
        rows.append(
            {
                "id": f"{app}-hub",
                "source_app_id": app,
                "target_app_id": "hub",
                "integration_type": "event",
            }
        )
        rows.append(
            {
                "id": f"hub-{app}",
                "source_app_id": "hub",
                "target_app_id": app,
                "integration_type": "event",
            }
        )
    rows.append(
        {
            "id": "core-bill",
            "source_app_id": "core",
            "target_app_id": "bill",
            "integration_type": "API",
        }
    )
    await _insert(s, ss._integrations, rows)


@pytest.fixture()
async def app_and_client(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/adoptions_api.db")
    async with engine.begin() as conn:
        await conn.run_sync(pstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await _seed_estate(s)
        await s.commit()

    async def _costs(_session):  # type: ignore[no-untyped-def]
        return {"core": Decimal("5000000"), "portal": Decimal("10")}

    monkeypatch.setattr(ss, "_default_cost_loader", _costs)

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[prouter._get_session] = _override
    app.dependency_overrides[arouter._get_session] = _override
    app.dependency_overrides[prouter._get_embed] = lambda: lambda title, text: [0.0] * 384
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        for name in (
            "ea.integration.point-to-point-mesh@1.0.0.yaml",
            "ea.data.one-sor-per-capability@1.0.0.yaml",
            "ea.integration.domain-event-backbone@1.0.0.yaml",
            "ea.integration.mesh-to-backbone@1.0.0.yaml",
        ):
            r = await c.post(
                f"{API}/import",
                content=_fixture(name).encode(),
                headers={"Content-Type": "application/yaml"},
            )
            assert r.status_code == 201, r.text
            key = r.json()["version"]["pattern_key"]
            for to in ("proposed", "current"):
                t = await c.post(
                    f"{API}/{key}/versions/1.0.0/lifecycle",
                    json={"to": to, "reason": "test", "confirmation_id": "c"},
                )
                assert t.status_code == 200, t.text
        yield app, c
    await engine.dispose()


@pytest.fixture()
async def client(app_and_client):
    return app_and_client[1]


def _as_role(app, role: PersonaRole) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="u", username="u", email="u@localhost", role=role, groups=[]
    )


async def _adopt(client, **kw) -> httpx.Response:  # type: ignore[no-untyped-def]
    body = {
        "pattern_key": BACKBONE_KEY,
        "name": "Claims backbone",
        "scope_type": "business_domain",
        "scope_ref": "claims",
        "pins": [HUB_PIN],
        **kw,
    }
    return await client.post(f"{API}/adoptions", json=body)


# ── US2: adoption CRUD ───────────────────────────────────────────────────────────────
async def test_adoption_crud(client) -> None:
    created = await _adopt(client)
    assert created.status_code == 201, created.text
    a = created.json()
    assert (a["scope_name"], a["resolved_version"], a["pins"]) == ("Claims", "1.0.0", [HUB_PIN])
    aid = a["id"]

    listing = (await client.get(f"{API}/adoptions")).json()
    assert [x["id"] for x in listing["items"]] == [aid]
    assert listing["items"][0]["status"] is None
    assert (await client.get(f"{API}/adoptions/{aid}")).json()["name"] == "Claims backbone"

    renamed = await client.patch(f"{API}/adoptions/{aid}", json={"name": "Renamed"})
    assert renamed.status_code == 200 and renamed.json()["name"] == "Renamed"
    pinned = await client.patch(f"{API}/adoptions/{aid}", json={"pinned_version": "1.0.0"})
    assert pinned.json()["pinned_version"] == "1.0.0"

    assert (await client.put(f"{API}/adoptions/{aid}/pins", json={"pins": []})).json()["pins"] == []
    bad = await client.put(
        f"{API}/adoptions/{aid}/pins",
        json={"pins": [{"role_key": "backbone", "element_type": "agent", "element_id": "hub"}]},
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["reasons"]
    members = await client.put(f"{API}/adoptions/{aid}/members", json={"member_ids": ["core"]})
    assert members.status_code == 422  # not an application set

    assert (await client.delete(f"{API}/adoptions/{aid}")).status_code == 204
    assert (await client.get(f"{API}/adoptions/{aid}")).status_code == 404


async def test_adoption_errors(client) -> None:
    await _adopt(client)
    assert (await _adopt(client, name="Other")).status_code == 409
    assert (await _adopt(client, name="X", scope_ref="nope")).status_code == 404
    assert (await _adopt(client, pattern_key="ea.no.such")).status_code == 404
    assert (
        await _adopt(client, name="Y", scope_ref="billing", pinned_version="9.9.9")
    ).status_code == 404
    assert (
        await _adopt(client, name="Z", scope_type="portfolio", scope_ref="claims")
    ).status_code == 422


@pytest.mark.parametrize(
    "role",
    [PersonaRole.REVIEWER, PersonaRole.SOLUTION_ARCHITECT, PersonaRole.TECHNICAL_ARCHITECT],
)
async def test_adoption_writes_forbidden_for_non_ea(app_and_client, role) -> None:
    app, client = app_and_client
    aid = (await _adopt(client)).json()["id"]
    _as_role(app, role)
    assert (await _adopt(client, name="Mine", scope_ref="billing")).status_code == 403
    assert (await client.delete(f"{API}/adoptions/{aid}")).status_code == 403
    assert (await client.get(f"{API}/adoptions/{aid}/conformance")).status_code == 200


# ── US1: conformance ────────────────────────────────────────────────────────────────
async def test_conformance_non_conformant_and_with_status(client) -> None:
    aid = (await _adopt(client)).json()["id"]
    report = (await client.get(f"{API}/adoptions/{aid}/conformance")).json()
    assert report["status"] == "non_conformant"
    c1 = next(f for f in report["findings"] if f["code"] == "C1")
    assert [e["name"] for e in c1["element_refs"]] == ["Claims Core → Billing"]
    assert {b["role_key"]: b["count"] for b in report["bindings"]}["backbone"] == 1
    assert report["plateau"] is None
    listing = (await client.get(f"{API}/adoptions", params={"with_status": "true"})).json()
    assert listing["items"][0]["status"] == "non_conformant"


async def test_adoptions_route_is_not_a_pattern_key(client) -> None:
    resp = await client.get(f"{API}/adoptions")
    assert resp.status_code == 200 and "items" in resp.json()


async def test_no_current_version_is_not_applicable(client) -> None:
    aid = (await _adopt(client)).json()["id"]
    await client.post(
        f"{API}/{BACKBONE_KEY}/versions/1.0.0/lifecycle",
        json={"to": "deprecated", "reason": "r", "confirmation_id": "c"},
    )
    report = (await client.get(f"{API}/adoptions/{aid}/conformance")).json()
    assert report["status"] == "not_applicable"
    assert report["findings"][0]["code"] == "B1.no_current_version"


async def test_gated_attribute_depends_on_caller(app_and_client) -> None:
    """A tco constraint is decided for an EA but field_unavailable for a Reviewer (FR-006)."""
    app, client = app_and_client
    yaml = re.sub(
        r"^version: .*$",
        "version: 1.1.0",
        _fixture("ea.integration.domain-event-backbone@1.0.0.yaml"),
        count=1,
        flags=re.M,
    )
    yaml = yaml.replace(
        "  - id: C2\n",
        "  - id: C3\n    rule: Cheap apps.\n    for_each: domain_app\n"
        '    expr: "it.tco < 1000000.0"\n  - id: C2\n',
        1,
    )
    body = {
        "yaml": yaml,
        "scope": {"scope_type": "business_domain", "scope_ref": "claims"},
        "pins": [HUB_PIN],
    }
    ea = (await client.post(f"{API}/evaluate", json=body)).json()
    c3 = [f for f in ea["findings"] if f["code"] == "C3"]
    assert [f["kind"] for f in c3] == ["violation"]  # core costs 5M
    assert [e["id"] for e in c3[0]["element_refs"]] == ["core"]


async def test_reviewer_gets_field_unavailable_on_adoption(app_and_client) -> None:
    app, client = app_and_client
    yaml = re.sub(
        r"^version: .*$",
        "version: 1.1.0",
        _fixture("ea.integration.domain-event-backbone@1.0.0.yaml"),
        count=1,
        flags=re.M,
    )
    yaml = yaml.replace(
        "  - id: C2\n",
        "  - id: C3\n    rule: Cheap apps.\n    for_each: domain_app\n"
        '    expr: "it.tco < 1000000.0"\n  - id: C2\n',
        1,
    )
    await client.post(
        f"{API}/import", content=yaml.encode(), headers={"Content-Type": "application/yaml"}
    )
    for to in ("proposed", "current"):
        await client.post(
            f"{API}/{BACKBONE_KEY}/versions/1.1.0/lifecycle",
            json={"to": to, "reason": "r", "confirmation_id": "c"},
        )
    aid = (await _adopt(client)).json()["id"]
    _as_role(app, PersonaRole.REVIEWER)
    report = (await client.get(f"{API}/adoptions/{aid}/conformance")).json()
    kinds = {f["kind"] for f in report["findings"] if f["code"] == "C3"}
    assert kinds == {"field_unavailable"}


# ── US3 / US4 / US6 ──────────────────────────────────────────────────────────────────
async def test_transition_adoption_reports_plateau(client) -> None:
    resp = await _adopt(client, pattern_key=TRANSITION_KEY, name="Claims migration")
    report = (await client.get(f"{API}/adoptions/{resp.json()['id']}/conformance")).json()
    assert report["plateau"] == {"reached": "PL1", "next": "PL2", "blocking": ["C2"]}


async def test_discovery(client) -> None:
    resp = await client.get(f"{API}/{MESH_KEY}/versions/1.0.0/discover")
    assert resp.status_code == 200
    names = {e["name"] for m in resp.json()["matches"] for e in m["element_refs"]}
    assert "Claims Core → Billing" in names
    assert (await client.get(f"{API}/{BACKBONE_KEY}/versions/1.0.0/discover")).status_code == 422
    assert (await client.get(f"{API}/{MESH_KEY}/versions/9.9.9/discover")).status_code == 404


async def test_evaluate_dry_run(client) -> None:
    scope = {"scope_type": "business_domain", "scope_ref": "claims"}
    stored = await client.post(
        f"{API}/evaluate",
        json={"pattern_key": BACKBONE_KEY, "version": "1.0.0", "scope": scope, "pins": [HUB_PIN]},
    )
    assert stored.status_code == 200, stored.text
    assert stored.json()["status"] == "non_conformant" and stored.json()["adoption_id"] is None
    bad = await client.post(f"{API}/evaluate", json={"yaml": "pattern: [", "scope": scope})
    assert bad.status_code == 422 and bad.json()["detail"]["issues"]
    assert (await client.get(f"{API}/adoptions")).json()["total"] == 0


async def test_candidates(client) -> None:
    aid = (await _adopt(client)).json()["id"]
    resp = await client.get(f"{API}/adoptions/{aid}/candidates/backbone")
    assert [c["name"] for c in resp.json()] == [
        "Billing",
        "Claims Core",
        "Claims Portal",
        "Enterprise Event Hub",
    ]
    assert (await client.get(f"{API}/adoptions/{aid}/candidates/nope")).status_code == 404


# ── US5: views ───────────────────────────────────────────────────────────────────────
async def test_conformance_and_transition_views(client) -> None:
    aid = (await _adopt(client)).json()["id"]
    resp = await client.get(f"{API}/adoptions/{aid}/views/conformance", params={"max_per_role": 2})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["view"] == "conformance"
    assert body["flowchart"].startswith(f"%% adp-pattern {BACKBONE_KEY}@1.0.0 view=conformance")
    assert "Claims Core → Billing · FAIL" in body["flowchart"]
    assert body["truncated"]
    assert (await client.get(f"{API}/adoptions/{aid}/views/transition")).status_code == 422
    assert (await client.get(f"{API}/adoptions/{aid}/views/structure")).status_code == 422

    tid = (await _adopt(client, pattern_key=TRANSITION_KEY, name="Migration")).json()["id"]
    t = (await client.get(f"{API}/adoptions/{tid}/views/transition")).json()
    assert "blocked: C2" in t["flowchart"]
