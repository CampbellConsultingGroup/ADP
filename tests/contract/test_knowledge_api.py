"""Contract tests for the Knowledge Base CRUD API (ADP-SPEC-020).

Tests are isolated — no real DB. The knowledge router's DB session dependency
is overridden with an in-memory SQLite database per test.

The client fixture is async and uses httpx.ASGITransport (matching every
other contract test's convention, e.g. tests/contract/test_apm_cost_api.py)
rather than the sync TestClient + asyncio.get_event_loop().run_until_complete(...)
this file used previously — that legacy pattern relied on an implicit
current event loop existing in the fixture's thread, which some CI runners'
pytest-asyncio/anyio versions no longer create automatically (ADP-s3j: 17
"no current event loop" setup errors in CI, not reproducible locally).
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def _create_tables(engine):
    async with engine.begin() as conn:
        # Minimal table without pgvector — embedding stored as JSON text in SQLite
        await conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                full_text TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                source_ref TEXT NOT NULL,
                schema_version TEXT NOT NULL DEFAULT '1.0.0',
                active INTEGER NOT NULL DEFAULT 1,
                embedding TEXT NOT NULL DEFAULT '[]',
                indexed_at TEXT NOT NULL
            )
        """))


@pytest.fixture()
async def client(tmp_path):
    """Provide an async client with an in-memory SQLite DB injected as the session dependency."""
    from adp.api.app import create_app
    from adp.api.deps import get_kb_session
    from adp.api.routers import knowledge as kb_module

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/kb.db", echo=False)
    await _create_tables(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _fake_session():
        async with factory() as session:
            yield session

    # Patch embed so tests don't need sentence-transformers
    with patch.object(kb_module, "_embed", return_value=[0.0] * 384):
        app = create_app()
        app.dependency_overrides[get_kb_session] = _fake_session
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    await engine.dispose()


async def _seed_item(client, item_id: str = "TEST-001", kind: str = "principle") -> None:
    resp = await client.post("/api/v1/knowledge", json={
        "id": item_id,
        "kind": kind,
        "title": f"Test Principle {item_id}",
        "full_text": "This is the full text content of the knowledge item.",
        "source_ref": "https://example.com/test",
    })
    assert resp.status_code == 201, resp.text


# ── US1: Browse ───────────────────────────────────────────────────────────────

async def test_list_knowledge_items_empty_returns_empty_list(client):
    resp = await client.get("/api/v1/knowledge")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_list_knowledge_items_returns_seeded_item(client):
    await _seed_item(client, "PRIN-001", "principle")
    resp = await client.get("/api/v1/knowledge")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == "PRIN-001"
    assert items[0]["kind"] == "principle"
    assert "title" in items[0]
    assert "source_ref" in items[0]
    assert "full_text" not in items[0]  # summary endpoint omits full_text


async def test_list_knowledge_items_multiple(client):
    await _seed_item(client, "PRIN-001", "principle")
    await _seed_item(client, "PAT-001", "pattern")
    resp = await client.get("/api/v1/knowledge")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


async def test_get_knowledge_item_returns_full_text(client):
    await _seed_item(client, "PRIN-001", "principle")
    resp = await client.get("/api/v1/knowledge/PRIN-001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "PRIN-001"
    assert "full_text" in body
    assert len(body["full_text"]) > 0


async def test_get_knowledge_item_not_found_returns_404(client):
    resp = await client.get("/api/v1/knowledge/NONEXISTENT")
    assert resp.status_code == 404


# ── US2: Create ───────────────────────────────────────────────────────────────

async def test_create_knowledge_item_returns_201(client):
    resp = await client.post("/api/v1/knowledge", json={
        "id": "NEW-001",
        "kind": "pattern",
        "title": "Circuit Breaker",
        "full_text": "Wraps calls to external services and monitors for failures.",
        "source_ref": "https://martinfowler.com/bliki/CircuitBreaker.html",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "NEW-001"
    assert body["kind"] == "pattern"
    assert body["title"] == "Circuit Breaker"


async def test_create_knowledge_item_without_id_generates_uuid(client):
    resp = await client.post("/api/v1/knowledge", json={
        "kind": "standard",
        "title": "OAuth2",
        "full_text": "Industry standard authorisation framework.",
        "source_ref": "https://oauth.net/2/",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"]  # UUID generated server-side
    assert len(body["id"]) > 0


async def test_create_knowledge_item_blank_title_returns_422(client):
    resp = await client.post("/api/v1/knowledge", json={
        "kind": "principle",
        "title": "",
        "full_text": "Some content.",
        "source_ref": "https://example.com",
    })
    assert resp.status_code == 422


async def test_create_knowledge_item_blank_full_text_returns_422(client):
    resp = await client.post("/api/v1/knowledge", json={
        "kind": "principle",
        "title": "Valid Title",
        "full_text": "",
        "source_ref": "https://example.com",
    })
    assert resp.status_code == 422


async def test_create_knowledge_item_invalid_kind_returns_422(client):
    resp = await client.post("/api/v1/knowledge", json={
        "kind": "not_a_real_kind",
        "title": "Title",
        "full_text": "Content.",
        "source_ref": "https://example.com",
    })
    assert resp.status_code == 422


# ── US3: Update ───────────────────────────────────────────────────────────────

async def test_update_knowledge_item_returns_200(client):
    await _seed_item(client, "PRIN-001")
    resp = await client.put("/api/v1/knowledge/PRIN-001", json={"title": "Updated Title"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"


async def test_update_knowledge_item_not_found_returns_404(client):
    resp = await client.put("/api/v1/knowledge/NONEXISTENT", json={"title": "Updated"})
    assert resp.status_code == 404


async def test_update_knowledge_item_blank_title_returns_422(client):
    await _seed_item(client, "PRIN-001")
    resp = await client.put("/api/v1/knowledge/PRIN-001", json={"title": ""})
    assert resp.status_code == 422


# ── US4: Delete ───────────────────────────────────────────────────────────────

async def test_delete_knowledge_item_returns_204(client):
    await _seed_item(client, "PRIN-001")
    resp = await client.delete("/api/v1/knowledge/PRIN-001")
    assert resp.status_code == 204


async def test_delete_knowledge_item_not_in_list_after_delete(client):
    await _seed_item(client, "PRIN-001")
    await client.delete("/api/v1/knowledge/PRIN-001")
    resp = await client.get("/api/v1/knowledge")
    ids = [item["id"] for item in resp.json()["items"]]
    assert "PRIN-001" not in ids


async def test_delete_knowledge_item_not_found_returns_404(client):
    resp = await client.delete("/api/v1/knowledge/NONEXISTENT")
    assert resp.status_code == 404


async def test_delete_already_deleted_returns_404(client):
    await _seed_item(client, "PRIN-001")
    await client.delete("/api/v1/knowledge/PRIN-001")
    resp = await client.delete("/api/v1/knowledge/PRIN-001")
    assert resp.status_code == 404
