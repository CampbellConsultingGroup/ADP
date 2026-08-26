"""Contract tests for the Portfolio Analysis API (ADP-SPEC-031).

T007: GET /portfolio/summary
T002/T010 (919-insights-dashboard): GET /portfolio/applications-heatmap
ADP-8xo (Application Portfolio pivot): GET /portfolio/application-capability-groups

ADP-704: T001-T006 (/portfolio/technologies, /portfolio/designs, /portfolio/search) removed
alongside the endpoints themselves -- see adp.api.routers.portfolio's own module docstring.
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


# ── ADP-8xo: GET /portfolio/application-capability-groups (Application Portfolio) ──

def test_application_capability_groups_returns_every_link(client_factory):
    """Every app-capability link across the whole registry comes back in one call --
    the bulk read the Application Portfolio pivot's capability dimension relies on.
    Row access is attribute-style (row.app_id, mirroring list_app_capability_links's
    own established pattern), so mock rows use SimpleNamespace, not plain dicts."""
    from types import SimpleNamespace

    link_rows = [
        SimpleNamespace(
            app_id="app-01", capability_id="cap-01",
            capability_name="Claims Processing", fit_score=4,
        ),
        SimpleNamespace(
            app_id="app-01", capability_id="cap-02",
            capability_name="Fraud Detection", fit_score=2,
        ),
        SimpleNamespace(
            app_id="app-02", capability_id="cap-01",
            capability_name="Claims Processing", fit_score=3,
        ),
    ]
    session = AsyncMock()
    links_result = MagicMock()
    links_result.mappings.return_value.all = MagicMock(return_value=link_rows)
    session.execute = AsyncMock(return_value=links_result)

    c = client_factory(session)

    resp = c.get("/api/v1/portfolio/application-capability-groups")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3
    # The multi-membership contract: app-01 appears in 2 links (2 capabilities).
    app01_links = [i for i in body["items"] if i["app_id"] == "app-01"]
    assert len(app01_links) == 2
    assert {i["capability_id"] for i in app01_links} == {"cap-01", "cap-02"}


def test_application_capability_groups_open_read_no_auth_required(client_factory):
    """No READ_APPLICATION_* gate covers fit_score -- open read, no role override
    needed (unlike applications-heatmap's cost dimension)."""
    from types import SimpleNamespace

    session = AsyncMock()
    links_result = MagicMock()
    links_result.mappings.return_value.all = MagicMock(
        return_value=[
            SimpleNamespace(
                app_id="app-01", capability_id="cap-01",
                capability_name="Claims Processing", fit_score=5,
            ),
        ]
    )
    session.execute = AsyncMock(return_value=links_result)

    c = client_factory(session)  # no role override

    resp = c.get("/api/v1/portfolio/application-capability-groups")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["fit_score"] == 5
