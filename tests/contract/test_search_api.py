"""Contract test for the hybrid search API (ADP-b6o)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from adp.search import SearchHit


@pytest.fixture()
def client(monkeypatch):
    from adp.api.app import create_app
    from adp.api.routers import search as search_module

    captured: dict = {}

    class _FakeIndex:
        async def hybrid_search(self, q, session, *, entity_types=None, limit=10, **kw):
            captured["q"] = q
            captured["entity_types"] = entity_types
            captured["limit"] = limit
            return [
                SearchHit("business_capability", "cap-1", "Payments — checkout", 0.031),
                SearchHit("technical_capability", "tc-1", "Messaging", 0.016),
            ]

    monkeypatch.setattr(search_module, "default_index", lambda: _FakeIndex())

    async def _fake_session():
        yield object()

    app = create_app()
    app.dependency_overrides[search_module._get_session] = _fake_session
    return TestClient(app, raise_server_exceptions=False), captured


def test_search_returns_ranked_hits(client):
    c, captured = client
    resp = c.get("/api/v1/search", params={"q": "payments"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "payments"
    assert body["total"] == 2
    assert body["hits"][0]["entity_id"] == "cap-1"
    assert body["hits"][0]["entity_type"] == "business_capability"
    # defaults to the two capability entity types
    assert captured["entity_types"] == ["business_capability", "technical_capability"]


def test_search_respects_entity_types_and_limit(client):
    c, captured = client
    resp = c.get(
        "/api/v1/search",
        params={"q": "messaging", "entity_types": "technical_capability", "limit": 5},
    )
    assert resp.status_code == 200
    assert captured["entity_types"] == ["technical_capability"]
    assert captured["limit"] == 5


def test_search_requires_query(client):
    c, _ = client
    resp = c.get("/api/v1/search", params={"q": ""})
    assert resp.status_code == 422
