"""Contract tests for the Portfolio Analysis API (ADP-SPEC-031).

T001–T007: GET /portfolio/technologies, /portfolio/designs, /portfolio/search, /portfolio/summary
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_session_mock(rows=None):
    """Return an AsyncMock that simulates an AsyncSession execute + fetchall/fetchone."""
    session = AsyncMock()
    result = MagicMock()
    result.fetchall = MagicMock(return_value=rows or [])
    result.fetchone = MagicMock(return_value=rows[0] if rows else None)
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.fixture()
def client_factory():
    """Return a factory that creates a test client with an injectable session mock."""
    def _make(session_mock):
        import adp.api.deps as deps_module
        from adp.api.app import create_app

        app = create_app()

        async def _fake_session():
            yield session_mock

        app.dependency_overrides[deps_module.get_kb_session] = _fake_session
        return TestClient(app, raise_server_exceptions=False)

    return _make


# ── T001: GET /portfolio/technologies aggregates counts ────────────────────────

def test_technologies_returns_aggregated_counts(client_factory):
    """Returns list of technologies sorted by design_count descending."""
    rows = [
        MagicMock(technology="Kafka", design_count=3),
        MagicMock(technology="RabbitMQ", design_count=2),
    ]
    session = _make_session_mock(rows)
    c = client_factory(session)

    resp = c.get("/api/v1/portfolio/technologies")
    assert resp.status_code == 200
    body = resp.json()
    assert "technologies" in body
    assert "total_unique" in body
    names = [t["technology"] for t in body["technologies"]]
    assert "Kafka" in names
    assert "RabbitMQ" in names
    # first item should be highest count
    kafka = next(t for t in body["technologies"] if t["technology"] == "Kafka")
    assert kafka["design_count"] == 3


# ── T002: GET /portfolio/designs filters by technology ────────────────────────

def test_portfolio_designs_filter_by_technology(client_factory):
    """Returns designs matching the technology filter; primary_technology field present."""
    rows = [
        MagicMock(
            id="DSN-001", title="API Platform", lifecycle_status="current",
            review_due=None, primary_technology="Kafka", element_count=5,
        ),
    ]
    session = _make_session_mock(rows)
    c = client_factory(session)

    resp = c.get("/api/v1/portfolio/designs?technology=Kafka")
    assert resp.status_code == 200
    body = resp.json()
    assert "designs" in body
    assert len(body["designs"]) == 1
    assert body["designs"][0]["primary_technology"] == "Kafka"


# ── T003: GET /portfolio/designs filters by status ────────────────────────────

def test_portfolio_designs_filter_by_status(client_factory):
    """Returns only designs with the requested lifecycle_status."""
    rows = [
        MagicMock(
            id="DSN-002", title="Current Design", lifecycle_status="current",
            review_due=None, primary_technology=None, element_count=3,
        ),
    ]
    session = _make_session_mock(rows)
    c = client_factory(session)

    resp = c.get("/api/v1/portfolio/designs?status=current")
    assert resp.status_code == 200
    body = resp.json()
    assert all(d["lifecycle_status"] == "current" for d in body["designs"])


# ── T004: GET /portfolio/designs combined filter ──────────────────────────────

def test_portfolio_designs_combined_filter(client_factory):
    """Both technology and status params applied together."""
    rows = [
        MagicMock(
            id="DSN-003", title="Kong Gateway", lifecycle_status="current",
            review_due=None, primary_technology="Kong", element_count=2,
        ),
    ]
    session = _make_session_mock(rows)
    c = client_factory(session)

    resp = c.get("/api/v1/portfolio/designs?technology=Kong&status=current")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["designs"]) == 1
    assert body["designs"][0]["lifecycle_status"] == "current"
    assert body["designs"][0]["primary_technology"] == "Kong"


# ── T005: GET /portfolio/search finds by technology keyword ───────────────────

def test_portfolio_search_finds_by_technology(client_factory):
    """Returns designs with matched_elements list populated."""
    rows = [
        MagicMock(
            design_id="DSN-001", title="API Platform", lifecycle_status="current",
            review_due=None, element_id="ELM-001", element_name="API Gateway",
            technology="Kong API Gateway",
        ),
    ]
    session = _make_session_mock(rows)
    c = client_factory(session)

    resp = c.get("/api/v1/portfolio/search?q=Kong")
    assert resp.status_code == 200
    body = resp.json()
    assert "designs" in body
    assert len(body["designs"]) >= 1
    first = body["designs"][0]
    assert "matched_elements" in first
    assert len(first["matched_elements"]) >= 1


# ── T006: GET /portfolio/search rejects single-char query ─────────────────────

def test_portfolio_search_requires_min_2_chars(client_factory):
    """Query shorter than 2 chars returns 422."""
    session = _make_session_mock([])
    c = client_factory(session)

    resp = c.get("/api/v1/portfolio/search?q=K")
    assert resp.status_code == 422


# ── T007: GET /portfolio/summary returns correct counts ───────────────────────

def test_portfolio_summary_returns_correct_counts(client_factory):
    """Summary aggregates by lifecycle_status and counts overdue reviews."""
    rows = [
        MagicMock(lifecycle_status="draft", cnt=3),
        MagicMock(lifecycle_status="current", cnt=2),
    ]
    # Second call (overdue count) returns a scalar
    session = AsyncMock()
    result1 = MagicMock()
    result1.fetchall = MagicMock(return_value=rows)
    result2 = MagicMock()
    result2.fetchone = MagicMock(return_value=MagicMock(overdue_count=1))
    session.execute = AsyncMock(side_effect=[result1, result2])

    c = client_factory(session)

    resp = c.get("/api/v1/portfolio/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "total_designs" in body
    assert "by_status" in body
    assert body["by_status"]["draft"] == 3
    assert body["by_status"]["current"] == 2
    assert "overdue_review_count" in body
