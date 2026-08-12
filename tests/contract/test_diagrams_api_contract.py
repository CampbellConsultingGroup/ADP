"""Contract tests for the Diagrams API (ADP-SPEC-046).

Full-stack against the real router on in-memory SQLite. Auth is disabled in
tests, so the default caller is ENTERPRISE_ARCHITECT, which holds
WRITE_DIAGRAM via its wildcard grant -- no per-test role override needed
for the happy paths; the denial path is covered in tests/authz/test_permissions.py
(WRITE_DIAGRAM denied to Reviewer) and tests/authz/test_enforcement.py's
route-completeness gate.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.diagrams import router as drouter
from adp.diagrams import store as dstore


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/diagrams.db")
    async with engine.begin() as conn:
        await conn.run_sync(dstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[drouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


# ── User Story 1: create / read / update ─────────────────────────────────────

@pytest.mark.parametrize(
    "diagram_type", ["flowchart", "sequence", "erd", "uml", "architecture", "c4"]
)
async def test_create_persists_each_supported_type(client, diagram_type) -> None:
    resp = await client.post(
        "/api/v1/diagrams", json={"title": f"Test {diagram_type}", "diagram_type": diagram_type}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["diagram_type"] == diagram_type
    assert body["dsl_source"] == ""


async def test_get_retrieves_with_content_intact(client) -> None:
    create_resp = await client.post(
        "/api/v1/diagrams",
        json={
            "title": "Claims Intake",
            "diagram_type": "flowchart",
            "dsl_source": "flowchart LR\nA-->B\n",
        },
    )
    diagram_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/diagrams/{diagram_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["dsl_source"] == "flowchart LR\nA-->B\n"


async def test_get_404_for_unknown_id(client) -> None:
    resp = await client.get("/api/v1/diagrams/nonexistent")
    assert resp.status_code == 404


async def test_put_updates_dsl_source_partial(client) -> None:
    create_resp = await client.post(
        "/api/v1/diagrams", json={"title": "Original", "diagram_type": "uml"}
    )
    diagram_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/diagrams/{diagram_id}",
        json={"dsl_source": "classDiagram\nclass Foo\n"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Original"  # untouched
    assert body["dsl_source"] == "classDiagram\nclass Foo\n"


async def test_put_404_for_unknown_id(client) -> None:
    resp = await client.put("/api/v1/diagrams/nonexistent", json={"title": "X"})
    assert resp.status_code == 404


async def test_create_422_blank_title(client) -> None:
    resp = await client.post(
        "/api/v1/diagrams", json={"title": "  ", "diagram_type": "flowchart"}
    )
    assert resp.status_code == 422


async def test_create_422_oversized_dsl_source(client) -> None:
    resp = await client.post(
        "/api/v1/diagrams",
        json={"title": "T", "diagram_type": "flowchart", "dsl_source": "x" * 50_001},
    )
    assert resp.status_code == 422


async def test_create_422_unsupported_type(client) -> None:
    # ADP-SPEC-053: "c4" used to be the example of an unsupported type here -- it isn't anymore
    # (see test_create_persists_each_supported_type above), so this now exercises a genuinely
    # unsupported value instead. The test's purpose (reject unknown types) is unchanged.
    resp = await client.post(
        "/api/v1/diagrams", json={"title": "T", "diagram_type": "gantt"}
    )
    assert resp.status_code == 422


# ── User Story 2: export (render) ────────────────────────────────────────────

async def test_export_converts_svg_to_png(client) -> None:
    create_resp = await client.post(
        "/api/v1/diagrams", json={"title": "T", "diagram_type": "flowchart"}
    )
    diagram_id = create_resp.json()["id"]

    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
    svg += '<rect width="100" height="100" fill="blue"/></svg>'
    resp = await client.post(f"/api/v1/diagrams/{diagram_id}/export", json={"svg": svg})

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


async def test_export_404_for_unknown_diagram(client) -> None:
    resp = await client.post(
        "/api/v1/diagrams/nonexistent/export",
        json={"svg": '<svg xmlns="http://www.w3.org/2000/svg"></svg>'},
    )
    assert resp.status_code == 404


async def test_export_422_for_invalid_svg(client) -> None:
    create_resp = await client.post(
        "/api/v1/diagrams", json={"title": "T", "diagram_type": "flowchart"}
    )
    diagram_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/diagrams/{diagram_id}/export", json={"svg": "not valid svg at all {{{"}
    )
    assert resp.status_code == 422


# ── User Story 3: browse / manage ────────────────────────────────────────────

async def test_list_returns_summaries_across_all_types(client) -> None:
    for diagram_type in ("flowchart", "sequence", "erd", "uml", "architecture", "c4"):
        await client.post(
            "/api/v1/diagrams", json={"title": f"T-{diagram_type}", "diagram_type": diagram_type}
        )

    resp = await client.get("/api/v1/diagrams")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 6
    types = {item["diagram_type"] for item in body["items"]}
    assert types == {"flowchart", "sequence", "erd", "uml", "architecture", "c4"}
    assert all("dsl_source" not in item for item in body["items"])


async def test_delete_removes_diagram(client) -> None:
    create_resp = await client.post(
        "/api/v1/diagrams", json={"title": "Doomed", "diagram_type": "flowchart"}
    )
    diagram_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/diagrams/{diagram_id}")
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/v1/diagrams/{diagram_id}")
    assert get_resp.status_code == 404

    list_resp = await client.get("/api/v1/diagrams")
    assert diagram_id not in [item["id"] for item in list_resp.json()["items"]]


async def test_delete_404_for_unknown_id(client) -> None:
    resp = await client.delete("/api/v1/diagrams/nonexistent")
    assert resp.status_code == 404
