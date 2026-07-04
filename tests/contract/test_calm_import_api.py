"""Contract tests for the CALM Pattern Import API (ADP-SPEC-022 T015-T017)."""

from __future__ import annotations

import asyncio
import json

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.api.routers import calm as calm_module
from adp.api.routers import knowledge as kb_module

_VALID_CALM = {
    "$id": "https://example.com/patterns/api-gateway",
    "nodes": [
        {"unique-id": "N-001", "node-type": "actor", "name": "Client", "description": "API consumer"},
        {"unique-id": "N-002", "node-type": "service", "name": "API Gateway", "description": "Entry point"},
    ],
    "relationships": [
        {
            "unique-id": "REL-001",
            "relationship-type": "connects",
            "connects": {"source-node": "N-001", "destination-node": "N-002", "protocol": "HTTPS"},
        }
    ],
}


async def _create_tables(engine):
    async with engine.begin() as conn:
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
def client(monkeypatch):
    """TestClient with in-memory SQLite DB and patched embed to avoid model load."""
    from unittest.mock import patch

    from adp.api.app import create_app

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    asyncio.get_event_loop().run_until_complete(_create_tables(engine))

    async def _fake_kb_session():
        async with factory() as session:
            yield session

    async def _fake_kb_session_for_knowledge():
        async with factory() as session:
            yield session

    from adp.api.deps import get_kb_session
    app = create_app()
    # Both the calm import endpoint and the knowledge router use get_kb_session from deps
    app.dependency_overrides[get_kb_session] = _fake_kb_session

    with patch("adp.knowledge.embedder.EmbeddingProvider") as mock_ep:
        mock_ep.return_value.embed.return_value = [0.0] * 384
        yield TestClient(app, raise_server_exceptions=True)


# ── T015: 201 with items_created ─────────────────────────────────────────────

def test_import_calm_pattern_returns_201(client):
    resp = client.post(
        "/api/v1/knowledge/import/calm",
        content=json.dumps(_VALID_CALM),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["items_created"] == 1
    assert body["items_updated"] == 0
    assert body["items_failed"] == 0
    assert len(body["items"]) == 1
    assert body["items"][0]["kind"] == "reference_architecture"


def test_import_calm_pattern_item_has_correct_title(client):
    resp = client.post(
        "/api/v1/knowledge/import/calm",
        content=json.dumps(_VALID_CALM),
        headers={"Content-Type": "application/json"},
    )
    body = resp.json()
    assert "api-gateway" in body["items"][0]["title"].lower() or "api gateway" in body["items"][0]["title"].lower()


# ── T016: 422 for invalid JSON ────────────────────────────────────────────────

def test_import_calm_invalid_json_returns_422(client):
    resp = client.post(
        "/api/v1/knowledge/import/calm",
        content="not json at all",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


def test_import_calm_json_array_returns_422(client):
    resp = client.post(
        "/api/v1/knowledge/import/calm",
        content=json.dumps([1, 2, 3]),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


# ── T017: upsert — second import returns items_updated ───────────────────────

def test_import_calm_upsert_returns_items_updated(client):
    payload = json.dumps(_VALID_CALM)
    headers = {"Content-Type": "application/json"}

    # First import — creates
    resp1 = client.post("/api/v1/knowledge/import/calm", content=payload, headers=headers)
    assert resp1.status_code == 201
    assert resp1.json()["items_created"] == 1

    # Second import — updates
    resp2 = client.post("/api/v1/knowledge/import/calm", content=payload, headers=headers)
    assert resp2.status_code == 201
    assert resp2.json()["items_updated"] == 1
    assert resp2.json()["items_created"] == 0
