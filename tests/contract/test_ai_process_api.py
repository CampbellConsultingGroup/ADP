"""Contract tests for the AI Process Reporting API (ADP-3ei).

Covers: 404 for an unknown design, the summary endpoint's response shape
for a design with no captured activity (exercises every query path except
the recommendation-options-by-run branch, which needs run_ids populated),
and the timeline endpoint's pagination shape.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


def _zero_agg(**overrides):
    """A MagicMock standing in for a `.mappings().one()` aggregate row."""
    m = MagicMock()
    base = {"total": 0, "confirmed": 0, "edited_confirmed": 0, "rejected": 0, "pending": 0,
            "accepted": 0, "findings": 0, "blocking": 0, "models": []}
    base.update(overrides)
    m.__getitem__.side_effect = base.__getitem__
    return m


def _mappings_one(row) -> MagicMock:
    result = MagicMock()
    result.mappings.return_value.one.return_value = row
    return result


def _mappings_all(rows: list) -> MagicMock:
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    return result


def _scalar(value) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    return result


@pytest.fixture()
def client_factory():
    def _make(session_mock):
        import adp.api.deps as deps_module
        from adp.api.app import create_app

        app = create_app()

        async def _fake_session():
            yield session_mock

        app.dependency_overrides[deps_module.get_kb_session] = _fake_session
        return TestClient(app, raise_server_exceptions=False)

    return _make


def test_summary_returns_404_for_unknown_design(client_factory):
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar(None))
    c = client_factory(session)

    resp = c.get("/api/v1/designs/DSN-999/ai-process")
    assert resp.status_code == 404


def test_summary_returns_zero_activity_shape(client_factory):
    """A design that exists but has no captured AI activity — every section is
    present with zero counts, and no query blows up on empty results."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _scalar(1),                       # design existence check
        _mappings_one(_zero_agg()),        # submission_agg
        _mappings_one(_zero_agg()),        # proposal_agg
        _mappings_all([]),                 # submission_rows
        _mappings_one(_zero_agg()),        # run_agg
        _mappings_one(_zero_agg()),        # option_agg
        _mappings_all([]),                 # run_rows (empty -> no option_rows query)
        _mappings_one(_zero_agg()),        # verdict_agg
        _mappings_all([]),                 # verdict_rows
        _mappings_one(_zero_agg()),        # reasoning_agg
    ])
    c = client_factory(session)

    resp = c.get("/api/v1/designs/DSN-001/ai-process")
    assert resp.status_code == 200
    body = resp.json()
    assert body["design_id"] == "DSN-001"
    assert body["intake"]["submission_count"] == 0
    assert body["intake"]["submissions"] == []
    assert body["recommendation"]["run_count"] == 0
    assert body["recommendation"]["runs"] == []
    assert body["validation"]["verdict_count"] == 0
    assert body["validation"]["latest_status"] is None
    assert body["reasoning"]["record_count"] == 0
    assert body["reasoning"]["models_used"] == []


def test_timeline_returns_404_for_unknown_design(client_factory):
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar(None))
    c = client_factory(session)

    resp = c.get("/api/v1/designs/DSN-999/ai-process/timeline")
    assert resp.status_code == 404


def test_timeline_returns_paginated_shape(client_factory):
    row = MagicMock()
    row.__getitem__.side_effect = {
        "event_type": "submission", "entity_id": "SUB-1", "occurred_at": None,
        "actor": "alice", "status": "completed", "summary": "Intake submission (bulk_text)",
    }.__getitem__

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _scalar(1),            # design existence check
        _scalar(1),            # timeline count
        _mappings_all([row]),  # timeline rows
    ])
    c = client_factory(session)

    resp = c.get("/api/v1/designs/DSN-001/ai-process/timeline?page=1&page_size=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["entries"][0]["event_type"] == "submission"
    assert body["entries"][0]["occurred_at"] == ""
