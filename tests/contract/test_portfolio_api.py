"""Contract tests for the Portfolio Analysis API (ADP-SPEC-031).

T001–T007: GET /portfolio/technologies, /portfolio/designs, /portfolio/search, /portfolio/summary
T002/T010 (919-insights-dashboard): GET /portfolio/applications-heatmap
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole


def _make_session_mock(rows=None):
    """Return an AsyncMock that simulates an AsyncSession execute + fetchall/fetchone."""
    session = AsyncMock()
    result = MagicMock()
    result.fetchall = MagicMock(return_value=rows or [])
    result.fetchone = MagicMock(return_value=rows[0] if rows else None)
    session.execute = AsyncMock(return_value=result)
    return session


def _user(role: PersonaRole) -> AuthenticatedUser:
    return AuthenticatedUser(sub="t", username="t", email="t@localhost", role=role, groups=[])


# TCO_BUCKET_NAMES mirrors adp.application.models's own constant -- duplicated here (not
# imported) since this is a contract test asserting the *wire* shape, not the internal model.
_TCO_BUCKETS = (
    "acquisition", "implementation", "training", "operational",
    "maintenance", "upgrades", "risk_downtime", "end_of_life",
)


@pytest.fixture()
def client_factory():
    """Return a factory that creates a test client with an injectable session mock.

    919-insights-dashboard: an optional ``role`` overrides ``get_current_user`` (default
    behaviour under ``ADP_AUTH_ENABLED=false`` is already ENTERPRISE_ARCHITECT via
    ``UNAUTHENTICATED_USER`` — this override exists only for tests that need a *different*
    role, e.g. one lacking READ_APPLICATION_COST).
    """
    def _make(session_mock, role: PersonaRole | None = None):
        import adp.api.deps as deps_module
        from adp.api.app import create_app

        app = create_app()

        async def _fake_session():
            yield session_mock

        app.dependency_overrides[deps_module.get_kb_session] = _fake_session
        if role is not None:
            app.dependency_overrides[get_current_user] = lambda: _user(role)
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


# ── T002 (919-insights-dashboard): GET /portfolio/applications-heatmap ────────

def test_applications_heatmap_returns_every_application_once(client_factory):
    """Every application appears once; unscored fields are null, not defaulted."""
    app_rows = [
        {
            "id": "app-01", "name": "Policy Admin System", "health_score": 4,
            "business_criticality": 5, "time_classification": "Invest",
        },
        {
            "id": "app-02", "name": "Legacy Claims Batch", "health_score": None,
            "business_criticality": 2, "time_classification": "Eliminate",
        },
    ]
    session = AsyncMock()
    apps_result = MagicMock()
    apps_result.mappings.return_value.all = MagicMock(return_value=app_rows)
    costs_result = MagicMock()
    costs_result.mappings.return_value.all = MagicMock(return_value=[])
    session.execute = AsyncMock(side_effect=[apps_result, costs_result])

    # Default dev/test caller (ADP_AUTH_ENABLED=false) is ENTERPRISE_ARCHITECT, who holds
    # READ_APPLICATION_COST -- no role override needed here.
    c = client_factory(session)

    resp = c.get("/api/v1/portfolio/applications-heatmap")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    by_id = {i["id"]: i for i in body["items"]}
    assert by_id["app-01"]["health_score"] == 4
    assert by_id["app-01"]["business_criticality"] == 5
    assert by_id["app-01"]["time_classification"] == "Invest"
    # Unscored field is null, never a false default (FR-005)
    assert by_id["app-02"]["health_score"] is None


# ── T010 (919-insights-dashboard): cost dimension is permission-gated ─────────

def test_applications_heatmap_cost_visible_when_permitted(client_factory):
    """A caller holding READ_APPLICATION_COST sees cost data and cost_permitted=true."""
    app_rows = [
        {
            "id": "app-01", "name": "Policy Admin System", "health_score": 4,
            "business_criticality": 5, "time_classification": "Invest",
        },
    ]
    cost_rows = [
        {
            "app_id": "app-01", "currency": "USD", "horizon_years": 5,
            "updated_at": None,
            **{f"{b}_one_time": 0 for b in _TCO_BUCKETS},
            **{f"{b}_annual": 0 for b in _TCO_BUCKETS},
            "acquisition_one_time": 100000, "operational_annual": 50000,
        }
    ]
    session = AsyncMock()
    apps_result = MagicMock()
    apps_result.mappings.return_value.all = MagicMock(return_value=app_rows)
    costs_result = MagicMock()
    costs_result.mappings.return_value.all = MagicMock(return_value=cost_rows)
    session.execute = AsyncMock(side_effect=[apps_result, costs_result])

    c = client_factory(session, role=PersonaRole.ENTERPRISE_ARCHITECT)

    resp = c.get("/api/v1/portfolio/applications-heatmap")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cost_permitted"] is True
    # tco = 100000 (acquisition one_time) + 50000 * 5 (operational annual * horizon) = 350000
    assert float(body["items"][0]["cost"]) == 350000.0


def test_applications_heatmap_cost_hidden_when_not_permitted(client_factory):
    """A REVIEWER (no READ_APPLICATION_COST) gets cost=null and cost_permitted=false,
    and the cost table is never even queried (only one session.execute call)."""
    app_rows = [
        {
            "id": "app-01", "name": "Policy Admin System", "health_score": 4,
            "business_criticality": 5, "time_classification": "Invest",
        },
    ]
    session = AsyncMock()
    apps_result = MagicMock()
    apps_result.mappings.return_value.all = MagicMock(return_value=app_rows)
    # Only one result configured -- a second session.execute() call (i.e. the cost query
    # firing despite lacking permission) would raise StopIteration and fail the test.
    session.execute = AsyncMock(side_effect=[apps_result])

    c = client_factory(session, role=PersonaRole.REVIEWER)

    resp = c.get("/api/v1/portfolio/applications-heatmap")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cost_permitted"] is False
    assert body["items"][0]["cost"] is None
