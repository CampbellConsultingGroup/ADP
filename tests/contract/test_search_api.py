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


def test_search_with_empty_entity_types_string_returns_200(client):
    """ADP-jyu's exact ZAP repro: GET .../search?q=q&entity_types=&limit=10 --
    an explicitly empty (not absent) entity_types param must still default to
    the capability types and return 200, not 500."""
    c, captured = client
    resp = c.get("/api/v1/search", params={"q": "q", "entity_types": "", "limit": 10})
    assert resp.status_code == 200
    assert captured["entity_types"] == ["business_capability", "technical_capability"]


def test_search_rejects_out_of_range_limit(client):
    c, _ = client
    resp = c.get("/api/v1/search", params={"q": "payments", "limit": 0})
    assert resp.status_code == 422
    resp2 = c.get("/api/v1/search", params={"q": "payments", "limit": 51})
    assert resp2.status_code == 422


def test_unexpected_index_failure_returns_generic_500_without_leaking_details(monkeypatch):
    """ADP-jyu: ZAP flagged Application Error Disclosure -- confirm an
    unexpected failure surfaces as the app's generic sanitized 500 body
    (adp.api.app._unhandled_exception_handler), never a raw exception
    message or traceback."""
    from adp.api.app import create_app
    from adp.api.routers import search as search_module

    class _RaisingIndex:
        async def hybrid_search(self, q, session, *, entity_types=None, limit=10, **kw):
            raise RuntimeError("super secret internal file path /etc/definitely-secret")

    monkeypatch.setattr(search_module, "default_index", lambda: _RaisingIndex())

    async def _fake_session():
        yield object()

    app = create_app()
    app.dependency_overrides[search_module._get_session] = _fake_session
    c = TestClient(app, raise_server_exceptions=False)

    resp = c.get("/api/v1/search", params={"q": "payments"})
    assert resp.status_code == 500
    assert resp.json() == {"detail": "An unexpected error occurred."}
    assert "secret" not in resp.text
