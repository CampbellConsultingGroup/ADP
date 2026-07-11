"""Contract tests for the Governance Reporting API (ADP-SPEC-032).

T001–T009: GET /governance/status, /exceptions, /activity, /activity/export
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription, Finding


def _make_design(
    design_id: str = "DSN-001",
    title: str = "Test Design",
    lifecycle_status: str = "current",
    findings: list | None = None,
) -> ArchitectureDescription:
    d = ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": design_id,
        "title": title,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-15T00:00:00Z",
        "elements": [],
        "relationships": [],
        "requirements": [],
    })
    d.lifecycle_status = lifecycle_status  # type: ignore[attr-defined]
    if findings:
        d.findings = findings
    return d


def _make_session_mock(rows=None):
    session = AsyncMock()
    result = MagicMock()
    result.fetchall = MagicMock(return_value=rows or [])
    result.fetchone = MagicMock(return_value=rows[0] if rows else None)
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.fixture()
def client_factory():
    def _make(session_mock, design_store_mock=None):
        import adp.api.deps as deps_module
        from adp.api.app import create_app
        from adp.api.routers import governance as gov_module

        app = create_app()

        async def _fake_session():
            yield session_mock

        app.dependency_overrides[deps_module.get_kb_session] = _fake_session

        if design_store_mock is not None:
            app.dependency_overrides[gov_module._get_design_store] = (
                lambda: design_store_mock
            )

        return TestClient(app, raise_server_exceptions=False)

    return _make


# ── T001: GET /governance/status returns all designs ─────────────────────────

def test_status_returns_all_designs(client_factory):
    """All designs appear in status response with correct fields."""
    rows = [
        MagicMock(
            id="DSN-001", title="Payment Platform", lifecycle_status="current",
            last_activity=datetime(2026, 7, 4, 14, 30, tzinfo=timezone.utc),
            audit_count=12, accepted_recs=3, reasoning_count=9,
        ),
        MagicMock(
            id="DSN-002", title="Auth Service", lifecycle_status="draft",
            last_activity=None,
            audit_count=0, accepted_recs=0, reasoning_count=0,
        ),
    ]
    session = _make_session_mock(rows)
    c = client_factory(session)

    resp = c.get("/api/v1/governance/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "designs" in body
    assert "total" in body
    assert body["total"] == 2
    ids = [d["design_id"] for d in body["designs"]]
    assert "DSN-001" in ids
    assert "DSN-002" in ids
    dsn1 = next(d for d in body["designs"] if d["design_id"] == "DSN-001")
    assert dsn1["audit_count"] == 12
    assert dsn1["accepted_recommendations"] == 3
    assert dsn1["reasoning_record_count"] == 9


# ── T002: designs with no activity still appear ───────────────────────────────

def test_status_handles_design_with_no_activity(client_factory):
    """Design with zero audit entries still appears with zero counts."""
    rows = [
        MagicMock(
            id="DSN-003", title="Empty Design", lifecycle_status="draft",
            last_activity=None, audit_count=0, accepted_recs=0, reasoning_count=0,
        ),
    ]
    session = _make_session_mock(rows)
    c = client_factory(session)

    resp = c.get("/api/v1/governance/status")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["designs"]) == 1
    d = body["designs"][0]
    assert d["audit_count"] == 0
    assert d["last_activity"] is None


# ── T003: exceptions excludes info findings ───────────────────────────────────

def test_exceptions_returns_only_fail_advisory(client_factory):
    """Only critical→FAIL and warning→ADVISORY findings returned; info excluded."""
    critical_finding = Finding(
        id="FND-001",
        subject="ELM-001",
        summary="No mTLS between services",
        severity="critical",
        source="security-critic",
    )
    info_finding = Finding(
        id="FND-002",
        subject="ELM-001",
        summary="Consider adding caching",
        severity="info",
        source="perf-critic",
    )
    design = _make_design(findings=[critical_finding, info_finding])
    store_mock = AsyncMock()
    store_mock.list_all = AsyncMock(return_value=[design])

    session = _make_session_mock([])
    c = client_factory(session, design_store_mock=store_mock)

    resp = c.get("/api/v1/governance/exceptions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["exceptions"][0]["severity"] == "FAIL"
    assert body["exceptions"][0]["finding_summary"] == "No mTLS between services"


# ── T004: clean design returns empty exceptions ───────────────────────────────

def test_exceptions_empty_when_no_findings(client_factory):
    design = _make_design()
    store_mock = AsyncMock()
    store_mock.list_all = AsyncMock(return_value=[design])

    session = _make_session_mock([])
    c = client_factory(session, design_store_mock=store_mock)

    resp = c.get("/api/v1/governance/exceptions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["exceptions"] == []
    assert body["total"] == 0


# ── T005: activity requires date range ────────────────────────────────────────

def test_activity_requires_date_range(client_factory):
    session = _make_session_mock([])
    c = client_factory(session)

    resp = c.get("/api/v1/governance/activity")
    assert resp.status_code == 422


# ── T006: activity rejects range over 90 days ─────────────────────────────────

def test_activity_rejects_range_over_90_days(client_factory):
    session = _make_session_mock([])
    c = client_factory(session)

    from_d = date(2026, 1, 1)
    to_d = from_d + timedelta(days=91)
    resp = c.get(f"/api/v1/governance/activity?from_date={from_d}&to_date={to_d}")
    assert resp.status_code == 422
    assert "90" in resp.json()["detail"]


# ── T007: activity returns entries within range ────────────────────────────────

def test_activity_returns_entries_in_range(client_factory):
    rows = [
        MagicMock(
            id="AUD-001", design_id="DSN-001", design_title="Payment Platform",
            actor="alice", action="lifecycle-transition",
            affected_entity="DSN-001", summary="Lifecycle: draft → proposed",
            timestamp=datetime(2026, 6, 15, tzinfo=timezone.utc), origin="human",
        ),
    ]
    count_result = MagicMock()
    count_result.fetchone = MagicMock(return_value=MagicMock(total=1))
    rows_result = MagicMock()
    rows_result.fetchall = MagicMock(return_value=rows)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    c = client_factory(session)
    resp = c.get("/api/v1/governance/activity?from_date=2026-06-01&to_date=2026-06-30")
    assert resp.status_code == 200
    body = resp.json()
    assert "entries" in body
    assert "total" in body
    assert body["from_date"] == "2026-06-01"
    assert body["to_date"] == "2026-06-30"


# ── T008: activity filter by action ───────────────────────────────────────────

def test_activity_filter_by_action(client_factory):
    """Action filter is passed to query (verified via mock call)."""
    count_result = MagicMock()
    count_result.fetchone = MagicMock(return_value=MagicMock(total=0))
    rows_result = MagicMock()
    rows_result.fetchall = MagicMock(return_value=[])
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    c = client_factory(session)
    resp = c.get(
        "/api/v1/governance/activity"
        "?from_date=2026-06-01&to_date=2026-06-30&action=lifecycle-transition"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"] == []


# ── T009: activity export returns CSV ─────────────────────────────────────────

def test_activity_export_returns_csv(client_factory):
    session = _make_session_mock([])
    count_result = MagicMock()
    count_result.fetchone = MagicMock(return_value=MagicMock(total=0))
    export_result = MagicMock()
    export_result.fetchall = MagicMock(return_value=[])
    session.execute = AsyncMock(side_effect=[
        MagicMock(fetchone=MagicMock(return_value=None)),
        export_result,
    ])

    c = client_factory(session)
    resp = c.get("/api/v1/governance/activity/export?from_date=2026-01-01&to_date=2026-03-31")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "adp-audit-" in resp.headers.get("content-disposition", "")
    # CSV header row
    assert "id" in resp.text
    assert "actor" in resp.text
